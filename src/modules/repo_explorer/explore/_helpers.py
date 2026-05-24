"""Response compression and token-budget helpers (agent-optimised output)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..graph.model.types import RelationshipType

CYPHER_WRITE_RE = re.compile(
    r"\b(CREATE|DELETE|SET|MERGE|REMOVE|DROP|ALTER|COPY|DETACH)\b", re.I
)

_META_RELATIONS = {"MEMBER_OF", "STEP_IN_PROCESS", "COMMUNITY_INTERACTS"}
VALID_RELATION_TYPES = {r.value for r in RelationshipType} - _META_RELATIONS


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def _estimate_tokens(data: Any) -> int:
    """Rough token estimate for a data structure (~4 chars per token)."""
    return len(json.dumps(data, default=str)) // 4


@dataclass
class _ResponseAccumulator:
    """Track token budget and accumulate compressed sections."""

    max_tokens: int = 4000
    sections: dict[str, Any] = field(default_factory=dict)
    _estimated_tokens: int = 0
    _depth_reached: str = ""
    _search_stats: dict[str, Any] = field(default_factory=dict)

    def can_add(self, estimated_tokens: int) -> bool:
        return self._estimated_tokens + estimated_tokens < self.max_tokens

    def add(self, key: str, data: Any) -> None:
        tokens = _estimate_tokens(data)
        self.sections[key] = data
        self._estimated_tokens += tokens
        self._depth_reached = key

    def set_search_stats(self, stats: dict[str, Any]) -> None:
        self._search_stats = stats

    def finalize(self) -> dict:
        result: dict[str, Any] = {}
        for key, data in self.sections.items():
            if isinstance(data, dict):
                result[key] = data
            else:
                result[key] = data
        meta: dict[str, Any] = {
            "tokens_used": self._estimated_tokens,
            "depth_reached": self._depth_reached,
        }
        if self._search_stats:
            meta["search"] = self._search_stats
        result["_meta"] = meta
        return result


# ---------------------------------------------------------------------------
# Layer compression
# ---------------------------------------------------------------------------


def _compress_topology(data: dict) -> dict:
    """Compress topology layer to essentials."""
    communities = data.get("communities", [])[:10]
    compressed_comms = []
    for c in communities:
        entry: dict[str, Any] = {
            "name": c.get("label") or c.get("name"),
            "symbolCount": c.get("symbolCount"),
            "cohesion": c.get("cohesion"),
        }
        top_members = c.get("topMembers")
        if top_members:
            entry["topMembers"] = top_members
        compressed_comms.append(entry)
    # Deduplicate by name (defense-in-depth)
    seen: dict[str, dict] = {}
    for c in compressed_comms:
        key = c.get("name") or ""
        if key in seen:
            existing = seen[key]
            old_count = existing.get("symbolCount") or 0
            new_count = c.get("symbolCount") or 0
            total = old_count + new_count
            if total > 0:
                old_coh = existing.get("cohesion") or 0
                new_coh = c.get("cohesion") or 0
                existing["cohesion"] = round(
                    (old_coh * old_count + new_coh * new_count) / total, 4
                )
            existing["symbolCount"] = total
            # Merge topMembers
            for m in c.get("topMembers", []):
                members = existing.setdefault("topMembers", [])
                if m not in members and len(members) < 5:
                    members.append(m)
        else:
            seen[key] = c
    compressed_comms = sorted(
        seen.values(), key=lambda x: x.get("symbolCount") or 0, reverse=True
    )
    interactions = data.get("cross_community_edges", [])[:15]
    compressed_interactions = [
        {
            "source": e.get("source"),
            "target": e.get("target"),
            "weight": e.get("weight"),
        }
        for e in interactions
    ]
    return {
        "communities": compressed_comms,
        "interactions": compressed_interactions,
        "confidence": data.get("confidence"),
        "signal": data.get("signal"),
    }


def _compress_relevance(data: dict) -> dict:
    """Compress relevance layer: top communities with top hits."""
    communities = data.get("communities", [])[:5]
    compressed_comms = []
    for c in communities:
        hits = c.get("hits", [])[:3]
        compressed_hits = [
            {
                "name": h.get("name"),
                "label": h.get("label"),
                "filePath": h.get("filePath"),
            }
            for h in hits
        ]
        compressed_comms.append(
            {
                "name": c.get("name"),
                "score": c.get("score"),
                "hitCount": c.get("hitCount"),
                "hits": compressed_hits,
            }
        )
    return {
        "query": data.get("query"),
        "communities": compressed_comms,
        "is_crosscutting": data.get("is_crosscutting", False),
        "confidence": data.get("confidence"),
        "signal": data.get("signal"),
    }


def _compress_context(data: dict) -> dict:
    """Compress context layer: processes + key symbols."""
    processes = data.get("processes", [])[:3]
    compressed_procs = []
    for proc in processes:
        steps = proc.get("steps", [])[:8]
        compressed_steps = [
            {
                "name": s.get("name"),
                "type": s.get("type"),
                "filePath": s.get("filePath"),
            }
            for s in steps
        ]
        compressed_procs.append(
            {
                "name": proc.get("name"),
                "processType": proc.get("type"),
                "stepCount": proc.get("stepCount"),
                "avgConfidence": proc.get("avgConfidence"),
                "steps": compressed_steps,
            }
        )

    symbols = data.get("symbols", [])
    sorted_syms = sorted(symbols, key=lambda s: s.get("fanIn") or 0, reverse=True)[:15]
    compressed_syms = [
        {
            "name": s.get("name"),
            "type": s.get("type"),
            "filePath": s.get("filePath"),
            "isExported": s.get("isExported"),
            "fanIn": s.get("fanIn"),
        }
        for s in sorted_syms
    ]

    return {
        "processes": compressed_procs,
        "symbols": compressed_syms,
        "confidence": data.get("confidence"),
        "signal": data.get("signal"),
    }


def _compress_contracts(data: dict) -> dict:
    """Compress contract layer: signatures + key callers/callees."""
    symbols = data.get("symbols", [])
    compressed = []
    for sym in symbols:
        if "error" in sym:
            continue
        entry: dict[str, Any] = {
            "name": sym.get("name"),
            "type": sym.get("type"),
            "filePath": sym.get("filePath"),
            "signature": sym.get("signature"),
            "returnType": sym.get("returnType"),
            "parameterCount": sym.get("parameterCount"),
            "callers": [
                {"name": c.get("name"), "filePath": c.get("filePath")}
                for c in sym.get("callers", [])[:5]
            ],
            "callees": [
                {"name": c.get("name"), "filePath": c.get("filePath")}
                for c in sym.get("callees", [])[:5]
            ],
        }
        heritage = sym.get("heritage")
        if heritage:
            entry["heritage"] = heritage
        overrides = sym.get("overrides")
        if overrides:
            entry["overrides"] = overrides
        compressed.append(entry)
    return {"symbols": compressed}


def _compress_implementation(data: dict, max_chars: int = 500) -> dict:
    """Compress implementation layer: truncated source code for key symbols."""
    symbols = data.get("symbols", [])
    compressed = []
    for sym in symbols:
        if "error" in sym or not sym.get("content"):
            continue
        content = sym["content"]
        if len(content) > max_chars:
            # Truncate at word boundary
            cut = content[:max_chars].rfind("\n")
            if cut < max_chars // 2:
                cut = max_chars
            content = content[:cut] + "\n..."
        compressed.append(
            {
                "name": sym.get("name"),
                "type": sym.get("type"),
                "filePath": sym.get("filePath"),
                "startLine": sym.get("startLine"),
                "endLine": sym.get("endLine"),
                "content": content,
            }
        )
    return {"symbols": compressed}


def _compress_crosscut(data: dict) -> dict:
    """Compress crosscut layer: cycles, shared symbols, duplicates."""
    cycles = data.get("cycles", [])
    compressed_cycles = [
        {"members": c.get("members", []), "weakestEdge": c.get("weakestEdge")}
        for c in cycles
    ]
    shared = data.get("shared_symbols", [])[:10]
    compressed_shared = [
        {"name": s.get("name"), "filePath": s.get("filePath"), "fanIn": s.get("fanIn")}
        for s in shared
    ]
    duplicates = data.get("duplicates", [])
    return {
        "cycles": compressed_cycles,
        "shared_symbols": compressed_shared,
        "duplicates": duplicates,
    }


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_envelope(data: dict) -> dict:
    """Pull confidence envelope fields from a layer result."""
    return {
        "confidence": data.get("confidence", 0),
        "confidence_gap": data.get("confidence_gap", 0),
        "signal": data.get("signal", "weak"),
        "recommendation": data.get("recommendation", ""),
    }


def _extract_key_symbols(
    ctx_data: dict,
    max_count: int = 5,
    prefer_names: list[str] | None = None,
) -> list[str]:
    """Get top symbol names, preferring query-relevant hits over fanIn."""
    symbols = ctx_data.get("symbols", [])
    prefer_set = set(prefer_names) if prefer_names else set()

    def _sort_key(s: dict) -> tuple[int, int]:
        # Preferred symbols first (1 sorts before 0 in reverse), then by fanIn
        is_preferred = 1 if s.get("name") in prefer_set else 0
        return (is_preferred, s.get("fanIn") or 0)

    sorted_syms = sorted(symbols, key=_sort_key, reverse=True)
    return [s["name"] for s in sorted_syms[:max_count] if s.get("name")]


def _extract_key_symbols_from_acc(
    acc: _ResponseAccumulator,
    max_count: int = 5,
    prefer_names: list[str] | None = None,
) -> list[str]:
    """Aggregate top symbols from all context sections, preferring query hits."""
    all_symbols: list[dict] = []
    for key, section in acc.sections.items():
        if key.startswith("context") and isinstance(section, dict):
            all_symbols.extend(section.get("symbols", []))
    prefer_set = set(prefer_names) if prefer_names else set()

    def _sort_key(s: dict) -> tuple[int, int]:
        is_preferred = 1 if s.get("name") in prefer_set else 0
        return (is_preferred, s.get("fanIn") or 0)

    sorted_syms = sorted(all_symbols, key=_sort_key, reverse=True)
    return [s["name"] for s in sorted_syms[:max_count] if s.get("name")]


def _extract_top_hits(rel_data: dict, max_count: int = 5) -> list[str]:
    """Get top symbol names from relevance hits."""
    names: list[str] = []
    for comm in rel_data.get("communities", []):
        for hit in comm.get("hits", []):
            name = hit.get("name")
            if name and name not in names:
                names.append(name)
            if len(names) >= max_count:
                return names
    return names
