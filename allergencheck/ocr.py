"""Read text from a label photo with OpenCV preprocessing and Tesseract."""
from dataclasses import dataclass

import numpy as np


@dataclass
class OcrResult:
    text: str
    confidence: float  # mean Tesseract word confidence, 0-100
    words: int


def preprocess(image_bytes: bytes) -> np.ndarray:
    import cv2

    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("The file isn't a readable image.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Small text on packaging reads much better at higher resolution.
    h, w = gray.shape
    if max(h, w) < 1600:
        scale = 1600 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    # Adaptive threshold copes with glare and uneven lighting better than one global threshold.
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)


def read_label(image_bytes: bytes) -> OcrResult:
    import pytesseract

    processed = preprocess(image_bytes)
    data = pytesseract.image_to_data(processed, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
    words, confs = [], []
    for word, conf in zip(data["text"], data["conf"]):
        conf = float(conf)
        if word.strip() and conf >= 0:
            words.append(word)
            confs.append(conf)
    return OcrResult(" ".join(words), round(sum(confs) / len(confs), 1) if confs else 0.0, len(words))
