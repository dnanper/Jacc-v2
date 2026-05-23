"""LadybugDB index phase wrapper.

This module mirrors the pipeline ``create_indexes`` phase so callers can make
the loaded graph searchable and register the repo with a single function call.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.storage.code_adapter import LadybugAdapter
from ..repository.git import get_current_commit
from ..repository.repo_manager import (
    RepoMeta,
    get_storage_path,
    register_repo,
    save_meta,
)


@dataclass
class IndexCreationResult:
    db_path: str
    meta_path: str
    registry_updated: bool
    graph_json_path: str | None
    stats: dict


def _json_safe(value: Any) -> Any:
    """Convert common graph/pipeline objects into JSON-safe values."""
    if isinstance(value, KnowledgeGraph):
        return {
            "nodes": [_json_safe(node) for node in value.iter_nodes()],
            "relationships": [
                _json_safe(rel) for rel in value.iter_relationships()
            ],
        }
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def serialize_pipeline_state(state: dict) -> dict:
    """Serialize the useful pipeline state for ``graph.json`` cache."""
    graph = state.get("knowledge_graph")
    result = {
        "repo_path": _json_safe(state.get("repo_path")),
        "repo_name": _json_safe(state.get("repo_name")),
        "file_paths": _json_safe(state.get("file_paths", [])),
        "stats": _json_safe(state.get("stats", {})),
    }
    if isinstance(graph, KnowledgeGraph):
        result["graph"] = _json_safe(graph)
    return result


def save_graph_json(repo_path: str | Path, results: dict) -> str:
    """Persist graph results beside LadybugDB for API/MCP consumers."""
    storage_path = get_storage_path(repo_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    graph_json_path = storage_path / "graph.json"
    tmp_path = graph_json_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(_json_safe(results), indent=2), encoding="utf-8")
    tmp_path.replace(graph_json_path)
    return str(graph_json_path)


def create_lbug_indexes(
    repo_path: str | Path,
    stats: dict | None = None,
    state: dict | None = None,
    save_graph_cache: bool = True,
) -> IndexCreationResult:
    """Create FTS indexes and register the LadybugDB-backed repo.

    The sequence intentionally matches ``pipeline.create_indexes``:
    connect to LadybugDB, create FTS indexes, write ``meta.json``, update the
    global repo registry, and optionally save a ``graph.json`` cache.
    """
    storage_path = get_storage_path(repo_path)
    db_path = str(storage_path / "lbug")

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    try:
        adapter.create_fts_indexes()
    finally:
        adapter.close()

    stats = stats or {}
    commit = get_current_commit(repo_path)
    meta = RepoMeta(
        repo_path=str(repo_path),
        last_commit=commit or "",
        indexed_at=datetime.now(timezone.utc).isoformat(),
        stats={
            "files": stats.get("files", 0),
            "nodes": stats.get("nodes", 0),
            "edges": stats.get("relationships", stats.get("edges", 0)),
            "communities": stats.get("communities", 0),
            "processes": stats.get("processes", 0),
            "embeddings": stats.get("embeddings", 0),
        },
    )
    save_meta(repo_path, meta)
    register_repo(repo_path, meta)

    graph_json_path: str | None = None
    if save_graph_cache and state is not None:
        graph_json_path = save_graph_json(repo_path, serialize_pipeline_state(state))

    return IndexCreationResult(
        db_path=db_path,
        meta_path=str(storage_path / "meta.json"),
        registry_updated=True,
        graph_json_path=graph_json_path,
        stats=meta.stats,
    )
