"""Artifact A3S: the other functions the same fix must edit, next to the targets of A3's first hypothesis.

A3 names edit sites as hypothesis targets, but on multi-location fixes it splits the sites of one fix
across competing hypotheses, and the answer (H1's targets) misses them (RECALL_ANALYSIS.vn.md §11).
This step makes one call on a bounded neighbourhood of H1's targets:

- candidates: targets of the other hypotheses, one-hop graph neighbours of each H1 target (callers,
  callees, siblings, overrides, same-name methods), and other functions of the targets' files. Each
  candidate is shown with numbered code: its header plus up to 6 body lines naming an issue or
  hypothesis term, else its first body lines. The targets are shown in full (exploration's view).
- question: which candidates must also change in this fix. Each pick cites one shown line; a pick
  whose citation is not among the lines shown is dropped (exploration._cited), so the answer grows
  only on evidence (S6). No pick is a valid answer.

The answer is H1's targets followed by the kept picks, in the model's order.
"""

from __future__ import annotations

from itertools import zip_longest
from typing import Any

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.exploration import _cited, _Graph, _issue_terms, _terms
from src.modules.hypotheses import _matching_lines, _render_issue, _words
from src.modules.issue_model import IssueModel
from src.modules.repo_profile import Query, _is_test, _loc

EDIT_SITES_VERSION = 1
# Caps per source, chosen on tuning 27 + multigold10 (.tmp/s2_probe.py): they keep 25 of 27 and 40 of 55 missed gold;
# 10/24/24 keep 25 and 43 for about 50% more prompt.
MAX_OTHER, MAX_NEIGHBOURS, MAX_SAME_FILE = 8, 16, 16
_FUNCTIONS = ("Function:", "Method:", "Constructor:")


class Pick(BaseModel):
    candidate: str = Field(description="Candidate alias, e.g. C4.")
    line: int = Field(description="A shown line of that candidate that the fix must change, or where new code must go.")
    quote: str = Field(description="Exact text copied from that line.")
    reason: str = Field(description="One sentence: why the fix of the first hypothesis cannot be complete without changing this function.")


class EditSites(BaseModel):
    picks: list[Pick] = Field(description="Candidates the same fix must also edit, most certain first. Empty when the targets alone are the whole fix.")


PROMPT = """A fix for the issue below edits the target function(s) of the hypothesis. Decide which candidate \
functions the SAME fix must also edit: a sibling override or call site that has the same fault, a caller that \
must pass a new argument, a helper the change needs, a second branch of the same feature.

Rules:
- Pick a candidate only if the fix is incomplete without changing it. Related, nearby, or similar code is not enough.
- Each pick cites one numbered line of that candidate, copied exactly: the line that changes, or the line where new code goes.
- An empty list is a good answer when the targets alone are the whole fix.

<issue>
{issue}
</issue>

<hypothesis>
{claim}
</hypothesis>

<targets>
{targets}
</targets>

<candidates>
{candidates}
</candidates>"""


def find_edit_sites(issue: IssueModel, a3: dict[str, Any], query: Query, llm: Runnable) -> dict[str, Any]:
    """`llm` must be `chat.with_structured_output(EditSites, strict=True)`. No call without a function or class target
    (a class target says the fix is somewhere in it; its methods are candidates)."""
    hyps = a3["hypotheses"]
    targets = list(dict.fromkeys(a["node"] for a in hyps[0]["anchors"] if a["role"] == "target")) if hyps else []
    out = {"artifact": "A3S", "version": EDIT_SITES_VERSION, "targets": targets, "candidates": [], "picks": [], "dropped": [], "calls": 0}
    if not any(t.startswith((*_FUNCTIONS, "Class:")) for t in targets):
        return out
    graph = _Graph(query)
    terms = _issue_terms(issue) | _terms(hyps[0])
    cands = _candidates(targets, hyps[1:], graph, query, terms)
    if not cands:
        return out
    alias = {f"C{i + 1}": node for i, (node, _) in enumerate(cands)}
    shown = {t: graph.view(t, terms) for t in targets if t.startswith(_FUNCTIONS)} | {node: _snippet(graph, node, terms) for node in alias.values()}
    prompt = PROMPT.format(
        issue=_render_issue(issue),
        claim=hyps[0]["claim"],
        targets="\n\n".join(f"{_loc(t)}\n{shown[t][0]}" if t in shown else f"{_loc(t)} (a class: the edit is in its methods)" for t in targets),
        candidates="\n\n".join(f"{name} {_loc(node)} ({why})\n{shown[node][0]}" for (name, node), (_, why) in zip(alias.items(), cands)),
    )
    stats = {"citation_failures": 0}
    picks = llm.invoke(prompt).picks
    out["calls"], out["prompt_chars"] = 1, len(prompt)
    out["candidates"] = [{"alias": name, "node": node, "why": why} for (name, node), (_, why) in zip(alias.items(), cands)]
    for p in picks:
        node = alias.get(p.candidate)
        reason = "unknown candidate" if not node else None if _cited(p.line, p.quote, shown[node][1], stats) else "citation not among the shown lines"
        if reason or node in out["picks"]:
            out["dropped"].append({**p.model_dump(), "reason": reason or "repeated"})
        else:
            out["picks"].append(node)
            out.setdefault("evidence", []).append({**p.model_dump(), "node": node})
    return out


def answer(a3s: dict[str, Any]) -> list[str]:
    """H1's targets, then the evidence-backed picks."""
    return list(dict.fromkeys([*a3s["targets"], *a3s["picks"]]))


def _snippet(graph: _Graph, node: str, terms: set[str]) -> tuple[str, dict[int, str]]:
    graph.load([node])
    d = graph.nodes[node]
    code, start = d["code"] or "", d["start"] or 1
    lines = {start: code.splitlines()[0].strip()[:120]} if code else {}
    lines |= dict(_matching_lines(code, start, terms, True))
    return "\n".join(f"{n:>5} {text}" for n, text in sorted(lines.items())) or "(no code in graph)", lines


def _candidates(targets: list[str], others: list[dict], graph: _Graph, query: Query, terms: set[str]) -> list[tuple[str, str]]:
    """(node, why) from three sources, each capped, first source wins on overlap; functions only, no tests."""
    seen, out = set(targets), []

    def add(nodes: list[str], why, cap: int) -> None:
        kept = [n for n in dict.fromkeys(nodes) if n.startswith(_FUNCTIONS) and n not in seen and not _is_test(n.split(":", 2)[1])][:cap]
        seen.update(kept)
        out.extend((n, why(n)) for n in kept)

    add([a["node"] for h in others for a in h["anchors"] if a["role"] == "target"], lambda n: "target of another hypothesis", MAX_OTHER)
    via = {}
    for rank in zip_longest(*(graph.shown(t, terms) for t in targets)):  # round robin: every target's best neighbours fit the cap
        for t, n in zip(targets, rank):
            if n:
                via.setdefault(n["id"], f"{n['via']} of {_loc(t).split('::')[-1]}")
    add(list(via), via.get, MAX_NEIGHBOURS)
    files = list(dict.fromkeys(t.split(":", 2)[1] for t in targets if t.count(":") >= 2))
    rows = query(
        "MATCH (n) WHERE n.filePath IN $p AND (label(n) = 'Function' OR label(n) = 'Method' OR label(n) = 'Constructor') "
        "RETURN n.id AS id, n.startLine AS start",
        {"p": files},
    )
    want = _words(" ".join(terms))
    ranked = sorted(rows, key=lambda r: (-len(_words(_loc(r["id"]).split("::")[-1]) & want), r["start"] or 0))
    add([r["id"] for r in ranked], lambda n: "same file", MAX_SAME_FILE)
    return out
