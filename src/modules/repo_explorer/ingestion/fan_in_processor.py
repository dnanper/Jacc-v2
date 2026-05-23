"""Fan-in and fan-out computation — Phase 8.5.

Computes how many files/symbols import or call each target node (fan-in)
and how many targets each source node reaches (fan-out).
Stores ``fan_in`` and ``fan_out`` on ``NodeProperties`` so that
the retrieval layer can find shared utilities (high fan-in) and
infrastructure sinks like logging/audit (high fan-out, low fan-in).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import RelationshipType

if TYPE_CHECKING:
    from .community_processor import CommunityMembership

logger = logging.getLogger(__name__)

_COUNTED_EDGE_TYPES = frozenset({RelationshipType.IMPORTS, RelationshipType.CALLS})


def compute_fan_in(
    graph: KnowledgeGraph,
    memberships: list["CommunityMembership"] | None = None,
) -> dict[str, int]:
    """Compute fan-in and fan-out for IMPORTS and CALLS edges.

    - ``fan_in``  = number of distinct sources that point at a target.
    - ``fan_out`` = number of distinct targets that a source points to.

    Both are stored on ``NodeProperties``.

    Returns
    -------
    dict[str, int]
        Mapping of ``node_id -> fan_in`` for nodes that received at
        least one incoming IMPORTS or CALLS edge.
    """
    fan_in_counts: dict[str, set[str]] = defaultdict(set)
    fan_out_counts: dict[str, set[str]] = defaultdict(set)

    for rel in graph.iter_relationships():
        if rel.type in _COUNTED_EDGE_TYPES:
            fan_in_counts[rel.target_id].add(rel.source_id)
            fan_out_counts[rel.source_id].add(rel.target_id)

    node_to_community: dict[str, str] = {}
    if memberships:
        for m in memberships:
            node_to_community[m.node_id] = m.community_id

    cross_community_fan_in: dict[str, int] = {}

    # Store fan-in
    result: dict[str, int] = {}
    for target_id, sources in fan_in_counts.items():
        count = len(sources)
        result[target_id] = count

        node = graph.get_node(target_id)
        if node is not None:
            node.properties.fan_in = count

        if node_to_community:
            communities = {
                node_to_community[src] for src in sources if src in node_to_community
            }
            if len(communities) > 1:
                cross_community_fan_in[target_id] = len(communities)

    # Store fan-out
    for source_id, targets in fan_out_counts.items():
        node = graph.get_node(source_id)
        if node is not None:
            node.properties.fan_out = len(targets)

    total_in = len(result)
    high_fan_in = sum(1 for v in result.values() if v >= 5)
    total_out = len(fan_out_counts)
    high_fan_out = sum(1 for ts in fan_out_counts.values() if len(ts) >= 5)
    logger.info(
        "Fan-in: %d nodes, %d with >= 5 | Fan-out: %d nodes, %d with >= 5",
        total_in,
        high_fan_in,
        total_out,
        high_fan_out,
    )

    return result
