"""Unit tests for storage-agnostic photo validation."""

from io import BytesIO

from PIL import Image

from api.services.storage import validation


def _png(width: int, height: int) -> bytes:
    """Encode a real single-channel PNG of the given canvas size.

    Grayscale and a flat fill keep the encoded file tiny even for huge canvases --
    which is exactly what makes a decompression bomb cheap to send.
    """
    buffer = BytesIO()
    Image.new("L", (width, height), 255).save(buffer, format="PNG")
    return buffer.getvalue()


class TestExtensionFor:
    """Tests for content-type to extension mapping."""

    def test_maps_known_types(self):
        """Known content types map to their canonical extension."""
        assert validation.extension_for("image/jpeg") == "jpg"
        assert validation.extension_for("image/png") == "png"
        assert validation.extension_for("image/gif") == "gif"
        assert validation.extension_for("image/webp") == "webp"

    def test_falls_back_to_jpg(self):
        """An unknown content type falls back to the jpg extension."""
        assert validation.extension_for("application/octet-stream") == "jpg"


class TestValidateImageContent:
    """Tests for magic-byte validation."""

    def test_valid_jpeg(self):
        """Valid JPEG content passes validation."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert validation.validate_image_content(content, "image/jpeg")

    def test_valid_png(self):
        """Valid PNG content passes validation."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert validation.validate_image_content(content, "image/png")

    def test_valid_gif87a(self):
        """Valid GIF87a content passes validation."""
        assert validation.validate_image_content(b"GIF87a" + b"\x00" * 100, "image/gif")

    def test_valid_gif89a(self):
        """Valid GIF89a content passes validation."""
        assert validation.validate_image_content(b"GIF89a" + b"\x00" * 100, "image/gif")

    def test_valid_webp(self):
        """Valid WebP content passes validation."""
        content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert validation.validate_image_content(content, "image/webp")

    def test_invalid_content(self):
        """Non-image content fails validation."""
        assert not validation.validate_image_content(b"This is just text", "image/jpeg")

    def test_mismatched_type(self):
        """JPEG content with a PNG claimed type fails."""
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert not validation.validate_image_content(jpeg, "image/png")

    def test_empty_content(self):
        """Empty content fails validation."""
        assert not validation.validate_image_content(b"", "image/jpeg")

    def test_riff_without_webp(self):
        """A RIFF container that is not WebP fails validation."""
        content = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
        assert not validation.validate_image_content(content, "image/webp")


class TestValidateImageDimensions:
    """Tests for the pixel-canvas guard on uploads."""

    def test_accepts_a_normal_avatar(self):
        """A small real image passes."""
        assert validation.validate_image_dimensions(_png(256, 256))

    def test_accepts_the_exact_pixel_budget(self):
        """An image sitting exactly on the pixel budget is still accepted."""
        side = 4096
        assert side * side == validation.MAX_IMAGE_PIXELS
        assert validation.validate_image_dimensions(_png(side, side))

    def test_rejects_a_decompression_bomb(self):
        """A tiny file declaring a huge canvas is rejected.

        This is the case the byte cap cannot catch: the encoded PNG below is a few
        dozen KB, well under MAX_FILE_SIZE_BYTES, but decoding it would allocate
        hundreds of megabytes.
        """
        bomb = _png(5000, 5000)
        assert len(bomb) < validation.MAX_FILE_SIZE_BYTES
        assert not validation.validate_image_dimensions(bomb)

    def test_rejects_an_over_long_side(self):
        """An image within the pixel budget but too long on one side is rejected."""
        content = _png(validation.MAX_IMAGE_DIMENSION + 1, 1)
        assert not validation.validate_image_dimensions(content)

    def test_rejects_unparseable_content(self):
        """Bytes that are not an image at all are rejected rather than raising."""
        assert not validation.validate_image_dimensions(b"This is not an image file")

    def test_rejects_empty_content(self):
        """Empty content is rejected rather than raising."""
        assert not validation.validate_image_dimensions(b"")
