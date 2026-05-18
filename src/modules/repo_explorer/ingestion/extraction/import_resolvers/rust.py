"""Rust import resolver — crate::, super::, self:: and bare path resolution.

Handles:
- crate:: → resolve from src/ or repo root
- super:: → parent module
- self:: → current module
- Bare paths with :: separators
- mod.rs / lib.rs directory module fallback
"""

from __future__ import annotations


def resolve_rust_import(
    current_file: str,
    import_path: str,
    all_files: set[str],
) -> str | None:
    """Resolve a Rust use path to a file.

    Returns resolved file path, or None to fall back to suffix resolution.
    """
    normalized = import_path.replace("\\", "/")

    if "{" in normalized:
        normalized = normalized[:normalized.index("{")].rstrip(":")

    path = normalized.replace("::", "/")

    if path.startswith("crate/"):
        return _resolve_crate(path[6:], all_files)

    if path.startswith("super/"):
        return _resolve_super(current_file, path[6:], all_files)

    if path.startswith("self/"):
        return _resolve_self(current_file, path[5:], all_files)

    return _try_module_path(path, all_files)


def _resolve_crate(relative: str, all_files: set[str]) -> str | None:
    """Resolve crate:: path — tries src/ prefix first, then root."""
    result = _try_module_path("src/" + relative, all_files)
    if result:
        return result
    return _try_module_path(relative, all_files)


def _resolve_super(
    current_file: str,
    relative: str,
    all_files: set[str],
) -> str | None:
    """Resolve super:: path — parent of current module."""
    dir_parts = current_file.replace("\\", "/").split("/")[:-1]

    filename = current_file.replace("\\", "/").split("/")[-1]
    if filename in ("mod.rs", "lib.rs"):
        if dir_parts:
            dir_parts = dir_parts[:-1]

    if dir_parts:
        dir_parts = dir_parts[:-1]

    base = "/".join(dir_parts)
    target = (base + "/" + relative) if base else relative
    return _try_module_path(target, all_files)


def _resolve_self(
    current_file: str,
    relative: str,
    all_files: set[str],
) -> str | None:
    """Resolve self:: path — current module directory."""
    dir_parts = current_file.replace("\\", "/").split("/")[:-1]

    filename = current_file.replace("\\", "/").split("/")[-1]
    if filename in ("mod.rs", "lib.rs"):
        pass
    else:
        pass

    base = "/".join(dir_parts)
    target = (base + "/" + relative) if base else relative
    return _try_module_path(target, all_files)


def _try_module_path(module_path: str, all_files: set[str]) -> str | None:
    """Try to resolve a module path to a .rs file.

    Tries in order:
    1. {path}.rs (file module)
    2. {path}/mod.rs (directory module)
    3. {path}/lib.rs (crate root)
    4. Strip last segment (might be a symbol) and retry
    """
    candidate = module_path + ".rs"
    if candidate in all_files:
        return candidate

    candidate = module_path + "/mod.rs"
    if candidate in all_files:
        return candidate

    candidate = module_path + "/lib.rs"
    if candidate in all_files:
        return candidate

    parts = module_path.split("/")
    if len(parts) >= 2:
        parent = "/".join(parts[:-1])
        candidate = parent + ".rs"
        if candidate in all_files:
            return candidate
        candidate = parent + "/mod.rs"
        if candidate in all_files:
            return candidate

    return None
