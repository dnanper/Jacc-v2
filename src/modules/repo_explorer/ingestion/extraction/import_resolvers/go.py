"""Go import resolver — package-based resolution via go.mod module path.

Go imports entire packages (directories), not individual files.
Returns all .go files in the matched package directory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GoModuleConfig:
    """Parsed go.mod module configuration."""
    module_path: str


def resolve_go_import(
    import_path: str,
    go_module: GoModuleConfig | None,
    all_files: list[str],
) -> list[str] | None:
    """Resolve a Go import to all .go files in the target package.

    Returns list of matching files, or None to fall back to suffix resolution.
    """
    if go_module is None:
        return None

    if not import_path.startswith(go_module.module_path):
        return None

    relative_pkg = import_path[len(go_module.module_path):]
    if relative_pkg.startswith("/"):
        relative_pkg = relative_pkg[1:]

    if not relative_pkg:
        return None

    pkg_suffix = "/" + relative_pkg + "/"

    results: list[str] = []
    for fp in all_files:
        if not fp.endswith(".go"):
            continue
        normalized = "/" + fp.replace("\\", "/")
        if pkg_suffix not in normalized:
            continue

        idx = normalized.index(pkg_suffix) + len(pkg_suffix)
        rest = normalized[idx:]
        if "/" in rest:
            continue

        if rest.endswith("_test.go"):
            continue

        results.append(fp)

    return results if results else None
