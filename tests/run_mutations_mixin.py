"""Show what repo_explorer.explore.mutations.MutationsMixin does.

The default mode uses a fake backend and avoids writes/deletes.  Use --real
to exercise read-only parts against a LadybugDB database.
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
from repo_explorer.explore.mutations import MutationsMixin
from repo_explorer.graph.storage.code_adapter import LadybugAdapter
from repo_explorer.repository.repo_manager import get_storage_path


class FakeMutationsBackend(MutationsMixin):
    """Small backend surface needed by MutationsMixin."""

    def context(self, symbol_name: str) -> dict[str, Any]:
        if symbol_name == "missing":
            return {"error": "Symbol 'missing' not found"}

        return {
            "symbol": {
                "id": "Method:app/main.py:Service.build",
                "name": symbol_name,
                "type": "Method",
                "filePath": "app/main.py",
            },
            "callers": [
                {
                    "uid": "Function:cli.py:main",
                    "name": "main",
                    "filePath": "cli.py",
                    "relType": "CALLS",
                },
                {
                    "uid": "Class:app/main.py:Service",
                    "name": "Service",
                    "filePath": "app/main.py",
                    "relType": "HAS_METHOD",
                },
            ],
            "_all_matches": [
                {
                    "name": symbol_name,
                    "type": "Method",
                    "filePath": "app/main.py",
                },
                {
                    "name": symbol_name,
                    "type": "Method",
                    "filePath": "workers/job.py",
                },
            ],
        }

    def _query(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        if "MATCH" in query.upper() or "RETURN" in query.upper():
            return [{"name": "build", "type": "Method", "filePath": "app/main.py"}]
        raise RuntimeError("Fake backend only accepts simple read queries")


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


def build_real_backend(repo_path: str | None, db_path: str | None) -> tuple[Backend, Path]:
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


def run_safe_mutation_examples(backend: MutationsMixin, symbol: str) -> None:
    dump("rename(symbol, new_name, dry_run=True)", backend.rename(symbol, "renamed_build"))
    dump("rename('missing', new_name, dry_run=True)", backend.rename("missing", "anything"))
    dump(
        "cypher(read query)",
        backend.cypher("MATCH (n) RETURN n.name AS name LIMIT 3"),
    )
    dump(
        "cypher(write query blocked by CYPHER_WRITE_RE)",
        backend.cypher("CREATE (n:Test {name: 'x'}) RETURN n"),
    )
    dump("list_repos()", backend.list_repos())
    dump("delete_repo() without target", MutationsMixin.delete_repo(clean_storage=False))
    dump("analyze() without path", MutationsMixin.analyze())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise repo_explorer.explore.mutations.MutationsMixin safely."
    )
    parser.add_argument("--real", action="store_true", help="Use a real LadybugDB.")
    parser.add_argument("--repo-path", help="Ingested repo path.")
    parser.add_argument("--db-path", help="Direct path to the lbug database directory.")
    parser.add_argument("--symbol", default="build", help="Symbol name for rename dry-run.")
    args = parser.parse_args()

    if args.real:
        backend, db_path = build_real_backend(args.repo_path, args.db_path)
        print(f"using real LadybugDB: {db_path}")
        try:
            run_safe_mutation_examples(backend, args.symbol)
        finally:
            backend._adapter.close()
        return 0

    run_safe_mutation_examples(FakeMutationsBackend(), args.symbol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
