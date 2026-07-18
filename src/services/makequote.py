import colorsys
import io
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import AppleEmojiSource

logger = logging.getLogger()

# Telegram dark-theme peer name colors (red, green, yellow, blue, purple, pink, cyan, orange).
TELEGRAM_NAME_COLORS: list[tuple[int, int, int]] = [
    (251, 97, 105),
    (133, 222, 133),
    (243, 188, 92),
    (101, 189, 243),
    (180, 139, 242),
    (255, 86, 148),
    (98, 212, 227),
    (250, 163, 87),
]
# Telegram maps user_id % 7 to a palette index in this order.
_PEER_COLOR_ORDER = [0, 7, 4, 1, 6, 3, 5]


@dataclass
class QuoteConfig:
    """Configuration for quote image rendering."""

    width: int = 640
    height: int = 640
    # Render at a higher resolution and downscale for crisp text and emoji.
    supersample: int = 2

    max_font_size: int = 30
    min_font_size: int = 16
    stroke_width: int = 2

    blur_radius: int = 8
    # Darkening applied over the blurred background for text contrast (0..1).
    overlay_opacity: float = 0.4

    # Fraction of the canvas the text block is allowed to occupy.
    text_width_ratio: float = 0.86
    text_height_ratio: float = 0.80

    max_name_length: int = 31
    max_quote_length: int = 300


class QuoteMaker:
    def __init__(self, bot: Bot, config: QuoteConfig | None = None):
        """
        Initialize QuoteMaker for aiogram.

        Args:
            bot: aiogram Bot instance
            config: Optional QuoteConfig instance for customization
        """
        self.bot = bot
        self.config = config or QuoteConfig()

        self.base_path = Path(__file__).parent.parent
        self.font_path = self._resolve_font_path()

        # Cache loaded fonts by pixel size to avoid re-reading from disk.
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}

    def _resolve_font_path(self) -> Path:
        """Locate the bold font, falling back to a system font."""
        font_path = self.base_path.parent / "assets" / "fonts" / "SFNSRounded.ttf"
        # print(f"Looking for font at {font_path}")
        if font_path.exists():
            return font_path

        fallbacks = [
            "/System/Library/Fonts/SFNSText.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
            "C:\\Windows\\Fonts\\segoeui.ttf",  # Windows
        ]
        for font in fallbacks:
            if Path(font).exists():
                return Path(font)

        logger.warning("No bundled or system font found; using PIL default font.")
        return font_path

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load (and cache) the font at a given pixel size."""
        if size not in self._font_cache:
            try:
                self._font_cache[size] = ImageFont.truetype(str(self.font_path), size=size)
            except OSError as e:
                logger.warning("Failed to load font at size %s: %s", size, e)
                self._font_cache[size] = ImageFont.load_default(size)  # type: ignore[arg-type]
        return self._font_cache[size]

    def _get_user_color(self, user_id: int) -> tuple[int, int, int]:
        """Generate a consistent, pleasant color for a user based on their ID."""
        rng = random.Random(user_id)
        hue = rng.random()
        saturation = 0.5 + rng.random() * 0.3  # 0.5-0.8
        value = 0.7 + rng.random() * 0.2  # 0.7-0.9
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        return tuple(int(x * 255) for x in rgb)  # type: ignore[return-value]

    async def _get_profile_photo(self, user_id: int) -> Image.Image | None:
        """Download a user's profile photo as an RGB image."""
        try:
            photos = await self.bot.get_user_profile_photos(user_id=user_id, limit=1)
            if photos.total_count == 0 or not photos.photos:
                return None

            largest_photo = photos.photos[0][-1]  # highest resolution size
            photo_bytes = io.BytesIO()
            await self.bot.download(file=largest_photo.file_id, destination=photo_bytes)
            photo_bytes.seek(0)
            return Image.open(photo_bytes).convert("RGB")
        except Exception as e:
            logger.exception("Error loading profile photo: %s", e)
            return None

    def _create_default_avatar(self, user_id: int, author_name: str, size: int) -> Image.Image:
        """Create a default avatar with the user's initials."""
        initials = "".join(word[0].upper() for word in author_name.split()[:2]) or "?"
        avatar = Image.new("RGB", (size, size), color=self._get_user_color(user_id))
        draw = ImageDraw.Draw(avatar)

        font = self._load_font(int(size * 0.28))
        draw.text((size / 2, size / 2), initials, font=font, fill="white", anchor="mm")
        return avatar

    @staticmethod
    def _crop_to_square(image: Image.Image) -> Image.Image:
        """Center-crop an image to a square (cover), preserving aspect ratio."""
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        return image.crop((left, top, left + side, top + side))

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
        """Word-wrap text to a pixel width, hard-splitting words that overflow."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split(" "):
                # Break a single word that is too wide to ever fit on one line.
                while font.getlength(word) > max_width and len(word) > 1:
                    cut = len(word)
                    while cut > 1 and font.getlength(word[:cut]) > max_width:
                        cut -= 1
                    if current:
                        lines.append(current)
                        current = ""
                    lines.append(word[:cut])
                    word = word[cut:]

                candidate = f"{current} {word}".strip()
                if font.getlength(candidate) <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _layout_text(
        self, quote_text: str, author_name: str, canvas_w: int, canvas_h: int
    ) -> tuple[str, ImageFont.FreeTypeFont]:
        """Pick the largest font size at which the text block fits the canvas."""
        scale = self.config.supersample
        max_width = canvas_w * self.config.text_width_ratio
        max_height = canvas_h * self.config.text_height_ratio
        stroke = self.config.stroke_width * scale
        measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        best_text = ""
        for base_size in range(self.config.max_font_size, self.config.min_font_size - 1, -1):
            font = self._load_font(base_size * scale)

            lines = self._wrap_text(quote_text, font, max_width)
            if lines:
                lines[0] = f"«{lines[0]}"
                lines[-1] = f"{lines[-1]}»"
            lines += ["", f"— {author_name}"]
            block = "\n".join(lines)
            best_text = block

            bbox = measure.multiline_textbbox(
                (0, 0), block, font=font, stroke_width=stroke, align="center"
            )
            if (bbox[3] - bbox[1]) <= max_height and (bbox[2] - bbox[0]) <= max_width:
                return block, font

        # Nothing fit even at the smallest size; use it anyway.
        return best_text, self._load_font(self.config.min_font_size * scale)

    def _generate_quote_image(
        self, background: Image.Image, quote_text: str, author_name: str
    ) -> io.BytesIO:
        """Render the quote onto a blurred, darkened background."""
        scale = self.config.supersample
        canvas_w = self.config.width * scale
        canvas_h = self.config.height * scale

        # Square-crop and resize the background to fill the canvas, then blur.
        background = self._crop_to_square(background).resize(
            (canvas_w, canvas_h), Image.Resampling.LANCZOS
        )
        canvas = background.filter(ImageFilter.GaussianBlur(self.config.blur_radius * scale))

        # Darken for text contrast.
        overlay = Image.new("RGB", canvas.size, (0, 0, 0))
        canvas = Image.blend(canvas, overlay, self.config.overlay_opacity)

        block, font = self._layout_text(quote_text, author_name, canvas_w, canvas_h)

        draw = ImageDraw.Draw(canvas)
        bbox = draw.multiline_textbbox((0, 0), block, font=font, align="center")
        text_x = int((canvas_w - (bbox[2] - bbox[0])) / 2 - bbox[0])
        text_y = int((canvas_h - (bbox[3] - bbox[1])) / 2 - bbox[1])

        with Pilmoji(canvas, source=AppleEmojiSource) as pilmoji:
            pilmoji.text(
                (text_x, text_y),
                block,
                font=font,
                fill="white",
                align="center",
            )

        # Downscale to the target size for anti-aliased, crisp output.
        canvas = canvas.resize((self.config.width, self.config.height), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        canvas.save(output, format="PNG")
        output.seek(0)
        return output

    @staticmethod
    def _extract_quote_text(message: Message) -> str | None:
        """
        Resolve the text to quote.

        If the user replied to a specific selected fragment (Telegram's
        "reply with quote"), use only that fragment; otherwise fall back to
        the full replied message text/caption.
        """
        if message.quote and message.quote.text:
            return message.quote.text

        reply = message.reply_to_message
        if reply is None:
            return None
        return reply.text or reply.caption

    async def create_quote(self, message: Message) -> io.BytesIO | None:
        """
        Create a quote image from the replied (or selected) message.

        Args:
            message: aiogram Message that is a reply to another message

        Returns:
            BytesIO with the generated PNG, or None if it could not be built.
        """
        try:
            reply_message = message.reply_to_message
            if reply_message is None:
                return None

            quote_text = self._extract_quote_text(message)
            if not quote_text or not quote_text.strip():
                return None

            quote_text = self._shorten(quote_text, self.config.max_quote_length)

            from_user = reply_message.from_user
            if from_user is None:
                return None

            author_name = self._shorten(
                from_user.full_name or "Unknown User", self.config.max_name_length
            )

            canvas_side = self.config.width * self.config.supersample
            background = await self._get_profile_photo(from_user.id)
            if background is None:
                background = self._create_default_avatar(from_user.id, author_name, canvas_side)

            return self._generate_quote_image(background, quote_text, author_name)
        except Exception as e:
            logger.exception("Error creating quote: %s", e)
            return None

    @staticmethod
    def _shorten(text: str, width: int) -> str:
        """Collapse whitespace and truncate with an ellipsis if too long."""
        text = " ".join(text.split())
        if len(text) <= width:
            return text
        return text[: max(0, width - 1)].rstrip() + "…"

    async def send_quote(self, message: Message):
        """Create and send the quote image, or report failure to the user."""
        quote_buffer = await self.create_quote(message)
        if quote_buffer is None:
            await message.answer(
                "❌ Failed to create quote. Use /qq to create quote with image or sticker."
            )
            return

        photo = BufferedInputFile(quote_buffer.read(), filename="quote.png")
        await message.reply_photo(photo=photo)


@dataclass
class TelegramQuoteConfig:
    """Configuration for the Telegram-UI style quote sticker (base design units)."""

    # Stickers are capped at 512px on the longest side by Telegram.
    sticker_size: int = 512
    # Render at a multiple of the base design and downscale for crisp output.
    supersample: int = 3

    padding: int = 8
    # Extra transparent space below the bubble so Telegram's floating
    # timestamp badge doesn't overlap the content.
    bottom_margin: int = 28
    avatar_size: int = 60
    avatar_gap: int = 12

    bubble_radius: int = 22
    bubble_pad_x: int = 18
    bubble_pad_top: int = 10
    bubble_pad_bottom: int = 14
    tail_width: int = 12
    tail_height: int = 20

    # Quoted photos inside a bubble and quoted stickers (bare, no bubble).
    media_max_size: int = 300
    media_radius: int = 10
    sticker_quote_size: int = 240
    caption_gap: int = 8
    max_caption_lines: int = 8

    name_font_size: int = 25
    text_font_size: int = 30
    name_gap: int = 6
    line_spacing: int = 6

    bubble_color: tuple[int, int, int, int] = (44, 38, 55, 255)
    bubble_outline: tuple[int, int, int, int] = (255, 255, 255, 22)
    text_color: tuple[int, int, int, int] = (252, 252, 252, 255)

    max_name_length: int = 25
    max_quote_length: int = 400
    max_lines: int = 14


class TelegramQuoteMaker(QuoteMaker):
    """Renders quotes as Telegram-UI style stickers: avatar + chat bubble on transparency."""

    def __init__(self, bot: Bot, tg_config: TelegramQuoteConfig | None = None):
        super().__init__(bot)
        self.tg = tg_config or TelegramQuoteConfig()
        self._weighted_font_cache: dict[tuple[int, str], ImageFont.FreeTypeFont] = {}

    def _load_weighted_font(self, size: int, weight: str) -> ImageFont.FreeTypeFont:
        """Load the font at a named variation weight (falls back to the plain face)."""
        key = (size, weight)
        if key not in self._weighted_font_cache:
            try:
                font = ImageFont.truetype(str(self.font_path), size=size)
                try:
                    font.set_variation_by_name(weight)
                except (OSError, ValueError):
                    pass  # static font: use as-is
            except OSError:
                font = self._load_font(size)
            self._weighted_font_cache[key] = font
        return self._weighted_font_cache[key]

    @staticmethod
    def _get_name_color(user_id: int) -> tuple[int, int, int]:
        return TELEGRAM_NAME_COLORS[_PEER_COLOR_ORDER[user_id % 7]]

    def _make_circle_avatar(
        self, source: Image.Image | None, user_id: int, name: str, size: int
    ) -> Image.Image:
        """Build a circular avatar: profile photo, or a Telegram-style initials gradient."""
        if source is None:
            top = self._get_name_color(user_id)
            bottom = tuple(int(c * 0.6) for c in top)
            source = Image.new("RGB", (1, 2))
            source.putpixel((0, 0), top)
            source.putpixel((0, 1), bottom)  # type: ignore[arg-type]
            source = source.resize((size, size), Image.Resampling.BILINEAR)

            initials = "".join(word[0].upper() for word in name.split()[:2]) or "?"
            font = self._load_weighted_font(int(size * 0.38), "Semibold")
            ImageDraw.Draw(source).text(
                (size / 2, size / 2), initials, font=font, fill="white", anchor="mm"
            )
        else:
            source = self._crop_to_square(source).resize((size, size), Image.Resampling.LANCZOS)

        # Antialiased circular mask drawn at 4x.
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
        mask = mask.resize((size, size), Image.Resampling.LANCZOS)

        avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        avatar.paste(source, (0, 0), mask)
        return avatar

    @staticmethod
    def _tail_polygon(
        x: float, bottom: float, width: float, height: float
    ) -> list[tuple[float, float]]:
        """Telegram-style bubble tail: curves from the left edge out to a point at the bottom."""

        def quad(p0, p1, p2, steps=12):
            return [
                (
                    (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1],
                )
                for t in (i / steps for i in range(steps + 1))
            ]

        tip = (x - width, bottom)
        points = quad((x, bottom - height), (x - width * 0.1, bottom - height * 0.25), tip)
        points += quad(tip, (x + width * 0.2, bottom), (x + width * 1.2, bottom - height * 0.15))
        return points

    def _draw_bubble_with_avatar(
        self,
        canvas: Image.Image,
        avatar_source: Image.Image | None,
        user_id: int,
        author_name: str,
        bx0: int,
        by0: int,
        bubble_w: int,
        bubble_h: int,
    ) -> None:
        """Draw the bubble body, tail, outline and the bottom-aligned avatar."""
        cfg = self.tg
        s = cfg.supersample
        draw = ImageDraw.Draw(canvas)
        by1 = by0 + bubble_h
        radius = cfg.bubble_radius * s
        box = (bx0, by0, bx0 + bubble_w, by1)
        # Square bottom-left corner: the tail takes its place.
        corners = (True, True, True, False)
        draw.rounded_rectangle(box, radius=radius, fill=cfg.bubble_color, corners=corners)
        draw.polygon(
            self._tail_polygon(bx0, by1, cfg.tail_width * s, cfg.tail_height * s),
            fill=cfg.bubble_color,
        )
        draw.rounded_rectangle(
            box, radius=radius, outline=cfg.bubble_outline, width=s, corners=corners
        )

        avatar_px = cfg.avatar_size * s
        avatar = self._make_circle_avatar(avatar_source, user_id, author_name, avatar_px)
        canvas.alpha_composite(avatar, (cfg.padding * s, by1 - avatar_px))

    def _finalize(self, canvas: Image.Image) -> io.BytesIO:
        """Fit the longest side to the sticker limit and encode as WebP."""
        cfg = self.tg
        scale = cfg.sticker_size / max(canvas.size)
        final_size = (round(canvas.width * scale), round(canvas.height * scale))
        canvas = canvas.resize(final_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        canvas.save(output, format="WEBP", lossless=True)
        output.seek(0)
        return output

    @staticmethod
    def _round_corners(image: Image.Image, top_radius: int, bottom_radius: int) -> Image.Image:
        """Clip an RGBA image to rounded corners (different radii for top and bottom)."""
        w, h = image.size
        top_mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(top_mask).rounded_rectangle((0, 0, w, h), radius=top_radius, fill=255)
        mask = top_mask
        if bottom_radius != top_radius:
            bottom_mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(bottom_mask).rounded_rectangle(
                (0, 0, w, h), radius=bottom_radius, fill=255
            )
            mask = top_mask.copy()
            mask.paste(bottom_mask.crop((0, h // 2, w, h)), (0, h // 2))

        image = image.copy()
        image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
        return image

    async def _download_image(self, file_id: str) -> Image.Image | None:
        """Download a Telegram file as an RGBA image."""
        try:
            buffer = io.BytesIO()
            await self.bot.download(file=file_id, destination=buffer)
            buffer.seek(0)
            return Image.open(buffer).convert("RGBA")
        except Exception as e:
            logger.exception("Error downloading media for quote: %s", e)
            return None

    def _render_sticker(
        self,
        avatar_source: Image.Image | None,
        user_id: int,
        author_name: str,
        quote_text: str,
    ) -> io.BytesIO:
        """Compose the Telegram-style bubble and return it as a WebP sticker."""
        cfg = self.tg
        s = cfg.supersample

        name_font = self._load_weighted_font(cfg.name_font_size * s, "Bold")
        text_font = self._load_weighted_font(cfg.text_font_size * s, "Regular")

        max_text_width = (
            cfg.sticker_size
            - 2 * cfg.padding
            - cfg.avatar_size
            - cfg.avatar_gap
            - 2 * cfg.bubble_pad_x
        ) * s

        lines: list[str] = []
        for paragraph in quote_text.split("\n"):
            lines.extend(self._wrap_text(paragraph, text_font, max_text_width) or [""])
        if len(lines) > cfg.max_lines:
            lines = lines[: cfg.max_lines]
            lines[-1] = lines[-1].rstrip() + "…"
        body = "\n".join(lines)

        measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        spacing = cfg.line_spacing * s
        name_w = name_font.getlength(author_name)
        name_ascent, name_descent = name_font.getmetrics()
        name_h = name_ascent + name_descent
        raw_bbox = measure.multiline_textbbox((0, 0), body, font=text_font, spacing=spacing)
        body_bbox = tuple(int(v) for v in raw_bbox)
        body_w, body_h = body_bbox[2] - body_bbox[0], body_bbox[3] - body_bbox[1]

        bubble_w = int(max(name_w, body_w)) + 2 * cfg.bubble_pad_x * s
        bubble_h = (
            cfg.bubble_pad_top * s + name_h + cfg.name_gap * s + body_h + cfg.bubble_pad_bottom * s
        )

        avatar_px = cfg.avatar_size * s
        pad = cfg.padding * s
        bx0 = pad + avatar_px + cfg.avatar_gap * s
        canvas_w = bx0 + bubble_w + pad
        canvas_h = pad + max(bubble_h, avatar_px) + cfg.bottom_margin * s

        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        by0 = pad
        self._draw_bubble_with_avatar(
            canvas, avatar_source, user_id, author_name, bx0, by0, bubble_w, bubble_h
        )

        tx = bx0 + cfg.bubble_pad_x * s
        ty = by0 + cfg.bubble_pad_top * s
        name_color = self._get_name_color(user_id)
        with Pilmoji(canvas, source=AppleEmojiSource) as pilmoji:
            pilmoji.text((tx, ty), author_name, font=name_font, fill=name_color)
            pilmoji.text(
                (tx - body_bbox[0], ty + name_h + cfg.name_gap * s - body_bbox[1]),
                body,
                font=text_font,
                fill=cfg.text_color,
                spacing=spacing,
            )

        return self._finalize(canvas)

    def _render_photo_quote(
        self,
        avatar_source: Image.Image | None,
        user_id: int,
        author_name: str,
        photo: Image.Image,
        caption: str | None,
    ) -> io.BytesIO:
        """Render a quoted photo as a bubble: author name on top, image below, optional caption."""
        cfg = self.tg
        s = cfg.supersample

        name_font = self._load_weighted_font(cfg.name_font_size * s, "Bold")
        text_font = self._load_weighted_font(cfg.text_font_size * s, "Regular")

        name_w = name_font.getlength(author_name)
        name_ascent, name_descent = name_font.getmetrics()
        name_h = name_ascent + name_descent

        # The photo spans the full bubble width; make it at least as wide as the name row.
        max_media = cfg.media_max_size * s
        media_w = min(max_media, int(max_media * photo.width / photo.height))
        media_w = max(media_w, int(name_w) + 2 * cfg.bubble_pad_x * s)
        media_h = round(media_w * photo.height / photo.width)
        max_media_h = int(max_media * 1.3)
        photo = photo.resize((media_w, media_h), Image.Resampling.LANCZOS)
        if media_h > max_media_h:
            top = (media_h - max_media_h) // 2  # center-crop overly tall images
            photo = photo.crop((0, top, media_w, top + max_media_h))
            media_h = max_media_h

        caption_lines: list[str] = []
        spacing = cfg.line_spacing * s
        body = ""
        body_bbox = (0, 0, 0, 0)
        if caption:
            max_text_width = media_w - 2 * cfg.bubble_pad_x * s
            for paragraph in caption.split("\n"):
                caption_lines.extend(self._wrap_text(paragraph, text_font, max_text_width) or [""])
            if len(caption_lines) > cfg.max_caption_lines:
                caption_lines = caption_lines[: cfg.max_caption_lines]
                caption_lines[-1] = caption_lines[-1].rstrip() + "…"
            body = "\n".join(caption_lines)
            measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            raw_bbox = measure.multiline_textbbox((0, 0), body, font=text_font, spacing=spacing)
            body_bbox = tuple(int(v) for v in raw_bbox)

        bubble_w = media_w
        header_h = cfg.bubble_pad_top * s + name_h + cfg.name_gap * s
        bubble_h = header_h + media_h
        if caption:
            bubble_h += (
                cfg.caption_gap * s + (body_bbox[3] - body_bbox[1]) + cfg.bubble_pad_bottom * s
            )

        avatar_px = cfg.avatar_size * s
        pad = cfg.padding * s
        bx0 = pad + avatar_px + cfg.avatar_gap * s
        canvas_w = bx0 + bubble_w + pad
        canvas_h = pad + max(bubble_h, avatar_px) + cfg.bottom_margin * s

        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        by0 = pad
        self._draw_bubble_with_avatar(
            canvas, avatar_source, user_id, author_name, bx0, by0, bubble_w, bubble_h
        )

        # With no caption the photo sits flush with the bubble bottom, so its
        # bottom corners follow the bubble radius.
        media_radius = cfg.media_radius * s
        bottom_radius = media_radius if caption else cfg.bubble_radius * s
        photo = self._round_corners(photo, media_radius, bottom_radius)
        canvas.alpha_composite(photo, (bx0, by0 + header_h))

        tx = bx0 + cfg.bubble_pad_x * s
        name_color = self._get_name_color(user_id)
        with Pilmoji(canvas, source=AppleEmojiSource) as pilmoji:
            pilmoji.text(
                (tx, by0 + cfg.bubble_pad_top * s), author_name, font=name_font, fill=name_color
            )
            if caption:
                pilmoji.text(
                    (
                        tx - body_bbox[0],
                        by0 + header_h + media_h + cfg.caption_gap * s - body_bbox[1],
                    ),
                    body,
                    font=text_font,
                    fill=cfg.text_color,
                    spacing=spacing,
                )

        return self._finalize(canvas)

    def _render_sticker_quote(
        self,
        avatar_source: Image.Image | None,
        user_id: int,
        author_name: str,
        sticker_image: Image.Image,
    ) -> io.BytesIO:
        """Render a quoted sticker: no bubble, just the sticker next to the avatar."""
        cfg = self.tg
        s = cfg.supersample

        box = cfg.sticker_quote_size * s
        factor = min(box / sticker_image.width, box / sticker_image.height)
        media_w = round(sticker_image.width * factor)
        media_h = round(sticker_image.height * factor)
        sticker_image = sticker_image.resize((media_w, media_h), Image.Resampling.LANCZOS)
        radius = cfg.media_radius * s
        sticker_image = self._round_corners(sticker_image, radius, radius)

        avatar_px = cfg.avatar_size * s
        pad = cfg.padding * s
        mx0 = pad + avatar_px + cfg.avatar_gap * s
        canvas_w = mx0 + media_w + pad
        canvas_h = pad + max(media_h, avatar_px) + cfg.bottom_margin * s

        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        media_y1 = pad + max(media_h, avatar_px)
        canvas.alpha_composite(sticker_image, (mx0, media_y1 - media_h))

        avatar = self._make_circle_avatar(avatar_source, user_id, author_name, avatar_px)
        canvas.alpha_composite(avatar, (pad, media_y1 - avatar_px))

        return self._finalize(canvas)

    @staticmethod
    def _shorten_multiline(text: str, width: int) -> str:
        """Trim trailing whitespace and truncate, preserving line breaks."""
        text = text.strip()
        if len(text) <= width:
            return text
        return text[: max(0, width - 1)].rstrip() + "…"

    async def create_quote(self, message: Message) -> io.BytesIO | None:
        """Create a Telegram-UI style quote sticker from the replied (or selected) message."""
        try:
            reply_message = message.reply_to_message
            if reply_message is None:
                return None

            from_user = reply_message.from_user
            if from_user is None:
                return None

            author_name = self._shorten(
                from_user.full_name or "Unknown User", self.tg.max_name_length
            )
            avatar_source = await self._get_profile_photo(from_user.id)

            if reply_message.sticker:
                sticker = reply_message.sticker
                # Animated/video stickers can't be rendered; use their static thumbnail.
                if sticker.is_animated or sticker.is_video:
                    file_id = sticker.thumbnail.file_id if sticker.thumbnail else None
                else:
                    file_id = sticker.file_id
                media = await self._download_image(file_id) if file_id else None
                if media is None:
                    return None
                return self._render_sticker_quote(avatar_source, from_user.id, author_name, media)

            if reply_message.photo:
                media = await self._download_image(reply_message.photo[-1].file_id)
                if media is None:
                    return None
                caption = self._extract_quote_text(message)
                if caption and caption.strip():
                    caption = self._shorten_multiline(caption, self.tg.max_quote_length)
                else:
                    caption = None
                return self._render_photo_quote(
                    avatar_source, from_user.id, author_name, media, caption
                )

            quote_text = self._extract_quote_text(message)
            if not quote_text or not quote_text.strip():
                return None

            quote_text = self._shorten_multiline(quote_text, self.tg.max_quote_length)
            return self._render_sticker(avatar_source, from_user.id, author_name, quote_text)
        except Exception as e:
            logger.exception("Error creating telegram-style quote: %s", e)
            return None

    async def send_quote(self, message: Message):
        """Create and send the quote sticker, or report failure to the user."""
        quote_buffer = await self.create_quote(message)
        if quote_buffer is None:
            await message.answer("❌ Failed to create quote.")
            return

        sticker = BufferedInputFile(quote_buffer.read(), filename="quote.webp")
        await message.reply_sticker(sticker=sticker)
