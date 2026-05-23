"""MRO (Method Resolution Order) processor.

Port of GitNexus ingestion/mro-processor.ts.

Walks the inheritance DAG (EXTENDS/IMPLEMENTS edges), collects methods from
each ancestor via HAS_METHOD edges, detects method-name collisions across
parents, and applies language-specific resolution rules to emit OVERRIDES edges.

Language-specific rules:
- C++:       leftmost base class in declaration order wins
- C#/Java:   class method wins over interface default; multiple interface
             methods with same name are ambiguous (null resolution)
- Python:    C3 linearization determines MRO; first in linearized order wins
- Rust:      no auto-resolution — requires qualified syntax, resolvedTo = None
- Default:   single inheritance — first definition wins

OVERRIDES edge direction: Class → Method (child class → winning ancestor method).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import SupportedLanguages
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import GraphRelationship, RelationshipType
from ..parsing.ast_helpers import generate_id


@dataclass
class MethodAmbiguity:
    method_name: str
    defined_in: list[dict]
    resolved_to: str | None
    reason: str


@dataclass
class MROEntry:
    class_id: str
    class_name: str
    language: SupportedLanguages
    mro_order: list[str]
    ambiguities: list[MethodAmbiguity]


@dataclass
class MROResult:
    entries: list[MROEntry]
    override_edges: int
    ambiguity_count: int


def _build_adjacency(graph: KnowledgeGraph):
    """Collect EXTENDS, IMPLEMENTS, and HAS_METHOD adjacency from the graph."""
    parent_map: dict[str, list[str]] = {}
    method_map: dict[str, list[str]] = {}
    parent_edge_type: dict[str, dict[str, str]] = {}

    for rel in graph.iter_relationships():
        if rel.type in (RelationshipType.EXTENDS, RelationshipType.IMPLEMENTS):
            parent_map.setdefault(rel.source_id, []).append(rel.target_id)
            parent_edge_type.setdefault(rel.source_id, {})[rel.target_id] = rel.type
        elif rel.type == RelationshipType.HAS_METHOD:
            method_map.setdefault(rel.source_id, []).append(rel.target_id)

    return parent_map, method_map, parent_edge_type


def _gather_ancestors(class_id: str, parent_map: dict[str, list[str]]) -> list[str]:
    """Gather all ancestor IDs in BFS / topological order."""
    visited: set[str] = set()
    order: list[str] = []
    queue = list(parent_map.get(class_id, []))

    while queue:
        cid = queue.pop(0)
        if cid in visited:
            continue
        visited.add(cid)
        order.append(cid)
        for gp in parent_map.get(cid, []):
            if gp not in visited:
                queue.append(gp)

    return order


def _c3_linearize(
    class_id: str,
    parent_map: dict[str, list[str]],
    cache: dict[str, list[str] | None],
    in_progress: set[str] | None = None,
) -> list[str] | None:
    """Compute C3 linearization for a class.

    Returns list of ancestor IDs in C3 order (excluding the class itself),
    or None if linearization fails (inconsistent or cyclic hierarchy).
    """
    if class_id in cache:
        return cache[class_id]

    visiting = in_progress if in_progress is not None else set()
    if class_id in visiting:
        cache[class_id] = None
        return None
    visiting.add(class_id)

    direct_parents = parent_map.get(class_id, [])
    if not direct_parents:
        visiting.discard(class_id)
        cache[class_id] = []
        return []

    parent_linearizations: list[list[str]] = []
    for pid in direct_parents:
        p_lin = _c3_linearize(pid, parent_map, cache, visiting)
        if p_lin is None:
            visiting.discard(class_id)
            cache[class_id] = None
            return None
        parent_linearizations.append([pid] + list(p_lin))

    sequences = [list(s) for s in parent_linearizations] + [list(direct_parents)]
    result: list[str] = []

    while any(s for s in sequences):
        head: str | None = None
        for seq in sequences:
            if not seq:
                continue
            candidate = seq[0]
            in_tail = any(
                candidate in other[1:] for other in sequences if len(other) > 1
            )
            if not in_tail:
                head = candidate
                break

        if head is None:
            visiting.discard(class_id)
            cache[class_id] = None
            return None

        result.append(head)
        for seq in sequences:
            if seq and seq[0] == head:
                seq.pop(0)

    visiting.discard(class_id)
    cache[class_id] = result
    return result


def _resolve_by_mro_order(
    method_name: str,
    defs: list[dict],
    mro_order: list[str],
    reason_prefix: str,
) -> tuple[str | None, str, float]:
    """Resolve by MRO order — first ancestor in linearized order wins.

    Returns (resolved_method_id, reason, confidence).
    """
    for ancestor_id in mro_order:
        match = next((d for d in defs if d["class_id"] == ancestor_id), None)
        if match:
            return (
                match["method_id"],
                f"{reason_prefix}: {match['class_name']}::{method_name}",
                0.9,
            )
    return (
        defs[0]["method_id"],
        f"{reason_prefix} fallback: first definition",
        0.7,
    )


def _resolve_csharp_java(
    method_name: str,
    defs: list[dict],
    edge_types: dict[str, str] | None,
) -> tuple[str | None, str, float]:
    """C#/Java: class method wins over interface default."""
    class_defs = []
    interface_defs = []

    for d in defs:
        et = edge_types.get(d["class_id"]) if edge_types else None
        if et == RelationshipType.IMPLEMENTS:
            interface_defs.append(d)
        else:
            class_defs.append(d)

    if class_defs:
        return (
            class_defs[0]["method_id"],
            f"class method wins: {class_defs[0]['class_name']}::{method_name}",
            0.95,
        )

    if len(interface_defs) > 1:
        names = ", ".join(d["class_name"] for d in interface_defs)
        return None, f"ambiguous: {method_name} in multiple interfaces: {names}", 0.5

    if len(interface_defs) == 1:
        return (
            interface_defs[0]["method_id"],
            f"single interface default: {interface_defs[0]['class_name']}::{method_name}",
            0.85,
        )

    return None, "no resolution found", 0.5


def _build_transitive_edge_types(
    class_id: str,
    parent_map: dict[str, list[str]],
    parent_edge_type: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Build transitive edge types for C#/Java/Kotlin conflict resolution."""
    result: dict[str, str] = {}
    direct_edges = parent_edge_type.get(class_id, {})
    if not direct_edges:
        return result

    queue: list[tuple[str, str]] = []
    for pid in parent_map.get(class_id, []):
        et = direct_edges.get(pid, "EXTENDS")
        if pid not in result:
            result[pid] = et
            queue.append((pid, et))

    while queue:
        cid, edge_type = queue.pop(0)
        for gp in parent_map.get(cid, []):
            if gp not in result:
                result[gp] = edge_type
                queue.append((gp, edge_type))

    return result


def compute_mro(graph: KnowledgeGraph) -> MROResult:
    """Compute Method Resolution Order and emit OVERRIDES edges."""
    parent_map, method_map, parent_edge_type = _build_adjacency(graph)
    c3_cache: dict[str, list[str] | None] = {}

    entries: list[MROEntry] = []
    override_edges = 0
    ambiguity_count = 0

    for class_id, direct_parents in parent_map.items():
        if not direct_parents:
            continue

        class_node = graph.get_node(class_id)
        if not class_node:
            continue

        language = class_node.properties.get("language")
        if not language:
            continue
        class_name = class_node.properties.get("name", "")

        if language == SupportedLanguages.PYTHON:
            c3_result = _c3_linearize(class_id, parent_map, c3_cache)
            mro_order = (
                c3_result
                if c3_result is not None
                else _gather_ancestors(class_id, parent_map)
            )
        else:
            mro_order = _gather_ancestors(class_id, parent_map)

        mro_names = []
        for aid in mro_order:
            n = graph.get_node(aid)
            if n and n.properties.get("name"):
                mro_names.append(n.properties.get("name"))

        methods_by_name: dict[str, list[dict]] = {}
        for ancestor_id in mro_order:
            ancestor_node = graph.get_node(ancestor_id)
            if not ancestor_node:
                continue

            for method_id in method_map.get(ancestor_id, []):
                method_node = graph.get_node(method_id)
                if not method_node:
                    continue
                if method_node.label == "Property":
                    continue

                method_name = method_node.properties.get("name", "")
                defs = methods_by_name.setdefault(method_name, [])
                if not any(d["method_id"] == method_id for d in defs):
                    defs.append(
                        {
                            "class_id": ancestor_id,
                            "class_name": ancestor_node.properties.get("name", ""),
                            "method_id": method_id,
                        }
                    )

        ambiguities: list[MethodAmbiguity] = []

        needs_edge_types = language in (
            SupportedLanguages.C_SHARP,
            SupportedLanguages.JAVA,
            SupportedLanguages.KOTLIN,
        )
        class_edge_types = (
            _build_transitive_edge_types(class_id, parent_map, parent_edge_type)
            if needs_edge_types
            else None
        )

        for method_name, defs in methods_by_name.items():
            if len(defs) < 2:
                continue

            own_methods = method_map.get(class_id, [])
            own_defines_it = any(
                graph.get_node(mid)
                and graph.get_node(mid).properties.get("name") == method_name
                for mid in own_methods
            )
            if own_defines_it:
                continue

            if language == SupportedLanguages.C_PLUS_PLUS:
                resolved_to, reason, confidence = _resolve_by_mro_order(
                    method_name, defs, mro_order, "C++ leftmost base"
                )
            elif language in (
                SupportedLanguages.C_SHARP,
                SupportedLanguages.JAVA,
                SupportedLanguages.KOTLIN,
            ):
                resolved_to, reason, confidence = _resolve_csharp_java(
                    method_name, defs, class_edge_types
                )
            elif language == SupportedLanguages.PYTHON:
                resolved_to, reason, confidence = _resolve_by_mro_order(
                    method_name, defs, mro_order, "Python C3 MRO"
                )
            elif language == SupportedLanguages.RUST:
                resolved_to = None
                reason = (
                    f"Rust requires qualified syntax: <Type as Trait>::{method_name}()"
                )
                confidence = 0.5
            else:
                resolved_to, reason, confidence = _resolve_by_mro_order(
                    method_name, defs, mro_order, "first definition"
                )

            ambiguities.append(
                MethodAmbiguity(
                    method_name=method_name,
                    defined_in=defs,
                    resolved_to=resolved_to,
                    reason=reason,
                )
            )

            if resolved_to is None:
                ambiguity_count += 1
            else:
                graph.add_relationship(
                    GraphRelationship(
                        id=generate_id("OVERRIDES", f"{class_id}->{resolved_to}"),
                        source_id=class_id,
                        target_id=resolved_to,
                        type=RelationshipType.OVERRIDES,
                        confidence=confidence,
                        reason=reason,
                    )
                )
                override_edges += 1

        entries.append(
            MROEntry(
                class_id=class_id,
                class_name=class_name,
                language=language,
                mro_order=mro_names,
                ambiguities=ambiguities,
            )
        )

    return MROResult(
        entries=entries,
        override_edges=override_edges,
        ambiguity_count=ambiguity_count,
    )
