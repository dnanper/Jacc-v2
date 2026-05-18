from typing import Iterator

from graph.model.types import GraphNode, GraphRelationship


class KnowledgeGraph:
    """In-memory knowledge graph backed by two dicts.

    - Nodes keyed by ``node.id`` (deterministic: ``"Label:filePath:name"``)
    - Relationships keyed by ``rel.id``
    - ``add_node`` / ``add_relationship`` are idempotent (skip if id exists)
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._relationships: dict[str, GraphRelationship] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def relationship_count(self) -> int:
        return len(self._relationships)

    def iter_nodes(self) -> Iterator[GraphNode]:
        return iter(self._nodes.values())

    def iter_relationships(self) -> Iterator[GraphRelationship]:
        return iter(self._relationships.values())

    @property
    def nodes(self) -> list[GraphNode]:
        """Full list copy — prefer ``iter_nodes()`` for iteration."""
        return list(self._nodes.values())

    @property
    def relationships(self) -> list[GraphRelationship]:
        """Full list copy — prefer ``iter_relationships()`` for iteration."""
        return list(self._relationships.values())

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_relationship(self, rel_id: str) -> GraphRelationship | None:
        return self._relationships.get(rel_id)

    def add_node(self, node: GraphNode) -> None:
        if node.id not in self._nodes:
            self._nodes[node.id] = node

    def add_relationship(self, rel: GraphRelationship) -> None:
        if rel.id not in self._relationships:
            self._relationships[rel.id] = rel

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all relationships involving it."""
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        to_remove = [
            rid
            for rid, rel in self._relationships.items()
            if rel.source_id == node_id or rel.target_id == node_id
        ]
        for rid in to_remove:
            del self._relationships[rid]
        return True

    def remove_nodes_by_file(self, file_path: str) -> int:
        """Remove all nodes belonging to a file and their relationships."""
        to_remove = [
            nid
            for nid, node in self._nodes.items()
            if node.properties.file_path == file_path
        ]
        for nid in to_remove:
            self.remove_node(nid)
        return len(to_remove)

    def clear(self) -> None:
        """Remove all nodes and relationships."""
        self._nodes.clear()
        self._relationships.clear()
