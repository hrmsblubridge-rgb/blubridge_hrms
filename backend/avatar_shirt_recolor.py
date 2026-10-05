"""Auto-replace light/white shirts in newly uploaded profile photos.

Why: avatars are delivered on a strict #FFFFFF background, so a white or very
light shirt visually bleeds into the backdrop and looks unprofessional on ID
cards / the Photo Wall. For those photos only we prepend Cloudinary's
Generative-AI replace transformation to recolour the shirt navy blue.

Detection is deliberately conservative — it runs on the ALREADY whitened,
face-cropped 512x512 delivery (so the torso is always in the lower band) and
only fires when the shirt band is BOTH very bright and low-saturation
(white / off-white / beige / pastel). Pure-white background pixels are
excluded, and saturated colours (teal, orange, maroon, navy...) never match.
Validated against 12 real employee photos: 12/12 correct.
"""
import io
import logging
import re
import urllib.request

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Generative AI replace — Cloudinary handles the actual repaint.
GEN_REPLACE_TRANSFORM = (
    "e_gen_replace:from_white%20or%20light%20coloured%20shirt;to_navy%20blue%20shirt"
)

# Flat, uncompressed delivery used purely for pixel inspection.
_DETECT_TRANSFORM = "e_background_removal,b_rgb:ffffff,c_fill,g_face,w_512,h_512/f_png"

# Torso band of the 512x512 face-aware crop.
_BAND = (400, 508, 100, 412)  # y0, y1, x0, x1
_BG_WHITE = 250      # >= on all channels => background, ignore
_MIN_SHIRT_PX = 2000
_V_MIN = 185         # median brightness of shirt pixels
_S_MAX = 125         # median saturation of shirt pixels

_CLOUD_RE = re.compile(r"^(https://res\.cloudinary\.com/[^/]+/image/upload/)(.+)$")


def _split_cloudinary_url(url: str):
    """Return (base_upload_url, asset_path) or None when not a Cloudinary image."""
    m = _CLOUD_RE.match(url or "")
    if not m:
        return None
    base, rest = m.groups()
    vm = re.search(r"(v\d+/.+)$", rest)
    return (base, vm.group(1)) if vm else (base, rest)


def is_light_shirt(avatar_url: str) -> bool:
    parts = _split_cloudinary_url(avatar_url)
    if not parts:
        return False
    base, asset = parts
    detect_url = f"{base}{_DETECT_TRANSFORM}/{asset}"
    try:
        with urllib.request.urlopen(detect_url, timeout=25) as resp:
            data = resp.read()
    except Exception as e:
        logger.warning(f"Shirt detection download failed: {e}")
        return False

    try:
        img = Image.open(io.BytesIO(data))
        rgb = np.asarray(img.convert("RGB")).astype(np.int16)
        hsv = np.asarray(img.convert("HSV")).astype(np.float32)
    except Exception as e:
        logger.warning(f"Shirt detection decode failed: {e}")
        return False

    y0, y1, x0, x1 = _BAND
    if rgb.shape[0] < y1 or rgb.shape[1] < x1:
        return False
    band_rgb = rgb[y0:y1, x0:x1]
    band_hsv = hsv[y0:y1, x0:x1]
    bg = (band_rgb >= _BG_WHITE).all(axis=2)
    sat = band_hsv[:, :, 1][~bg]
    val = band_hsv[:, :, 2][~bg]
    if sat.size < _MIN_SHIRT_PX:
        return False
    med_s = float(np.median(sat))
    med_v = float(np.median(val))
    light = med_v >= _V_MIN and med_s <= _S_MAX
    logger.info(f"Shirt detection: medV={med_v:.0f} medS={med_s:.0f} light={light}")
    return light


def apply_gen_replace(avatar_url: str) -> str:
    """Prepend the generative-replace step ahead of the existing transforms."""
    if GEN_REPLACE_TRANSFORM in avatar_url:
        return avatar_url
    return avatar_url.replace("/upload/", f"/upload/{GEN_REPLACE_TRANSFORM}/", 1)


def maybe_recolor_shirt(avatar_url: str):
    """Return (final_url, recoloured: bool) for a freshly uploaded avatar."""
    if not avatar_url or "res.cloudinary.com" not in avatar_url:
        return avatar_url, False
    if GEN_REPLACE_TRANSFORM in avatar_url or "e_gen_replace" in avatar_url:
        return avatar_url, False
    try:
        if not is_light_shirt(avatar_url):
            return avatar_url, False
        return apply_gen_replace(avatar_url), True
    except Exception as e:
        logger.warning(f"Shirt recolour skipped: {e}")
        return avatar_url, False
