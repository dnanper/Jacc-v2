"""Shared resolver utilities — SuffixIndex, extension resolution helpers.

Extracted from standard.py for reuse by per-language resolvers.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath


EXTENSIONS = (
    "", ".tsx", ".ts", ".jsx", ".js",
    "/index.tsx", "/index.ts", "/index.jsx", "/index.js",
    ".py", "/__init__.py",
    ".java", ".kt", ".kts",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh",
    ".cs", ".go", ".rs", "/mod.rs",
    ".php", ".phtml",
    ".swift", ".rb",
)


class SuffixIndex:
    """Maps path suffixes to full file paths for fast import resolution.

    Also supports directory lookups (get_files_in_dir) and
    case-insensitive matching (get_insensitive).
    """

    def __init__(self, file_paths: list[str]) -> None:
        self._index: dict[str, list[str]] = {}
        self._lower_index: dict[str, list[str]] = {}
        self._dir_index: dict[str, dict[str, list[str]]] = {}

        for fp in file_paths:
            normalized = fp.replace("\\", "/")
            parts = normalized.split("/")
            for i in range(len(parts)):
                suffix = "/".join(parts[i:])
                self._index.setdefault(suffix, []).append(normalized)
                self._lower_index.setdefault(suffix.lower(), []).append(normalized)
                no_ext = os.path.splitext(suffix)[0]
                if no_ext != suffix:
                    self._index.setdefault(no_ext, []).append(normalized)
                    self._lower_index.setdefault(no_ext.lower(), []).append(normalized)

            if len(parts) >= 2:
                dir_part = "/".join(parts[:-1])
                ext = os.path.splitext(parts[-1])[1]
                for i in range(len(parts) - 1):
                    dir_suffix = "/".join(parts[i:-1])
                    if dir_suffix:
                        dir_key = "/" + dir_suffix + "/"
                        self._dir_index.setdefault(dir_key, {}).setdefault(ext, []).append(normalized)

    def lookup(self, import_path: str) -> str | None:
        """Resolve an import path to a single file path (unique match only)."""
        normalized = import_path.replace("\\", "/").lstrip("./")
        candidates = self._index.get(normalized, [])
        if len(candidates) == 1:
            return candidates[0]

        for ext in EXTENSIONS:
            if not ext:
                continue
            with_ext = normalized + ext
            candidates = self._index.get(with_ext, [])
            if len(candidates) == 1:
                return candidates[0]

        return None

    def get(self, suffix: str) -> str | None:
        """Get exact suffix match (single candidate only)."""
        candidates = self._index.get(suffix, [])
        return candidates[0] if len(candidates) == 1 else None

    def get_insensitive(self, suffix: str) -> str | None:
        """Case-insensitive suffix match (single candidate only)."""
        candidates = self._lower_index.get(suffix.lower(), [])
        return candidates[0] if len(candidates) == 1 else None

    def get_all(self, suffix: str) -> list[str]:
        """Get all files matching a suffix."""
        return self._index.get(suffix, [])

    def get_files_in_dir(self, dir_suffix: str, extension: str) -> list[str]:
        """Get all files with a given extension in a directory suffix.

        Args:
            dir_suffix: Directory suffix like "/com/example/" (with slashes).
            extension: File extension like ".java".
        """
        dir_entries = self._dir_index.get(dir_suffix, {})
        return dir_entries.get(extension, [])


def try_resolve_with_extensions(base_path: str, all_files: set[str]) -> str | None:
    """Try resolving a base path by appending various extensions."""
    for ext in EXTENSIONS:
        candidate = base_path + ext
        if candidate in all_files:
            return candidate
    return None


def suffix_resolve(
    path_parts: list[str],
    normalized_file_list: list[str],
    all_file_list: list[str],
    index: SuffixIndex | None = None,
) -> str | None:
    """Resolve path parts using suffix matching.

    Tries joining path_parts with '/' and looking up with extensions.
    Falls back to linear scan if index is unavailable.
    """
    suffix = "/".join(path_parts)
    if not suffix:
        return None

    if index is not None:
        result = index.lookup(suffix)
        if result:
            return result

    for ext in EXTENSIONS:
        if not ext:
            continue
        target = suffix + ext
        for i, nf in enumerate(normalized_file_list):
            if nf.endswith(target):
                return all_file_list[i]
    return None


def resolve_relative_path(
    raw_path: str,
    from_file: str,
    all_files: set[str],
) -> str | None:
    """Resolve a relative import path (./ or ../) against the importing file."""
    normalized = raw_path.replace("\\", "/").strip("'\"")
    if not normalized.startswith("."):
        return None

    from_dir = str(PurePosixPath(from_file.replace("\\", "/")).parent)
    resolved = str(PurePosixPath(from_dir) / normalized)

    parts = resolved.split("/")
    stack: list[str] = []
    for part in parts:
        if part == "..":
            if stack:
                stack.pop()
        elif part != ".":
            stack.append(part)
    resolved = "/".join(stack)

    return try_resolve_with_extensions(resolved, all_files)
