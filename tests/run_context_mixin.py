"""Show what repo_explorer.explore.context.ContextMixin returns.

This runner uses a fake adapter so it can exercise context.py without a real
LadybugDB database.
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_MODULES = ROOT / "src" / "modules"
if str(SRC_MODULES) not in sys.path:
    sys.path.insert(0, str(SRC_MODULES))

from repo_explorer.explore._helpers import VALID_RELATION_TYPES
from repo_explorer.explore import Backend
from repo_explorer.explore.context import ContextMixin
from repo_explorer.explore.explore import ExploreMixin
from repo_explorer.graph.storage.code_adapter import LadybugAdapter
from repo_explorer.repository.repo_manager import get_storage_path


BUILD_ID = "Method:app/main.py:Service.build"


class FakeAdapter:
    """Minimal adapter surface used by ContextMixin and ExploreMixin."""

    def match_by_name(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        matches = {
            "build": [
                {
                    "id": BUILD_ID,
                    "name": "build",
                    "type": "Method",
                    "filePath": "app/main.py",
                    "startLine": 7,
                    "endLine": 12,
                },
                {
                    "id": "Method:workers/job.py:Worker.build",
                    "name": "build",
                    "type": "Method",
                    "filePath": "workers/job.py",
                    "startLine": 20,
                    "endLine": 30,
                },
            ],
            "Repository": [
                {
                    "id": "Class:models/user.py:Repository",
                    "name": "Repository",
                    "type": "Class",
                    "filePath": "models/user.py",
                    "startLine": 13,
                    "endLine": 18,
                }
            ],
        }.get(name, [])
        return matches[:limit]

    def execute_query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        params = params or {}
        node_id = params.get("id")

        if "MATCH (caller)-[r:CodeRelation]->(n {id: $id})" in cypher:
            if "r.type = 'CALLS'" in cypher:
                return [
                    {
                        "name": "main",
                        "filePath": "cli.py",
                        "type": "Function",
                        "confidence": 0.91,
                    }
                ]
            return [
                {
                    "relType": "CALLS",
                    "uid": "Function:cli.py:main",
                    "name": "main",
                    "filePath": "cli.py",
                    "kind": "Function",
                    "confidence": 0.91,
                }
            ]

        if "MATCH (n {id: $id})-[r:CodeRelation]->(target)" in cypher:
            return [
                {
                    "relType": "CALLS",
                    "uid": "Method:models/user.py:Repository.load",
                    "name": "load",
                    "filePath": "models/user.py",
                    "kind": "Method",
                    "confidence": 0.88,
                },
                {
                    "relType": "CALLS",
                    "uid": "Method:models/user.py:Repository.save",
                    "name": "save",
                    "filePath": "models/user.py",
                    "kind": "Method",
                    "confidence": None,
                },
            ]

        if "MATCH (n {id: $id})-[r:CodeRelation]->(p:Process)" in cypher:
            return [
                {
                    "id": "proc_0_build",
                    "label": "Build -> Hydrate_user",
                    "heuristicLabel": "Build flow",
                    "stepCount": 3,
                    "step": "step-1",
                }
            ]

        if "RETURN n.parameterCount AS parameterCount" in cypher:
            return [
                {
                    "parameterCount": 1,
                    "returnType": "User",
                    "signature": "build(self) -> User",
                }
            ]

        if "MATCH (n {id: $id})-[r:CodeRelation]->(callee)" in cypher:
            return [
                {
                    "name": "load",
                    "filePath": "models/user.py",
                    "type": "Method",
                    "confidence": 0.88,
                }
            ]

        if "WHERE r.type IN ['EXTENDS', 'IMPLEMENTS']" in cypher:
            return []

        if "WHERE r.type = 'OVERRIDES'" in cypher:
            return []

        if "RETURN n.content AS content" in cypher:
            return [
                {
                    "content": (
                        "def build(self):\n"
                        "    repo = Repository()\n"
                        "    user = repo.load()\n"
                        "    return repo.save(user)\n"
                    ),
                    "startLine": 7,
                    "endLine": 12,
                    "filePath": "app/main.py",
                }
            ]

        raise AssertionError(f"Unexpected query for {node_id}:\n{cypher}")


class DemoBackend(ContextMixin, ExploreMixin):
    def __init__(self) -> None:
        self._adapter = FakeAdapter()

    def _query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return self._adapter.execute_query(cypher, params)


def dump(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, indent=2, ensure_ascii=True, default=str))


def build_real_backend(repo_path: str | None, db_path: str | None) -> tuple[Backend, Path]:
    if db_path:
        resolved_db_path = Path(db_path).resolve()
        repo_source_path = repo_path
    elif repo_path:
        resolved_repo_path = Path(repo_path).resolve()
        resolved_db_path = get_storage_path(resolved_repo_path) / "lbug"
        repo_source_path = str(resolved_repo_path)
    else:
        raise ValueError("--real needs --repo-path or --db-path")

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


def run_demo(backend: Any, symbol: str) -> None:
    dump("VALID_RELATION_TYPES used for caller/callee filtering", sorted(VALID_RELATION_TYPES))
    dump(f"context({symbol!r})", backend.context(symbol))
    dump(f"context_360({symbol!r})", backend.context_360(symbol))
    dump("context('missing')", backend.context("missing"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show what repo_explorer.explore.context.ContextMixin returns."
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use a real LadybugDB created by tests/run_ingestion_pipeline.py --persist.",
    )
    parser.add_argument(
        "--repo-path",
        help="Repo path that was ingested. Used to resolve data/repos/<repo>-<hash>/lbug.",
    )
    parser.add_argument(
        "--db-path",
        help="Direct path to the lbug directory printed by run_ingestion_pipeline.py --persist.",
    )
    parser.add_argument(
        "--symbol",
        default="build",
        help="Symbol name to inspect.",
    )
    args = parser.parse_args()

    if args.real:
        backend, db_path = build_real_backend(args.repo_path, args.db_path)
        print(f"using real LadybugDB: {db_path}")
        try:
            run_demo(backend, args.symbol)
        finally:
            backend._adapter.close()
        return

    run_demo(DemoBackend(), args.symbol)


if __name__ == "__main__":
    main()
