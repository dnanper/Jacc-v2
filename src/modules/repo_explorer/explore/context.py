"""Context mixin — symbol 360-degree view."""

from __future__ import annotations

import logging

from ._helpers import VALID_RELATION_TYPES

logger = logging.getLogger(__name__)

_REL_TYPES_LIST = list(VALID_RELATION_TYPES)


class ContextMixin:
    """Symbol context: callers, callees, processes, heritage."""

    @staticmethod
    def _compress_processes(raw_processes: list[dict]) -> list[dict] | dict:
        """Compress processes: flat list when <= 10, grouped summary when > 10."""
        flat = [
            {
                "name": p.get("label") or p.get("heuristicLabel"),
                "stepCount": p.get("stepCount"),
                "step": p.get("step"),
            }
            for p in raw_processes
        ]
        if len(flat) <= 10:
            return flat

        entry_points: list[str] = []
        endpoints: list[str] = []
        for p in flat:
            name = p.get("name") or ""
            if " \u2192 " in name:
                parts = name.split(" \u2192 ", 1)
                if parts[0] not in entry_points:
                    entry_points.append(parts[0])
                if parts[1] not in endpoints:
                    endpoints.append(parts[1])

        return {
            "summary": {
                "entryPoints": entry_points,
                "endpoints": endpoints,
                "totalCount": len(flat),
            },
            "sample": flat[:5],
        }

    def context(self, name: str) -> dict:
        """Get 360-degree context for a symbol."""
        symbols = self._adapter.match_by_name(name, limit=5)

        if not symbols:
            return {"error": f"Symbol '{name}' not found"}

        # Deduplicate by filePath so candidates represent distinct locations.
        seen_files: set[str] = set()
        unique_matches: list[dict] = []
        for s in symbols:
            fp = s.get("filePath", "")
            if fp not in seen_files:
                seen_files.add(fp)
                unique_matches.append(s)

        sym = symbols[0]
        sym_id = sym["id"]

        callers = self._query(
            "MATCH (caller)-[r:CodeRelation]->(n {id: $id}) "
            "WHERE r.type IN $relTypes "
            "RETURN r.type AS relType, caller.id AS uid, caller.name AS name, "
            "caller.filePath AS filePath, label(caller) AS kind, "
            "r.confidence AS confidence "
            "LIMIT 30",
            {"id": sym_id, "relTypes": _REL_TYPES_LIST},
        )
        for c in callers:
            c["confidence"] = c.get("confidence") or 0.5
            c["source"] = "INFERRED"

        callees = self._query(
            "MATCH (n {id: $id})-[r:CodeRelation]->(target) "
            "WHERE r.type IN $relTypes "
            "RETURN r.type AS relType, target.id AS uid, target.name AS name, "
            "target.filePath AS filePath, label(target) AS kind, "
            "r.confidence AS confidence "
            "LIMIT 30",
            {"id": sym_id, "relTypes": _REL_TYPES_LIST},
        )
        for c in callees:
            c["confidence"] = c.get("confidence") or 0.5
            c["source"] = "INFERRED"

        processes = self._query(
            "MATCH (n {id: $id})-[r:CodeRelation]->(p:Process) "
            "WHERE r.type = 'STEP_IN_PROCESS' "
            "RETURN p.id AS id, p.name AS label, p.heuristicLabel AS heuristicLabel, "
            "p.stepCount AS stepCount, r.reason AS step",
            {"id": sym_id},
        )

        return {
            "symbol": sym,
            "callers": callers,
            "callees": callees,
            "processes": processes,
            "_all_matches": unique_matches,
        }

    def context_360(self, symbol_name: str) -> dict:
        """Complete 360-degree view for a symbol.

        Combines context() (callers, callees, processes) with contract data
        (signature, heritage, overrides) into a single compressed response.
        Backs the ``csg_context`` MCP tool.

        When multiple symbols share the same name (e.g. ``constructor``,
        ``findByIdOrFail``), the response includes a ``candidates`` list so
        the caller can disambiguate and re-query with a more specific scope.
        """
        ctx = self.context(symbol_name)
        if "error" in ctx:
            return ctx

        contract = self._resolve_one_contract(symbol_name)
        impl = self._resolve_one_implementation(symbol_name)

        sym = ctx["symbol"]
        content = impl.get("content") if impl and "error" not in impl else None

        result = {
            "symbol": {
                "name": sym.get("name"),
                "type": sym.get("type"),
                "filePath": sym.get("filePath"),
                "startLine": sym.get("startLine"),
                "endLine": sym.get("endLine"),
            },
            "content": content,
            "signature": contract.get("signature"),
            "returnType": contract.get("returnType"),
            "parameterCount": contract.get("parameterCount"),
            "callers": [
                {
                    "name": c["name"],
                    "file": c.get("filePath"),
                    "kind": c.get("kind"),
                    "rel": c.get("relType"),
                }
                for c in ctx.get("callers", [])[:10]
            ],
            "callees": [
                {
                    "name": c["name"],
                    "file": c.get("filePath"),
                    "kind": c.get("kind"),
                    "rel": c.get("relType"),
                }
                for c in ctx.get("callees", [])[:10]
            ],
            "processes": self._compress_processes(ctx.get("processes", [])),
            "heritage": contract.get("heritage") or None,
            "overrides": contract.get("overrides") or None,
        }

        # Disambiguation: when multiple symbols share the same name,
        # list the alternatives so the caller can narrow by file scope.
        all_matches = ctx.get("_all_matches", [])
        if len(all_matches) > 1:
            result["candidates"] = [
                {
                    "name": m.get("name"),
                    "type": m.get("type"),
                    "filePath": m.get("filePath"),
                }
                for m in all_matches
            ]
            result["_disambiguation"] = (
                f"Found {len(all_matches)} symbols named '{symbol_name}'. "
                "Showing the first match. Use csg_explore with "
                "scope='file:<path>' to target a specific one."
            )

        return result
