"""Call resolution — 4-pass call target resolution with confidence scoring.

Port of GitNexus ingestion/call-processor.ts.

Resolution tiers (highest confidence first):
1. same-file   — exact match in the same file (confidence 0.95)
2. import-scoped — found via import chain (confidence 0.9)
3. type-inferred — via receiver type + field lookup (confidence 0.7)
4. global      — fuzzy match across repo (confidence 0.5)
"""

from __future__ import annotations

import logging
import re

from ..config import BUILT_IN_NAMES
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import GraphRelationship, RelationshipType
from ..parsing.ast_helpers import generate_id
from .infile_processor import ExtractedCall
from .resolution_context import (
    TIER_CONFIDENCE,
    ResolutionContext,
)
from .symbol_table import SymbolDefinition

logger = logging.getLogger(__name__)

CALLABLE_SYMBOL_TYPES = frozenset(
    {
        "Function",
        "Method",
        "Constructor",
        "Macro",
        "Delegate",
    }
)

CONSTRUCTOR_TARGET_TYPES = frozenset({"Constructor", "Class", "Struct", "Record"})


def _is_builtin_or_noise(name: str) -> bool:
    """Filter out built-in / noise names that shouldn't become CALLS edges."""
    if not name or len(name) <= 1:
        return True
    if name in BUILT_IN_NAMES:
        return True
    if re.match(r"^[A-Z_]+$", name):
        return True
    return False


def _filter_callable_candidates(
    candidates: list[SymbolDefinition],
    arg_count: int | None = None,
    call_form: str | None = None,
) -> list[SymbolDefinition]:
    """Filter candidates to callable symbol types, optionally by arity."""
    if call_form == "constructor":
        constructors = [c for c in candidates if c.type == "Constructor"]
        if constructors:
            kind_filtered = constructors
        else:
            types = [c for c in candidates if c.type in CONSTRUCTOR_TARGET_TYPES]
            kind_filtered = (
                types
                if types
                else [c for c in candidates if c.type in CALLABLE_SYMBOL_TYPES]
            )
    else:
        kind_filtered = [c for c in candidates if c.type in CALLABLE_SYMBOL_TYPES]

    if not kind_filtered:
        return []
    if arg_count is None:
        return kind_filtered

    has_param_metadata = any(c.parameter_count is not None for c in kind_filtered)
    if not has_param_metadata:
        return kind_filtered

    return [
        c
        for c in kind_filtered
        if c.parameter_count is None or arg_count <= c.parameter_count
    ]


class _ResolveResult:
    __slots__ = ("node_id", "confidence", "reason")

    def __init__(self, node_id: str, confidence: float, reason: str) -> None:
        self.node_id = node_id
        self.confidence = confidence
        self.reason = reason


def _resolve_call_target(
    called_name: str,
    arg_count: int | None,
    call_form: str | None,
    receiver_type_name: str | None,
    file_path: str,
    ctx: ResolutionContext,
) -> _ResolveResult | None:
    """Resolve a call to a target symbol using tiered resolution."""

    if call_form == "member" and receiver_type_name:
        field_defs = ctx.symbols.lookup_field_by_owner(receiver_type_name, called_name)
        if field_defs:
            filtered = _filter_callable_candidates(field_defs, arg_count, call_form)
            if len(filtered) == 1:
                return _ResolveResult(filtered[0].node_id, 0.9, "member-resolved")

    resolved = ctx.resolve(called_name, file_path)
    if resolved is None:
        return None

    filtered = _filter_callable_candidates(resolved.candidates, arg_count, call_form)
    if not filtered:
        return None

    if len(filtered) == 1:
        return _ResolveResult(
            filtered[0].node_id,
            TIER_CONFIDENCE[resolved.tier],
            resolved.tier,
        )

    if receiver_type_name and call_form == "member":
        by_owner = [
            d
            for d in filtered
            if d.owner_id and _owner_matches(d.owner_id, receiver_type_name, ctx)
        ]
        if len(by_owner) == 1:
            return _ResolveResult(
                by_owner[0].node_id,
                TIER_CONFIDENCE[resolved.tier],
                f"{resolved.tier}+owner",
            )

    return _ResolveResult(
        filtered[0].node_id,
        max(TIER_CONFIDENCE.get(resolved.tier, 0.5) * 0.8, 0.3),
        f"{resolved.tier}-ambiguous",
    )


def _owner_matches(owner_id: str, type_name: str, ctx: ResolutionContext) -> bool:
    """Check if an owner node ID corresponds to the given type name."""
    return type_name.lower() in owner_id.lower()


def process_calls(
    graph: KnowledgeGraph,
    calls: list[ExtractedCall],
    ctx: ResolutionContext,
    on_progress: callable = None,
    type_envs: dict | None = None,
) -> None:
    """Resolve calls and create CALLS edges.

    Args:
        graph: Knowledge graph to add CALLS edges to.
        calls: Extracted call records from parsing.
        ctx: Resolution context (must have symbols and import maps populated).
        on_progress: Optional ``(current, total)`` callback.
        type_envs: Per-file TypeEnv for receiver type resolution.
    """
    if type_envs:
        for call in calls:
            if call.receiver_name and not call.receiver_type_name:
                type_env = type_envs.get(call.file_path)
                if type_env:
                    try:
                        resolved = type_env.lookup(call.receiver_name)
                        if resolved:
                            call.receiver_type_name = resolved
                    except Exception as exc:
                        logger.debug(
                            "Type lookup failed for %s: %s", call.receiver_name, exc
                        )

    total = len(calls)
    resolved_count = 0

    for idx, call in enumerate(calls):
        if on_progress and idx % 200 == 0:
            on_progress(idx, total)

        called_name = call.called_name
        if _is_builtin_or_noise(called_name):
            continue

        source_id = (
            call.source_id if call.source_id else generate_id("File", call.file_path)
        )

        result = _resolve_call_target(
            called_name=called_name,
            arg_count=call.arg_count,
            call_form=call.call_form,
            receiver_type_name=call.receiver_type_name,
            file_path=call.file_path,
            ctx=ctx,
        )

        if result is None:
            continue

        resolved_count += 1
        rel_id = generate_id("CALLS", f"{source_id}:{called_name}->{result.node_id}")

        graph.add_relationship(
            GraphRelationship(
                id=rel_id,
                source_id=source_id,
                target_id=result.node_id,
                type=RelationshipType.CALLS,
                confidence=result.confidence,
                reason=result.reason,
            )
        )

    if on_progress:
        on_progress(total, total)
