"""Ruby import resolver — require/require_relative resolution.

Simple suffix-based resolution with .rb extension.
"""

from __future__ import annotations

from .utils import SuffixIndex, suffix_resolve


def resolve_ruby_import(
    import_path: str,
    all_files: list[str],
    index: SuffixIndex | None = None,
) -> str | None:
    """Resolve a Ruby require/require_relative path."""
    normalized = import_path.replace("\\", "/").lstrip("./")
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return None

    normalized_list = [f.replace("\\", "/").lower() for f in all_files]
    return suffix_resolve(parts, normalized_list, all_files, index)
