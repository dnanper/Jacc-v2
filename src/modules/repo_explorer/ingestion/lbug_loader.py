"""LadybugDB load phase wrapper.

This module mirrors the pipeline ``load_to_lbug`` phase so callers can load
the in-memory knowledge graph with a single function call.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.storage.code_adapter import LadybugAdapter
from ..repository.repo_manager import get_storage_path


@dataclass
class LbugLoadResult:
    db_path: str
    csv_dir: str
    cached_embeddings: list[dict]
    stats: dict


def load_graph_to_lbug(
    graph: KnowledgeGraph,
    repo_path: str | Path,
    file_paths: list[str] | None = None,
    community_nodes: list | None = None,
    process_nodes: list | None = None,
    force: bool = False,
) -> LbugLoadResult:
    """Load a knowledge graph into LadybugDB.

    The sequence intentionally matches ``pipeline.load_to_lbug``:
    connect, optionally read cached embeddings, clear DB, create schema,
    bulk-load graph via CSV, create FTS indexes, then remove CSV scratch files.
    """
    storage_path = get_storage_path(repo_path)
    db_path = str(storage_path / "lbug")
    csv_dir = str(storage_path / "csv_tmp")

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    cached_embeddings: list[dict] = []
    if not force:
        cached_embeddings = adapter.load_cached_embeddings()

    try:
        adapter.clear_database()
        adapter.create_schema()
        load_stats = adapter.load_graph(graph, csv_dir)
        adapter.create_fts_indexes()
    finally:
        adapter.close()
        shutil.rmtree(csv_dir, ignore_errors=True)

    return LbugLoadResult(
        db_path=db_path,
        csv_dir=csv_dir,
        cached_embeddings=cached_embeddings,
        stats={
            "nodes": load_stats["node_count"],
            "relationships": load_stats["relationship_count"],
            "files": len(file_paths or []),
            "communities": len(community_nodes or []),
            "processes": len(process_nodes or []),
            "failed_tables": load_stats.get("failed_tables", []),
        },
    )
