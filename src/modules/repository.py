"""Read-only GitHub source snapshots for benchmark localization."""

from __future__ import annotations

import hashlib
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

from .benchmarks import LocalizationInstance


@dataclass(frozen=True)
class Snapshot:
    path: Path
    repo: str
    commit: str
    reused_repo: bool
    reused_snapshot: bool


class GitSnapshotProvider:
    """Clone repositories once and materialize immutable commit snapshots."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.repositories = root / "repositories"
        self.snapshots = root / "snapshots"

    def get(self, instance: LocalizationInstance, *, force: bool = False) -> Snapshot:
        repo_key = _safe_key(instance.repo)
        commit_key = _safe_key(instance.base_commit)
        repository = self.repositories / repo_key
        snapshot = self.snapshots / f"{repo_key}-{commit_key}"
        reused_repo = repository.exists()
        reused_snapshot = snapshot.exists() and not force

        self.repositories.mkdir(parents=True, exist_ok=True)
        self.snapshots.mkdir(parents=True, exist_ok=True)
        if not reused_repo:
            _run(["git", "clone", f"https://github.com/{instance.repo}.git", str(repository)])
        if force and snapshot.exists():
            _remove_tree(snapshot)
        if not reused_snapshot:
            archive = snapshot.with_suffix(".tar")
            _run(["git", "-C", str(repository), "fetch", "--quiet", "--all", "--tags"])
            _run(["git", "-C", str(repository), "cat-file", "-e", f"{instance.base_commit}^{{commit}}"])
            snapshot_tmp = snapshot.with_name(snapshot.name + ".tmp")
            _remove_tree(snapshot_tmp)
            snapshot_tmp.mkdir(parents=True)
            with archive.open("wb") as stream:
                subprocess.run(
                    ["git", "-C", str(repository), "archive", "--format=tar", instance.base_commit],
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=False,
                )
            with tarfile.open(archive) as tar:
                tar.extractall(snapshot_tmp)
            archive.unlink(missing_ok=True)
            snapshot_tmp.rename(snapshot)
            reused_snapshot = False
        return Snapshot(snapshot, instance.repo, instance.base_commit, reused_repo, reused_snapshot)


def _safe_key(value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    readable = "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
    return f"{readable[:80]}-{digest}"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _remove_tree(path: Path) -> None:
    if path.is_dir():
        import shutil

        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
