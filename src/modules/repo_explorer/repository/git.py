"""Git utilities — root detection, commit tracking, diff parsing."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str | Path) -> str:
    """Run a git command and return stripped stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_git_root(path: str | Path) -> str | None:
    """Find the git root directory for the given path."""
    root = _run_git(["rev-parse", "--show-toplevel"], cwd=path)
    return root or None


def is_git_repo(path: str | Path) -> bool:
    """Check if the path is inside a git repository."""
    return get_git_root(path) is not None


def get_current_commit(path: str | Path) -> str | None:
    """Get the current HEAD commit hash."""
    commit = _run_git(["rev-parse", "HEAD"], cwd=path)
    return commit or None


def get_diff_files(
    path: str | Path,
    scope: str = "all",
    base_ref: str | None = None,
) -> list[str]:
    """Get list of changed files from git diff.

    Args:
        path: Repository path.
        scope: One of "unstaged", "staged", "all", "compare".
        base_ref: Base ref for "compare" scope (e.g., "main").

    Returns:
        List of relative file paths that changed.
    """
    if scope == "unstaged":
        args = ["diff", "--name-only"]
    elif scope == "staged":
        args = ["diff", "--staged", "--name-only"]
    elif scope == "compare" and base_ref:
        args = ["diff", base_ref, "--name-only"]
    else:
        args = ["diff", "HEAD", "--name-only"]

    output = _run_git(args, cwd=path)
    if not output:
        return []
    return [line for line in output.splitlines() if line.strip()]
