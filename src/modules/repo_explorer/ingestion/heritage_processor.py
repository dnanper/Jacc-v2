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

import math
import re

from ..config import SupportedLanguages, get_language_from_filename
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import GraphRelationship, RelationshipType
from ..parsing.ast_helpers import generate_id
from .infile_processor import ExtractedHeritage
from .support.resolution_context import TIER_CONFIDENCE, ResolutionContext

_INTERFACE_NAME_RE = re.compile(r"^I[A-Z]")


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
    if resolved and resolved.candidates:
        is_interface = resolved.candidates[0].type == "Interface"
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
) -> tuple[str, float]:
    """Resolve a symbol ID for heritage, with fallback to generated ID.

    Returns (id, confidence).
    """
    resolved = ctx.resolve(name, file_path)
    if resolved and resolved.candidates:
        if resolved.tier == "global" and len(resolved.candidates) > 1:
            return (
                generate_id(fallback_label, fallback_key or name),
                TIER_CONFIDENCE["global"],
            )
        return resolved.candidates[0].node_id, TIER_CONFIDENCE[resolved.tier]

    return (
        generate_id(fallback_label, fallback_key or name),
        TIER_CONFIDENCE["global"],
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
            child_id, child_conf = _resolve_heritage_id(
                h.class_name,
                h.file_path,
                ctx,
                "Class",
                f"{h.file_path}:{h.class_name}",
            )
            parent_id, parent_conf = _resolve_heritage_id(
                h.parent_name,
                h.file_path,
                ctx,
                id_prefix,
            )

            if child_id and parent_id and child_id != parent_id:
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
            cls_id, cls_conf = _resolve_heritage_id(
                h.class_name,
                h.file_path,
                ctx,
                "Class",
                f"{h.file_path}:{h.class_name}",
            )
            iface_id, iface_conf = _resolve_heritage_id(
                h.parent_name,
                h.file_path,
                ctx,
                "Interface",
            )

            if cls_id and iface_id:
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

            if struct_id and trait_id:
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
