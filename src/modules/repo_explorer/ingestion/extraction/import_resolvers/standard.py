"""Standard import resolver — suffix-index based fallback.

This module re-exports SuffixIndex and resolve_import_path for backward
compatibility. The actual SuffixIndex implementation lives in utils.py.
"""

from __future__ import annotations

from .utils import (
    SuffixIndex,
    resolve_relative_path,
    try_resolve_with_extensions,
)


def resolve_import_path(
    raw_path: str,
    from_file: str,
    suffix_index: SuffixIndex,
) -> str | None:
    """Resolve a raw import path to an actual file path.

    Handles relative paths (./foo, ../bar) and absolute paths.
    This is the generic fallback used when no language-specific resolver
    matches.
    """
    result = resolve_relative_path(raw_path, from_file, set())
    if result:
        return result

    normalized = raw_path.replace("\\", "/").strip("'\"").lstrip("./")
    return suffix_index.lookup(normalized)
