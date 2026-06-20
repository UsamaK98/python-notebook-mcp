"""
Image handler: process, resize, and return visualization image data.

Supports returning images as base64 strings for vision-capable LLMs,
and optionally downscaling large images to reduce token cost.
"""

import base64
import io
import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def _try_resize_png(b64_data: str, max_width: int, max_height: int) -> str:
    """Resize a base64 PNG to fit within max_width x max_height.

    Falls back to the original data if Pillow is not installed.
    """
    try:
        from PIL import Image
    except ImportError:
        log.debug("Pillow not installed; returning original image without resizing.")
        return b64_data

    try:
        raw_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(raw_bytes))
        orig_w, orig_h = img.size

        if orig_w <= max_width and orig_h <= max_height:
            return b64_data  # Already within bounds

        ratio = min(max_width / orig_w, max_height / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        log.warning("Image resize failed: %s", e)
        return b64_data


def get_cell_image(
    cell: Any,
    max_width: int = 1200,
    max_height: int = 900,
    max_size_kb: int = 500,
) -> Optional[Dict[str, Any]]:
    """Return image data from *cell*'s first image output.

    Args:
        cell:        A notebook cell node.
        max_width:   Maximum image width in pixels (PNG only).
        max_height:  Maximum image height in pixels (PNG only).
        max_size_kb: Maximum output size in KB. Images exceeding this are
                     resized further.

    Returns:
        Dict with: mime, data (base64), original_size_chars,
        returned_size_chars, resized. Or None if no image output.
    """
    if cell.cell_type != "code":
        return None

    for out in getattr(cell, "outputs", []):
        if out.output_type not in ("execute_result", "display_data"):
            continue
        data = getattr(out, "data", {})

        # Prefer PNG > JPEG > SVG
        for mime in ("image/png", "image/jpeg", "image/svg+xml"):
            if mime not in data:
                continue

            raw = data[mime]

            if mime == "image/svg+xml":
                # SVG is text; return as-is
                return {
                    "mime": mime,
                    "data": raw,
                    "original_size_chars": len(raw),
                    "returned_size_chars": len(raw),
                    "resized": False,
                    "format": "svg",
                }

            original_size = len(raw)
            result_data = raw
            resized = False

            if mime == "image/png":
                result_data = _try_resize_png(raw, max_width, max_height)
                if result_data != raw:
                    resized = True

            # Check final size against max_size_kb
            max_chars = max_size_kb * 1024
            if len(result_data) > max_chars and mime == "image/png":
                # Aggressively resize
                result_data = _try_resize_png(raw, max_width // 2, max_height // 2)
                resized = True

            return {
                "mime": mime,
                "data": result_data,
                "original_size_chars": original_size,
                "returned_size_chars": len(result_data),
                "resized": resized,
                "format": "png" if mime == "image/png" else "jpeg",
            }

    return None


def get_image_dimensions(b64_png: str) -> Optional[Dict[str, int]]:
    """Return the width and height of a base64 PNG image."""
    try:
        from PIL import Image
        raw = base64.b64decode(b64_png)
        img = Image.open(io.BytesIO(raw))
        return {"width": img.width, "height": img.height}
    except Exception:
        # Fallback: read PNG header directly (bytes 16-24 of PNG contain WxH)
        try:
            import struct
            raw = base64.b64decode(b64_png)
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                width = struct.unpack(">I", raw[16:20])[0]
                height = struct.unpack(">I", raw[20:24])[0]
                return {"width": width, "height": height}
        except Exception:
            pass
    return None
