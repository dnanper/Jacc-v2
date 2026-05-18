r"""PHP import resolver -- PSR-4 namespace resolution via composer.json.

Handles:
- PSR-4 autoloading: App\Models\User -> app/Models/User.php
- Namespace directory scanning for function/constant imports
- Fallback to suffix matching
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ComposerConfig:
    """Parsed composer.json PSR-4 configuration."""
    psr4: dict[str, str] = field(default_factory=dict)


def resolve_php_import(
    import_path: str,
    composer_config: ComposerConfig | None,
    all_files: set[str],
) -> str | None:
    """Resolve a PHP use/require path via PSR-4.

    Returns resolved file path, or None to fall back.
    """
    if composer_config is None or not composer_config.psr4:
        return None

    normalized = import_path.replace("\\", "/")

    if ".." in normalized:
        return None

    sorted_entries = sorted(composer_config.psr4.items(), key=lambda x: -len(x[0]))

    for namespace, directory in sorted_entries:
        ns_normalized = namespace.replace("\\", "/").rstrip("/")
        if not normalized.startswith(ns_normalized):
            continue

        remainder = normalized[len(ns_normalized):]
        if remainder.startswith("/"):
            remainder = remainder[1:]
        elif remainder:
            continue

        dir_prefix = directory.rstrip("/")

        candidate = dir_prefix + "/" + remainder + ".php" if remainder else dir_prefix + ".php"
        if candidate in all_files:
            return candidate

        if "/" in remainder:
            parent = remainder.rsplit("/", 1)[0]
            candidate = dir_prefix + "/" + parent + ".php"
            if candidate in all_files:
                return candidate

    return None
