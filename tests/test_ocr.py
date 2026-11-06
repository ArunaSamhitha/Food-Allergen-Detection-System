"""Real OCR on a rendered label image. Runs where Tesseract is installed (CI, Docker)."""
import shutil

import pytest

pytest.importorskip("cv2")
pytest.importorskip("pytesseract")
PIL = pytest.importorskip("PIL")
if not shutil.which("tesseract"):
    pytest.skip("tesseract binary not installed", allow_module_level=True)

import io  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from allergencheck import Profile, analyze  # noqa: E402
from allergencheck.ocr import read_label  # noqa: E402


def label_png(lines):
    img = Image.new("RGB", (900, 60 + 44 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    for i, line in enumerate(lines):
        draw.text((30, 30 + 44 * i), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_photo_to_verdict():
    png = label_png(["INGREDIENTS: SUGAR, PALM OIL,", "HAZELNUTS, SKIM MILK POWDER,", "COCOA, SOY LECITHIN."])
    ocr = read_label(png)
    assert ocr.confidence > 60, ocr
    report = analyze(ocr.text, Profile(["tree_nut", "milk"]))
    assert report.verdict == "unsafe"
    assert {f.category for f in report.findings} == {"tree_nut", "milk"}
