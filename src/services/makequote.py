import colorsys
import io
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import AppleEmojiSource

logger = logging.getLogger()


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
            await message.answer("❌ Не удалось создать цитату. Ответьте на текстовое сообщение.")
            return

        photo = BufferedInputFile(quote_buffer.read(), filename="quote.png")
        await message.reply_photo(photo=photo)
