"""Language config file parsing — tsconfig, go.mod, composer.json, .csproj, Swift SPM.

Port of GitNexus ingestion/language-config.ts.

Reads language-specific config files from the repo root to improve import
resolution accuracy. Missing configs are None, not errors.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ImportConfigs:
    """Parsed config data from all supported toolchain files."""

    tsconfig_paths: dict[str, str] | None = None
    tsconfig_base_url: str | None = None
    go_module: str | None = None
    php_psr4: dict[str, str] | None = None
    csharp_root_namespaces: list[dict] | None = None
    swift_targets: dict[str, str] | None = None


def load_import_configs(repo_path: str) -> ImportConfigs:
    """Load all language config files from a repository root.

    Each loader is wrapped in try/except — missing or invalid configs
    produce None, not errors.
    """
    configs = ImportConfigs()

    configs.tsconfig_paths, configs.tsconfig_base_url = _load_tsconfig(repo_path)
    configs.go_module = _load_go_mod(repo_path)
    configs.php_psr4 = _load_composer_json(repo_path)
    configs.csharp_root_namespaces = _load_csproj(repo_path)
    configs.swift_targets = _load_swift_spm(repo_path)

    return configs


def _load_tsconfig(repo_path: str) -> tuple[dict[str, str] | None, str | None]:
    """Load path aliases and baseUrl from tsconfig.json."""
    for name in ("tsconfig.json", "tsconfig.app.json", "tsconfig.base.json"):
        config_path = os.path.join(repo_path, name)
        if not os.path.isfile(config_path):
            continue
        try:
            text = Path(config_path).read_text(errors="replace")
            text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
            data = json.loads(text)

            compiler = data.get("compilerOptions", {})
            base_url = compiler.get("baseUrl")
            paths = compiler.get("paths", {})

            if not paths:
                continue

            alias_map = {}
            for pattern, targets in paths.items():
                if isinstance(targets, list) and targets:
                    alias = pattern.rstrip("*")
                    target = targets[0].rstrip("*")
                    alias_map[alias] = target

            if alias_map:
                return alias_map, base_url

        except Exception as exc:
            logger.debug("Failed to parse %s: %s", name, exc)
            continue

    return None, None


def _load_go_mod(repo_path: str) -> str | None:
    """Load module path from go.mod."""
    mod_path = os.path.join(repo_path, "go.mod")
    if not os.path.isfile(mod_path):
        return None
    try:
        text = Path(mod_path).read_text(errors="replace")
        match = re.search(r"^module\s+(\S+)", text, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception as exc:
        logger.debug("Failed to parse go.mod: %s", exc)
    return None


def _load_composer_json(repo_path: str) -> dict[str, str] | None:
    """Load PSR-4 autoload mappings from composer.json."""
    composer_path = os.path.join(repo_path, "composer.json")
    if not os.path.isfile(composer_path):
        return None
    try:
        data = json.loads(Path(composer_path).read_text(errors="replace"))
        psr4 = {}

        for key in ("autoload", "autoload-dev"):
            section = data.get(key, {})
            mappings = section.get("psr-4", {})
            for namespace, directory in mappings.items():
                if isinstance(directory, list):
                    directory = directory[0] if directory else ""
                psr4[namespace] = directory

        return psr4 if psr4 else None

    except Exception as exc:
        logger.debug("Failed to parse composer.json: %s", exc)
        return None


def _load_csproj(repo_path: str) -> list[dict] | None:
    """Scan for .csproj files and extract RootNamespace."""
    results = []
    skip_dirs = {"node_modules", ".git", "bin", "obj", ".vs", "packages"}

    dirs_scanned = 0
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        dirs_scanned += 1
        if dirs_scanned > 100:
            break

        rel_dir = os.path.relpath(dirpath, repo_path)
        if rel_dir.count(os.sep) > 5:
            dirnames.clear()
            continue

        for fname in filenames:
            if fname.endswith(".csproj"):
                csproj_path = os.path.join(dirpath, fname)
                try:
                    text = Path(csproj_path).read_text(errors="replace")
                    match = re.search(r"<RootNamespace>([^<]+)</RootNamespace>", text)
                    root_ns = match.group(1) if match else fname.replace(".csproj", "")
                    results.append(
                        {
                            "rootNamespace": root_ns,
                            "projectDir": os.path.relpath(dirpath, repo_path),
                        }
                    )
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", fname, exc)
                    continue

    return results if results else None


def _load_swift_spm(repo_path: str) -> dict[str, str] | None:
    """Scan for Swift Package Manager target directories."""
    targets = {}

    for sources_dir in ("Sources", "Package/Sources", "src"):
        full_path = os.path.join(repo_path, sources_dir)
        if not os.path.isdir(full_path):
            continue

        for entry in os.listdir(full_path):
            entry_path = os.path.join(full_path, entry)
            if os.path.isdir(entry_path):
                targets[entry] = os.path.join(sources_dir, entry)

    return targets if targets else None
