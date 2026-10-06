"""Heritage processor — EXTENDS / IMPLEMENTS edges.

Port of GitNexus ingestion/heritage-processor.ts.

Resolves class inheritance relationships:
- EXTENDS: class extends another class
- IMPLEMENTS: class implements an interface / trait

For languages like C# / Java where the tree-sitter query can't distinguish
classes from interfaces, we check the symbol table first; if unresolved,
we fall back to language-specific heuristics (I[A-Z] naming convention for
C#/Java, protocol-first for Swift).
"""

from __future__ import annotations

import logging
import math
import re

from ..config import SupportedLanguages, get_language_from_filename
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from ..parsing.ast_helpers import generate_id
from .infile_processor import ExtractedHeritage
from .support.resolution_context import TIER_CONFIDENCE, ResolutionContext

logger = logging.getLogger(__name__)
_INTERFACE_NAME_RE = re.compile(r"^I[A-Z]")
_TYPE_LABELS = frozenset({"Class", "Interface", "Struct", "Trait", "Record", "Enum"})


def _resolve_extends_type(
    parent_name: str,
    file_path: str,
    ctx: ResolutionContext,
    language: SupportedLanguages,
) -> tuple[str, str]:
    """Determine whether an 'extends' is actually IMPLEMENTS.

    Returns (rel_type, id_prefix) — e.g. ("EXTENDS", "Class") or
    ("IMPLEMENTS", "Interface").
    """
    resolved = ctx.resolve(parent_name, file_path)
    types = [c for c in resolved.candidates if c.type in _TYPE_LABELS] if resolved else []
    if types:
        is_interface = types[0].type == "Interface"
        if is_interface:
            return "IMPLEMENTS", "Interface"
        return "EXTENDS", "Class"

    if language in (SupportedLanguages.C_SHARP, SupportedLanguages.JAVA):
        if _INTERFACE_NAME_RE.match(parent_name):
            return "IMPLEMENTS", "Interface"
    elif language == SupportedLanguages.SWIFT:
        return "IMPLEMENTS", "Interface"

    return "EXTENDS", "Class"


def _resolve_heritage_id(
    name: str,
    file_path: str,
    ctx: ResolutionContext,
    fallback_label: str,
    fallback_key: str | None = None,
    types_only: bool = False,
) -> tuple[str, float]:
    """Resolve a symbol ID for heritage, with fallback to generated ID.

    Returns (id, confidence). With `types_only` (a base class/interface), a name that resolves only to
    non-type symbols (a function call base, a module, an assignment) returns ("", 0.0): the edge is
    dropped rather than linked to the wrong kind of node or to an invented stub.
    """
    resolved = ctx.resolve(name, file_path)
    candidates = list(resolved.candidates) if resolved else []
    if types_only and candidates:
        candidates = [c for c in candidates if c.type in _TYPE_LABELS]
        if not candidates:
            logger.debug("Heritage parent %s in %s resolves only to non-type symbols", name, file_path)
            return "", 0.0
    if candidates:
        if resolved.tier == "global" and len(candidates) > 1:
            return (
                generate_id(fallback_label, fallback_key or name),
                TIER_CONFIDENCE["global"],
            )
        return candidates[0].node_id, TIER_CONFIDENCE[resolved.tier]

    return (
        generate_id(fallback_label, fallback_key or name),
        TIER_CONFIDENCE["global"],
    )


def _declared_source_id(graph: KnowledgeGraph, name: str, file_path: str) -> tuple[str, float]:
    """A heritage source is the declaration in this file, not an import/assignment sharing its name.
    Never create a placeholder child or select an ambiguous declaration."""
    ids = [generate_id(label, f"{file_path}:{name}") for label in sorted(_TYPE_LABELS)]
    present = [node_id for node_id in ids if graph.get_node(node_id) is not None]
    if len(present) == 1:
        return present[0], 1.0
    logger.debug("Unresolved/ambiguous heritage source %s in %s", name, file_path)
    return "", 0.0


def _ensure_external_parent_node(
    graph: KnowledgeGraph,
    node_id: str,
    name: str,
    label: str,
) -> None:
    """Create a stub node for an unresolved external heritage parent."""
    if graph.get_node(node_id) is not None:
        return

    graph.add_node(
        GraphNode(
            id=node_id,
            label=NodeLabel(label),
            properties=NodeProperties(
                name=name,
                file_path="",
                is_exported=True,
                description="external heritage parent",
            ),
        )
    )


def process_heritage(
    graph: KnowledgeGraph,
    heritage_records: list[ExtractedHeritage],
    ctx: ResolutionContext,
    on_progress: callable = None,
) -> None:
    """Resolve heritage records and create EXTENDS / IMPLEMENTS edges.

    Args:
        graph: Knowledge graph to add edges to.
        heritage_records: Extracted heritage from parsing.
        ctx: Resolution context with symbol table populated.
        on_progress: Optional ``(current, total)`` callback.
    """
    total = len(heritage_records)

    for idx, h in enumerate(heritage_records):
        if on_progress and idx % 200 == 0:
            on_progress(idx, total)

        language = get_language_from_filename(h.file_path)
        if not language:
            continue

        if h.kind == "extends":
            rel_type, id_prefix = _resolve_extends_type(
                h.parent_name, h.file_path, ctx, language
            )
            child_id, child_conf = _declared_source_id(graph, h.class_name, h.file_path)
            parent_id, parent_conf = _resolve_heritage_id(
                h.parent_name,
                h.file_path,
                ctx,
                id_prefix,
                types_only=True,
            )

            if parent_id:
                _ensure_external_parent_node(graph, parent_id, h.parent_name, id_prefix)

            if (
                child_id
                and parent_id
                and child_id != parent_id
                and graph.get_node(child_id) is not None
                and graph.get_node(parent_id) is not None
            ):
                graph.add_relationship(
                    GraphRelationship(
                        id=generate_id(rel_type, f"{child_id}->{parent_id}"),
                        source_id=child_id,
                        target_id=parent_id,
                        type=RelationshipType(rel_type),
                        confidence=math.sqrt(child_conf * parent_conf),
                        reason="",
                    )
                )

        elif h.kind == "implements":
            cls_id, cls_conf = _declared_source_id(graph, h.class_name, h.file_path)
            iface_id, iface_conf = _resolve_heritage_id(
                h.parent_name,
                h.file_path,
                ctx,
                "Interface",
                types_only=True,
            )

            if iface_id:
                _ensure_external_parent_node(
                    graph, iface_id, h.parent_name, "Interface"
                )

            if (
                cls_id
                and iface_id
                and graph.get_node(cls_id) is not None
                and graph.get_node(iface_id) is not None
            ):
                graph.add_relationship(
                    GraphRelationship(
                        id=generate_id("IMPLEMENTS", f"{cls_id}->{iface_id}"),
                        source_id=cls_id,
                        target_id=iface_id,
                        type=RelationshipType.IMPLEMENTS,
                        confidence=math.sqrt(cls_conf * iface_conf),
                        reason="",
                    )
                )

        elif h.kind in ("trait-impl", "include", "extend", "prepend"):
            struct_id, struct_conf = _resolve_heritage_id(
                h.class_name,
                h.file_path,
                ctx,
                "Struct",
                f"{h.file_path}:{h.class_name}",
            )
            trait_id, trait_conf = _resolve_heritage_id(
                h.parent_name,
                h.file_path,
                ctx,
                "Trait",
            )

            if trait_id:
                _ensure_external_parent_node(graph, trait_id, h.parent_name, "Trait")

            if (
                struct_id
                and trait_id
                and graph.get_node(struct_id) is not None
                and graph.get_node(trait_id) is not None
            ):
                graph.add_relationship(
                    GraphRelationship(
                        id=generate_id(
                            "IMPLEMENTS", f"{struct_id}->{trait_id}:{h.kind}"
                        ),
                        source_id=struct_id,
                        target_id=trait_id,
                        type=RelationshipType.IMPLEMENTS,
                        confidence=math.sqrt(struct_conf * trait_conf),
                        reason=h.kind,
                    )
                )

    if on_progress:
        on_progress(total, total)
