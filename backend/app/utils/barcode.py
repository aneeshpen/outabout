"""Barcode / QR decoding for the guard's image-upload endpoint.

``zxing-cpp`` is the Python binding of the same ZXing engine the Express
backend used through ``zxing-wasm``, so Code 128 and QR payloads decode
identically.  Both it and Pillow are optional: if they are not installed the
endpoint reports that cleanly instead of pretending to scan.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional


@dataclass
class BarcodeResult:
    ok: bool
    data: Optional[str] = None
    format: Optional[str] = None
    reason: Optional[str] = None


def decoder_available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        import zxingcpp  # noqa: F401
    except ImportError:
        return False
    return True


def extract_barcode(image_bytes: bytes) -> BarcodeResult:
    try:
        from PIL import Image, ImageOps
        import zxingcpp
    except ImportError:
        return BarcodeResult(
            ok=False,
            reason="Barcode decoding is not available: install 'zxing-cpp' and 'pillow'",
        )

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("L")
    except Exception:
        return BarcodeResult(ok=False, reason="cannot read image")

    # Try the image as-is, then rotations, like the previous implementation.
    for angle in (0, 90, 180, 270):
        candidate = image if angle == 0 else image.rotate(angle, expand=True)
        try:
            results = zxingcpp.read_barcodes(candidate)
        except Exception:
            results = []
        for result in results:
            text = (result.text or "").strip()
            if text:
                return BarcodeResult(
                    ok=True, data=text, format=str(getattr(result, "format", ""))
                )

    return BarcodeResult(ok=False, reason="No barcode found")
