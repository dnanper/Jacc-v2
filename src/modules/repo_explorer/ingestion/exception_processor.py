"""Resolve extracted raise/catch/throws sites into RAISES / CATCHES / THROWS edges.

Edge direction: Function/Method/Constructor -> Class (exception type). Module-level
sites use the File as source. Names resolve with the same tiers as CALLS; a name
that resolves nowhere in the repo becomes an external stub (``Class:<Name>``, the id
heritage already uses for ValueError & co.) only when it looks like an exception
class, so ``raise err`` on a variable does not invent a node.

The site line and raise message go on the edge (``line``, ``detail``), so one
function raising the same class twice keeps both sites as evidence.
"""

from __future__ import annotations

import re

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import GraphNode, GraphRelationship, NodeLabel, NodeProperties, RelationshipType
from ..parsing.ast_helpers import generate_id
from .infile_processor import ExtractedException
from .support.resolution_context import TIER_CONFIDENCE, ResolutionContext

_KIND_TO_TYPE = {
    "raise": RelationshipType.RAISES,
    "catch": RelationshipType.CATCHES,
    "throws": RelationshipType.THROWS,
}
_TYPE_LABELS = {"Class", "Interface", "Record"}
# ponytail: name heuristic for unresolved (library/builtin) types; a real type
# resolver would decide this from the class hierarchy instead.
_EXCEPTION_NAME = re.compile(r"^[A-Z]\w*(Error|Exception|Warning|Exit|Interrupt|Throwable|Iteration)$")


def process_exceptions(
    graph: KnowledgeGraph, records: list[ExtractedException], ctx: ResolutionContext
) -> dict[str, int]:
    stats = {"resolved": 0, "external": 0, "unresolved": 0}
    for rec in records:
        target_id, confidence, reason = _resolve(rec.type_name, rec.file_path, ctx)
        if target_id is None:
            if not _EXCEPTION_NAME.match(rec.type_name):
                stats["unresolved"] += 1
                continue
            target_id, confidence, reason = generate_id("Class", rec.type_name), 1.0, "external"
            _ensure_external_class(graph, target_id, rec.type_name)
            stats["external"] += 1
        else:
            stats["resolved"] += 1
        if graph.get_node(rec.source_id) is None:
            stats["unresolved"] += 1
            continue
        rel_type = _KIND_TO_TYPE[rec.kind]
        graph.add_relationship(
            GraphRelationship(
                id=generate_id(rel_type.value, f"{rec.source_id}->{target_id}:L{rec.line}"),
                source_id=rec.source_id,
                target_id=target_id,
                type=rel_type,
                confidence=confidence,
                reason=reason,
                line=rec.line,
                detail=rec.message,
            )
        )
    return stats


def _resolve(name: str, file_path: str, ctx: ResolutionContext) -> tuple[str | None, float, str]:
    resolved = ctx.resolve(name, file_path)
    if resolved is None:
        return None, 0.0, ""
    types = [c for c in resolved.candidates if c.type in _TYPE_LABELS]
    if not types:
        return None, 0.0, ""
    confidence = TIER_CONFIDENCE.get(resolved.tier, 0.5)
    if len(types) == 1:
        return types[0].node_id, confidence, resolved.tier
    # Same-named classes in several files: keep the edge, mark it a guess (MAY).
    return types[0].node_id, max(confidence * 0.8, 0.3), f"{resolved.tier}-ambiguous"


def _ensure_external_class(graph: KnowledgeGraph, node_id: str, name: str) -> None:
    if graph.get_node(node_id) is not None:
        return
    graph.add_node(
        GraphNode(
            id=node_id,
            label=NodeLabel.CLASS,
            properties=NodeProperties(
                name=name, file_path="", is_exported=True, description="external exception class"
            ),
        )
    )
