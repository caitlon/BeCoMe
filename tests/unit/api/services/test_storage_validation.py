"""Unit tests for storage-agnostic photo validation."""

from api.services.storage import validation


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
