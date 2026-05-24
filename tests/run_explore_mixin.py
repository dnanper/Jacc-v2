"""Run ExploreMixin against a real LadybugDB database.

Prepare a database first with:
    uv run python tests/run_ingestion_pipeline.py --persist

Then run:
    uv run python tests/run_explore_mixin.py
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
        description="Exercise repo_explorer.explore.explore.ExploreMixin."
    )
    parser.add_argument("--repo-path", help="Ingested repo path.")
    parser.add_argument("--db-path", help="Direct path to the lbug database directory.")
    parser.add_argument("--query", default="Repository user", help="Search query.")
    parser.add_argument("--scope", default="file:models/user.py", help="Context scope.")
    parser.add_argument(
        "--symbols",
        default="build,Repository,load,save,hydrate_user",
        help="Comma-separated symbols for contract/implementation layers.",
    )
    args = parser.parse_args()

    backend, db_path = build_backend(args.repo_path, args.db_path)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    symbol_query = ", ".join(symbols)

    print(f"using LadybugDB: {db_path}")
    print(f"query: {args.query}")
    print(f"scope: {args.scope}")
    print(f"symbols: {symbol_query}")

    try:
        dump("0. topology()", backend.topology())
        dump("1. relevance(query)", backend.relevance(args.query, limit=5))
        dump("2. context_layer(scope, query)", backend.context_layer(args.scope, args.query, limit=5))
        dump("3. crosscut(query)", backend.crosscut(args.query))
        dump("4. contract(symbols)", backend.contract(symbols))
        dump("5. implementation(symbols)", backend.implementation(symbols))

        dump("6. explore_auto() -> compressed topology", backend.explore_auto())
        dump(
            "7. explore_auto(layer='relevance') -> compressed relevance",
            backend.explore_auto(query=args.query, layer="relevance"),
        )
        dump(
            "8. explore_auto(layer='context') -> compressed context",
            backend.explore_auto(query=args.query, scope=args.scope, layer="context"),
        )
        dump(
            "9. explore_auto(layer='contract') -> compressed contract",
            backend.explore_auto(query=symbol_query, layer="contract"),
        )
        dump(
            "10. explore_auto(layer='implementation') -> compressed implementation",
            backend.explore_auto(query=symbol_query, layer="implementation"),
        )
        dump(
            "11. explore_auto(query) -> auto-chained compressed result",
            backend.explore_auto(query=args.query),
        )
    finally:
        backend._adapter.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
