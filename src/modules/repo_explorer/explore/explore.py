"""Explore mixin — 6-layer retrieval (topology through implementation)."""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..graph.schema.code_schema import escape_table_name
from ._helpers import (
    _compress_context,
    _compress_contracts,
    _compress_crosscut,
    _compress_implementation,
    _compress_relevance,
    _compress_topology,
    _extract_envelope,
    _extract_key_symbols,
    _extract_key_symbols_from_acc,
    _extract_top_hits,
    _ResponseAccumulator,
)
from ._search.bm25_search import search_fts_symbols

logger = logging.getLogger(__name__)


class ExploreMixin:
    """Six-layer retrieval: topology, relevance, context, crosscut, contract, implementation."""

    # ------------------------------------------------------------------
    # Layer 0 — Topology
    # ------------------------------------------------------------------

    def topology(self) -> dict:
        """Layer 0 -- Static project map: communities, cross-community edges, folder tree."""
        try:
            communities = self._query(
                "MATCH (c:Community) "
                "RETURN c.id AS id, c.name AS name, c.heuristicLabel AS label, "
                "c.symbolCount AS symbolCount, c.cohesion AS cohesion "
                "ORDER BY c.symbolCount DESC"
            )
        except Exception:
            communities = []

        try:
            interactions = self._query(
                "MATCH (c1:Community)-[r:CodeRelation]->(c2:Community) "
                "WHERE r.type = 'COMMUNITY_INTERACTS' "
                "RETURN c1.heuristicLabel AS source, c2.heuristicLabel AS target, "
                "r.confidence AS weight, r.reason AS detail"
            )
        except Exception:
            interactions = []

        try:
            folders = self._query(
                "MATCH (f:Folder)-[r:CodeRelation]->(child:File) "
                "WHERE r.type = 'CONTAINS' "
                "RETURN f.filePath AS path, count(child) AS fileCount "
                "ORDER BY f.filePath"
            )
        except Exception:
            folders = []

        # Deduplicate communities by heuristicLabel
        if communities:
            grouped: dict[str, dict] = {}
            for c in communities:
                key = c.get("label") or c.get("name") or c.get("id", "")
                if key in grouped:
                    existing = grouped[key]
                    old_count = existing.get("symbolCount") or 0
                    new_count = c.get("symbolCount") or 0
                    total = old_count + new_count
                    if total > 0:
                        old_coh = existing.get("cohesion") or 0
                        new_coh = c.get("cohesion") or 0
                        existing["cohesion"] = (
                            old_coh * old_count + new_coh * new_count
                        ) / total
                    existing["symbolCount"] = total
                else:
                    grouped[key] = dict(c)
            communities = sorted(
                grouped.values(), key=lambda x: x.get("symbolCount") or 0, reverse=True
            )

        # Fetch top members per community (saves a follow-up call)
        if communities:
            labels = [c.get("label") or c.get("name") or "" for c in communities[:10]]
            labels = [la for la in labels if la]
            members_by_comm: dict[str, list[str]] = {}
            for sym_label in ("Function", "Class", "Method"):
                escaped = escape_table_name(sym_label)
                try:
                    rows = self._query(
                        f"MATCH (n:{escaped})-[r:CodeRelation]->(c:Community) "
                        f"WHERE r.type = 'MEMBER_OF' AND c.heuristicLabel IN $labels "
                        f"RETURN c.heuristicLabel AS community, n.name AS name, "
                        f"n.fanIn AS fanIn, n.entryPointScore AS eps "
                        f"ORDER BY (COALESCE(n.fanIn, 0) * 0.6 + COALESCE(n.entryPointScore, 0) * 40) DESC",
                        {"labels": labels},
                    )
                    for row in rows:
                        comm_name = row["community"]
                        members_by_comm.setdefault(comm_name, [])
                        if len(members_by_comm[comm_name]) < 5:
                            name = row.get("name", "")
                            if name and name not in members_by_comm[comm_name]:
                                members_by_comm[comm_name].append(name)
                except Exception:
                    continue
            for c in communities:
                key = c.get("label") or c.get("name") or ""
                c["topMembers"] = members_by_comm.get(key, [])

        if communities:
            cohesions = [c.get("cohesion", 0) or 0 for c in communities]
            avg_cohesion = sum(cohesions) / len(cohesions) if cohesions else 0
        else:
            avg_cohesion = 0

        envelope = self._confidence_envelope(avg_cohesion)

        # File stats: total, binary, lines of code
        file_stats: dict[str, int] = {}
        try:
            rows = self._query(
                "MATCH (f:File) "
                "RETURN count(f) AS total, "
                "count(CASE WHEN f.binary = true THEN 1 END) AS binaryCount, "
                "sum(f.lineCount) AS totalLines"
            )
            if rows:
                file_stats = {
                    "total_files": rows[0].get("total", 0),
                    "binary_files": rows[0].get("binaryCount", 0),
                    "total_lines": rows[0].get("totalLines", 0),
                }
        except Exception:
            pass

        return {
            "layer": "topology",
            "communities": communities,
            "cross_community_edges": interactions,
            "folder_tree": folders,
            "file_stats": file_stats,
            **envelope,
            "hints": [
                {
                    "action": "search",
                    "layer": "relevance",
                    "description": "Search within this topology.",
                },
            ],
        }

    # ------------------------------------------------------------------
    # Layer 1 — Relevance
    # ------------------------------------------------------------------

    def relevance(self, query: str, limit: int = 10) -> dict:
        """Layer 1 -- Project the question onto the topology via hybrid search grouped by community."""
        symbol_hits = []
        semantic_hits: list[dict] = []

        # Capture the current adapter reference — _adapter uses thread-local
        # storage, so ThreadPoolExecutor workers would fall back to the
        # default adapter instead of the scoped one.
        adapter = self._adapter
        execute_query = adapter.execute_query

        def _bm25():
            return search_fts_symbols(
                execute_query=execute_query,
                query=query,
                limit=limit * 2,
            )

        def _semantic():
            return adapter.vector_search(query_text=query, top_k=limit)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_bm25 = pool.submit(_bm25)
            fut_sem = pool.submit(_semantic)

            try:
                symbol_hits = fut_bm25.result()
            except Exception as exc:
                logger.debug("BM25 search failed in relevance layer: %s", exc)

            try:
                semantic_hits = fut_sem.result()
            except Exception as exc:
                logger.debug("Semantic search unavailable in relevance layer: %s", exc)

        all_hit_ids: dict[str, dict] = {}
        for h in symbol_hits:
            all_hit_ids[h.node_id] = {
                "name": h.name,
                "label": h.label,
                "filePath": h.file_path,
                "score": h.score,
                "source": "bm25",
            }
        for h in semantic_hits:
            nid = h.get("nodeId", "")
            if not nid:
                continue
            if nid in all_hit_ids:
                # Dual-source match — boost score (strongest relevance signal)
                all_hit_ids[nid]["score"] *= 1.5
                all_hit_ids[nid]["source"] = "bm25+semantic"
            else:
                all_hit_ids[nid] = {
                    "name": h.get("name", ""),
                    "label": h.get("label", ""),
                    "filePath": h.get("filePath", ""),
                    "score": h.get("similarity", 0),
                    "source": "semantic",
                }

        if not all_hit_ids:
            return {
                "layer": "relevance",
                "query": query,
                "communities": [],
                **self._confidence_envelope(0),
                "hints": [],
            }

        community_map: dict[str, str] = {}
        member_labels = ["Function", "Class", "Method", "Interface"]
        for label in member_labels:
            escaped = escape_table_name(label)
            node_ids = [
                nid for nid, info in all_hit_ids.items() if info["label"] == label
            ]
            if not node_ids:
                continue
            try:
                rows = self._query(
                    f"MATCH (n:{escaped})-[r:CodeRelation]->(c:Community) "
                    f"WHERE r.type = 'MEMBER_OF' AND n.id IN $ids "
                    f"RETURN n.id AS nodeId, c.heuristicLabel AS community",
                    {"ids": node_ids},
                )
                for row in rows:
                    community_map[row["nodeId"]] = row["community"]
            except Exception:
                continue

        # Score boosting: query terms that match file paths, symbol names,
        # or community labels get boosted so domain-relevant results rank
        # higher. Uses three tiers:
        #   - Exact term match in name → strong boost (0.8x per match)
        #   - Exact term match in path segment → moderate boost (0.5x per match)
        #   - Substring containment → mild boost (0.3x)
        query_terms = {t.lower() for t in re.split(r"\W+", query) if len(t) >= 3}

        if query_terms:
            for info in all_hit_ids.values():
                fp = info.get("filePath", "")
                name = info.get("name", "")
                name_lower = name.lower()
                path_lower = fp.lower()
                path_terms = {
                    t.lower() for t in re.split(r"[\W_/\\]+", fp) if len(t) >= 3
                }
                name_terms = {
                    t.lower() for t in re.split(r"[\W_]+", name) if len(t) >= 3
                }

                # Tier 1: exact token match in symbol name (strongest signal)
                name_overlap = len(query_terms & name_terms)
                # Tier 2: exact token match in path segments
                path_overlap = len(query_terms & path_terms)
                # Tier 3: substring containment (catches "websocket" in
                # "websocket.gateway.ts" even without tokenization split)
                substring_hits = sum(
                    1
                    for qt in query_terms
                    if qt not in name_terms
                    and qt not in path_terms
                    and (qt in name_lower or qt in path_lower)
                )

                boost = name_overlap * 0.8 + path_overlap * 0.5 + substring_hits * 0.3
                if boost > 0:
                    info["score"] *= 1.0 + boost

        comm_groups: dict[str, list[dict]] = defaultdict(list)
        unmapped: list[dict] = []
        for nid, info in all_hit_ids.items():
            comm = community_map.get(nid)
            hit = {"nodeId": nid, **info}
            if comm:
                comm_groups[comm].append(hit)
            else:
                unmapped.append(hit)

        # Community name boost: communities whose label matches query
        # terms get a multiplicative boost (50% per matching term, max 2x).

        community_results = []
        for comm_name, hits in sorted(
            comm_groups.items(),
            key=lambda x: sum(h["score"] for h in x[1]),
            reverse=True,
        ):
            raw_score = sum(h["score"] for h in hits)
            # Boost if any query term appears in the community label
            comm_terms = {t.lower() for t in re.split(r"\W+", comm_name) if len(t) >= 2}
            overlap = query_terms & comm_terms
            if overlap:
                # 50% boost per matching term, capped at 2x
                boost = min(1.0 + 0.5 * len(overlap), 2.0)
                raw_score *= boost
            community_results.append(
                {
                    "name": comm_name,
                    "score": round(raw_score, 3),
                    "hitCount": len(hits),
                    "hits": sorted(hits, key=lambda h: h["score"], reverse=True)[:5],
                }
            )
        # Re-sort after boosting
        community_results.sort(key=lambda c: c["score"], reverse=True)

        scores = [c["score"] for c in community_results]
        if len(scores) >= 2:
            gap = (scores[0] - scores[1]) / scores[0] if scores[0] > 0 else 0
        elif len(scores) == 1:
            gap = 1.0
        else:
            gap = 0

        top_score = scores[0] if scores else 0
        total_score = sum(scores) if scores else 1
        confidence = top_score / total_score if total_score > 0 else 0

        # Count hit sources (needed for quality dampener and return value).
        bm25_count = sum(1 for v in all_hit_ids.values() if v.get("source") == "bm25")
        semantic_count = sum(
            1 for v in all_hit_ids.values() if v.get("source") == "semantic"
        )

        # Quality dampener: when very few BM25 hits are found, the
        # relative confidence (top/total) can be misleadingly high
        # (e.g. 1 community = 1.0 regardless of match quality).
        # Scale down confidence based on hit count so weak/incidental
        # matches (like a gibberish query hitting 2 results) aren't
        # reported as "strong".
        hit_count = bm25_count + semantic_count
        if hit_count < 5:
            quality = hit_count / 5.0
            confidence *= quality

        is_crosscutting = False
        if len(community_results) >= 3:
            probs = [
                c["score"] / total_score for c in community_results if total_score > 0
            ]
            entropy = -sum(p * math.log(p) for p in probs if p > 0)
            max_entropy = (
                math.log(len(community_results)) if len(community_results) > 1 else 1
            )
            is_crosscutting = (entropy / max_entropy > 0.7) and (gap < 0.1)

        envelope = self._confidence_envelope(confidence, gap)

        hints = []
        if envelope["signal"] == "weak":
            hints.append(
                {
                    "action": "explore_multiple",
                    "description": "Low confidence gap. Explore top 2-3 communities.",
                }
            )
        if is_crosscutting:
            hints.append(
                {
                    "action": "crosscut",
                    "layer": "crosscut",
                    "description": "Hits spread across many communities -- likely a cross-cutting concern.",
                }
            )
        if community_results:
            hints.append(
                {
                    "action": "drill_down",
                    "layer": "context",
                    "scope": f"community:{community_results[0]['name']}",
                    "description": f"Drill into top community: {community_results[0]['name']}",
                }
            )

        return {
            "layer": "relevance",
            "query": query,
            "communities": community_results[:limit],
            "unmapped_hits": len(unmapped),
            "is_crosscutting": is_crosscutting,
            "bm25_hits": bm25_count,
            "semantic_hits": semantic_count,
            **envelope,
            "confidence_gap": round(gap, 3),
            "hints": hints,
        }

    # ------------------------------------------------------------------
    # Layer 2 — Context
    # ------------------------------------------------------------------

    def context_layer(self, scope: str, query: str = "", limit: int = 3) -> dict:
        """Layer 2 -- Execution paths and symbol listing within a scoped area."""
        scope_type, _, scope_value = scope.partition(":")
        if not scope_value:
            return {
                "layer": "context",
                "error": "Scope required. Use 'community:<name>', 'symbol:<name>', or 'file:<path>'.",
            }

        processes = []
        symbols = []

        if scope_type == "community":
            member_set: set[str] = set()
            for label in ("Function", "Method"):
                escaped = escape_table_name(label)
                try:
                    rows = self._query(
                        f"MATCH (n:{escaped})-[m:CodeRelation]->(c:Community) "
                        f"WHERE m.type = 'MEMBER_OF' AND c.heuristicLabel = $comm "
                        f"RETURN n.id AS nid",
                        {"comm": scope_value},
                    )
                    member_set.update(row["nid"] for row in rows)
                except Exception as exc:
                    logger.debug(
                        "context_layer member query failed for %s: %s", label, exc
                    )
                    continue

            if member_set:
                proc_map: dict[str, dict] = {}
                member_ids = list(member_set)
                for label in ("Function", "Method"):
                    escaped = escape_table_name(label)
                    try:
                        rows = self._query(
                            f"MATCH (n:{escaped})-[s:CodeRelation]->(p:Process) "
                            f"WHERE s.type = 'STEP_IN_PROCESS' AND n.id IN $memberIds "
                            f"RETURN p.id AS pid, p.name AS name, "
                            f"p.processType AS type, p.stepCount AS stepCount",
                            {"memberIds": member_ids},
                        )
                        for row in rows:
                            pid = row["pid"]
                            if pid not in proc_map:
                                proc_map[pid] = {
                                    "id": pid,
                                    "name": row["name"],
                                    "type": row["type"],
                                    "stepCount": row["stepCount"],
                                }
                    except Exception as exc:
                        logger.debug(
                            "context_layer process query failed for %s: %s", label, exc
                        )
                        continue

                processes = sorted(
                    proc_map.values(),
                    key=lambda p: p.get("stepCount") or 0,
                    reverse=True,
                )[:limit]

            seen_procs: set[str] = set()
            unique_processes = []
            for p in processes:
                if p["id"] not in seen_procs:
                    seen_procs.add(p["id"])
                    unique_processes.append(p)
            processes = unique_processes[:limit]

            for proc in processes:
                steps = []
                for label in ("Function", "Method", "Class"):
                    escaped = escape_table_name(label)
                    try:
                        rows = self._query(
                            f"MATCH (n:{escaped})-[r:CodeRelation]->(p:Process {{id: $pid}}) "
                            f"WHERE r.type = 'STEP_IN_PROCESS' "
                            f"RETURN n.id AS nodeId, n.name AS name, '{label}' AS type, "
                            f"n.filePath AS filePath, r.reason AS step, "
                            f"r.confidence AS confidence",
                            {"pid": proc["id"]},
                        )
                        steps.extend(rows)
                    except Exception as exc:
                        logger.debug(
                            "context_layer steps query failed for %s: %s", label, exc
                        )
                        continue

                for s in steps:
                    reason = s.get("step", "step-0")
                    try:
                        s["stepNum"] = int(reason.split("-")[1]) if "-" in reason else 0
                    except (ValueError, IndexError):
                        s["stepNum"] = 0
                    s["confidence"] = s.get("confidence") or 0.5
                    s["source"] = "INFERRED"
                steps.sort(key=lambda s: s["stepNum"])
                proc["steps"] = steps
                if steps:
                    proc["avgConfidence"] = round(
                        sum(s["confidence"] for s in steps) / len(steps), 3
                    )
                else:
                    proc["avgConfidence"] = 0.5

            for label in ("Function", "Method", "Class", "Interface"):
                escaped = escape_table_name(label)
                try:
                    rows = self._query(
                        f"MATCH (n:{escaped})-[m:CodeRelation]->(c:Community) "
                        f"WHERE m.type = 'MEMBER_OF' AND c.heuristicLabel = $comm "
                        f"RETURN n.id AS id, n.name AS name, '{label}' AS type, "
                        f"n.filePath AS filePath, n.fanIn AS fanIn, "
                        f"n.isExported AS isExported "
                        f"ORDER BY n.name LIMIT 50",
                        {"comm": scope_value},
                    )
                    symbols.extend(rows)
                except Exception as exc:
                    logger.debug(
                        "context_layer symbols query failed for %s: %s", label, exc
                    )
                    continue

        elif scope_type == "symbol":
            sym_matches = self._adapter.match_by_name(scope_value, limit=1)
            if sym_matches:
                sym = sym_matches[0]
                sym_id = sym["id"]
                symbols = [
                    {
                        "id": sym_id,
                        "name": sym.get("name", scope_value),
                        "type": sym.get("label", "Unknown"),
                        "filePath": sym.get("filePath", ""),
                        "startLine": sym.get("startLine"),
                        "endLine": sym.get("endLine"),
                        "isExported": sym.get("isExported"),
                    }
                ]

                callers = []
                for rel_type in ("CALLS", "IMPORTS", "EXTENDS", "IMPLEMENTS"):
                    try:
                        rows = self._query(
                            "MATCH (caller)-[r:CodeRelation]->(target {id: $id}) "
                            f"WHERE r.type = '{rel_type}' "
                            "RETURN caller.id AS uid, caller.name AS name, "
                            "label(caller) AS kind, caller.filePath AS filePath, "
                            f"'{rel_type}' AS relType, r.confidence AS confidence",
                            {"id": sym_id},
                        )
                        callers.extend(rows)
                    except Exception:
                        continue

                callees = []
                for rel_type in ("CALLS", "IMPORTS", "EXTENDS", "IMPLEMENTS"):
                    try:
                        rows = self._query(
                            "MATCH (source {id: $id})-[r:CodeRelation]->(callee) "
                            f"WHERE r.type = '{rel_type}' "
                            "RETURN callee.id AS uid, callee.name AS name, "
                            "label(callee) AS kind, callee.filePath AS filePath, "
                            f"'{rel_type}' AS relType, r.confidence AS confidence",
                            {"id": sym_id},
                        )
                        callees.extend(rows)
                    except Exception:
                        continue

                try:
                    proc_rows = self._query(
                        "MATCH (n {id: $id})-[r:CodeRelation]->(p:Process) "
                        "WHERE r.type = 'STEP_IN_PROCESS' "
                        "RETURN p.id AS id, p.name AS name, p.processType AS type, "
                        "p.stepCount AS stepCount",
                        {"id": sym_id},
                    )
                    processes = proc_rows[:limit]
                except Exception:
                    pass

                envelope = self._confidence_envelope(1.0)
                return {
                    "layer": "context",
                    "scope": scope,
                    "symbol": symbols[0] if symbols else {},
                    "callers": callers,
                    "callees": callees,
                    "processes": processes,
                    **envelope,
                    "hints": [
                        {
                            "action": "drill_down",
                            "layer": "contract",
                            "symbols": [scope_value],
                            "description": f"Get interface contract for {scope_value}",
                        }
                    ]
                    if sym_matches
                    else [],
                }

        elif scope_type == "file":
            for label in ("Function", "Method", "Class", "Interface"):
                escaped = escape_table_name(label)
                try:
                    rows = self._query(
                        f"MATCH (n:{escaped}) WHERE n.filePath = $path "
                        f"RETURN n.id AS id, n.name AS name, '{label}' AS type, "
                        f"n.filePath AS filePath, n.startLine AS startLine, "
                        f"n.endLine AS endLine, n.fanIn AS fanIn, "
                        f"n.isExported AS isExported "
                        f"ORDER BY n.startLine LIMIT 50",
                        {"path": scope_value},
                    )
                    symbols.extend(rows)
                except Exception as exc:
                    logger.debug(
                        "context_layer file query failed for %s: %s", label, exc
                    )
                    continue

        if processes:
            processes.sort(key=lambda p: p.get("avgConfidence", 0), reverse=True)
            processes[0]["recommended"] = True
            conf = processes[0].get("avgConfidence", 0.5)
        elif symbols:
            conf = 0.6
        else:
            conf = 0.3

        envelope = self._confidence_envelope(conf)

        hints = []
        if processes:
            step_names = []
            for p in processes[:1]:
                for s in p.get("steps", [])[:3]:
                    step_names.append(s.get("name", ""))
            if step_names:
                hints.append(
                    {
                        "action": "drill_down",
                        "layer": "contract",
                        "symbols": step_names,
                        "description": f"Get contracts for: {', '.join(step_names[:3])}",
                    }
                )
        elif symbols:
            top_symbols = sorted(
                symbols,
                key=lambda s: (
                    (s.get("fanIn") or 0) * 0.6 + (s.get("entryPointScore") or 0) * 40
                ),
                reverse=True,
            )[:3]
            top_names = [s["name"] for s in top_symbols if s.get("name")]
            if top_names:
                hints.append(
                    {
                        "action": "drill_down",
                        "layer": "contract",
                        "symbols": top_names,
                        "description": f"Get contracts for top symbols: {', '.join(top_names)}",
                    }
                )

        return {
            "layer": "context",
            "scope": scope,
            "processes": processes,
            "symbols": symbols[:30],
            **envelope,
            "hints": hints,
        }

    # ------------------------------------------------------------------
    # Layer 3 — Crosscut
    # ------------------------------------------------------------------

    def crosscut(self, query: str = "", scope: str = "") -> dict:
        """Layer 3 -- Horizontal patterns: cycles, shared utilities, cross-cutting concerns."""
        cycles = []
        try:
            cycle_edges = self._query(
                "MATCH (f1:File)-[r:CodeRelation]->(f2:File) "
                "WHERE r.type = 'IMPORTS' AND r.inCycle = true "
                "RETURN f1.filePath AS source, f2.filePath AS target, "
                "r.confidence AS confidence"
            )
            if cycle_edges:
                from collections import defaultdict as _dd

                adj: dict[str, set[str]] = _dd(set)
                edge_conf: dict[tuple[str, str], float] = {}
                for e in cycle_edges:
                    adj[e["source"]].add(e["target"])
                    edge_conf[(e["source"], e["target"])] = e.get("confidence", 1.0)

                all_cycle_files = set(adj.keys())
                for targets in adj.values():
                    all_cycle_files.update(targets)
                visited: set[str] = set()
                for start in all_cycle_files:
                    if start in visited:
                        continue
                    component: set[str] = set()
                    queue = [start]
                    while queue:
                        f = queue.pop()
                        if f in component:
                            continue
                        component.add(f)
                        visited.add(f)
                        queue.extend(adj.get(f, set()) - component)
                    if len(component) >= 2:
                        weakest = None
                        weakest_conf = float("inf")
                        for (s, t), c in edge_conf.items():
                            if s in component and t in component and c < weakest_conf:
                                weakest = {"from": s, "to": t, "confidence": c}
                                weakest_conf = c
                        cycles.append(
                            {
                                "members": sorted(component),
                                "edgeCount": sum(
                                    1
                                    for (s, t) in edge_conf
                                    if s in component and t in component
                                ),
                                "weakestEdge": weakest,
                            }
                        )
        except Exception as exc:
            logger.debug("Cycle query failed: %s", exc)

        if len(cycles) > 1:
            cycles.sort(key=lambda c: len(c["members"]), reverse=True)
            deduped = []
            for cycle in cycles:
                members = set(cycle["members"])
                is_subset = False
                for kept in deduped:
                    kept_members = set(kept["members"])
                    overlap = len(members & kept_members) / max(len(members), 1)
                    if overlap >= 0.8:
                        is_subset = True
                        break
                if not is_subset:
                    deduped.append(cycle)
            cycles = deduped[:10]

        shared_symbols = []
        try:
            rows = self._query(
                "MATCH (f:File) WHERE f.fanIn >= 5 "
                "RETURN f.filePath AS filePath, f.name AS name, f.fanIn AS fanIn "
                "ORDER BY f.fanIn DESC LIMIT 20"
            )
            shared_symbols = rows
        except Exception as exc:
            logger.debug("Fan-in query failed: %s", exc)

        duplicates: list[dict] = []
        try:
            for sym in shared_symbols[:5]:
                name = sym.get("name", "")
                if not name:
                    continue
                similar = self._adapter.vector_search(name, top_k=5)
                cluster = [
                    {
                        "name": s["name"],
                        "filePath": s.get("filePath", ""),
                        "similarity": round(s.get("similarity", 0), 3),
                    }
                    for s in similar
                    if s.get("similarity", 0) >= 0.90 and s.get("name") != name
                ]
                if cluster:
                    duplicates.append({"anchor": name, "similar": cluster})
        except Exception:
            pass

        has_cycles = len(cycles) > 0
        has_shared = len(shared_symbols) > 0
        has_duplicates = len(duplicates) > 0
        if has_cycles and has_shared:
            conf = 0.9
        elif has_cycles or has_shared:
            conf = 0.7
        else:
            conf = 0.3

        envelope = self._confidence_envelope(conf)

        return {
            "layer": "crosscut",
            "cycles": cycles,
            "shared_symbols": shared_symbols,
            "duplicates": duplicates,
            **envelope,
            "hints": [
                {
                    "action": "drill_down",
                    "layer": "contract",
                    "description": "Inspect contracts of shared symbols or cycle participants.",
                },
            ]
            + (
                [
                    {
                        "action": "review",
                        "layer": "implementation",
                        "description": f"Found {len(duplicates)} potential duplicate cluster(s) via embedding similarity.",
                    },
                ]
                if has_duplicates
                else []
            )
            if (has_cycles or has_shared or has_duplicates)
            else [],
        }

    # ------------------------------------------------------------------
    # Layer 4 — Contract
    # ------------------------------------------------------------------

    def _resolve_one_contract(self, sym_name: str, adapter=None) -> dict[str, Any]:
        """Resolve the contract for a single symbol (parallelizable).

        Accepts an explicit *adapter* so callers from ThreadPoolExecutor
        workers bypass the thread-local ``_adapter`` property.
        """
        _adapter = adapter or self._adapter
        _query = _adapter.execute_query
        matches = _adapter.match_by_name(sym_name, limit=1)
        if not matches:
            return {"name": sym_name, "error": "not found"}

        sym = matches[0]
        sym_id = sym["id"]
        sym_type = sym.get("type", "")

        sig_info: dict[str, Any] = {}
        if sym_type in ("Method", "Function"):
            escaped = escape_table_name(sym_type)
            try:
                rows = _query(
                    f"MATCH (n:{escaped} {{id: $id}}) "
                    f"RETURN n.parameterCount AS parameterCount, n.returnType AS returnType, "
                    f"n.signature AS signature",
                    {"id": sym_id},
                )
                if rows:
                    sig_info = rows[0]
            except Exception:
                pass

        callers = []
        try:
            callers = _query(
                "MATCH (caller)-[r:CodeRelation]->(n {id: $id}) "
                "WHERE r.type = 'CALLS' "
                "RETURN caller.name AS name, caller.filePath AS filePath, "
                "label(caller) AS type, r.confidence AS confidence LIMIT 10",
                {"id": sym_id},
            )
        except Exception:
            pass

        callees = []
        try:
            callees = _query(
                "MATCH (n {id: $id})-[r:CodeRelation]->(callee) "
                "WHERE r.type = 'CALLS' "
                "RETURN callee.name AS name, callee.filePath AS filePath, "
                "label(callee) AS type, r.confidence AS confidence LIMIT 10",
                {"id": sym_id},
            )
        except Exception:
            pass

        heritage: dict[str, Any] = {}
        try:
            ext_rows = _query(
                "MATCH (n {id: $id})-[r:CodeRelation]->(parent) "
                "WHERE r.type IN ['EXTENDS', 'IMPLEMENTS'] "
                "RETURN r.type AS relType, parent.name AS name, label(parent) AS type",
                {"id": sym_id},
            )
            extends = [r["name"] for r in ext_rows if r["relType"] == "EXTENDS"]
            implements = [r["name"] for r in ext_rows if r["relType"] == "IMPLEMENTS"]
            if extends:
                heritage["extends"] = extends
            if implements:
                heritage["implements"] = implements
        except Exception:
            pass

        overrides = []
        try:
            overrides = _query(
                "MATCH (n {id: $id})-[r:CodeRelation]->(method) "
                "WHERE r.type = 'OVERRIDES' "
                "RETURN method.name AS name, r.confidence AS confidence",
                {"id": sym_id},
            )
        except Exception:
            pass

        entry: dict[str, Any] = {
            "name": sym_name,
            "type": sym_type,
            "filePath": sym.get("filePath", ""),
            "signature": sig_info.get("signature"),
            "parameterCount": sig_info.get("parameterCount"),
            "returnType": sig_info.get("returnType"),
            "callers": callers,
            "callees": callees,
        }
        if heritage:
            entry["heritage"] = heritage
        if overrides:
            entry["overrides"] = overrides
        return entry

    def contract(self, symbols: list[str]) -> dict:
        """Layer 4 -- Interface-level view: signatures, types, heritage, callers/callees."""
        capped = symbols[:10]

        # Capture adapter before spawning threads (thread-local fix)
        adapter = self._adapter

        results: list[dict[str, Any]] = [{}] * len(capped)
        with ThreadPoolExecutor(max_workers=min(len(capped), 4)) as pool:
            futures = {
                pool.submit(self._resolve_one_contract, name, adapter): idx
                for idx, name in enumerate(capped)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception:
                    results[idx] = {"name": capped[idx], "error": "resolution failed"}

        typed_count = 0
        total_fields = 0
        for entry in results:
            if "error" in entry:
                continue
            total_fields += 4
            if entry.get("signature"):
                typed_count += 1
            if entry.get("returnType"):
                typed_count += 1
            if entry.get("callers"):
                typed_count += 1
            if entry.get("callees"):
                typed_count += 1

        type_coverage = typed_count / total_fields if total_fields > 0 else 0
        envelope = self._confidence_envelope(type_coverage)

        hints = []
        if envelope["signal"] == "weak":
            hints.append(
                {
                    "action": "skip_to",
                    "layer": "implementation",
                    "description": "Type coverage is low. Skip to source code.",
                }
            )
        else:
            symbol_names = [r["name"] for r in results if "error" not in r]
            if symbol_names:
                hints.append(
                    {
                        "action": "drill_down",
                        "layer": "implementation",
                        "symbols": symbol_names,
                        "description": "Read the implementation of these symbols.",
                    }
                )

        return {
            "layer": "contract",
            "symbols": results,
            "typeCoverage": round(type_coverage, 2),
            **envelope,
            "hints": hints,
        }

    # ------------------------------------------------------------------
    # Layer 5 — Implementation
    # ------------------------------------------------------------------

    def _resolve_one_implementation(
        self, sym_name: str, adapter=None
    ) -> dict[str, Any]:
        """Resolve implementation for a single symbol (parallelizable).

        Accepts an explicit *adapter* to bypass thread-local in pool workers.
        """
        _adapter = adapter or self._adapter
        _query = _adapter.execute_query
        matches = _adapter.match_by_name(sym_name, limit=1)
        if not matches:
            return {"name": sym_name, "error": "not found"}

        sym = matches[0]
        sym_id = sym["id"]
        sym_type = sym.get("type", "")

        content_info: dict[str, Any] = {}
        escaped = escape_table_name(sym_type) if sym_type else "Function"
        try:
            rows = _query(
                f"MATCH (n:{escaped} {{id: $id}}) "
                f"RETURN n.content AS content, n.startLine AS startLine, "
                f"n.endLine AS endLine, n.filePath AS filePath",
                {"id": sym_id},
            )
            if rows:
                content_info = rows[0]
        except Exception:
            pass

        content = content_info.get("content", "")
        return {
            "name": sym_name,
            "type": sym_type,
            "filePath": content_info.get("filePath", sym.get("filePath", "")),
            "startLine": content_info.get("startLine"),
            "endLine": content_info.get("endLine"),
            "content": content,
            "complete": bool(content),
        }

    def implementation(self, symbols: list[str]) -> dict:
        """Layer 5 -- Actual source code for specific symbols."""
        capped = symbols[:10]

        # Capture adapter before spawning threads (thread-local fix)
        adapter = self._adapter

        results: list[dict[str, Any]] = [{}] * len(capped)
        with ThreadPoolExecutor(max_workers=min(len(capped), 4)) as pool:
            futures = {
                pool.submit(self._resolve_one_implementation, name, adapter): idx
                for idx, name in enumerate(capped)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception:
                    results[idx] = {"name": capped[idx], "error": "resolution failed"}

        has_content = sum(1 for r in results if r.get("content"))
        conf = has_content / len(results) if results else 0
        envelope = self._confidence_envelope(conf)

        return {
            "layer": "implementation",
            "symbols": results,
            **envelope,
            "hints": [],
        }

    # ------------------------------------------------------------------
    # Auto-resolving orchestrator
    # ------------------------------------------------------------------

    _VALID_LAYERS = frozenset(
        {
            "topology",
            "relevance",
            "context",
            "crosscut",
            "contract",
            "implementation",
        }
    )

    def explore_auto(
        self,
        query: str = "",
        scope: str = "",
        layer: str = "",
    ) -> dict:
        """Explore the knowledge graph.

        When *layer* is given, that single layer runs in isolation and
        returns only its own data — the LLM decides what to chain next.

        When *layer* is omitted, the auto-resolver chains layers based
        on confidence (legacy convenience mode).
        """
        try:
            if layer:
                return self._explore_layer(layer, query, scope)
            return self._explore_auto_impl(query, scope)
        except Exception as exc:
            logger.error("explore_auto failed: %s", exc)
            return {
                "error": str(exc),
                "_meta": {"tokens_used": 0, "depth_reached": "error"},
            }

    # ------------------------------------------------------------------
    # Independent layer dispatch
    # ------------------------------------------------------------------

    def _explore_layer(self, layer: str, query: str, scope: str) -> dict:
        """Run a single retrieval layer and return its compressed output."""
        layer = layer.strip().lower()
        if layer not in self._VALID_LAYERS:
            return {
                "error": f"Unknown layer '{layer}'. "
                f"Valid: {', '.join(sorted(self._VALID_LAYERS))}",
            }

        if layer == "topology":
            topo = self.topology()
            result = _compress_topology(topo)
            result["_meta"] = {"depth_reached": "topology"}
            return result

        if layer == "relevance":
            if not query:
                return {"error": "query is required for the relevance layer."}
            rel = self.relevance(query, limit=8)
            result = _compress_relevance(rel)
            result["_meta"] = {
                "depth_reached": "relevance",
                "search": {
                    "bm25_hits": rel.get("bm25_hits", 0),
                    "semantic_hits": rel.get("semantic_hits", 0),
                    "communities_matched": len(rel.get("communities", [])),
                    "signal": rel.get("signal", "weak"),
                },
            }
            return result

        if layer == "context":
            if not scope:
                return {
                    "error": "scope is required for the context layer "
                    "(e.g. scope='community:<name>' or scope='file:<path>').",
                }
            ctx = self.context_layer(scope, query, limit=5)
            result = _compress_context(ctx)
            result["_meta"] = {"depth_reached": "context"}
            return result

        if layer == "crosscut":
            xc = self.crosscut(query or "", scope or "")
            result = _compress_crosscut(xc)
            result["_meta"] = {"depth_reached": "crosscut"}
            return result

        # contract & implementation expect comma-separated symbol names
        # in the `query` field.
        symbols = [s.strip() for s in query.split(",") if s.strip()] if query else []
        if not symbols:
            return {
                "error": f"query must contain comma-separated symbol names "
                f"for the {layer} layer (e.g. query='funcA, funcB').",
            }

        if layer == "contract":
            contracts = self.contract(symbols[:5])
            result = _compress_contracts(contracts)
            result["_meta"] = {"depth_reached": "contract"}
            return result

        # layer == "implementation"
        impl = self.implementation(symbols[:5])
        result = _compress_implementation(impl)
        result["_meta"] = {"depth_reached": "implementation"}
        return result

    # ------------------------------------------------------------------
    # Auto-resolving orchestrator (legacy convenience — no layer param)
    # ------------------------------------------------------------------

    def _explore_auto_impl(self, query: str, scope: str) -> dict:
        acc = _ResponseAccumulator(max_tokens=4000)

        if not query and not scope:
            topo = self.topology()
            result = _compress_topology(topo)
            result["_meta"] = {"tokens_used": 0, "depth_reached": "topology"}
            return result

        if scope.startswith("symbol:"):
            symbol_name = scope[len("symbol:") :]
            return self.context_360(symbol_name)

        if scope:
            ctx = self.context_layer(scope, query, limit=5)
            acc.add("context", _compress_context(ctx))
            target_symbols = _extract_key_symbols(ctx, max_count=5)

            ctx_conf = ctx.get("confidence", 0)
            if ctx_conf > 0.4 and target_symbols and acc.can_add(800):
                contracts = self.contract(target_symbols[:5])
                acc.add("contracts", _compress_contracts(contracts))

            return acc.finalize()

        rel = self.relevance(query, limit=8)
        envelope = _extract_envelope(rel)
        acc.add("relevance", _compress_relevance(rel))

        acc.set_search_stats(
            {
                "bm25_hits": rel.get("bm25_hits", 0),
                "semantic_hits": rel.get("semantic_hits", 0),
                "communities_matched": len(rel.get("communities", [])),
                "signal": envelope["signal"],
            }
        )

        target_symbols: list[str] = []
        hit_names = _extract_top_hits(rel, max_count=15)

        if envelope["signal"] == "strong":
            communities = rel.get("communities", [])
            if communities:
                top_comm = communities[0]["name"]
                ctx = self.context_layer(f"community:{top_comm}", query, limit=3)
                acc.add("context", _compress_context(ctx))
                target_symbols = _extract_key_symbols(
                    ctx, max_count=3, prefer_names=hit_names
                )

        elif envelope["signal"] == "moderate":
            for comm in rel.get("communities", [])[:2]:
                ctx = self.context_layer(
                    f"community:{comm['name']}",
                    query,
                    limit=2,
                )
                acc.add(f"context:{comm['name']}", _compress_context(ctx))
            target_symbols = _extract_key_symbols_from_acc(
                acc, max_count=5, prefer_names=hit_names
            )

        else:
            target_symbols = _extract_top_hits(rel, max_count=5)

        if rel.get("is_crosscutting") and acc.can_add(600):
            xc = self.crosscut(query)
            acc.add("crosscut", _compress_crosscut(xc))

        if target_symbols and acc.can_add(800):
            contracts = self.contract(target_symbols[:5])
            acc.add("contracts", _compress_contracts(contracts))

        return acc.finalize()
