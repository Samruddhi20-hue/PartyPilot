import pytest
from app.storage import _image_extension


def test_storage_accepts_matching_png_signature():
    assert _image_extension(
        b"\x89PNG\r\n\x1a\n" + b"sample-data",
        "image/png",
        "venue.png",
    ) == ".png"


def test_storage_rejects_mismatched_extension():
    with pytest.raises(ValueError):
        _image_extension(
            b"\x89PNG\r\n\x1a\n" + b"sample-data",
            "image/png",
            "venue.jpg",
        )


def test_storage_rejects_unsupported_mime_type():
    with pytest.raises(ValueError):
        _image_extension(b"sample", "application/pdf", "venue.pdf")
