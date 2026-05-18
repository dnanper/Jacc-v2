"""Python import resolver — PEP 328 relative imports + proximity bare imports.

Handles:
- Relative imports: from .module import X, from ..package import Y
- Proximity bare imports: single-segment imports check co-located modules first
- Falls back to None for suffix resolution by the standard resolver.
"""

from __future__ import annotations


def resolve_python_import(
    current_file: str,
    import_path: str,
    all_files: set[str],
) -> str | None:
    """Resolve a Python import path.

    Returns resolved file path, or None to fall back to suffix resolution.
    """
    normalized = import_path.replace("\\", "/")

    if normalized.startswith("."):
        return _resolve_relative(current_file, normalized, all_files)

    if "/" not in normalized and "." not in normalized:
        result = _resolve_proximity(current_file, normalized, all_files)
        if result:
            return result

    if "." in normalized and "/" not in normalized:
        parts = normalized.split(".")
        path = "/".join(parts)
        pkg = path + "/__init__.py"
        if pkg in all_files:
            return pkg
        mod = path + ".py"
        if mod in all_files:
            return mod

    return None


def _resolve_relative(
    current_file: str,
    import_path: str,
    all_files: set[str],
) -> str | None:
    """PEP 328 relative import resolution."""
    dot_count = 0
    for ch in import_path:
        if ch == ".":
            dot_count += 1
        else:
            break

    remainder = import_path[dot_count:]
    dir_parts = current_file.replace("\\", "/").split("/")[:-1]

    levels_up = dot_count - 1
    if levels_up > len(dir_parts):
        return None

    if levels_up > 0:
        dir_parts = dir_parts[:-levels_up]

    if remainder:
        dir_parts.extend(remainder.split("."))

    base = "/".join(dir_parts)

    pkg = base + "/__init__.py"
    if pkg in all_files:
        return pkg
    mod = base + ".py"
    if mod in all_files:
        return mod

    return None


def _resolve_proximity(
    current_file: str,
    name: str,
    all_files: set[str],
) -> str | None:
    """Single-segment bare import: check same directory first."""
    dir_parts = current_file.replace("\\", "/").split("/")[:-1]
    base_dir = "/".join(dir_parts) if dir_parts else ""
    prefix = (base_dir + "/") if base_dir else ""

    pkg = prefix + name + "/__init__.py"
    if pkg in all_files:
        return pkg
    mod = prefix + name + ".py"
    if mod in all_files:
        return mod

    return None
