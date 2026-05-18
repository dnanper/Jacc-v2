"""File discovery — walk a repository, respect .gitignore, collect paths + sizes.

Two-phase design (matches GitNexus):
1. ``walk_repository_paths`` — scan only (stat), returns ScannedFile list
2. ``read_file_contents`` — lazy load specific file contents on demand
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pathspec
from discovery.content_filter import is_binary_path

from ..config import MAX_FILE_SIZE

logger = logging.getLogger(__name__)


@dataclass
class ScannedFile:
    """Lightweight file reference (no content loaded yet)."""

    path: str
    size: int


def _load_gitignore(repo_path: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns from the repo root."""
    gitignore = repo_path / ".gitignore"
    patterns = [
        ".git",
        ".csg",  # legacy per-repo storage
        "data",  # central CSG data directory
        ".gitnexus",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
    ]
    if gitignore.exists():
        patterns.extend(gitignore.read_text(errors="ignore").splitlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def walk_repository_paths(
    repo_path: str | Path,
    on_progress: callable = None,
    exclude_dirs: frozenset[str] | None = None,
) -> list[ScannedFile]:
    """Scan all files in the repository, returning lightweight references.

    Args:
        repo_path: Absolute path to the repository root.
        on_progress: Optional callback ``(current, total, file_path)``.
        exclude_dirs: Directory names to skip (e.g. ``{"dist", "build"}``).

    Returns:
        List of ScannedFile entries (relative paths + sizes).
    """
    repo = Path(repo_path).resolve()
    spec = _load_gitignore(repo)
    skip_dirs = exclude_dirs or frozenset()
    results: list[ScannedFile] = []

    all_entries: list[tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(repo, topdown=True):
        rel_dir = os.path.relpath(dirpath, repo)
        if rel_dir == ".":
            rel_dir = ""

        dirnames[:] = [
            d
            for d in dirnames
            if not spec.match_file(os.path.join(rel_dir, d) + "/")
            and not d.startswith(".")
            and d not in skip_dirs
        ]

        for fname in filenames:
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            if spec.match_file(rel_path):
                continue
            full_path = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue
            if size > MAX_FILE_SIZE:
                continue
            all_entries.append((rel_path, size))

    total = len(all_entries)
    for i, (rel_path, size) in enumerate(all_entries):
        results.append(ScannedFile(path=rel_path, size=size))
        if on_progress and i % 100 == 0:
            on_progress(i, total, rel_path)

    return results


CHUNK_BYTE_BUDGET = 20 * 1024 * 1024


def group_by_byte_budget(
    files: list[ScannedFile],
    budget: int = CHUNK_BYTE_BUDGET,
) -> list[list[ScannedFile]]:
    """Group files into byte-budget chunks for memory-bounded parsing.

    Each chunk contains files whose total size does not exceed *budget*.
    A single file larger than the budget gets its own chunk.

    Args:
        files: ScannedFile entries with sizes.
        budget: Maximum total bytes per chunk (default 20MB).

    Returns:
        List of chunks, each a list of ScannedFile objects.
    """
    if not files:
        return []

    chunks: list[list[ScannedFile]] = []
    current_chunk: list[ScannedFile] = []
    current_size = 0

    for f in files:
        if current_chunk and current_size + f.size > budget:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
        current_chunk.append(f)
        current_size += f.size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def read_file_contents(
    repo_path: str | Path,
    relative_paths: list[str],
) -> dict[str, str]:
    """Read contents of specific files using parallel I/O.

    Args:
        repo_path: Absolute path to the repository root.
        relative_paths: List of relative file paths to read.

    Returns:
        Dict mapping relative_path → file content string.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    repo = Path(repo_path).resolve()

    def _read_one(rel_path: str) -> tuple[str, str | None]:
        full_path = repo / rel_path
        try:
            if is_binary_path(full_path):
                logger.debug("Skipping binary file: %s", rel_path)
                return rel_path, None
            return rel_path, full_path.read_text(errors="replace")
        except (OSError, UnicodeDecodeError):
            return rel_path, None

    workers = min(os.cpu_count() or 4, 8, len(relative_paths))
    contents: dict[str, str] = {}

    if workers <= 1 or len(relative_paths) < 20:
        for rel_path in relative_paths:
            path, text = _read_one(rel_path)
            if text is not None:
                contents[path] = text
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for path, text in pool.map(_read_one, relative_paths):
                if text is not None:
                    contents[path] = text

    return contents
