"""Deterministic allergen check: label text + a person's profile -> verdict with evidence.

The verdict never depends on a language model. Every flag points at the exact
words on the label that caused it, so a result can be checked by a person.
"""
import re
from dataclasses import asdict, dataclass, field
from functools import cache
from typing import Literal

from .parser import ParsedLabel, parse_label
from .rules import AMBIGUOUS, CATEGORIES, KNOWN_WORDS

Verdict = Literal["unsafe", "caution", "safe", "unreadable"]
Source = Literal["ingredients", "contains_statement", "precaution"]


@dataclass
class Profile:
    avoid: list[str] = field(default_factory=list)   # category keys from rules.CATEGORIES
    custom: list[str] = field(default_factory=list)  # extra words, e.g. "kiwi", "mustard"

    def validate(self) -> None:
        unknown = [k for k in self.avoid if k not in CATEGORIES]
        if unknown:
            raise ValueError(f"Unknown categories: {', '.join(unknown)}. Valid: {', '.join(CATEGORIES)}")


@dataclass
class Finding:
    category: str
    label: str
    term: str            # the vocabulary word that matched
    text: str            # what the label actually said
    source: Source
    ocr_corrected: bool = False


@dataclass
class Check:
    ingredient: str
    reason: str
    relevant_to: str


@dataclass
class Report:
    verdict: Verdict
    summary: str
    findings: list[Finding]          # matches for categories in the profile
    other_allergens: list[str]       # major allergens present that the profile doesn't avoid
    checks: list[Check]              # ambiguous ingredients worth confirming
    ingredients: list[str]
    precautions: list[str]
    contains_statement: str

    def to_dict(self) -> dict:
        return asdict(self)


def _phrase_pattern(phrase: str) -> str:
    return r"(?<![a-z])" + r"[\s\-]+".join(map(re.escape, phrase.split())) + r"(?![a-z])"


@cache
def _compiled(key: str):
    cat = CATEGORIES[key]
    terms = sorted(cat.terms, key=len, reverse=True)
    include = re.compile("|".join(f"(?P<t{i}>{_phrase_pattern(t)})" for i, t in enumerate(terms)))
    longest_first = sorted(cat.exclude, key=len, reverse=True)
    exclude = re.compile("|".join(_phrase_pattern(t) for t in longest_first)) if cat.exclude else None
    single_words = tuple(t for t in cat.terms if " " not in t and len(t) >= 5)
    return terms, include, exclude, single_words


def _match_category(key: str, text: str) -> list[tuple[str, str, bool]]:
    """(term, matched text, ocr_corrected) for every hit of a category in `text`."""
    terms, include, exclude, single_words = _compiled(key)
    blocked = [m.span() for m in exclude.finditer(text)] if exclude else []
    hits = []
    for m in include.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in blocked):
            continue
        term = terms[int(m.lastgroup[1:])]
        hits.append((term, m.group(0), False))
    if not hits:  # OCR-tolerant pass: near-miss spellings of single-word terms
        blocked_text = " ".join(text[a:b] for a, b in blocked)
        for word in sorted(set(re.findall(r"[a-z]{5,}", text))):
            if word in blocked_text or word in KNOWN_WORDS:
                continue
            limit = 1 if len(word) < 8 else 2
            best = min(single_words, key=lambda t: _edit_distance(word, t), default=None)
            if best and _edit_distance(word, best) <= limit:
                hits.append((best, word, True))
    return hits


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (insertions, deletions, substitutions)."""
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _custom_hits(word: str, text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(_phrase_pattern(word.lower()), text)]


def analyze(raw_text: str, profile: Profile) -> Report:
    profile.validate()
    parsed: ParsedLabel = parse_label(raw_text)
    sections: list[tuple[Source, list[str]]] = [
        ("ingredients", parsed.ingredients),
        ("contains_statement", [parsed.contains] if parsed.contains else []),
        ("precaution", parsed.precautions),
    ]

    findings: list[Finding] = []
    for key in profile.avoid:
        cat = CATEGORIES[key]
        for source, chunks in sections:
            for chunk in chunks:
                for term, _text, fuzzy in _match_category(key, chunk):
                    findings.append(Finding(key, cat.label, term, chunk, source, fuzzy))
    for word in profile.custom:
        for source, chunks in sections:
            for chunk in chunks:
                for _ in _custom_hits(word, chunk):
                    findings.append(Finding(f"custom:{word.lower()}", word, word.lower(), chunk, source))

    findings = _dedupe(findings)

    avoided = set(profile.avoid)
    other = []
    for key, cat in CATEGORIES.items():
        if (cat.kind == "allergen" and key not in avoided
                and any(_match_category(key, c) for _, chunks in sections[:2] for c in chunks)):
            other.append(cat.label)

    checks = []
    for item in parsed.ingredients:
        checks.extend(
            Check(item, reason, relevant)
            for phrase, (relevant, reason) in AMBIGUOUS.items()
            if re.search(_phrase_pattern(phrase), item) and (relevant == "any" or relevant in avoided)
        )

    verdict, summary = _verdict(findings, checks, parsed, raw_text)
    return Report(verdict, summary, findings, other, checks, parsed.ingredients, parsed.precautions,
                  parsed.contains)


_ORDER = {"ingredients": 0, "contains_statement": 1, "precaution": 2}


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """One finding per category per ingredient item ("wheat flour" -> Gluten once, not twice)."""
    findings = sorted(findings, key=lambda f: (_ORDER[f.source], f.ocr_corrected))
    seen, out = set(), []
    for f in findings:
        key = (f.category, f.source, f.text)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _verdict(findings, checks, parsed: ParsedLabel, raw: str) -> tuple[Verdict, str]:
    definite = [f for f in findings if f.source != "precaution"]
    if definite:
        labels = sorted({f.label for f in definite})
        fuzzy = all(f.ocr_corrected for f in definite)
        note = " (read from a blurry label; please double-check)" if fuzzy else ""
        return "unsafe", f"Contains {', '.join(labels)}{note}."
    if findings:
        labels = sorted({f.label for f in findings})
        return "caution", f"May contain {', '.join(labels)} (cross-contact warning on the label)."
    if len(parsed.ingredients) < 2 and len(raw.strip()) < 25:
        return "unreadable", "Couldn't read an ingredient list. Try a sharper photo or type the ingredients."
    if checks:
        return "caution", "No listed allergens matched, but some ingredients have unclear sources."
    return "safe", "No ingredients matched your profile. Always confirm with the package for severe allergies."
