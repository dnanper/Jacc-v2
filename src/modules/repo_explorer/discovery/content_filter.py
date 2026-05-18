"""Detect binary, encrypted, or non-text files before ingestion.

Heuristics (applied to first 8 KB of raw bytes):
1. Null-byte presence (skip UTF-16/32 BOMs)
2. Control-character density  (> 5 %)
3. Shannon entropy            (> 7.5 bits/byte → encrypted / compressed)
"""

from __future__ import annotations

import logging
from math import log2
from pathlib import Path

logger = logging.getLogger(__name__)

_SAMPLE_SIZE = 8192
_CONTROL_RATIO_THRESHOLD = 0.05
_ENTROPY_THRESHOLD = 7.5
_REPLACEMENT_RATIO_THRESHOLD = 0.01

# BOM signatures that legitimately contain null bytes
_UTF32_LE_BOM = b"\xff\xfe\x00\x00"
_UTF32_BE_BOM = b"\x00\x00\xfe\xff"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"

# Control chars excluding \t (0x09), \n (0x0A), \r (0x0D)
_CONTROL_CHARS = frozenset(range(0x01, 0x09)) | frozenset(range(0x0E, 0x20))


def _shannon_entropy(data: bytes) -> float:
    """Compute Shannon entropy in bits per byte (0.0 – 8.0)."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum((c / n) * log2(c / n) for c in freq if c > 0)


def _has_unicode_bom(data: bytes) -> bool:
    """Return True if *data* starts with a UTF-16 or UTF-32 BOM."""
    return (
        data[:4] == _UTF32_LE_BOM
        or data[:4] == _UTF32_BE_BOM
        or data[:2] == _UTF16_LE_BOM
        or data[:2] == _UTF16_BE_BOM
    )


def is_binary_path(file_path: str | Path) -> bool:
    """Check first bytes of a file and return True if it looks binary/encrypted.

    Returns False for empty files and files with a UTF-16/32 BOM.
    """
    try:
        with open(file_path, "rb") as f:
            sample = f.read(_SAMPLE_SIZE)
    except OSError:
        return False  # let caller handle missing files

    if not sample:
        return False

    # UTF-16/32 encoded text legitimately contains null bytes
    if _has_unicode_bom(sample):
        return False

    # 1. Null bytes — strong binary signal for source code files
    if b"\x00" in sample:
        return True

    # 2. Control character density
    control_count = sum(1 for b in sample if b in _CONTROL_CHARS)
    if control_count / len(sample) > _CONTROL_RATIO_THRESHOLD:
        return True

    # 3. Shannon entropy — encrypted / compressed data is near-random
    if _shannon_entropy(sample) > _ENTROPY_THRESHOLD:
        return True

    return False


def is_binary_content(content: str) -> bool:
    """Check already-decoded text for signs it was originally binary.

    Useful after ``read_text(errors='replace')`` where binary bytes
    become U+FFFD replacement characters.
    """
    if not content:
        return False
    replacement_count = content.count("\ufffd")
    return replacement_count / len(content) > _REPLACEMENT_RATIO_THRESHOLD
