"""Lightweight tokenization for BM25 full-text search over mixed CJK/Latin text.

SQLite FTS5's built-in unicode61 tokenizer treats a whole run of CJK characters
as a single token, which makes BM25 useless for Chinese. Instead of pulling in
a segmenter dependency (jieba), we approximate segmentation with character
bigrams for CJK runs and lowercase words for Latin/digit runs. Both indexed
chunks and queries go through the same function, so matching stays consistent.
"""
from __future__ import annotations

import re

_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9_\.\-/]+")

_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x3040, 0x30FF),   # Hiragana / Katakana
)


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(start <= code <= end for start, end in _CJK_RANGES)


def tokenize_for_bm25(text: str) -> str:
    """Return a space-joined token string: CJK bigrams + lowercase latin words."""
    if not text:
        return ""

    tokens: list[str] = []
    cjk_run: list[str] = []
    latin_run: list[str] = []

    def flush_cjk() -> None:
        if not cjk_run:
            return
        if len(cjk_run) == 1:
            tokens.append(cjk_run[0])
        else:
            tokens.extend(cjk_run[i] + cjk_run[i + 1] for i in range(len(cjk_run) - 1))
        cjk_run.clear()

    def flush_latin() -> None:
        if not latin_run:
            return
        word = "".join(latin_run)
        tokens.extend(match.group(0).lower() for match in _LATIN_WORD_RE.finditer(word))
        latin_run.clear()

    for char in text:
        if _is_cjk(char):
            flush_latin()
            cjk_run.append(char)
        elif char.isascii() and (char.isalnum() or char in "._-/"):
            flush_cjk()
            latin_run.append(char)
        else:
            flush_cjk()
            flush_latin()

    flush_cjk()
    flush_latin()
    return " ".join(tokens)


def build_match_query(text: str, max_tokens: int = 32) -> str:
    """Build an FTS5 MATCH expression (OR of quoted tokens) from raw query text."""
    tokens = tokenize_for_bm25(text).split()
    if not tokens:
        return ""
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
        if len(unique) >= max_tokens:
            break
    escaped = [token.replace('"', '""') for token in unique]
    return " OR ".join(f'"{token}"' for token in escaped)
