"""
Extract EXIF metadata from image bytes.
Returns datetime and GPS if present; None for missing fields.
"""

import io
from datetime import datetime
from typing import NamedTuple

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


class ImageMeta(NamedTuple):
    taken_at: datetime | None   # DateTimeOriginal from EXIF
    lat:      float | None
    lon:      float | None
    device:   str | None        # camera make/model


def extract(image_bytes: bytes) -> ImageMeta:
    try:
        img  = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif()
        if not exif:
            return ImageMeta(None, None, None, None)

        decoded = {TAGS.get(k, k): v for k, v in exif.items()}

        taken_at = _parse_dt(decoded.get("DateTimeOriginal") or decoded.get("DateTime"))
        lat, lon = _parse_gps(decoded.get("GPSInfo"))
        device   = _join(decoded.get("Make"), decoded.get("Model"))

        return ImageMeta(taken_at=taken_at, lat=lat, lon=lon, device=device)
    except Exception:
        return ImageMeta(None, None, None, None)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def _parse_gps(gps_info) -> tuple[float | None, float | None]:
    if not gps_info:
        return None, None
    try:
        g = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
        lat = _dms(g["GPSLatitude"],  g.get("GPSLatitudeRef",  "N"))
        lon = _dms(g["GPSLongitude"], g.get("GPSLongitudeRef", "E"))
        return lat, lon
    except Exception:
        return None, None


def _dms(dms, ref: str) -> float:
    d, m, s = [float(x) for x in dms]
    val = d + m / 60 + s / 3600
    return -val if ref in ("S", "W") else val


def _join(*parts) -> str | None:
    vals = [str(p).strip() for p in parts if p]
    return " ".join(vals) if vals else None
