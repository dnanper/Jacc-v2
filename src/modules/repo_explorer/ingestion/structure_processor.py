"""Create File and Folder nodes with CONTAINS relationships.

Port of GitNexus ingestion/structure-processor.ts.
Walks each file path, creating parent folders and linking them.
"""

from __future__ import annotations

import os

from ..discovery.content_filter import is_binary_path
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from .utils import generate_id


def process_structure(
    graph: KnowledgeGraph, paths: list[str], repo_path: str = ""
) -> None:
    """Create File/Folder nodes and CONTAINS edges for every path.

    Args:
        graph: The knowledge graph to populate.
        paths: List of relative file paths.
        repo_path: Absolute path to the repository root (used to count lines).
    """
    seen_folders: set[str] = set()

    for file_path in paths:
        parts = file_path.replace("\\", "/").split("/")

        # Count lines via fast binary newline count (skip binary files)
        line_count = 0
        is_binary = False
        if repo_path:
            full = os.path.join(repo_path, file_path)
            is_binary = is_binary_path(full)
            if not is_binary:
                try:
                    with open(full, "rb") as f:
                        line_count = f.read().count(b"\n")
                except (OSError, IOError):
                    pass

        file_id = generate_id("File", file_path)
        graph.add_node(
            GraphNode(
                id=file_id,
                label=NodeLabel.FILE,
                properties=NodeProperties(
                    name=parts[-1],
                    file_path=file_path,
                    _extra={"lineCount": line_count, "binary": is_binary},
                ),
            )
        )

        parent_id: str | None = None
        for depth in range(len(parts) - 1):
            folder_path = "/".join(parts[: depth + 1])
            folder_id = generate_id("Folder", folder_path)

            if folder_path not in seen_folders:
                seen_folders.add(folder_path)
                graph.add_node(
                    GraphNode(
                        id=folder_id,
                        label=NodeLabel.FOLDER,
                        properties=NodeProperties(
                            name=parts[depth],
                            file_path=folder_path,
                        ),
                    )
                )

            if parent_id is not None:
                graph.add_relationship(
                    GraphRelationship(
                        id=f"{parent_id}_contains_{folder_id}",
                        source_id=parent_id,
                        target_id=folder_id,
                        type=RelationshipType.CONTAINS,
                    )
                )

            parent_id = folder_id

        if parent_id is not None:
            graph.add_relationship(
                GraphRelationship(
                    id=f"{parent_id}_contains_{file_id}",
                    source_id=parent_id,
                    target_id=file_id,
                    type=RelationshipType.CONTAINS,
                )
            )
