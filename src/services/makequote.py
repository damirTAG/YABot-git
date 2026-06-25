import colorsys
import io
import random
import textwrap
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import AppleEmojiSource


@dataclass
class QuoteConfig:
    """Configuration class for quote settings"""

    width: int = 640
    height: int = 640
    font_size: int = 29
    blur_radius: int = 7
    max_name_length: int = 31
    max_quote_length: int = 300
    max_line_width: int = 29
    stroke_width: int = 2


class QuoteMaker:
    def __init__(self, bot: Bot, config: QuoteConfig | None = None):
        """
        Initialize QuoteMaker for aiogram

        Args:
            bot: aiogram Bot instance
            config: Optional QuoteConfig instance for customization
        """
        self.bot = bot
        self.config = config or QuoteConfig()

        # Initialize paths
        self.base_path = Path(__file__).parent.parent
        self.font_path = self.base_path / "fonts" / "SF-Pro-Text-Bold.otf"

        # Temporary files to cleanup
        self.temp_files: list[Path] = []

        # Fallback to system fonts if SF Pro not available
        if not self.font_path.exists():
            possible_fonts = [
                "/System/Library/Fonts/SFNSText.ttf",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                "C:\\Windows\\Fonts\\segoeui.ttf",  # Windows
            ]
            for font in possible_fonts:
                if Path(font).exists():
                    self.font_path = Path(font)
                    break

        # Initialize font
        self.font = self._load_font()

    def _load_font(self) -> ImageFont.FreeTypeFont:
        """Load font with error handling"""
        try:
            return ImageFont.truetype(str(self.font_path), size=self.config.font_size)
        except OSError as e:
            print(f"Warning: Failed to load font: {e}. Using default font.")
            return ImageFont.load_default()

    def _get_user_color(self, user_id: int) -> tuple[int, int, int]:
        """Generate consistent color for user based on their ID"""
        random.seed(user_id)

        # Generate pleasant colors
        hue = random.random()
        saturation = 0.5 + random.random() * 0.3  # 0.5-0.8
        value = 0.7 + random.random() * 0.2  # 0.7-0.9

        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        return tuple(int(x * 255) for x in rgb)

    async def _get_profile_photo(self, user_id: int) -> Image.Image | None:
        """Get user profile photo"""
        try:
            photos = await self.bot.get_user_profile_photos(user_id=user_id, limit=1)

            if photos.total_count == 0 or not photos.photos:
                return None

            # Get the largest photo size
            photo_sizes = photos.photos[0]
            largest_photo = photo_sizes[-1]

            # Download to BytesIO
            photo_bytes = io.BytesIO()
            await self.bot.download(file=largest_photo.file_id, destination=photo_bytes)
            photo_bytes.seek(0)

            return Image.open(photo_bytes)

        except Exception as e:
            print(f"Error loading profile photo: {e}")
            import traceback

            traceback.print_exc()
            return None

    async def _create_default_avatar(self, user_id: int, author_name: str) -> Image.Image:
        """Create a default avatar with user initials"""
        initials = "".join(word[0].upper() for word in author_name.split()[:2])
        if not initials:
            initials = "?"

        color = self._get_user_color(user_id)

        avatar = Image.new("RGB", (self.config.width, self.config.height), color=color)
        draw = ImageDraw.Draw(avatar)

        # Draw initials
        font_size = int(self.config.height * 0.28)
        try:
            font = ImageFont.truetype(str(self.font_path), size=font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), initials, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (self.config.width - w) / 2
        y = (self.config.height - h) / 2

        draw.text((x, y), initials, font=font, fill="white")
        return avatar

    async def _generate_quote_image(
        self, pfp: Image.Image, quote_text: str, author_name: str
    ) -> io.BytesIO:
        """Generate the quote image with blurred background"""
        # Resize profile picture
        pfp = pfp.resize((self.config.width, self.config.height), Image.Resampling.LANCZOS)

        # Apply blur effect
        pfp_blur = pfp.filter(ImageFilter.GaussianBlur(self.config.blur_radius))

        # Prepare text
        formatted_quote = textwrap.fill(f"«{quote_text}»", self.config.max_line_width)
        full_text = f"{formatted_quote}\n\n© {author_name}"

        # Calculate text position
        draw = ImageDraw.Draw(pfp_blur)
        bbox = draw.textbbox((0, 0), full_text, font=self.font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        text_x = int((self.config.width - text_width) / 2)
        text_y = int((self.config.height - text_height) / 2)

        # Draw text with emoji support
        with Pilmoji(pfp_blur, source=AppleEmojiSource) as pilmoji:
            pilmoji.text(
                (text_x, text_y),
                full_text,
                font=self.font,
                fill="white",
                stroke_width=self.config.stroke_width,
                stroke_fill="black",
                align="center",
            )

        # Save to BytesIO
        output_buffer = io.BytesIO()
        pfp_blur.save(output_buffer, format="PNG", quality=95)
        output_buffer.seek(0)

        return output_buffer

    async def create_quote(self, message: Message) -> io.BytesIO | None:
        """
        Create a quote image from replied message

        Args:
            message: aiogram Message object (should be reply to another message)

        Returns:
            BytesIO with generated quote image or None if failed
        """
        try:
            # Check if message is a reply
            if not message.reply_to_message:
                return None

            reply_message = message.reply_to_message

            # Get quote text
            quote_text = reply_message.text or reply_message.caption
            if not quote_text:
                return None

            # Limit quote length
            quote_text = textwrap.shorten(
                quote_text, width=self.config.max_quote_length, placeholder="..."
            )

            # Get author info
            from_user = reply_message.from_user
            if not from_user:
                return None

            author_name = from_user.full_name or "Unknown User"
            author_name = textwrap.shorten(
                author_name, width=self.config.max_name_length, placeholder="..."
            )

            # Get profile photo or create default avatar
            pfp = await self._get_profile_photo(from_user.id)
            if not pfp:
                pfp = await self._create_default_avatar(from_user.id, author_name)

            # Generate quote image
            quote_buffer = await self._generate_quote_image(pfp, quote_text, author_name)

            return quote_buffer

        except Exception as e:
            print(f"Error creating quote: {e}")
            import traceback

            traceback.print_exc()
            return None

    def cleanup(self):
        """Clean up all temporary files"""
        for file_path in self.temp_files:
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                except OSError as e:
                    print(f"Error deleting {file_path}: {e}")

        self.temp_files.clear()

    async def send_quote(self, message: Message):
        """Create and send quote image with automatic cleanup"""
        try:
            quote_buffer = await self.create_quote(message)

            if quote_buffer:
                photo = BufferedInputFile(quote_buffer.read(), filename="quote.png")
                await message.reply_photo(photo=photo)
            else:
                await message.answer(
                    "❌ Не удалось создать цитату. Ответьте на текстовое сообщение."
                )
        finally:
            self.cleanup()
