"""Community detection processor — Leiden algorithm.

Port of GitNexus ingestion/community-processor.ts.

Uses the Leiden algorithm (via leidenalg + igraph) to detect
communities/clusters in the code graph based on CALLS relationships.

Communities represent groups of code that work together frequently,
helping agents navigate the codebase by functional area.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from ..parsing.ast_helpers import generate_id
from .fan_in_processor import compute_fan_in
from .schema_extraction import extract_schema_entities

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import igraph as ig_type

try:
    import igraph as ig
    import leidenalg
except ImportError:
    ig = None
    leidenalg = None


@dataclass
class CommunityNode:
    id: str
    label: str
    heuristic_label: str
    cohesion: float
    symbol_count: int


@dataclass
class CommunityMembership:
    node_id: str
    community_id: str


@dataclass
class CommunityDetectionResult:
    communities: list[CommunityNode]
    memberships: list[CommunityMembership]
    stats: dict


COMMUNITY_COLORS = [
    "#ef4444",
    "#f97316",
    "#eab308",
    "#22c55e",
    "#06b6d4",
    "#3b82f6",
    "#8b5cf6",
    "#d946ef",
    "#ec4899",
    "#f43f5e",
    "#14b8a6",
    "#84cc16",
]

SYMBOL_TYPES = frozenset({"Function", "Class", "Method", "Interface"})
CLUSTERING_REL_TYPES = frozenset(
    {
        RelationshipType.CALLS,
        RelationshipType.EXTENDS,
        RelationshipType.IMPLEMENTS,
    }
)

MIN_CONFIDENCE_LARGE = 0.5


def process_communities(
    knowledge_graph: KnowledgeGraph,
    on_progress: callable = None,
) -> CommunityDetectionResult:
    """Detect communities in the knowledge graph using Leiden algorithm.

    Runs AFTER all relationships (CALLS, IMPORTS, etc.) have been built.
    """
    _ensure_leiden_dependencies()

    if on_progress:
        on_progress("Building graph for community detection...", 0)

    symbol_count = sum(
        1 for n in knowledge_graph.iter_nodes() if n.label in SYMBOL_TYPES
    )
    is_large = symbol_count > 10_000

    graph, node_ids, node_id_to_idx = _build_igraph(knowledge_graph, is_large)

    if graph.vcount() == 0:
        return CommunityDetectionResult(
            communities=[],
            memberships=[],
            stats={"total_communities": 0, "modularity": 0, "nodes_processed": 0},
        )

    if on_progress:
        on_progress(
            f"Running Leiden on {graph.vcount()} nodes, {graph.ecount()} edges"
            f"{' (filtered)' if is_large else ''}...",
            30,
        )

    # Adaptive resolution: finer partitions for smaller projects that
    # otherwise collapse into too few communities.
    file_count = sum(1 for n in knowledge_graph.iter_nodes() if n.label == "File")

    if symbol_count > 10_000:
        resolution = 3.0
    elif symbol_count > 1_000:
        resolution = 2.0
    elif symbol_count > 200:
        resolution = 1.5
    else:
        resolution = 1.0
    n_iterations = 3 if is_large else -1

    # Minimum community target — prevents 15 forms collapsing into 2 buckets
    min_communities = max(3, file_count // 5)

    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        n_iterations=n_iterations,
        resolution_parameter=resolution,
    )

    community_count = max(partition.membership) + 1 if partition.membership else 0

    # If we got fewer communities than the minimum, retry with higher resolution
    if community_count < min_communities and graph.vcount() >= min_communities:
        higher_res = resolution * 2.0
        logger.info(
            "Community count %d < min %d, retrying with resolution=%.1f",
            community_count,
            min_communities,
            higher_res,
        )
        partition = leidenalg.find_partition(
            graph,
            leidenalg.RBConfigurationVertexPartition,
            n_iterations=n_iterations,
            resolution_parameter=higher_res,
        )
        community_count = max(partition.membership) + 1 if partition.membership else 0

    membership_map: dict[str, int] = {}
    for idx, comm_id in enumerate(partition.membership):
        if idx < len(node_ids):
            membership_map[node_ids[idx]] = comm_id

    if on_progress:
        on_progress(f"Found {community_count} communities...", 60)

    community_nodes = _create_community_nodes(
        membership_map,
        community_count,
        knowledge_graph,
        graph,
        node_ids,
    )

    if on_progress:
        on_progress("Creating membership edges...", 80)

    memberships = [
        CommunityMembership(node_id=nid, community_id=f"comm_{comm}")
        for nid, comm in membership_map.items()
    ]

    if on_progress:
        on_progress("Community detection complete!", 100)

    return CommunityDetectionResult(
        communities=community_nodes,
        memberships=memberships,
        stats={
            "total_communities": len(community_nodes),
            "modularity": partition.modularity,
            "nodes_processed": graph.vcount(),
        },
    )


def run_community_detection_phase(
    knowledge_graph: KnowledgeGraph,
    on_progress: callable = None,
) -> dict:
    """Detect communities and mutate the graph with community artifacts.

    This wraps ``process_communities`` with the graph mutations that the
    pipeline phase needs: Community nodes, MEMBER_OF edges, and aggregate
    COMMUNITY_INTERACTS edges.
    """
    result = process_communities(knowledge_graph, on_progress=on_progress)

    before_community_nodes = sum(
        1 for node in knowledge_graph.iter_nodes() if node.label == NodeLabel.COMMUNITY
    )
    before_member_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.MEMBER_OF
    )
    before_interaction_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.COMMUNITY_INTERACTS
    )

    community_ids = {comm.id for comm in result.communities}
    for comm in result.communities:
        knowledge_graph.add_node(
            GraphNode(
                id=comm.id,
                label=NodeLabel.COMMUNITY,
                properties=NodeProperties(
                    name=comm.label,
                    heuristic_label=comm.heuristic_label,
                    cohesion=comm.cohesion,
                    symbol_count=comm.symbol_count,
                ),
            )
        )

    memberships = [
        membership
        for membership in result.memberships
        if membership.community_id in community_ids
    ]
    for membership in memberships:
        knowledge_graph.add_relationship(
            GraphRelationship(
                id=generate_id(
                    "MEMBER_OF",
                    f"{membership.node_id}->{membership.community_id}",
                ),
                source_id=membership.node_id,
                target_id=membership.community_id,
                type=RelationshipType.MEMBER_OF,
                confidence=1.0,
                reason="leiden",
            )
        )

    interaction_edge_count = _add_community_interaction_edges(
        knowledge_graph,
        memberships,
    )
    fan_in = compute_fan_in(knowledge_graph, memberships)
    schema_entity_count = extract_schema_entities(knowledge_graph)

    after_community_nodes = sum(
        1 for node in knowledge_graph.iter_nodes() if node.label == NodeLabel.COMMUNITY
    )
    after_member_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.MEMBER_OF
    )
    after_interaction_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.COMMUNITY_INTERACTS
    )

    return {
        "result": result,
        "communities": result.communities,
        "memberships": memberships,
        "stats": result.stats,
        "community_nodes_added": after_community_nodes - before_community_nodes,
        "member_edges_added": after_member_edges - before_member_edges,
        "interaction_edges_added": after_interaction_edges - before_interaction_edges,
        "interaction_edge_count": interaction_edge_count,
        "fan_in": fan_in,
        "schema_entity_count": schema_entity_count,
    }


def _ensure_leiden_dependencies() -> None:
    if ig is None or leidenalg is None:
        raise RuntimeError(
            "Community detection requires optional dependencies: "
            "install them with `uv add igraph leidenalg`."
        )


def _add_community_interaction_edges(
    knowledge_graph: KnowledgeGraph,
    memberships: list[CommunityMembership],
) -> int:
    node_to_community = {
        membership.node_id: membership.community_id for membership in memberships
    }
    interaction_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "imports": 0}
    )

    for rel in knowledge_graph.iter_relationships():
        src_comm = node_to_community.get(rel.source_id)
        tgt_comm = node_to_community.get(rel.target_id)
        if src_comm and tgt_comm and src_comm != tgt_comm:
            key = (src_comm, tgt_comm)
            if rel.type == RelationshipType.CALLS:
                interaction_counts[key]["calls"] += 1
            elif rel.type == RelationshipType.IMPORTS:
                interaction_counts[key]["imports"] += 1

    interaction_edge_count = 0
    for (src_comm, tgt_comm), counts in interaction_counts.items():
        total = counts["calls"] + counts["imports"]
        if total < 3:
            continue
        knowledge_graph.add_relationship(
            GraphRelationship(
                id=generate_id("COMMUNITY_INTERACTS", f"{src_comm}->{tgt_comm}"),
                source_id=src_comm,
                target_id=tgt_comm,
                type=RelationshipType.COMMUNITY_INTERACTS,
                confidence=float(total),
                reason=f"calls:{counts['calls']},imports:{counts['imports']}",
            )
        )
        interaction_edge_count += 1

    logger.info("Created %d COMMUNITY_INTERACTS edges", interaction_edge_count)
    return interaction_edge_count


def _build_igraph(
    knowledge_graph: KnowledgeGraph,
    is_large: bool,
) -> tuple["ig_type.Graph", list[str], dict[str, int]]:
    """Build an igraph Graph for Leiden from the knowledge graph."""
    connected_nodes: set[str] = set()
    node_degree: dict[str, int] = {}

    for rel in knowledge_graph.iter_relationships():
        if rel.type not in CLUSTERING_REL_TYPES or rel.source_id == rel.target_id:
            continue
        if is_large and rel.confidence < MIN_CONFIDENCE_LARGE:
            continue

        connected_nodes.add(rel.source_id)
        connected_nodes.add(rel.target_id)
        node_degree[rel.source_id] = node_degree.get(rel.source_id, 0) + 1
        node_degree[rel.target_id] = node_degree.get(rel.target_id, 0) + 1

    node_ids: list[str] = []
    node_id_to_idx: dict[str, int] = {}

    for node in knowledge_graph.iter_nodes():
        if node.label not in SYMBOL_TYPES or node.id not in connected_nodes:
            continue
        if is_large and node_degree.get(node.id, 0) < 2:
            continue

        node_id_to_idx[node.id] = len(node_ids)
        node_ids.append(node.id)

    graph = ig.Graph(n=len(node_ids), directed=False)

    edges: list[tuple[int, int]] = []
    seen_edges: set[tuple[int, int]] = set()

    for rel in knowledge_graph.iter_relationships():
        if rel.type not in CLUSTERING_REL_TYPES:
            continue
        if is_large and rel.confidence < MIN_CONFIDENCE_LARGE:
            continue

        src_idx = node_id_to_idx.get(rel.source_id)
        tgt_idx = node_id_to_idx.get(rel.target_id)
        if src_idx is None or tgt_idx is None or src_idx == tgt_idx:
            continue

        edge_key = (min(src_idx, tgt_idx), max(src_idx, tgt_idx))
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append(edge_key)

    graph.add_edges(edges)
    return graph, node_ids, node_id_to_idx


def _create_community_nodes(
    membership_map: dict[str, int],
    community_count: int,
    knowledge_graph: KnowledgeGraph,
    graph: "ig_type.Graph",
    node_ids: list[str],
) -> list[CommunityNode]:
    """Create Community nodes with auto-generated labels."""
    community_members: dict[int, list[str]] = {}
    for nid, comm in membership_map.items():
        community_members.setdefault(comm, []).append(nid)

    node_path_map: dict[str, str] = {}
    for node in knowledge_graph.iter_nodes():
        fp = node.properties.get("filePath")
        if fp:
            node_path_map[node.id] = fp

    node_name_map: dict[str, str] = {}
    for node in knowledge_graph.iter_nodes():
        name = node.properties.get("name")
        if name:
            node_name_map[node.id] = name

    community_nodes: list[CommunityNode] = []

    for comm_num, member_ids in community_members.items():
        if len(member_ids) < 2:
            continue

        label = _generate_heuristic_label(
            member_ids, node_path_map, node_name_map, comm_num
        )
        cohesion = _calculate_cohesion(member_ids, graph, node_ids, membership_map)

        community_nodes.append(
            CommunityNode(
                id=f"comm_{comm_num}",
                label=label,
                heuristic_label=label,
                cohesion=cohesion,
                symbol_count=len(member_ids),
            )
        )

    community_nodes.sort(key=lambda c: c.symbol_count, reverse=True)
    return community_nodes


def _generate_heuristic_label(
    member_ids: list[str],
    node_path_map: dict[str, str],
    node_name_map: dict[str, str],
    comm_num: int,
) -> str:
    """Generate a human-readable label from the most common folder name."""
    folder_counts: dict[str, int] = {}
    skip_folders = {"src", "lib", "core", "utils", "common", "shared", "helpers"}

    for nid in member_ids:
        fp = node_path_map.get(nid, "")
        parts = [p for p in fp.split("/") if p]
        if len(parts) >= 2:
            folder = parts[-2]
            if folder.lower() not in skip_folders:
                folder_counts[folder] = folder_counts.get(folder, 0) + 1

    if folder_counts:
        best_folder = max(folder_counts, key=folder_counts.get)
        return best_folder[0].upper() + best_folder[1:]

    names = [node_name_map.get(nid, "") for nid in member_ids if nid in node_name_map]
    if len(names) > 2:
        prefix = _find_common_prefix(names)
        if len(prefix) > 2:
            return prefix[0].upper() + prefix[1:]

    return f"Cluster_{comm_num}"


def _find_common_prefix(strings: list[str]) -> str:
    """Find common prefix among strings."""
    if not strings:
        return ""
    sorted_strings = sorted(strings)
    first, last = sorted_strings[0], sorted_strings[-1]
    i = 0
    while i < len(first) and i < len(last) and first[i] == last[i]:
        i += 1
    return first[:i]


def _calculate_cohesion(
    member_ids: list[str],
    graph: "ig_type.Graph",
    node_ids: list[str],
    membership_map: dict[str, int],
) -> float:
    """Estimate cohesion score (0-1) based on internal edge density."""
    if len(member_ids) <= 1:
        return 1.0

    member_set = set(member_ids)

    nid_to_idx: dict[str, int] = {}
    for idx, nid in enumerate(node_ids):
        nid_to_idx[nid] = idx

    sample = member_ids[:50]
    internal_edges = 0
    total_edges = 0

    for nid in sample:
        idx = nid_to_idx.get(nid)
        if idx is None or idx >= graph.vcount():
            continue
        for neighbor_idx in graph.neighbors(idx):
            total_edges += 1
            if neighbor_idx < len(node_ids) and node_ids[neighbor_idx] in member_set:
                internal_edges += 1

    if total_edges == 0:
        return 1.0
    return min(1.0, internal_edges / total_edges)
