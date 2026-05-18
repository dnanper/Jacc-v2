"""Repository index registry and per-repo storage management.

Per-repo storage:  data/repos/{hash}/
  - meta.json   — repo metadata (commit, stats, timestamps)
  - lbug/       — KuzuDB database (graph + embeddings + vector index)
  - cache/      — parse cache for incremental ingestion

Global registry:   data/registry.json
  - Maps repo names to paths for MCP server discovery
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..config import DATA_DIR, REPOS_DIR


@dataclass
class RepoMeta:
    """Metadata stored in {storage}/meta.json."""

    repo_path: str
    last_commit: str
    indexed_at: str
    stats: dict = field(
        default_factory=lambda: {
            "files": 0,
            "nodes": 0,
            "edges": 0,
            "communities": 0,
            "processes": 0,
            "embeddings": 0,
        }
    )


@dataclass
class RegistryEntry:
    """Entry in the global registry (data/registry.json)."""

    name: str
    path: str
    storage_path: str
    indexed_at: str
    last_commit: str
    stats: dict = field(default_factory=dict)


def _repo_hash(repo_path: str | Path) -> str:
    """Deterministic short hash for a repo path (first 12 hex chars of MD5)."""
    abs_path = str(Path(repo_path).resolve())
    return hashlib.md5(abs_path.encode()).hexdigest()[:12]


def get_storage_path(repo_path: str | Path) -> Path:
    """Get the central storage directory for a repo under data/repos/{hash}/.

    If *repo_path* is already nested inside REPOS_DIR (e.g. a codebase
    extracted into ``data/repos/<hash>/<project>/``), the first sub-directory
    under REPOS_DIR is returned so that artifacts stay alongside the codebase.
    """
    abs_path = Path(repo_path).resolve()
    repos_dir = REPOS_DIR.resolve()

    try:
        relative = abs_path.relative_to(repos_dir)
        parts = relative.parts
        if parts:
            return repos_dir / parts[0]
    except ValueError:
        pass

    h = _repo_hash(repo_path)
    return DATA_DIR / "repos" / h


def get_meta_path(repo_path: str | Path) -> Path:
    return get_storage_path(repo_path) / "meta.json"


def has_index(repo_path: str | Path) -> bool:
    """Check if a repo has a CSG index."""
    return get_meta_path(repo_path).exists()


def load_meta(repo_path: str | Path) -> RepoMeta | None:
    """Load repo metadata from storage."""
    meta_path = get_meta_path(repo_path)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text())
        return RepoMeta(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def save_meta(repo_path: str | Path, meta: RepoMeta) -> None:
    """Save repo metadata to storage (atomic write)."""
    storage = get_storage_path(repo_path)
    storage.mkdir(parents=True, exist_ok=True)
    meta_path = storage / "meta.json"
    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(asdict(meta), indent=2))
    tmp_path.replace(meta_path)


def _get_registry_path() -> Path:
    return DATA_DIR / "registry.json"


def _read_registry() -> list[dict]:
    path = _get_registry_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, TypeError):
        return []


def _write_registry(entries: list[dict]) -> None:
    path = _get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(entries, indent=2))
    tmp_path.replace(path)


def register_repo(repo_path: str | Path, meta: RepoMeta) -> None:
    """Add or update a repo in the global registry."""
    repo_path = str(Path(repo_path).resolve())
    name = Path(repo_path).name
    storage_path = str(get_storage_path(repo_path))

    entries = _read_registry()
    found = False
    for entry in entries:
        if entry.get("path") == repo_path:
            entry.update(
                {
                    "name": name,
                    "storage_path": storage_path,
                    "indexed_at": meta.indexed_at,
                    "last_commit": meta.last_commit,
                    "stats": meta.stats,
                }
            )
            found = True
            break
    if not found:
        entries.append(
            {
                "name": name,
                "path": repo_path,
                "storage_path": storage_path,
                "indexed_at": meta.indexed_at,
                "last_commit": meta.last_commit,
                "stats": meta.stats,
            }
        )
    _write_registry(entries)


def unregister_repo(repo_path: str | Path) -> None:
    """Remove a repo from the global registry."""
    repo_path = str(Path(repo_path).resolve())
    entries = [e for e in _read_registry() if e.get("path") != repo_path]
    _write_registry(entries)


def list_registered_repos(validate: bool = False) -> list[RegistryEntry]:
    """List all registered repos. If validate=True, skip entries with missing storage."""
    entries = []
    for raw in _read_registry():
        try:
            entry = RegistryEntry(**raw)
        except TypeError:
            continue
        if validate and not Path(entry.storage_path).exists():
            continue
        entries.append(entry)
    return entries


def get_repo_by_name(name: str) -> RegistryEntry | None:
    """Look up a registered repo by name (case-insensitive)."""
    matches = [
        e
        for e in list_registered_repos(validate=True)
        if e.name.lower() == name.lower()
    ]
    if not matches:
        return None
    matches.sort(key=lambda e: e.indexed_at, reverse=True)
    return matches[0]
