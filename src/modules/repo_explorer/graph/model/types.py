from dataclasses import dataclass

from .lables import NodeLabel
from .properties import NodeProperties
from .relationships import RelationshipType


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    id: str
    label: NodeLabel
    properties: NodeProperties


@dataclass
class GraphRelationship:
    """A relationship (edge) in the knowledge graph."""

    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    confidence: float = 1.0
    reason: str = ""
    step: int | None = None
    in_cycle: bool | None = None


@dataclass
class PipelineProgress:
    """Progress update from the analysis pipeline."""

    phase: str
    percent: int
    message: str
    detail: str | None = None
    stats: dict | None = None


@dataclass
class PipelineResult:
    """Result of a completed analysis pipeline run."""

    node_count: int
    relationship_count: int
    file_count: int
    community_count: int
    process_count: int
    duration_ms: int
    embedding_count: int = 0
