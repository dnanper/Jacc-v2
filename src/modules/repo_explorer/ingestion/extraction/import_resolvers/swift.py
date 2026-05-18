"""Swift import resolver — target-based resolution via Package.swift.

Swift imports are module-level. For local packages, we map the import
name to its target directory and return all .swift files in it.
External frameworks (Foundation, UIKit, etc.) return None.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SwiftPackageConfig:
    """Parsed Package.swift target configuration."""
    targets: dict[str, str] = field(default_factory=dict)


def resolve_swift_import(
    import_path: str,
    swift_config: SwiftPackageConfig | None,
    all_files: list[str],
) -> list[str] | None:
    """Resolve a Swift import to all .swift files in the target directory.

    Returns list of matching files, or None (external framework).
    """
    if swift_config is None or not swift_config.targets:
        return None

    target_dir = swift_config.targets.get(import_path)
    if target_dir is None:
        return None

    dir_prefix = target_dir.rstrip("/") + "/"
    results: list[str] = []

    for fp in all_files:
        normalized = fp.replace("\\", "/")
        if normalized.startswith(dir_prefix) and normalized.endswith(".swift"):
            results.append(fp)

    return results if results else None
