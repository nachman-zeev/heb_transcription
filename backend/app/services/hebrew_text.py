from __future__ import annotations

import re
import unicodedata


HEBREW_NIQQUD_RE = re.compile(r"[\u0591-\u05C7]")
PUNCTUATION_RE = re.compile(r"[^\w\s\u0590-\u05FF]", flags=re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_hebrew_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = HEBREW_NIQQUD_RE.sub("", text)
    text = text.replace("׳", "'").replace("״", '"')
    text = PUNCTUATION_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip().lower()


def normalize_hebrew_word(word: str) -> str:
    return normalize_hebrew_text(word)


def split_words(text: str) -> list[str]:
    normalized = normalize_hebrew_text(text)
    if not normalized:
        return []
    return [w for w in normalized.split(" ") if w]
