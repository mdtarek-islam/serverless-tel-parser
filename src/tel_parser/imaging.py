"""Open untrusted image bytes with byte, pixel, side and format caps.

The header gives the size before any pixel data is decoded, so the pixel
cap holds before ``load`` allocates the raster.
"""

from __future__ import annotations

import io
import struct
import warnings

from PIL import Image, ImageFile, UnidentifiedImageError

from .config import ALLOWED_FORMATS, MIN_IMAGE_SIDE, Settings
from .errors import RequestError, too_large

_DECODE_ERRORS = (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, struct.error)


def open_image(data: bytes, settings: Settings) -> Image.Image:
    """Return a fully loaded PNG or JPEG image. Raise RequestError otherwise."""
    if not data:
        raise RequestError("image is empty")
    if len(data) > settings.max_image_bytes:
        raise too_large("image exceeds the byte cap")
    # Truncated files must fail. Never rely on a caller to reset this flag.
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS)
            width, height = image.size
            if width * height > settings.max_image_pixels:
                raise too_large("image exceeds the pixel cap")
            if min(width, height) < MIN_IMAGE_SIDE:
                raise RequestError(f"image sides must be at least {MIN_IMAGE_SIDE} pixels")
            image.load()
        except RequestError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise too_large("image exceeds the pixel cap") from exc
        except MemoryError as exc:
            raise too_large("image needs too much memory to decode") from exc
        except _DECODE_ERRORS as exc:
            raise RequestError("image could not be decoded") from exc
    return image
