"""F16 Photo quality feedback — decodability/dimensions/blur heuristic before the paid call.

An unsupported or undecodable image is turned back (``readable=False``) with retake guidance;
a dark or low-resolution sample still reads but gets guidance; a slightly blurry but decodable
image is allowed (``readable=True``). No OCR confidence percentage is ever fabricated. The
worker exposes the gate through its existing owner, the dispatcher.

Not applicable to this pure, local pre-check: unauthorized / stale-revision / dependency-failure
cases — assess_photo touches no auth context, revision or external provider (that is exactly
why it runs before any paid call). The invalid-input and guidance cases below are its real
failure surface.
"""
from __future__ import annotations

import io
import unittest

from PIL import Image

from app.dispatcher import photo_quality_gate
from app.features.f16_photo_quality_feedback import F16Request, assess_photo


def _sharp(w: int, h: int, media: str = "PNG") -> bytes:
    """A bright, high-contrast checkerboard: high edge energy (not blurry), bright (not dark)."""
    img = Image.new("RGB", (w, h), (235, 235, 235))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if (x // 8 + y // 8) % 2 == 0:
                px[x, y] = (15, 15, 15)
    buf = io.BytesIO()
    img.save(buf, format=media)
    return buf.getvalue()


def _uniform(w: int, h: int, level: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (level, level, level)).save(buf, format="PNG")
    return buf.getvalue()


class AssessPhoto(unittest.TestCase):
    def test_good_photo_is_readable_without_issues(self):
        result = assess_photo(F16Request(image_bytes=_sharp(800, 640), media_type="image/png"))
        self.assertTrue(result.readable)
        self.assertEqual(result.issues, [])
        self.assertEqual((result.width, result.height), (800, 640))

    def test_unsupported_format_rejected(self):
        result = assess_photo(F16Request(image_bytes=_sharp(800, 640), media_type="image/gif"))
        self.assertFalse(result.readable)
        self.assertIn("unsupported_format", result.issues)

    def test_undecodable_bytes_rejected(self):
        result = assess_photo(F16Request(image_bytes=b"not an image", media_type="image/png"))
        self.assertFalse(result.readable)
        self.assertIn("undecodable_image", result.issues)

    def test_format_mismatch_rejected(self):
        # Real PNG bytes declared as JPEG — contents do not match the media type.
        result = assess_photo(F16Request(image_bytes=_sharp(800, 640), media_type="image/jpeg"))
        self.assertFalse(result.readable)
        self.assertIn("format_mismatch", result.issues)

    def test_low_resolution_gets_guidance_but_stays_readable(self):
        result = assess_photo(F16Request(image_bytes=_sharp(240, 180), media_type="image/png"))
        self.assertTrue(result.readable)
        self.assertIn("low_resolution", result.issues)

    def test_dark_sample_gets_guidance_but_stays_readable(self):
        result = assess_photo(F16Request(image_bytes=_uniform(800, 640, 8), media_type="image/png"))
        self.assertTrue(result.readable)
        self.assertIn("too_dark", result.issues)

    def test_blur_is_advisory_image_still_readable(self):
        # A bright, featureless image: low edge energy -> blur advised, but NOT blocked.
        result = assess_photo(F16Request(image_bytes=_uniform(800, 640, 160), media_type="image/png"))
        self.assertTrue(result.readable)
        self.assertIn("possible_blur", result.issues)

    def test_no_fabricated_confidence_percentage(self):
        result = assess_photo(F16Request(image_bytes=_uniform(800, 640, 160), media_type="image/png"))
        self.assertFalse(hasattr(result, "confidence"))
        self.assertTrue(all("%" not in issue for issue in result.issues))

    def test_decompression_bomb_rejected_before_decode(self):
        # Dimensions beyond the 40 MP cap are turned back without decoding pixels.
        result = assess_photo(F16Request(image_bytes=_uniform(8000, 6000, 160), media_type="image/png"))
        self.assertFalse(result.readable)
        self.assertIn("image_too_large", result.issues)


class DispatcherGate(unittest.TestCase):
    def test_gate_turns_back_unreadable_before_paid_call(self):
        result = photo_quality_gate(b"garbage", "image/png")
        self.assertFalse(result.readable)

    def test_gate_passes_a_readable_photo(self):
        result = photo_quality_gate(_sharp(800, 640), "image/png")
        self.assertTrue(result.readable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
