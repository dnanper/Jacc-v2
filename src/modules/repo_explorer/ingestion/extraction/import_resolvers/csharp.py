"""C# import resolver — namespace-based resolution via .csproj configs.

Handles:
- Namespace-to-directory mapping using root namespace stripping
- Single file resolution (MyApp.Models.User → Models/User.cs)
- Directory resolution (MyApp.Models → all .cs files in Models/)
- Fallback to suffix matching
"""

from __future__ import annotations

from dataclasses import dataclass

from .utils import SuffixIndex


@dataclass
class CSharpProjectConfig:
    """Parsed .csproj configuration."""
    root_namespace: str
    project_dir: str


def resolve_csharp_import(
    import_path: str,
    csharp_configs: list[CSharpProjectConfig],
    all_files: list[str],
    index: SuffixIndex | None = None,
) -> list[str] | None:
    """Resolve a C# using directive to files.

    Returns list of matching files, or None to fall back.
    """
    if not csharp_configs:
        return None

    sorted_configs = sorted(csharp_configs, key=lambda c: -len(c.root_namespace))

    for config in sorted_configs:
        if not import_path.startswith(config.root_namespace):
            continue

        remainder = import_path[len(config.root_namespace):]
        if remainder.startswith("."):
            remainder = remainder[1:]
        elif remainder:
            continue

        relative = remainder.replace(".", "/") if remainder else ""
        base_dir = config.project_dir.rstrip("/")
        target = (base_dir + "/" + relative) if relative else base_dir

        cs_file = target + ".cs"
        for fp in all_files:
            if fp.replace("\\", "/").endswith(cs_file):
                return [fp]

        dir_prefix = target + "/"
        results: list[str] = []
        for fp in all_files:
            normalized = fp.replace("\\", "/")
            if not normalized.endswith(".cs"):
                continue
            if dir_prefix in normalized:
                idx = normalized.index(dir_prefix) + len(dir_prefix)
                rest = normalized[idx:]
                if "/" not in rest:
                    results.append(fp)

        if results:
            return results

    return None


def resolve_csharp_namespace_dir(
    import_path: str,
    csharp_configs: list[CSharpProjectConfig],
) -> str | None:
    """Get the directory suffix for a C# namespace (for package-map)."""
    sorted_configs = sorted(csharp_configs, key=lambda c: -len(c.root_namespace))

    for config in sorted_configs:
        if not import_path.startswith(config.root_namespace):
            continue
        remainder = import_path[len(config.root_namespace):]
        if remainder.startswith("."):
            remainder = remainder[1:]
        elif remainder:
            continue

        relative = remainder.replace(".", "/") if remainder else ""
        base_dir = config.project_dir.rstrip("/")
        return "/" + ((base_dir + "/" + relative) if relative else base_dir) + "/"

    return None
