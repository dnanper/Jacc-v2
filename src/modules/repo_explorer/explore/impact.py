"""Impact mixin — blast-radius analysis and change detection."""

from __future__ import annotations

import logging

from ._helpers import VALID_RELATION_TYPES

logger = logging.getLogger(__name__)


class ImpactMixin:
    """Blast-radius and git-diff change analysis."""

    # Adaptive depth limits — the traversal goes deeper when results
    # are sparse and stops earlier when the affected set is already large.
    _IMPACT_MAX_DEPTH = 5
    _IMPACT_MAX_AFFECTED = 200

    def impact(
        self,
        target: str,
        direction: str = "upstream",
        min_confidence: float = 0.4,
    ) -> dict:
        """Blast radius analysis with adaptive depth.

        Traverses the call graph BFS-style, going deeper when results
        are sparse and stopping when the affected set is large enough
        to assess risk.  No hard depth cap — depth adapts to the symbol.
        """
        targets = self._adapter.match_by_name(target, limit=5)

        if not targets:
            return {"error": f"Symbol '{target}' not found"}

        # Deduplicate by filePath for disambiguation.
        seen_files: set[str] = set()
        unique_targets: list[dict] = []
        for t in targets:
            fp = t.get("filePath", "")
            if fp not in seen_files:
                seen_files.add(fp)
                unique_targets.append(t)

        target_ids = [t["id"] for t in targets]
        visited_ids: set[str] = set(target_ids)

        all_affected: list[dict] = []
        rel_types = list(VALID_RELATION_TYPES)

        for d in range(1, self._IMPACT_MAX_DEPTH + 1):
            if direction == "upstream":
                rows = self._query(
                    "MATCH (caller)-[r:CodeRelation]->(n) "
                    "WHERE n.id IN $ids AND r.type IN $relTypes AND r.confidence >= $minConf "
                    "RETURN n.id AS sourceId, caller.id AS id, caller.name AS name, "
                    "label(caller) AS type, caller.filePath AS filePath, "
                    "r.type AS relType, r.confidence AS confidence",
                    {
                        "ids": target_ids,
                        "relTypes": rel_types,
                        "minConf": min_confidence,
                    },
                )
            else:
                rows = self._query(
                    "MATCH (n)-[r:CodeRelation]->(callee) "
                    "WHERE n.id IN $ids AND r.type IN $relTypes AND r.confidence >= $minConf "
                    "RETURN n.id AS sourceId, callee.id AS id, callee.name AS name, "
                    "label(callee) AS type, callee.filePath AS filePath, "
                    "r.type AS relType, r.confidence AS confidence",
                    {
                        "ids": target_ids,
                        "relTypes": rel_types,
                        "minConf": min_confidence,
                    },
                )

            resolved_rows: list[dict] = []
            for row in rows:
                row["depth"] = d
                row["source"] = "INFERRED"
                # When a relation points to a File node, try to resolve
                # the actual symbols inside that file.  This reduces
                # the number of unresolved (file-level) approximations.
                if row.get("type") == "File":
                    file_path = row.get("filePath", "")
                    if file_path:
                        try:
                            file_symbols = self._adapter.match_by_file(
                                file_path, limit=10
                            )
                        except Exception:
                            file_symbols = []
                        if file_symbols:
                            for fs in file_symbols:
                                resolved_rows.append(
                                    {
                                        "sourceId": row.get("sourceId"),
                                        "id": fs["id"],
                                        "name": fs.get("name", ""),
                                        "type": fs.get("type", fs.get("label", "")),
                                        "filePath": fs.get("filePath", file_path),
                                        "relType": row.get("relType"),
                                        "confidence": row.get("confidence", 0.5),
                                        "depth": d,
                                        "source": "INFERRED",
                                    }
                                )
                            continue  # skip the file-level entry
                    # Couldn't resolve — keep as unresolved
                    row["resolved"] = False
                all_affected.append(row)
            all_affected.extend(resolved_rows)

            # Adaptive stop: move to next depth only with new, unseen IDs
            new_ids = [r["id"] for r in rows if r["id"] not in visited_ids]
            visited_ids.update(new_ids)
            target_ids = list(set(new_ids))

            if not target_ids:
                break
            if len(all_affected) >= self._IMPACT_MAX_AFFECTED:
                break

        unresolved_count = sum(1 for a in all_affected if a.get("resolved") is False)
        d1_count = sum(1 for a in all_affected if a.get("depth") == 1)
        process_count = 0
        if d1_count > 0:
            affected_ids = list({a["id"] for a in all_affected if a.get("id")})
            if affected_ids:
                proc_rows = self._query(
                    "MATCH (n)-[r:CodeRelation]->(p:Process) "
                    "WHERE r.type = 'STEP_IN_PROCESS' AND n.id IN $ids "
                    "RETURN DISTINCT p.id AS id",
                    {"ids": affected_ids},
                )
                process_count = len(proc_rows)

        if all_affected:
            avg_conf = sum(a.get("confidence", 0.5) or 0.5 for a in all_affected) / len(
                all_affected
            )
            min_conf_val = min(a.get("confidence", 0.5) or 0.5 for a in all_affected)
        else:
            avg_conf, min_conf_val = 1.0, 1.0

        if d1_count >= 30 or process_count >= 5:
            risk = "CRITICAL"
        elif d1_count >= 15 or process_count >= 3:
            risk = "HIGH"
        elif d1_count >= 5:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        if min_conf_val < 0.5 and risk in ("LOW", "MEDIUM"):
            risk = {"LOW": "MEDIUM", "MEDIUM": "HIGH"}[risk]

        result = {
            "target": targets[0],
            "direction": direction,
            "risk": risk,
            "affected": all_affected,
            "stats": {
                "d1": d1_count,
                "total": len(all_affected),
                "unresolved": unresolved_count,
                "processes_affected": process_count,
                "avgConfidence": round(avg_conf, 3),
                "minConfidence": round(min_conf_val, 3),
            },
        }

        if len(unique_targets) > 1:
            result["candidates"] = [
                {
                    "name": t.get("name"),
                    "type": t.get("type"),
                    "filePath": t.get("filePath"),
                }
                for t in unique_targets
            ]
            result["_disambiguation"] = (
                f"Found {len(unique_targets)} symbols named '{target}'. "
                "Analyzing all matches. Use csg_explore with "
                "scope='file:<path>' to target a specific one."
            )

        return result

    def detect_changes(self, scope: str = "all", base_ref: str = "") -> dict:
        """Detect changes from git diff and find affected symbols."""
        from repo_explorer.repository.git import get_diff_files, get_git_root

        repo_path = getattr(self._adapter, "repo_source_path", None)
        if not repo_path:
            return {"error": "No source path configured for this repository"}

        git_root = get_git_root(repo_path)
        if not git_root:
            return {
                "error": f"Repository at '{repo_path}' is not a git repository. "
                "detect_changes requires a git repo with commits.",
            }

        # Guard: ensure the git root belongs to the target repo, not
        # to the CSG project or some unrelated parent directory.
        from pathlib import Path

        repo_abs = str(Path(repo_path).resolve())
        root_abs = str(Path(git_root).resolve())
        if not repo_abs.startswith(root_abs):
            return {
                "error": f"Git root '{git_root}' does not contain repo path '{repo_path}'. "
                "This may indicate the repo was extracted outside a git tree.",
            }

        changed_files = get_diff_files(git_root, scope=scope, base_ref=base_ref)

        affected_symbols = []
        for fp in changed_files:
            try:
                symbols = self._adapter.match_by_file(fp, limit=20)
                affected_symbols.extend(symbols)
            except Exception as exc:
                logger.debug("Symbol lookup failed for %s: %s", fp, exc)

        return {
            "changed_files": changed_files,
            "affected_symbols": affected_symbols,
            "total_files": len(changed_files),
            "total_symbols": len(affected_symbols),
        }
