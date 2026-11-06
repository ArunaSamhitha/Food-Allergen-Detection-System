"""Turn raw label text (often noisy OCR output) into ingredient items and warnings."""
import re
import unicodedata
from dataclasses import dataclass, field

from .rules import CONTAINS_MARKERS, PRECAUTION_MARKERS

_STOP_HEADINGS = ("nutrition facts", "nutrition information", "distributed by", "manufactured by",
                  "manufactured for", "best before", "keep refrigerated", "storage", "directions")


@dataclass
class ParsedLabel:
    ingredients: list[str] = field(default_factory=list)
    contains: str = ""         # "Contains: milk, soy." statement, if any
    precautions: list[str] = field(default_factory=list)  # "May contain ..." sentences
    found_ingredients_heading: bool = False


def normalize(text: str) -> str:
    """Lowercase and repair the most common OCR artifacts."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)        # words hyphenated across lines
    text = text.replace("\n", " ").replace("|", "l")
    text = re.sub(r"(?<=[a-z])0(?=[a-z])", "o", text)          # pean0ts -> peanots
    text = re.sub(r"(?<=[a-z])1(?=[a-z])", "l", text)          # mi1k -> milk
    text = re.sub(r"[“”\"*•·]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences_with(text: str, markers: tuple[str, ...]) -> list[tuple[int, int]]:
    """Spans of every sentence that contains one of the markers."""
    spans = []
    for marker in markers:
        for m in re.finditer(re.escape(marker), text):
            start = text.rfind(".", 0, m.start()) + 1
            end = text.find(".", m.end())
            spans.append((start, len(text) if end == -1 else end + 1))
    return sorted(set(spans))


def split_items(text: str) -> list[str]:
    """Split an ingredient list on commas, semicolons and brackets; drop percentages and connectives."""
    parts = re.split(r"[,;:()\[\]{}]|\band/or\b|\.\s", text)
    items = []
    for part in parts:
        part = re.sub(r"\d+(\.\d+)?\s*%", " ", part)
        part = re.sub(r"\b(less than \d+% of|contains \d+% or less of|and|or|of each|ingredients?)\b", " ", part)
        part = re.sub(r"\s+", " ", part).strip(" .-")
        if len(part) > 1:
            items.append(part)
    return items


def parse_label(raw: str) -> ParsedLabel:
    text = normalize(raw)
    result = ParsedLabel()

    precaution_spans = _sentences_with(text, PRECAUTION_MARKERS)
    result.precautions = [text[a:b].strip() for a, b in precaution_spans]

    contains_spans = []
    for marker in CONTAINS_MARKERS:
        for m in re.finditer(r"(?<![a-z])" + re.escape(marker), text):
            if any(a <= m.start() < b for a, b in precaution_spans):
                continue
            end = text.find(".", m.end())
            contains_spans.append((m.start(), len(text) if end == -1 else end + 1))
    result.contains = " ".join(text[a:b] for a, b in sorted(set(contains_spans)))

    # Remove warnings from the text before reading the ingredient list.
    body = list(text)
    for a, b in precaution_spans + contains_spans:
        body[a:b] = " " * (b - a)
    body = "".join(body)

    heading = re.search(r"ingredients?\s*[:\-]?", body)
    if heading:
        result.found_ingredients_heading = True
        body = body[heading.end():]
    stops = [body.find(s) for s in _STOP_HEADINGS if body.find(s) != -1]
    if stops:
        body = body[:min(stops)]
    result.ingredients = split_items(body)
    return result
