"""Run ImpactMixin against a real LadybugDB database.

Prepare a database first with:
    uv run python tests/run_ingestion_pipeline.py --persist

Then run:
    uv run python tests/run_impact_mixin.py --target load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_MODULES = ROOT / "src" / "modules"
if str(SRC_MODULES) not in sys.path:
    sys.path.insert(0, str(SRC_MODULES))

from repo_explorer.explore import Backend
from repo_explorer.explore._helpers import VALID_RELATION_TYPES
from repo_explorer.graph.storage.code_adapter import LadybugAdapter
from repo_explorer.repository.repo_manager import get_storage_path


def dump(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, indent=2, ensure_ascii=True, default=str))


def latest_lbug_path() -> Path | None:
    repos_dir = SRC_MODULES / "data" / "repos"
    if not repos_dir.exists():
        return None

    candidates = [
        path / "lbug"
        for path in repos_dir.iterdir()
        if path.is_dir() and (path / "lbug").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_db_path(repo_path: str | None, db_path: str | None) -> tuple[Path, str | None]:
    if db_path:
        return Path(db_path).resolve(), repo_path

    if repo_path:
        resolved_repo = Path(repo_path).resolve()
        return get_storage_path(resolved_repo) / "lbug", str(resolved_repo)

    latest = latest_lbug_path()
    if latest:
        return latest.resolve(), None

    raise FileNotFoundError(
        "No LadybugDB found. Run: uv run python tests/run_ingestion_pipeline.py --persist"
    )


def build_backend(repo_path: str | None, db_path: str | None) -> tuple[Backend, Path]:
    resolved_db_path, repo_source_path = resolve_db_path(repo_path, db_path)
    if not resolved_db_path.exists():
        raise FileNotFoundError(
            f"LadybugDB not found at {resolved_db_path}. "
            "Run: uv run python tests/run_ingestion_pipeline.py <repo_path> --persist"
        )

    adapter = LadybugAdapter(
        db_path=str(resolved_db_path),
        repo_source_path=repo_source_path,
    )
    adapter.connect(read_only=True)
    return Backend(adapter), resolved_db_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise repo_explorer.explore.impact.ImpactMixin."
    )
    parser.add_argument("--repo-path", help="Ingested repo path.")
    parser.add_argument("--db-path", help="Direct path to the lbug database directory.")
    parser.add_argument("--target", default="load", help="Symbol name to analyze.")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.4,
        help="Minimum relationship confidence to traverse.",
    )
    parser.add_argument(
        "--detect-changes",
        action="store_true",
        help="Also run detect_changes(). Requires --repo-path pointing to a git repo.",
    )
    parser.add_argument(
        "--scope",
        default="all",
        choices=["all", "staged", "unstaged"],
        help="Git diff scope for --detect-changes.",
    )
    parser.add_argument("--base-ref", default="", help="Base ref for git diff.")
    args = parser.parse_args()

    backend, db_path = build_backend(args.repo_path, args.db_path)
    print(f"using LadybugDB: {db_path}")
    print(f"target: {args.target}")
    print(f"min_confidence: {args.min_confidence}")

    try:
        dump("VALID_RELATION_TYPES used for traversal", sorted(VALID_RELATION_TYPES))
        dump(
            "impact(direction='upstream')",
            backend.impact(
                args.target,
                direction="upstream",
                min_confidence=args.min_confidence,
            ),
        )
        dump(
            "impact(direction='downstream')",
            backend.impact(
                args.target,
                direction="downstream",
                min_confidence=args.min_confidence,
            ),
        )

        if args.detect_changes:
            dump(
                "detect_changes()",
                backend.detect_changes(scope=args.scope, base_ref=args.base_ref),
            )
    finally:
        backend._adapter.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
