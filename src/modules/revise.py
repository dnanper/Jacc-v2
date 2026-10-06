"""Artifact A5: revise the hypothesis set when A4's evidence leaves the answer open.

A4 already judged every hypothesis (status by fixed rules over cited checks, candidates,
anomalies). This node does not judge again. It only decides, by fixed rules, whether the
current set needs work, and if so asks the LLM once for new hypotheses, which A4 then checks:

- trigger (harness): NO_CANDIDATE only, i.e. no hypothesis reached a defect location with cited core
  evidence. An equal-budget control (REVISE_A5.vn.md §7) found PARTIAL and CONTESTED rounds gave nothing
  a larger A4 budget did not, and once moved gold down; NO_CANDIDATE produced the one gain.
- revise (1 LLM call): ops refine / retarget propose a replacement for a hypothesis, spawn adds one
  from an anomaly. A replacement takes effect only for a source it does not weaken: the new
  hypothesis must have at least as many cited core confirmations and not be refuted.
- validate (harness): same checks as A3 (`hypotheses._check`) plus: sources must exist, a new
  (target, mechanism) must not repeat a refuted one, at most MAX_NEW per round.
- re-explore: A4's `explore` runs on the new hypotheses only; replaced ones leave the candidate set.

Up to MAX_ROUNDS rounds. Every hypothesis records its origin, so the thesis can count what the
revision loop found that A3 did not. See research/codekg-survey/REVISE_A5.vn.md.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.exploration import MAX_CALLS, PRIOR, _Graph, explore, finalize
from src.modules.hypotheses import Anchor, Basis, Hypothesis, Prediction, _check, _render_issue, resolve_aliases
from src.modules.issue_model import IssueModel
from src.modules.repo_profile import Query, _loc

REVISE_VERSION = 6
# One round: on held-out 2 a second round changed 1 of 4 triggered instances for ~21 more calls.
MAX_ROUNDS, MAX_NEW, MAX_ALIASES, ROUND_CALLS = 1, 3, 25, 8


class Change(BaseModel):
    op: Literal["refine", "retarget", "spawn"] = Field(
        description=(
            "refine: a sharper mechanism for a hypothesis; retarget: same mechanism at a caller, callee, "
            "override, or member of the node checked; spawn: a new hypothesis from an anomaly."
        )
    )
    sources: list[str] = Field(description="Ids it builds on: the hypothesis replaced (H.., R..) or, for spawn, the anomaly (O..).")
    hypothesis: Hypothesis = Field(description="Anchors and predictions use node aliases (V..); a basis may also cite an anomaly (O..) or hypothesis (H..).")


class Revision(BaseModel):
    changes: list[Change] = Field(description=f"At most {MAX_NEW}; empty when nothing would change the answer.")


PROMPT = """Code was read to check root-cause hypotheses for an issue. The evidence below leaves the \
answer open ({why}). Propose at most {max_new} changes that the next round of reading can settle. \
Build on the cited evidence; do not re-propose a refuted hypothesis at the same place.

<issue>
{issue}
</issue>

<hypotheses>
{hyps}
</hypotheses>
{anomalies}
<nodes>
{nodes}
</nodes>"""

WHY = {"NO_CANDIDATE": "no hypothesis has confirmed evidence at a defect location"}


def revise(
    issue: IssueModel, a3: dict[str, Any], a4: dict[str, Any], query: Query, llm: Runnable, node_llm: Runnable, explain_llm: Runnable
) -> dict[str, Any]:
    """`llm` is `with_structured_output(Revision)`; `node_llm`/`explain_llm` are A4's NodeReview/ExplainCheck."""
    graph = _Graph(query)
    spec = {h["id"]: h for h in a3["hypotheses"]}
    hyps = [_complete({**_from_a3(spec[h["id"]]), **h, "origin": "A3"}) for h in a4["hypotheses"]]
    anomalies = [dict(o) for o in a4["anomalies"]]
    candidates, rounds, calls = a4["candidates"], [], 0
    for r in range(1, MAX_ROUNDS + 1):
        live = [h for h in hyps if not h.get("replaced_by")]
        triggers = _triggers(live, candidates)
        if not triggers:
            break
        alias, read = _aliases(live, anomalies, graph), _read(live)
        prompt = PROMPT.format(
            why="; ".join(WHY[t] for t in triggers), max_new=MAX_NEW, issue=_render_issue(issue),
            hyps="\n".join(_render(h) for h in live if h["status"] != "refuted" or h.get("evidence")),
            anomalies=_render_anomalies(anomalies),
            nodes="\n".join(f"{a} {_loc(n)} ({'read' if n in read else 'neighbour'}) {graph.sig(n)}" for a, n in alias.items()),
        )
        calls += 1
        out = llm.invoke(prompt)
        new, rejected = _validate(out.changes, live, anomalies, alias, r)
        record = {"round": r, "triggers": triggers, "proposed": len(out.changes), "rejected": rejected, "new": [h["id"] for h, _ in new]}
        rounds.append(record)
        if not new:
            break
        # A revision has no A3 rank: constant prior (an A3 rank prior would rank it as a fresh first hypothesis).
        a4r = explore(issue, {"hypotheses": [h for h, _ in new]}, query, node_llm, explain_llm, max_calls=ROUND_CALLS, prior=PRIOR)
        calls += a4r["calls"]
        for (spec, change), got in zip(new, a4r["hypotheses"]):
            got.update(id=spec["id"], origin=f"{change.op}({', '.join(change.sources)})", round=r)
            # A revision replaces a source only if it keeps at least that source's cited core evidence:
            # a weaker replacement would erase evidence (seen once: gold fell from rank 1 to 3).
            if change.op != "spawn" and got["core_confirmed"] and got["status"] != "refuted":
                for h in hyps:
                    if h["id"] in change.sources and not h.get("replaced_by") and got["core_confirmed"] >= h["core_confirmed"]:
                        h["replaced_by"] = spec["id"]
            hyps.append(got)
        anomalies += [o for o in a4r["anomalies"] if (o["node"], o["line"]) not in {(a["node"], a["line"]) for a in anomalies}]
        candidates = finalize([h for h in hyps if not h.get("replaced_by")])
        record["explored_calls"] = a4r["calls"]
    return {
        "artifact": "A5", "version": REVISE_VERSION, "rounds": rounds, "hypotheses": hyps,
        "candidates": candidates, "calls": calls, "changed": bool(rounds and any(x["new"] for x in rounds)),
    }


def _from_a3(h: dict) -> dict:
    """Fields an A4 output older than v8 lacks; recomputed from A3 and the A4 record itself."""
    return {"mechanism": h["mechanism"], "targets": [a["node"] for a in h["anchors"] if a["role"] == "target"],
            "prediction_text": {p["id"]: p["text"] for p in h["predictions"]},
            "core_kind": {p["id"]: p["kind"] for p in h["predictions"]}}


def _complete(h: dict) -> dict:
    if "core_confirmed" not in h:
        h["core_confirmed"] = sum(s == "confirmed" and h["core_kind"][pid] == "core" for pid, s in h["predictions"].items())
        h["deviations"] = list(dict.fromkeys(r["node"] for r in h["reads"] if r["role"] == "deviation"))
        h["rule_status"] = "supported" if h["status"] == "contested" else h["status"]
    return h


# --- triggers and validation ---------------------------------------------------------


def _triggers(live: list[dict], candidates: list[dict]) -> list[str]:
    return [] if candidates else ["NO_CANDIDATE"]


def _validate(changes: list[Change], live: list[dict], anomalies: list[dict], alias: dict[str, str], r: int) -> tuple[list, list[dict]]:
    """Returns ([(hypothesis dict ready for explore, change)], rejections with reasons)."""
    ids = {h["id"] for h in live}
    obs = {f"O{i + 1}" for i in range(len(anomalies))}
    refuted = {(frozenset(h["targets"]), h["mechanism"]) for h in live if h["status"] == "refuted"}
    rejected, ok = [], []
    for c in changes:
        reason = None
        if c.op == "spawn" and not set(c.sources) & obs:
            reason = "spawn must cite an anomaly"
        elif c.op != "spawn" and not set(c.sources) & ids:
            reason = f"{c.op} must name the hypothesis it replaces"
        if reason:
            rejected.append({"op": c.op, "sources": c.sources, "reason": reason})
            continue
        ok.append(c)
    kept, dropped = _check([c.hypothesis for c in ok], alias, basis_refs=frozenset(obs) | frozenset(ids))
    by_claim = {c.hypothesis.claim: c for c in ok}
    rejected += [{"reason": d["reason"], "claim": d.get("claim") or d.get("raw", {}).get("claim", "")} for d in dropped]
    out = []
    for h in kept:
        change = by_claim.get(h["claim"])  # keyed before aliases in the claim are resolved
        resolve_aliases(h, alias)
        targets = frozenset(a["node"] for a in h["anchors"] if a["role"] == "target")
        if (targets, h["mechanism"]) in refuted:
            rejected.append({"reason": "repeats a refuted hypothesis", "claim": h["claim"]})
            continue
        if change is None:  # merged into another new hypothesis by _check
            continue
        new_id = f"R{r}.{len(out) + 1}"
        for p in h["predictions"]:
            p["id"] = new_id + p["id"][len(h["id"]):]
        h["id"] = new_id
        out.append((h, change))
        if len(out) == MAX_NEW:
            break
    return out, rejected


# --- rendering -------------------------------------------------------------------------


def _read(hyps: list[dict]) -> set[str]:
    return {r["node"] for h in hyps for r in h["reads"]} | {n for h in hyps for n in h.get("checked_at", [])}


def _aliases(live: list[dict], anomalies: list[dict], graph: _Graph) -> dict[str, str]:
    """Nodes a change may point at: every node read, anomaly nodes, then read nodes' strongest neighbours."""
    nodes = list(dict.fromkeys([*sorted(_read(live)), *(o["node"] for o in anomalies), *(t for h in live for t in h["targets"])]))
    for n in list(nodes):  # retarget needs the neighbours of what was read
        nodes += [x["id"] for x in sorted(graph.neighbours(n), key=lambda x: -x["w"])[:2]]
    nodes = list(dict.fromkeys(nodes))[:MAX_ALIASES]
    graph.load(nodes)
    return {f"V{i + 1}": n for i, n in enumerate(nodes)}


def _render(h: dict) -> str:
    lines = [f"{h['id']} [{h['status']}] ({h['mechanism']}) {h['claim']}"]
    for pid, status in h["predictions"].items():
        lines.append(f"  {pid} {status}: {h['prediction_text'][pid]}")
    for e in h["evidence"][:3]:
        lines.append(f"    {e['pid']} {e['status']} at {_loc(e['node'])} L{e['line']} `{e['quote'][:80]}`: {e.get('reason', '')[:160]}")
    if h["refuted_by"]:
        r = h["refuted_by"]
        lines.append(f"  refuted at {_loc(r['node'])} L{r['line']} `{r['quote']}`")
    return "\n".join(lines)


def _render_anomalies(anomalies: list[dict]) -> str:
    rows = [f"O{i + 1} {_loc(o['node'])} L{o['line']} `{o['quote']}`: {o['text']}" for i, o in enumerate(anomalies)]
    return "\n<anomalies>\n" + "\n".join(rows) + "\n</anomalies>\n"


__all__ = ["Anchor", "Basis", "Change", "Hypothesis", "Prediction", "Revision", "revise", "MAX_CALLS"]
