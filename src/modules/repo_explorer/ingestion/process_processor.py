"""Process detection processor — execution flow discovery.

Port of GitNexus ingestion/process-processor.ts.

Detects execution flows (Processes) in the code graph by:
1. Finding entry points (functions with few callers, many callees)
2. Tracing forward via CALLS edges (BFS)
3. Deduplicating similar traces
4. Creating process nodes with heuristic labels
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import SupportedLanguages
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from ..parsing.ast_helpers import generate_id
from .community_processor import CommunityMembership
from .entry_point_scoring import (
    calculate_entry_point_score,
    is_test_file,
)


@dataclass
class ProcessDetectionConfig:
    max_trace_depth: int = 10
    max_branching: int = 4
    max_processes: int = 75
    min_steps: int = 3


@dataclass
class ProcessNode:
    id: str
    label: str
    heuristic_label: str
    process_type: str
    step_count: int
    communities: list[str]
    entry_point_id: str
    terminal_id: str
    trace: list[str]


@dataclass
class ProcessStep:
    node_id: str
    process_id: str
    step: int


@dataclass
class ProcessDetectionResult:
    processes: list[ProcessNode]
    steps: list[ProcessStep]
    stats: dict


MIN_TRACE_CONFIDENCE = 0.5


def process_processes(
    knowledge_graph: KnowledgeGraph,
    memberships: list[CommunityMembership],
    on_progress: callable = None,
    config: ProcessDetectionConfig | None = None,
) -> ProcessDetectionResult:
    """Detect processes (execution flows) in the knowledge graph.

    Runs AFTER community detection, using CALLS edges to trace flows.
    """
    cfg = config or ProcessDetectionConfig()

    if on_progress:
        on_progress("Finding entry points...", 0)

    membership_map: dict[str, str] = {m.node_id: m.community_id for m in memberships}

    calls_edges = _build_calls_graph(knowledge_graph)
    reverse_calls = _build_reverse_calls_graph(knowledge_graph)
    node_map: dict[str, dict] = {}
    for node in knowledge_graph.iter_nodes():
        node_map[node.id] = {
            "name": node.properties.get("name", ""),
            "label": node.label,
            "file_path": node.properties.get("filePath", ""),
            "is_exported": node.properties.get("isExported", False),
            "language": node.properties.get("language", SupportedLanguages.JAVASCRIPT),
        }

    entry_points = _find_entry_points(
        knowledge_graph,
        reverse_calls,
        calls_edges,
        node_map,
    )

    if on_progress:
        on_progress(f"Found {len(entry_points)} entry points, tracing flows...", 20)

    all_traces: list[list[str]] = []

    for i, entry_id in enumerate(entry_points):
        if len(all_traces) >= cfg.max_processes * 2:
            break

        traces = _trace_from_entry_point(entry_id, calls_edges, cfg)
        for t in traces:
            if len(t) >= cfg.min_steps:
                all_traces.append(t)

    if on_progress:
        on_progress(f"Found {len(all_traces)} traces, deduplicating...", 60)

    unique_traces = _deduplicate_traces(all_traces)
    endpoint_deduped = _deduplicate_by_endpoints(unique_traces)

    limited_traces = sorted(endpoint_deduped, key=len, reverse=True)[
        : cfg.max_processes
    ]

    if on_progress:
        on_progress(f"Creating {len(limited_traces)} process nodes...", 80)

    processes: list[ProcessNode] = []
    steps: list[ProcessStep] = []

    for idx, trace in enumerate(limited_traces):
        entry_point_id = trace[0]
        terminal_id = trace[-1]

        communities = list(
            {membership_map[nid] for nid in trace if nid in membership_map}
        )

        process_type = "cross_community" if len(communities) > 1 else "intra_community"

        entry_name = node_map.get(entry_point_id, {}).get("name", "Unknown")
        terminal_name = node_map.get(terminal_id, {}).get("name", "Unknown")
        heuristic_label = f"{_capitalize(entry_name)} -> {_capitalize(terminal_name)}"

        process_id = f"proc_{idx}_{_sanitize_id(entry_name)}"

        processes.append(
            ProcessNode(
                id=process_id,
                label=heuristic_label,
                heuristic_label=heuristic_label,
                process_type=process_type,
                step_count=len(trace),
                communities=communities,
                entry_point_id=entry_point_id,
                terminal_id=terminal_id,
                trace=trace,
            )
        )

        for step_idx, node_id in enumerate(trace):
            steps.append(
                ProcessStep(
                    node_id=node_id,
                    process_id=process_id,
                    step=step_idx + 1,
                )
            )

    if on_progress:
        on_progress("Process detection complete!", 100)

    cross_community_count = sum(
        1 for p in processes if p.process_type == "cross_community"
    )
    avg_step_count = (
        sum(p.step_count for p in processes) / len(processes) if processes else 0
    )

    return ProcessDetectionResult(
        processes=processes,
        steps=steps,
        stats={
            "total_processes": len(processes),
            "cross_community_count": cross_community_count,
            "avg_step_count": round(avg_step_count, 1),
            "entry_points_found": len(entry_points),
        },
    )


def run_process_detection_phase(
    knowledge_graph: KnowledgeGraph,
    memberships: list[CommunityMembership],
    on_progress: callable = None,
    config: ProcessDetectionConfig | None = None,
) -> dict:
    """Detect execution processes and mutate graph with process artifacts."""
    result = process_processes(
        knowledge_graph=knowledge_graph,
        memberships=memberships,
        on_progress=on_progress,
        config=config,
    )

    before_process_nodes = sum(
        1 for node in knowledge_graph.iter_nodes() if node.label == NodeLabel.PROCESS
    )
    before_step_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.STEP_IN_PROCESS
    )

    for proc in result.processes:
        knowledge_graph.add_node(
            GraphNode(
                id=proc.id,
                label=NodeLabel.PROCESS,
                properties=NodeProperties(
                    name=proc.label,
                    heuristic_label=proc.heuristic_label,
                    process_type=proc.process_type,
                    step_count=proc.step_count,
                    communities=proc.communities,
                    entry_point_id=proc.entry_point_id,
                    terminal_id=proc.terminal_id,
                ),
            )
        )

    for step in result.steps:
        knowledge_graph.add_relationship(
            GraphRelationship(
                id=generate_id(
                    "STEP_IN_PROCESS",
                    f"{step.node_id}->{step.process_id}:{step.step}",
                ),
                source_id=step.node_id,
                target_id=step.process_id,
                type=RelationshipType.STEP_IN_PROCESS,
                confidence=1.0,
                reason=f"step-{step.step}",
            )
        )

    after_process_nodes = sum(
        1 for node in knowledge_graph.iter_nodes() if node.label == NodeLabel.PROCESS
    )
    after_step_edges = sum(
        1
        for rel in knowledge_graph.iter_relationships()
        if rel.type == RelationshipType.STEP_IN_PROCESS
    )

    return {
        "result": result,
        "processes": result.processes,
        "steps": result.steps,
        "stats": result.stats,
        "process_nodes_added": after_process_nodes - before_process_nodes,
        "step_edges_added": after_step_edges - before_step_edges,
    }


def _build_calls_graph(graph: KnowledgeGraph) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for rel in graph.iter_relationships():
        if (
            rel.type == RelationshipType.CALLS
            and rel.confidence >= MIN_TRACE_CONFIDENCE
        ):
            adj.setdefault(rel.source_id, []).append(rel.target_id)
    return adj


def _build_reverse_calls_graph(graph: KnowledgeGraph) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for rel in graph.iter_relationships():
        if (
            rel.type == RelationshipType.CALLS
            and rel.confidence >= MIN_TRACE_CONFIDENCE
        ):
            adj.setdefault(rel.target_id, []).append(rel.source_id)
    return adj


def _find_entry_points(
    graph: KnowledgeGraph,
    reverse_calls: dict[str, list[str]],
    calls_edges: dict[str, list[str]],
    node_map: dict[str, dict],
) -> list[str]:
    """Find functions that are good entry points for tracing."""
    symbol_types = frozenset({"Function", "Method"})
    candidates: list[tuple[str, float]] = []

    for node in graph.iter_nodes():
        if node.label not in symbol_types:
            continue

        info = node_map.get(node.id, {})
        file_path = info.get("file_path", "")

        if is_test_file(file_path):
            continue

        callers = reverse_calls.get(node.id, [])
        callees = calls_edges.get(node.id, [])

        if not callees:
            continue

        result = calculate_entry_point_score(
            name=info.get("name", ""),
            language=info.get("language", SupportedLanguages.JAVASCRIPT),
            is_exported=info.get("is_exported", False),
            caller_count=len(callers),
            callee_count=len(callees),
            file_path=file_path,
        )

        if result.score > 0:
            candidates.append((node.id, result.score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [c[0] for c in candidates[:200]]


def _trace_from_entry_point(
    entry_id: str,
    calls_edges: dict[str, list[str]],
    config: ProcessDetectionConfig,
) -> list[list[str]]:
    """Trace forward from an entry point using BFS."""
    traces: list[list[str]] = []
    queue: list[tuple[str, list[str]]] = [(entry_id, [entry_id])]

    while queue and len(traces) < config.max_branching * 3:
        current_id, path = queue.pop(0)
        callees = calls_edges.get(current_id, [])

        if not callees:
            if len(path) >= config.min_steps:
                traces.append(list(path))
        elif len(path) >= config.max_trace_depth:
            if len(path) >= config.min_steps:
                traces.append(list(path))
        else:
            limited = callees[: config.max_branching]
            added_branch = False

            for callee_id in limited:
                if callee_id not in path:
                    queue.append((callee_id, path + [callee_id]))
                    added_branch = True

            if not added_branch and len(path) >= config.min_steps:
                traces.append(list(path))

    return traces


def _deduplicate_traces(traces: list[list[str]]) -> list[list[str]]:
    """Remove traces that are subsets of other traces."""
    if not traces:
        return []

    sorted_traces = sorted(traces, key=len, reverse=True)
    unique: list[list[str]] = []

    for trace in sorted_traces:
        trace_key = "->".join(trace)
        is_subset = any(trace_key in "->".join(existing) for existing in unique)
        if not is_subset:
            unique.append(trace)

    return unique


def _deduplicate_by_endpoints(traces: list[list[str]]) -> list[list[str]]:
    """Keep only the longest trace per unique entry→terminal pair."""
    if not traces:
        return []

    by_endpoints: dict[str, list[str]] = {}
    sorted_traces = sorted(traces, key=len, reverse=True)

    for trace in sorted_traces:
        key = f"{trace[0]}::{trace[-1]}"
        if key not in by_endpoints:
            by_endpoints[key] = trace

    return list(by_endpoints.values())


def _capitalize(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def _sanitize_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", s)[:20].lower()
