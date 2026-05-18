"""Content-hash parse cache for incremental ingestion.

Caches per-file parse results (symbols, imports, calls, heritage) keyed by
SHA-256 content hash. On re-ingestion, unchanged files are restored from
cache instead of being re-parsed.

Storage: data/repos/{hash}/cache/
  - manifest.json          — {rel_path: {content_hash, timestamp}}
  - parse_cache/{hash}.pkl — pickled FileParseResult per file
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FileParseResult:
    """Cached parse output for a single file."""

    content_hash: str
    rel_path: str
    language: str
    symbols: list[dict] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    heritage: list[dict] = field(default_factory=list)
    docstrings: list[dict] = field(default_factory=list)
    # Raw node data for KnowledgeGraph reconstruction
    nodes: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)


@dataclass
class DeltaInfo:
    """Result of comparing current files against the manifest."""

    new_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    unchanged_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)

    @property
    def changed_files(self) -> list[str]:
        return self.new_files + self.modified_files

    @property
    def has_changes(self) -> bool:
        return bool(self.new_files or self.modified_files or self.deleted_files)

    def summary(self) -> str:
        return (
            f"new={len(self.new_files)} modified={len(self.modified_files)} "
            f"unchanged={len(self.unchanged_files)} deleted={len(self.deleted_files)}"
        )


def hash_content(content: str | bytes) -> str:
    """SHA-256 hash of file content."""
    if isinstance(content, str):
        content = content.encode("utf-8", errors="replace")
    return hashlib.sha256(content).hexdigest()


def hash_file(file_path: str | Path) -> str:
    """SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class ParseCache:
    """Content-hash cache for per-file parse results."""

    def __init__(self, cache_dir: str | Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._pickle_dir = self._cache_dir / "parse_cache"
        self._manifest_path = self._cache_dir / "manifest.json"
        self._manifest: dict[str, dict[str, Any]] = {}  # rel_path -> {hash, ts}

    def load_manifest(self) -> None:
        """Load the manifest from disk."""
        if self._manifest_path.exists():
            try:
                self._manifest = json.loads(self._manifest_path.read_text())
                logger.info("Parse cache loaded: %d entries", len(self._manifest))
            except (json.JSONDecodeError, TypeError):
                self._manifest = {}
                logger.warning("Parse cache manifest corrupted, starting fresh")
        else:
            self._manifest = {}

    def save_manifest(self) -> None:
        """Persist the manifest to disk."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2))

    def compute_delta(
        self,
        repo_path: str | Path,
        file_paths: list[str],
    ) -> DeltaInfo:
        """Compare discovered files against the cached manifest.

        Args:
            repo_path: Absolute path to the repository root.
            file_paths: List of relative file paths from the walker.

        Returns:
            DeltaInfo with classified files.
        """
        delta = DeltaInfo()
        current_files = set(file_paths)
        cached_files = set(self._manifest.keys())

        # Deleted files: in cache but not in current scan
        delta.deleted_files = sorted(cached_files - current_files)

        for rel_path in file_paths:
            abs_path = os.path.join(repo_path, rel_path)
            try:
                current_hash = hash_file(abs_path)
            except (OSError, IOError):
                delta.new_files.append(rel_path)
                continue

            cached = self._manifest.get(rel_path)
            if cached is None:
                delta.new_files.append(rel_path)
            elif cached.get("hash") != current_hash:
                delta.modified_files.append(rel_path)
            else:
                delta.unchanged_files.append(rel_path)

        return delta

    def get(self, rel_path: str) -> FileParseResult | None:
        """Retrieve cached parse result for a file."""
        entry = self._manifest.get(rel_path)
        if not entry:
            return None

        pickle_path = self._pickle_dir / f"{entry['hash'][:16]}.pkl"
        if not pickle_path.exists():
            return None

        try:
            with open(pickle_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            logger.debug("Cache read failed for %s", rel_path)
            return None

    def put(self, rel_path: str, result: FileParseResult) -> None:
        """Store a parse result in cache."""
        self._pickle_dir.mkdir(parents=True, exist_ok=True)

        pickle_path = self._pickle_dir / f"{result.content_hash[:16]}.pkl"
        with open(pickle_path, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

        self._manifest[rel_path] = {
            "hash": result.content_hash,
            "language": result.language,
        }

    def invalidate(self, rel_paths: list[str]) -> None:
        """Remove cache entries for specified files."""
        for rel_path in rel_paths:
            entry = self._manifest.pop(rel_path, None)
            if entry:
                pickle_path = self._pickle_dir / f"{entry['hash'][:16]}.pkl"
                pickle_path.unlink(missing_ok=True)

    @property
    def size(self) -> int:
        return len(self._manifest)
