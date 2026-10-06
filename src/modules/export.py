"""Artifact A6: the pipeline's answer in the benchmark's three-level format. Deterministic, no LLM.

Input is the hypotheses of A5, or of A4 when A5 did not revise. A6 ranks them again with
`exploration.finalize`, so the answer follows the current ranking rule even for artifacts saved under an
older one (the rule needs no LLM). A candidate is a node a non-refuted hypothesis cites as its defect.
When there is none, the targets of the best standing hypothesis are the answer (`exploration.fallback`):
an empty answer scores zero.
Each candidate node becomes one entry per level:

- found_functions: the node itself when it is a Function, Method, or Constructor ('path::Qualified.name');
- found_modules: its owning class, read from the graph edge Class -HAS_METHOD-> node, or the node
  itself when the candidate is a class;
- found_files: the file that contains it.

Candidates keep their rank. `top_k` caps how many are exported (None: all); the benchmark metric
rewards recall and precision, so the cap is a reported setting, not a tuned one.
"""

from __future__ import annotations

from typing import Any

from src.modules.exploration import fallback, finalize, sites
from src.modules.localization import LocalizeResult
from src.modules.repo_profile import Query, _loc

EXPORT_VERSION = 4
_FUNCTION_KINDS = ("Function:", "Method:", "Constructor:")


def export(a4: dict[str, Any], a5: dict[str, Any] | None, query: Query, *, top_k: int | None = None) -> dict[str, Any]:
    source = "A5" if a5 and a5.get("changed") else "A4"
    hyps = [h for h in a5["hypotheses"] if not h.get("replaced_by")] if source == "A5" else a4["hypotheses"]
    candidates = (sites(finalize(hyps), hyps) or fallback(hyps))[:top_k]
    nodes = [c["node"] for c in candidates]
    result = localize_nodes(nodes, query)
    return {"artifact": "A6", "version": EXPORT_VERSION, "source": source, "top_k": top_k, "candidates": nodes,
            "fallback": bool(candidates) and candidates[0]["role"] == "fallback", **result.to_dict()}


def export_a3(a3: dict[str, Any], query: Query, a3s: dict[str, Any] | None = None, a3r: dict[str, Any] | None = None) -> dict[str, Any]:
    """The frozen A1-A3 answer: every target of A3's first hypothesis, in A3's order. A3 v7 names every edit
    site of a fix as a target and lists its most likely hypothesis first. This is exactly the answer measured
    on the tuning set, where it matched or beat A4 at no extra call (SL 15 vs 14, PRE .85 vs .52,
    AUDIT_PIPELINE.vn.md §9); nothing is added that was not measured there."""
    hyps = a3["hypotheses"]
    nodes = list(dict.fromkeys(a["node"] for a in hyps[0]["anchors"] if a["role"] == "target")) if hyps else []
    nodes = list(dict.fromkeys((a3r or {}).get("picks", nodes) if a3r is not None else [*nodes, *(a3s or {}).get("picks", [])]))
    result = localize_nodes(nodes, query)
    return {"artifact": "A6", "version": EXPORT_VERSION, "source": "A3R" if a3r is not None else "A3S" if a3s else "A3", "candidates": nodes, **result.to_dict()}


def export_ranked(a3v: dict[str, Any], query: Query) -> dict[str, Any]:
    """V6 answer (design v3): the expected-F1 prefix of the calibrated ranking. `ranked_functions` keeps the whole
    order, so rank-aware metrics (MAP@10, Acc@k) can be computed from the same artifact."""
    result = localize_nodes(a3v["answer"], query)
    ranked = [_loc(r["node"]) for r in a3v["ranked"] if r["node"].startswith(_FUNCTION_KINDS)]
    return {"artifact": "A6", "version": EXPORT_VERSION, "source": "A3V", "candidates": a3v["answer"], **result.to_dict(), "ranked_functions": ranked}


def localize_nodes(nodes: list[str], query: Query | None = None) -> LocalizeResult:
    """Shared export/probe projection. A File node has only one colon; its path is still a prediction.
    Without a graph query only file/function levels are complete (owning classes need HAS_METHOD)."""
    nodes = list(dict.fromkeys(nodes))
    owners = _owners(query, [n for n in nodes if n.startswith(_FUNCTION_KINDS)]) if query is not None else {}
    return LocalizeResult(
        found_files=_unique(_path(n) for n in nodes),
        found_modules=_unique(_loc(owners[n]) if n in owners else (_loc(n) if n.startswith("Class:") else "") for n in nodes),
        found_functions=_unique(_loc(n) for n in nodes if n.startswith(_FUNCTION_KINDS)),
    )


def _owners(query: Query, ids: list[str]) -> dict[str, str]:
    """Owning class of each method, from the graph (a nested def or module function has none)."""
    if not ids:
        return {}
    rows = query("MATCH (c:Class)-[r:CodeRelation]->(m) WHERE r.type = 'HAS_METHOD' AND m.id IN $ids RETURN m.id AS m, c.id AS c", {"ids": ids})
    return {r["m"]: r["c"] for r in rows}


def _path(node_id: str) -> str:
    return node_id.split(":", 2)[1] if node_id.count(":") >= 1 else node_id


def _unique(values) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))
