"""Artifact A4: evidence for each A3 hypothesis, gathered by best-first search on the code graph.

Per hypothesis h the harness keeps a frontier of graph nodes, starting from h's anchors and
prediction nodes. Each round every open h takes its best frontier node; nodes wanted by several
hypotheses are read once, and one LLM call judges that node for all of them (so it can compare
them). The model only makes local, cited judgements; everything else is harness arithmetic:

- the model returns, per h: prediction checks judged on the code window against h's claim about the
  current code (for/against/n/a with 1-3 cited lines and a one-sentence reason; a prediction worded
  as the fix is judged by what it implies about the current code), whether the refute condition is
  met, the node's role (deviation/co_change/supports/transit/unrelated) with a cited line for the
  first two, up to two neighbours to read next and up to two that would also have to change; plus
  observations that bear on the issue.
- every quote is checked against the node's code; a quote that is not there voids the claim.
- realized score  R(n|h) = R(parent|h) + w(edge) * e(n|h), e from the checks and the role.
- the frontier grows only with the neighbours the model picks (`next`, `also_change`) from the cards it
  was shown: every lane, co-change lanes included, up to SHOWN cards. Picks are aliases from a closed
  list, so the search cannot reach a node the graph does not have. Order among picks:
  F(c|h) = 0.8^depth * (R(parent|h) + w * (1 + lex + 2*[edge an open prediction asks for] + 2)).
  v12 also queued every neighbour by lexical overlap: on the tuning run those reads were half of all
  reads and put one gold into an answer (ISSUES_A2_A3_A4.vn.md §14).
- prune: an unrelated node whose score fell and whose neighbours share no term with h is not
  expanded; transit nodes are expanded (at most 2 in a row); a beam drops frontier nodes under
  30% of h's best; weak edges (w <= 0.5) cost two hops of the depth limit.
- every other open hypothesis also sees the node being read and may check its predictions there
  (a prediction can name the wrong function); it does not expand from that node.
- h's belief is a log-odds that h is right: a prior by h's A3 rank (RANK_PRIOR, estimated on the
  tuning set; a constant for A5's revisions) plus one log-likelihood ratio per read (_LLR),
  from that read's single strongest cited outcome (refute met > deviation > core for > core against
  > unrelated > nothing). The ratios were estimated once on the tuning set (27 instances, 635 reads,
  hypotheses targeting gold vs not) and are frozen; see EXPLORATION_A4.vn.md §17. Evidence is weighed,
  never a veto: one misread line cannot drop h.
- status from belief, never from the scores: refuted (pruned) at posterior <= PRUNE_P; supported at
  posterior >= 0.5 with a deviation node whose every link from the anchor is cited; partial with any
  deviation; else inconclusive. A prediction's status is the majority of its cited checks, and it is
  shown again until confirmed.
- a node is a defect candidate if a non-refuted h cites it as a deviation; ranked by the belief of the
  hypotheses citing it as a deviation, then A3 rank (finalize).
- a supported h does not stop: it reads up to `expand_reads` more nodes around its deviation (every
  lane plus same-class and same-name methods), asking whether each must change with the fix. A cited
  `co_change` node becomes a candidate after every deviation. While expanding, a role answers another
  question (must this change?), so only check and refute outcomes move belief; an h that falls below
  supported stops expanding, one below PRUNE_P is pruned.
- a hypothesis that has no deviation yet stops searching once one more read, at best a cited
  deviation, could not lift its belief to that of a hypothesis that already has one (myopic value of
  information: its reads could only change the answer by overtaking that leader). It is still read
  for its first start, and still checks its predictions as a bystander.
- ablations (same prompt and budget): expand_reads=0 (stop when supported), prune="veto" (a cited core
  violation or met refute condition refutes at once, as in v9), search=False (read anchors and
  prediction nodes only, no graph propagation).

After the search:
- two or more supported hypotheses with different deviation nodes are all marked `contested`:
  each passed the rules alone, but they cannot all be the cause, so a later step adjudicates.
- when there is no candidate, one more LLM call (explain-check) asks, per cited observation, which
  standing hypothesis's mechanism accounts for it. Sharing a node is not enough. Unexplained
  observations become anomalies for the revise step, which runs only when there is no candidate, so
  the call is skipped otherwise (v12 made it on 27/27 tuning instances, 23 of them with candidates).
- `touches` is clamped to parts the issue has (no error messages: `error` becomes `observed`).
See research/codekg-survey/EXPLORATION_A4.vn.md.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.hypotheses import _render_issue
from src.modules.issue_model import IssueModel
from src.modules.repo_profile import Query, _docs, _is_test, _loc

EXPLORATION_VERSION = 15
MAX_CALLS, MAX_READS, MAX_DEPTH, MAX_TRANSIT, MAX_OBS = 12, 6, 4, 2, 2
EXPAND_READS = 3
# Frozen on the tuning set (EXPLORATION_A4.vn.md §17): per-read log-likelihood ratio of h being right.
_LLR = {"refute_met": -0.65, "deviation": 0.72, "core_for": 0.49, "core_against": -0.31, "unrelated": -0.55, "none": 0.0}
PRIOR = -0.61  # log-odds of a hypothesis targeting gold on the tuning set (62 of 176); A5 revisions use it
# Log-odds that a hypothesis targets gold, by its A3 rank (1st, 2nd, 3rd and later): A3 lists its most likely
# first. Tuning set, both A3 runs pooled (40/54, 23/54, 22/124), Laplace-smoothed; ISSUES_A2_A3_A4.vn.md §14.
RANK_PRIOR = (1.01, -0.29, -1.50)
PRUNE_P = 0.1
_PRUNE = math.log(PRUNE_P / (1 - PRUNE_P))
VARIANTS = {"full": {}, "no_expand": {"expand_reads": 0}, "veto": {"prune": "veto"}, "anchors": {"search": False, "expand_reads": 0}}
GAMMA, BEAM, MIN_W, LONG_BODY, WINDOW = 0.8, 0.3, 0.4, 150, 3
# Neighbour cards per prompt, over every lane (co-change lanes included): the model can only pick
# `next`/`also_change` among these, and picks are the only way the search grows. 48 is the smallest of
# 8/12/16/24/32/48 that shows every 1-hop gold of the 27 tuning instances in that ranking (worst rank 37),
# ISSUES_A2_A3_A4.vn.md §8, §14. STARTS keeps v11's start fan-out for class and file anchors.
SHOWN, STARTS = 48, 8
_READABLE = frozenset({"Function", "Method", "Class", "Constructor"})
_READABLE_IDS = ("Function:", "Method:", "Constructor:")  # bodies read as one window
_ROLE_SCORE = {"deviation": 3, "co_change": 2, "supports": 1, "transit": 0, "unrelated": -2}
_CHECK = {"for": "confirmed", "against": "violated"}

_RET = "RETURN m.id AS id, label(m) AS label, m.name AS name, m.filePath AS path, {w} AS w LIMIT 200"
# via -> neighbours of node $id. ponytail: LIMIT 200 is arbitrary for hubs (sympify has 4k callers); rank in Cypher if gold gets cut.
_NEIGHBOURS = {
    "calls": "MATCH (n)-[r:CodeRelation]->(m) WHERE n.id = $id AND r.type = 'CALLS' " + _RET.format(w="r.confidence"),
    "called_by": "MATCH (m)-[r:CodeRelation]->(n) WHERE n.id = $id AND r.type = 'CALLS' " + _RET.format(w="r.confidence"),
    "extends": "MATCH (n)-[r:CodeRelation]->(m) WHERE n.id = $id AND r.type IN ['EXTENDS', 'IMPLEMENTS'] " + _RET.format(w="r.confidence"),
    # Methods of the class and of its ancestors (a subclass's behaviour often lives in an inherited method);
    # for a file, the code it contains, so a file anchor is not a dead end.
    "members": (
        "MATCH (n)-[e:CodeRelation*0..3 (x, _ | WHERE x.type = 'EXTENDS')]->(c) WHERE n.id = $id "
        "MATCH (c)-[r:CodeRelation]->(m) WHERE r.type IN ['HAS_METHOD', 'CONTAINS'] " + _RET.format(w="r.confidence")
    ),
    # OVERRIDES here links a subclass to the parent method, so dispatch is derived: same-name methods of subclasses.
    "overrides": (
        "MATCH (c)-[h:CodeRelation]->(n) WHERE n.id = $id AND h.type = 'HAS_METHOD' "
        "MATCH (s)-[e:CodeRelation]->(c) WHERE e.type = 'EXTENDS' "
        "MATCH (s)-[h2:CodeRelation]->(m) WHERE h2.type = 'HAS_METHOD' AND m.name = n.name " + _RET.format(w="0.9")
    ),
    "raises": (
        "MATCH (n)-[r:CodeRelation]->(x) WHERE n.id = $id AND r.type = 'RAISES' "
        "MATCH (m)-[c:CodeRelation]->(x) WHERE c.type = 'CATCHES' " + _RET.format(w="0.9")
    ),
}
# Expansion only (a supported hypothesis looking for code that changes with its defect). Both are
# too broad for the search itself (a class can have hundreds of methods). ponytail: fixed w priors.
_CO_CHANGE = {
    "siblings": (
        "MATCH (c)-[h:CodeRelation]->(n) WHERE n.id = $id AND h.type = 'HAS_METHOD' "
        "MATCH (c)-[r:CodeRelation]->(m) WHERE r.type = 'HAS_METHOD' " + _RET.format(w="0.7")
    ),
    # Same-name methods of classes sharing a direct parent (overrides elsewhere cover parent-to-child).
    # ponytail: one EXTENDS hop each way; a variable-length path here took ~5 s per node.
    "same_name": (
        "MATCH (c)-[h:CodeRelation]->(n) WHERE n.id = $id AND h.type = 'HAS_METHOD' "
        "MATCH (c)-[e:CodeRelation]->(a) WHERE e.type = 'EXTENDS' "
        "MATCH (s)-[e2:CodeRelation]->(a) WHERE e2.type = 'EXTENDS' "
        "MATCH (s)-[h2:CodeRelation]->(m) WHERE h2.type = 'HAS_METHOD' AND m.name = n.name " + _RET.format(w="0.9")
    ),
    "parent_method": (
        "MATCH (c)-[h:CodeRelation]->(n) WHERE n.id = $id AND h.type = 'HAS_METHOD' "
        "MATCH (c)-[e:CodeRelation]->(a) WHERE e.type = 'EXTENDS' "
        "MATCH (a)-[h2:CodeRelation]->(m) WHERE h2.type = 'HAS_METHOD' AND m.name = n.name " + _RET.format(w="0.9")
    ),
}


class Cite(BaseModel):
    line: int
    quote: str = Field(description="Exact text copied from that line.")


class Check(BaseModel):
    pid: str = Field(description="Prediction id, e.g. H1.P2.")
    status: Literal["for", "against", "n/a"] = Field(
        description="Whether these lines show what the hypothesis claims about the current code (for) or show otherwise (against)."
    )
    cites: list[Cite] = Field(description="1-3 shown lines that together decide it; empty for n/a.")
    reason: str = Field(
        description=(
            "One sentence: how these lines decide the prediction. For `for`, say why a correct implementation "
            "would not contain them; for something absent, name the shown line span it is absent from."
        )
    )


class Refute(BaseModel):
    met: bool
    line: int
    quote: str


class Record(BaseModel):
    h: str = Field(description="Hypothesis id, e.g. H2.")
    checks: list[Check]
    refute: Refute
    role: Literal["deviation", "co_change", "supports", "transit", "unrelated"] = Field(
        description=(
            "deviation: the defect is here; co_change: the defect is elsewhere but the fix must also change this code; "
            "supports: on the defect path and consistent; transit: only passes data or control along; unrelated."
        )
    )
    cite: Cite = Field(description="For deviation or co_change, the line that shows it; otherwise line 0 and an empty quote.")
    next: list[str] = Field(description="Up to 2 neighbour aliases (N1..) worth reading next for this hypothesis.")
    also_change: list[str] = Field(description="Up to 2 neighbour aliases that would also have to change if this hypothesis is true.")


class Observation(BaseModel):
    text: str = Field(description="A fact in this code that could make the observed behaviour differ from the expected one.")
    line: int
    quote: str
    touches: Literal["observed", "expected", "error", "none"] = Field(description="Which part of the issue this fact bears on.")


class NodeReview(BaseModel):
    records: list[Record]
    observations: list[Observation]
    new_terms: list[str] = Field(description="Code identifiers seen here that could matter for the issue.")


class Link(BaseModel):
    h: str = Field(description="Hypothesis id.")
    words: str = Field(description="The words of that hypothesis's claim that name this very fact, copied exactly.")


class Explained(BaseModel):
    obs: str = Field(description="Observation id, e.g. O3.")
    explained_by: list[Link] = Field(description="Hypotheses whose claim names this fact as part of the bug; empty if none.")


class ExplainCheck(BaseModel):
    items: list[Explained]


EXPLAIN_PROMPT = """Below are facts read from code while checking a bug report, and the hypotheses still standing. For each observation, list the hypotheses whose claimed mechanism accounts for it, copying the exact words of the claim that name this fact. Being in the same \
function, or a claim that is merely compatible with the fact, is not enough: the claim must \
itself name this fact as (part of) how the bug happens. Return an empty list when none does.

<issue>
{issue}
</issue>

<hypotheses>
{hyps}
</hypotheses>

<observations>
{obs}
</observations>"""


PROMPT = """You check root-cause hypotheses for a bug report against code. Below is one code \
node, the hypotheses that point at it now, and the node's graph neighbours.

For each hypothesis return one record:
- checks: for each open prediction listed, whether the shown code bears `for` or `against` the \
claim, or `n/a` when the relevant code is not shown.
- refute: met=true only when a shown line matches the refute condition, with line and exact quote.
- role of this node for the hypothesis, citing the line for deviation or co_change.
- next / also_change: neighbour aliases worth reading next for it / that would also have to change.
Also list at most 2 observations: facts in this code that could make the observed behaviour \
differ from the expected one, whichever hypothesis they fit (or none), each with line and exact \
quote. Skip descriptions of what the code does normally; list nothing if nothing qualifies.
Quotes are checked against the code; a quote that is not there voids the claim.

<issue>
{issue}
</issue>

<node id="{node}">
{code}
</node>

<hypotheses>
{hyps}
</hypotheses>

<neighbours>
{neighbours}
</neighbours>"""


def explore(
    issue: IssueModel, hyps: dict[str, Any], query: Query, llm: Runnable, explain_llm: Runnable,
    *, max_calls: int = MAX_CALLS, max_reads: int = MAX_READS, expand_reads: int = EXPAND_READS,
    prune: Literal["belief", "veto"] = "belief", search: bool = True, prior: float | None = None,
) -> dict[str, Any]:
    """`llm`/`explain_llm` are `chat.with_structured_output(NodeReview|ExplainCheck, strict=True)`.

    `prior`: None gives each hypothesis the prior of its A3 rank (list order); a number gives every
    hypothesis that prior (A5's revisions have no A3 rank).
    """
    graph = _Graph(query)
    issue_terms = _issue_terms(issue)
    states = [_init_state(h, issue_terms, graph) for h in hyps["hypotheses"]]
    for i, st in enumerate(states):
        belief = RANK_PRIOR[min(i, len(RANK_PRIOR) - 1)] if prior is None else prior
        # Every function target is an edit-site claim to check: the read cap never cuts one off.
        cap = max(max_reads, len([t for t in st["targets"] if t.startswith(_READABLE_IDS)]))
        st.update(read_cap=cap, expand_reads=expand_reads, prune=prune, search=search, belief=belief, prior=belief)
    issue_text = _render_issue(issue)
    parts = {"observed", "expected"} | ({"error"} if issue.error_messages else set())
    observations: list[dict] = []
    terms: dict[str, list[str]] = {}
    stats = {"calls": 0, "citation_failures": 0, "beam_dropped": 0, "dominated": 0}
    while stats["calls"] < max_calls:
        _dominate(states, graph, stats)
        picks: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
        for st in states:
            if st["status"] == "open" and len(st["reads"]) < st["read_cap"] and (c := _pop(st, stats)):
                picks[c["node"]].append((st, c))
        if not picks:
            break
        waiting = {st["id"] for its in picks.values() for st, _ in its}  # picks not yet read this round
        for node, items in sorted(picks.items(), key=lambda kv: -max(c["F"] for _, c in kv[1])):
            if stats["calls"] >= max_calls:
                break
            # Join every other open hypothesis that has this node queued, so the node is read once;
            # one whose own pick is still waiting would overrun its read budget.
            items += [(st, c) for st in states if st["status"] == "open" and st["id"] not in waiting and st not in [x for x, _ in items] and (c := _take(st, node))]
            stats["calls"] += 1
            terms[node] = _review(node, items, states, graph, issue_text, llm, observations, parts, stats)
            waiting -= {st["id"] for st, _ in items}
    for st in states:
        if st["status"] == "open":
            st["status"] = _status(st, graph)
    out_h = [_out_hypothesis(st, graph) for st in states]
    candidates = finalize(out_h)
    # Anomalies feed only A5, which runs only when there is no candidate.
    checked = not candidates
    _explain_check(observations, [h for h in out_h if h["status"] != "refuted"] if checked else [], issue_text, explain_llm, stats)
    return {
        "artifact": "A4", "version": EXPLORATION_VERSION, "hypotheses": out_h, "candidates": candidates,
        "anomalies": [o for o in observations if not o["explained_by"]] if checked else [], "observations": observations,
        "new_terms": {n: t for n, t in terms.items() if t}, "budget": {"calls": max_calls, "reads": max_reads},
        "options": {"expand_reads": expand_reads, "prune": prune, "search": search}, **stats,
    }


def finalize(hyps: list[dict]) -> list[dict]:
    """Status `contested` and ranked defect candidates over output hypotheses; A5 and A6 reuse it.

    Two or more supported hypotheses at different deviation nodes cannot all be the cause: all become
    contested. A node is a candidate if a non-refuted hypothesis cites it as a deviation. Its rank uses
    only those hypotheses: best belief, then best A3 rank (list order; A3 lists its most likely first),
    then how many cite it. Cited co_change nodes of supported (or contested) hypotheses follow every
    deviation, ranked the same way. A co_change vote never lends its belief to a deviation node (seen on
    pylint-7114: a hypothesis with a met refute condition outranked gold on another's co_change vote).
    A3 rank breaks belief ties because most supported hypotheses share one belief (PRIOR + one deviation)
    and vote counts mostly count near-duplicate A3 samples (ISSUES_A2_A3_A4.vn.md §11).
    """
    for h in hyps:
        h["status"] = h["rule_status"]
    supported = [h for h in hyps if h["status"] == "supported"]
    if len(supported) > 1 and len({frozenset(h["deviations"]) for h in supported}) > 1:
        for h in supported:
            h["status"] = "contested"
    dev: dict[str, dict[str, tuple[int, dict]]] = defaultdict(dict)
    co: dict[str, dict[str, tuple[int, dict]]] = defaultdict(dict)
    for i, h in enumerate(hyps):
        if h["status"] != "refuted":
            for d in h["deviations"]:
                dev[d][h["id"]] = (i, h)
        if h["status"] in ("supported", "contested"):
            for d in h.get("co_change", []):
                co[d][h["id"]] = (i, h)
    out = []
    for n in dict.fromkeys([*dev, *co]):
        hs = dev[n] or co[n]
        out.append({"node": n, "role": "deviation" if dev[n] else "co_change", "hypotheses": list(hs),
                    "belief": max(h.get("belief", PRIOR) for _, h in hs.values()), "a3_rank": min(i for i, _ in hs.values()),
                    "core_confirmed": sum(h["core_confirmed"] for _, h in hs.values()),
                    "supported": sum(h["status"] in ("supported", "contested") for _, h in hs.values())})
    return sorted(out, key=lambda c: (c["role"] != "deviation", -c["belief"], c["a3_rank"], -len(c["hypotheses"])))


def sites(candidates: list[dict], hyps: list[dict]) -> list[dict]:
    """Candidates, then the other targets of the hypothesis behind the top candidate (role `target`).

    A3 names every function a fix edits as a target of one hypothesis; when that hypothesis leads the answer,
    its other edit sites belong in it even if only one was cited as a deviation (a multi-site fix). Only the
    leader's: a lower hypothesis's targets compete with the answer rather than complete it."""
    if not candidates:
        return candidates
    by_id = {h["id"]: h for h in hyps}
    lead = max((by_id[i] for i in candidates[0]["hypotheses"] if i in by_id), key=lambda h: h.get("belief", PRIOR), default=None)
    have = {c["node"] for c in candidates}
    # A target the leader read and judged unrelated is evidence against that site, so it is left out.
    unrelated = {r["node"] for r in (lead or {}).get("reads", []) if r["role"] == "unrelated"}
    extra = [t for t in (lead["targets"] if lead else []) if t not in have and t not in unrelated]
    return candidates + [{"node": t, "role": "target", "hypotheses": [lead["id"]], "belief": lead.get("belief", PRIOR)} for t in dict.fromkeys(extra)]


def fallback(hyps: list[dict]) -> list[dict]:
    """The answer when no hypothesis reached a cited defect: the targets of the best standing hypothesis
    (belief, then A3 rank), with role `fallback`. An empty answer scores zero, and A3's target is right
    more often than A4 alone (ISSUES_A2_A3_A4.vn.md §10). Used by A6 only, so A5's NO_CANDIDATE trigger
    still sees no candidate."""
    live = [(i, h) for i, h in enumerate(hyps) if h["status"] != "refuted"] or list(enumerate(hyps))
    if not live:
        return []
    _, h = min(live, key=lambda ih: (-ih[1].get("belief", PRIOR), ih[0]))
    return [{"node": n, "role": "fallback", "hypotheses": [h["id"]], "belief": h.get("belief", PRIOR)} for n in dict.fromkeys(h["targets"])]


def _explain_check(observations: list[dict], standing: list[dict], issue_text: str, llm: Runnable, stats: dict) -> None:
    """Fill `explained_by` on every observation against the standing hypotheses; one call, skipped when none stand."""
    for i, o in enumerate(observations, 1):
        o["id"], o["explained_by"] = f"O{i}", []
    if not observations or not standing:
        return
    stats["calls"] += 1
    out = llm.invoke(EXPLAIN_PROMPT.format(
        issue=issue_text,
        hyps="\n".join(f"{st['id']} [{st['status']}]: {st['claim']}" for st in standing),
        obs="\n".join(f"{o['id']} {_loc(o['node'])} L{o['line']} `{o['quote']}`: {o['text']}" for o in observations),
    ))
    claims, by_obs = {st["id"]: " ".join(st["claim"].split()) for st in standing}, {o["id"]: o for o in observations}
    for item in out.items:
        if item.obs in by_obs:  # a link counts only if its words really are in that claim
            by_obs[item.obs]["explained_by"] = sorted({
                link.h for link in item.explained_by
                if link.h in claims and len(link.words.strip()) >= 3 and " ".join(link.words.split()) in claims[link.h]
            })


# --- one LLM call per node ----------------------------------------------------------


def _review(node: str, items: list[tuple[dict, dict]], states: list[dict], graph: "_Graph", issue_text: str, llm: Runnable, observations: list, parts: set[str], stats: dict) -> list[str]:
    terms = set().union(*(st["terms"] for st, _ in items))
    code, lines = graph.view(node, terms)
    queued = {st["id"] for st, _ in items}
    # A prediction may name the wrong function; any open hypothesis can check its predictions at a node being read.
    bystanders = [st for st in states if st["status"] == "open" and st["id"] not in queued and any(_open(st, pid) for pid in st["preds"])]
    shown = graph.shown(node, terms)
    alias = {f"N{i + 1}": n["id"] for i, n in enumerate(shown)}
    prompt = PROMPT.format(
        issue=issue_text, node=_loc(node), code=code,
        hyps="\n".join([*(_render_h(st) for st, _ in items), *(_render_h(st, bystander=True) for st in bystanders)]),
        neighbours="\n".join(f"{a} {graph.card(n)}" for a, n in zip(alias, shown)) or "(none)",
    )
    out = llm.invoke(prompt)
    by_h = {r.h: r for r in out.records}
    new_terms = list(dict.fromkeys(t.strip() for t in out.new_terms if t.strip()))[:10]
    for st, c in items:
        rec = by_h.get(st["id"])
        also = {alias[a] for a in (rec.also_change if rec else [])[:2] if a in alias}
        # Both picks, before _apply: when this read makes h supported, expansion starts from them
        # (v13 kept only also_change, so a `next` pick on that read was lost).
        st["hints"] |= also | {alias[a] for a in (rec.next if rec else [])[:2] if a in alias}
        started = _apply(st, node, c, rec, lines, graph, stats)
        if st["status"] == "open" and not started and st["search"]:
            _expand(st, node, graph, also | {alias[a] for a in (rec.next if rec else []) if a in alias})
    for st in bystanders:
        if (rec := by_h.get(st["id"])) and (kept := _record_checks(st, node, rec, lines, stats)) and any("pid" in ev for ev in kept):
            st["checked_at"].append(node)
            role = rec.role if rec.role in ("deviation", "unrelated") else "transit"
            if role == "deviation" and not _cited(rec.cite.line, rec.cite.quote, lines, stats):
                role = "transit"  # same rule as a searched node: a location claim needs its own cited line
            if role == "deviation":  # no search path leads here, so it can reach partial, not supported
                st["deviations"].append(node)
            _weigh(st, node, kept, role)
            _settle(st, graph)
    seen = {(o["node"], o["line"]) for o in observations}
    for o in out.observations[:MAX_OBS]:
        if o.touches != "none" and (node, o.line) not in seen and _cited(o.line, o.quote, lines, stats):
            touches = o.touches if o.touches in parts else "observed"  # the issue has no such part
            observations.append({"node": node, "text": o.text, "line": o.line, "quote": o.quote, "touches": touches})
            seen.add((node, o.line))
    return new_terms


def _record_checks(st: dict, node: str, rec: Record, lines: dict[int, str], stats: dict) -> list[dict]:
    """Keep the prediction checks whose every cited line is real, and a cited refute; returns the checks kept."""
    kept = []
    for chk in rec.checks:
        cites = chk.cites[:3]
        if chk.pid not in st["preds"] or chk.status == "n/a" or not cites or not all(_cited(c.line, c.quote, lines, stats) for c in cites):
            continue
        if any(e["pid"] == chk.pid and e["node"] == node for e in st["evidence"]):
            continue  # one judgement per prediction per node (a bystander may read the node again later)
        status = _CHECK[chk.status]
        ev = {"pid": chk.pid, "status": status, "node": node, "line": cites[0].line, "quote": cites[0].quote,
              "cites": [{"line": c.line, "quote": c.quote} for c in cites], "reason": chk.reason}
        st["evidence"].append(ev)
        kept.append(ev)
    if rec.refute.met and node not in {r["node"] for r in st["refutes"]} and _cited(rec.refute.line, rec.refute.quote, lines, stats):
        st["refutes"].append({"node": node, "line": rec.refute.line, "quote": rec.refute.quote})
        kept.append({"refute": True})
    return kept


def _weigh(st: dict, node: str, kept: list[dict], role: str) -> None:
    """Add this read's single strongest cited outcome to h's belief (outcomes of one read are not independent).

    `kept` is what `_record_checks` kept; a met refute condition shows up in it as {"refute": True}.
    """
    core = {ev["status"] for ev in kept if "pid" in ev and st["preds"][ev["pid"]]["kind"] == "core"}
    if st["expanding"] and role in ("deviation", "co_change", "unrelated"):
        role = "transit"  # while expanding, the role says whether this node must change, not whether h is right
    outcome = ("refute_met" if any("refute" in ev for ev in kept) else "deviation" if role == "deviation" else "core_for" if core == {"confirmed"}
               else "core_against" if core == {"violated"} else "unrelated" if role == "unrelated" else "none")
    # One node is one piece of evidence for h, however often it is shown: a bystander check and h's own
    # read of the same node keep the strongest outcome (v13 added both, 17 of 122 tuning hypotheses).
    prev = next((o for o in st["outcomes"] if o["node"] == node), None)
    if prev is None:
        st["outcomes"].append({"node": node, "outcome": outcome})
        st["belief"] += _LLR[outcome]
    elif abs(_LLR[outcome]) > abs(_LLR[prev["outcome"]]):
        st["belief"] += _LLR[outcome] - _LLR[prev["outcome"]]
        prev["outcome"] = outcome


def _apply(st: dict, node: str, c: dict, rec: Record | None, lines: dict[int, str], graph: "_Graph", stats: dict) -> bool:
    """Record the read; returns True when it made h supported, so h starts expanding from its deviations."""
    kept = _record_checks(st, node, rec, lines, stats) if rec else []
    checks = [ev for ev in kept if "pid" in ev]
    cited = bool(checks)
    kind = lambda ev: st["preds"][ev["pid"]]["kind"]
    core_ok = sum(kind(ev) == "core" and ev["status"] == "confirmed" for ev in checks)
    aux_ok = sum(kind(ev) == "aux" and ev["status"] == "confirmed" for ev in checks)
    aux_bad = sum(kind(ev) == "aux" and ev["status"] == "violated" for ev in checks)
    core_bad = sum(kind(ev) == "core" and ev["status"] == "violated" for ev in checks)  # no longer a veto, so it lowers the priority
    role = rec.role if rec else "transit"  # an unlabelled node is not evidence either way
    if role == "deviation" and st["expanding"]:
        role = "co_change"  # found while expanding a supported hypothesis: another place the fix touches
    # A location claim stands on its own cited line. v13 accepted it when any prediction check was cited,
    # even one against h, and never checked the role's line: an invented line passed, a real one alone did not.
    if role in ("deviation", "co_change") and not _cited(rec.cite.line, rec.cite.quote, lines, stats):
        role = "supports"
    _weigh(st, node, kept, role)
    r_parent = st["tree"][c["parent"]]["R"] if c["parent"] else 0.0
    score = r_parent + c["w"] * (2 * (core_ok - core_bad) + aux_ok - aux_bad + _ROLE_SCORE[role])
    run = (st["tree"][c["parent"]]["transit_run"] + 1 if c["parent"] else 1) if role == "transit" else 0
    st["tree"][node] = {**c, "R": round(score, 3), "role": role, "transit_run": run}
    st["reads"].append({"node": node, "role": role, "R": round(score, 3)})
    if role == "deviation":
        st["deviations"].append(node)
    if role == "co_change":
        st["co_change"].append(node)
    return _settle(st, graph)


def _settle(st: dict, graph: "_Graph") -> bool:
    """Pruned stops reading; supported starts expanding (returns True); falling from supported stops expanding."""
    s = _status(st, graph)
    if s == "refuted" or s == "supported" and not st["expand_reads"] and not st["expanding"]:
        st["status"] = s  # settled: stop reading (supported only when expansion is off)
    elif s == "supported" and not st["expanding"]:
        st["expanding"], st["read_cap"], st["frontier"] = True, len(st["reads"]) + st["expand_reads"], []
        for d in dict.fromkeys(st["deviations"]):
            if d in st["tree"]:
                _expand(st, d, graph, st["hints"])
        return True
    elif s != "supported" and st["expanding"]:
        st["expanding"], st["read_cap"] = False, len(st["reads"])
    return False


def _expand(st: dict, node: str, graph: "_Graph", chosen: set[str]) -> None:
    here, expanding = st["tree"][node], st["expanding"]
    if expanding and here["role"] not in ("deviation", "co_change"):
        return  # expansion only grows from code that has to change
    r_parent = st["tree"][here["parent"]]["R"] if here["parent"] else 0.0
    neigh = [n for n in graph.neighbours(node, True) if n["id"] in chosen]  # only what the model picked
    lex = {n["id"]: _lex(graph.text(n), st["terms"]) for n in neigh}
    if not expanding and here["role"] == "unrelated" and here["R"] < r_parent and not any(lex.values()):
        st["pruned"].append({"node": node, "reason": "unrelated, score fell, no neighbour shares a term"})
        return
    if here["transit_run"] > MAX_TRANSIT:
        st["pruned"].append({"node": node, "reason": f"more than {MAX_TRANSIT} transit nodes in a row"})
        return
    asked = {p["via"] for pid, p in st["preds"].items() if p["node"] == node and _open(st, pid)}
    for n in neigh:
        depth = here["depth"] + (2 if n["w"] <= 0.5 else 1)
        if n["id"] in st["tree"] or (depth > MAX_DEPTH and not expanding):
            continue
        bonus = 1 + lex[n["id"]] + 2 * (n["via"] in asked or n["id"] in st["pred_nodes"]) + 2
        st["frontier"].append({"node": n["id"], "parent": node, "edge": n["via"], "w": n["w"], "depth": depth, "F": GAMMA**depth * (here["R"] + n["w"] * bonus)})


def _dominate(states: list[dict], graph: "_Graph", stats: dict) -> None:
    """Stop searching for a hypothesis whose best next read could not lift it to the leader.

    Leader = best belief among standing hypotheses that already cite a deviation. A hypothesis with no
    deviation that has had its first read gains at most max(_LLR) from one more read; when that cannot
    reach the leader its reads cannot change the top of the answer, so it stops (myopic value of
    information). Its status is settled from the evidence it has.
    """
    lead = max((st["belief"] for st in states if st["deviations"] and st["status"] != "refuted"), default=None)
    if lead is None:
        return
    for st in states:
        if (st["status"] == "open" and not st["expanding"] and not st["deviations"] and st["reads"] and not _unread_targets(st)
                and st["belief"] + max(_LLR.values()) < lead):
            st["status"], st["stopped"] = _status(st, graph), "dominated"
            stats["dominated"] += 1


def _unread_targets(st: dict) -> list[str]:
    """Function targets of h not yet read by h or checked at as a bystander."""
    return [t for t in st["targets"] if t.startswith(_READABLE_IDS) and t not in st["tree"] and t not in st["checked_at"]]


def _take(st: dict, node: str) -> dict | None:
    """Remove and return st's best frontier entry for `node`, if it has one and read budget left."""
    mine = [c for c in st["frontier"] if c["node"] == node]
    if not mine or node in st["tree"] or len(st["reads"]) >= st["read_cap"]:
        return None
    best = max(mine, key=lambda c: c["F"])
    st["frontier"] = [c for c in st["frontier"] if c["node"] != node]
    return best


def _pop(st: dict, stats: dict) -> dict | None:
    live = [c for c in st["frontier"] if c["node"] not in st["tree"]]
    if not live:
        st["frontier"] = []
        return None
    best = max(c["F"] for c in live)
    targets = set(_unread_targets(st))  # an edit-site claim is read, never beamed away
    kept = [c for c in live if c["F"] >= BEAM * best or c["F"] == best or c["node"] in targets]
    stats["beam_dropped"] += len(live) - len(kept)
    pick = max(kept, key=lambda c: c["F"])
    kept.remove(pick)
    st["frontier"] = kept
    return pick


# --- status and chains ------------------------------------------------------------------


def _open(st: dict, pid: str) -> bool:
    """A prediction stays open until cited evidence confirms it: one line against it is not the last word."""
    return _pred(st, pid) != "confirmed"


def _pred(st: dict, pid: str) -> str:
    """Majority of the cited checks; a tie is a conflict, which counts as neither."""
    seen = [e["status"] for e in st["evidence"] if e["pid"] == pid]
    yes, no = seen.count("confirmed"), seen.count("violated")
    return "unchecked" if not seen else "confirmed" if yes > no else "violated" if no > yes else "conflict"


def _status(st: dict, graph: "_Graph") -> str:
    if st["prune"] == "veto":  # v9 rule, kept as an ablation
        core = [pid for pid, p in st["preds"].items() if p["kind"] == "core"]
        if st["refutes"] or any(e["status"] == "violated" and e["pid"] in core for e in st["evidence"]):
            return "refuted"
    elif st["belief"] <= _PRUNE:
        return "refuted"
    if st["belief"] >= 0 and any(_chain(st, d, graph)["closed"] for d in st["deviations"]):
        return "supported"
    return "partial" if st["deviations"] else "inconclusive"


def _chain(st: dict, node: str, graph: "_Graph") -> dict:
    """Links from the anchor to `node` in h's search tree; a CALLS link is cited by its call-site line."""
    if node not in st["tree"]:  # found as a bystander: no path, so no closed chain
        return {"start": node, "links": [], "closed": False}
    links, cur = [], node
    while (parent := st["tree"][cur]["parent"]):
        edge = st["tree"][cur]["edge"]
        caller, callee = (parent, cur) if edge == "calls" else (cur, parent)
        line = graph.call_line(caller, callee) if edge in ("calls", "called_by") else None
        links.append({"from": parent, "to": cur, "edge": edge, "line": line, "cited": line is not None or edge not in ("calls", "called_by")})
        cur = parent
    links.reverse()
    return {"start": cur, "links": links, "closed": all(link["cited"] for link in links)}


def _cited(line: int, quote: str, lines: dict[int, str], stats: dict) -> bool:
    """The quote must appear within two lines of the given line, among lines the model was shown.

    A fragment shorter than 8 characters (`else:`, `x):`) matches too much; it counts only as a whole line.
    """
    q = " ".join(quote.split())
    window = [" ".join(lines.get(n, "").split()) for n in range(line - 2, line + 3)]
    ok = bool(q) and q in " ".join(window) and (len(q) >= 8 or q in window)
    stats["citation_failures"] += not ok
    return ok


# --- graph access (tiers 0-2) -------------------------------------------------------------


class _Graph:
    def __init__(self, query: Query) -> None:
        self.q = query
        self.nodes: dict[str, dict] = {}
        self._neigh: dict[tuple[str, bool], list[dict]] = {}

    def load(self, ids: list[str]) -> None:
        need = [i for i in ids if i not in self.nodes]
        if not need:
            return
        rows = self.q("MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, n.name AS name, n.signature AS sig, n.content AS code, n.startLine AS start", {"ids": need})
        docs = _docs(self.q, need)
        for r in rows:
            self.nodes[r["id"]] = {**r, "doc": docs.get(r["id"], "")}
        for i in need:
            self.nodes.setdefault(i, {"id": i, "name": i.split(":")[-1], "sig": "", "code": "", "start": 1, "doc": ""})

    def neighbours(self, node: str, co_change: bool = False) -> list[dict]:
        """Tier 0: readable neighbours over every lane (plus the co-change lanes), best edge per neighbour, weak edges and tests dropped
        (script dirs such as examples/ stay: some issues are fixed there)."""
        if (node, co_change) not in self._neigh:
            best: dict[str, dict] = {}
            for via, cypher in (_NEIGHBOURS | _CO_CHANGE if co_change else _NEIGHBOURS).items():
                for r in self.q(cypher, {"id": node}):
                    w = r["w"] if r["w"] is not None else 0.9
                    if r["id"] == node or r["label"] not in _READABLE or w < MIN_W or _is_test(r["path"] or ""):
                        continue
                    if r["id"] not in best or w > best[r["id"]]["w"]:
                        best[r["id"]] = {"id": r["id"], "via": via, "w": w}
            self._neigh[node, co_change] = list(best.values())
            self.load(list(best))
        return self._neigh[node, co_change]

    def shown(self, node: str, terms: set[str]) -> list[dict]:
        neigh = self.neighbours(node, True)
        return sorted(neigh, key=lambda n: -n["w"] * (1 + _lex(self.text(n), terms)))[:SHOWN]

    def text(self, n: dict) -> str:
        d = self.nodes[n["id"]]
        return f"{d['name']} {d['sig'] or ''} {d['doc']}"

    def sig(self, node: str) -> str:
        self.load([node])
        return " ".join((self.nodes[node]["sig"] or "").split())[:100]

    def card(self, n: dict) -> str:
        """Tier 1."""
        d = self.nodes[n["id"]]
        sig = " ".join((d["sig"] or "").split())[:120]
        return f"{_loc(n['id'])} ({n['via']}, w={n['w']:.2f}) {sig}" + (f" | {d['doc']}" if d["doc"] else "")

    def view(self, node: str, terms: set[str]) -> tuple[str, dict[int, str]]:
        """Tier 2: numbered body; long bodies show the header plus a window around lines naming a term or neighbour."""
        self.load([node])
        d = self.nodes[node]
        body = (d["code"] or "").splitlines()
        lines = {d["start"] + i: text for i, text in enumerate(body)}
        keep = set(lines)
        if len(body) > LONG_BODY:
            names = terms | {self.nodes[n["id"]]["name"] for n in self.neighbours(node)}
            word = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(names))) + r")\b") if names else None
            header = next((i for i, t in enumerate(body) if t.rstrip().endswith(":")), 0)
            hits = [d["start"] + i for i, t in enumerate(body) if word and word.search(t) and not t.strip().startswith(("#", ">>>", "..."))]
            keep = set(range(d["start"], d["start"] + header + 1)) | {n for h in hits for n in range(h - WINDOW, h + WINDOW + 1)}
        out, prev = [], None
        for n in sorted(keep & set(lines)):
            if prev is not None and n != prev + 1:
                out.append("  ...")
            out.append(f"{n:>5} {lines[n]}")
            prev = n
        return "\n".join(out) or "(no code in graph)", {n: lines[n] for n in keep & set(lines)}

    def call_line(self, caller: str, callee: str) -> int | None:
        self.load([caller, callee])
        d, name = self.nodes[caller], self.nodes[callee]["name"]
        for i, text in enumerate((d["code"] or "").splitlines()):
            if i and re.search(rf"\b{re.escape(name)}\s*\(", text):
                return d["start"] + i
        return None


# --- state and output ---------------------------------------------------------------------


def _init_state(h: dict, issue_terms: set[str], graph: "_Graph") -> dict:
    preds = {p["id"]: p for p in h["predictions"]}
    st = {
        "id": h["id"], "claim": h["claim"], "refute_if": h["refute_if"], "preds": preds,
        "mechanism": h.get("mechanism", "other"), "targets": [a["node"] for a in h["anchors"] if a["role"] == "target"],
        "terms": _terms(h) | issue_terms, "pred_nodes": {p["node"] for p in h["predictions"]},
        "frontier": [], "tree": {}, "reads": [], "evidence": [], "deviations": [], "co_change": [], "pruned": [],
        "refutes": [], "status": "open", "checked_at": [], "expanding": False, "hints": set(), "belief": PRIOR, "outcomes": [],
        "read_cap": MAX_READS, "expand_reads": EXPAND_READS, "prune": "belief", "search": True,
    }
    weight = {"target": 2.0, "path": 1.0, "entry": 0.5}
    starts: dict[str, float] = {}
    def resolve(node: str, via: str) -> list[str]:
        """A class or file starts from its lane's best neighbours (its members when anchored on itself): only function bodies are read."""
        if node.startswith(_READABLE_IDS):
            return [node]
        lane = [n["id"] for n in graph.neighbours(node) if n["via"] == ("members" if via == "self" else via)]
        return sorted(lane, key=lambda i: -_lex(graph.text({"id": i}), st["terms"]))[:STARTS] or [node]

    for a in h["anchors"]:
        for t in resolve(a["node"], a["via"]):
            starts[t] = max(starts.get(t, 0), weight[a["role"]])
    for p in h["predictions"]:
        for t in resolve(p["node"], p["via"]):
            st["pred_nodes"].add(t)
            starts[t] = starts.get(t, 0) + 2
    st["frontier"] = [{"node": n, "parent": None, "edge": "anchor", "w": 1.0, "depth": 0, "F": f} for n, f in starts.items()]
    return st


def _issue_terms(issue: IssueModel) -> set[str]:
    """Identifiers the issue itself names; they steer every hypothesis, even one that did not repeat them."""
    return {w for r in issue.explicit_code_refs for w in re.findall(r"[A-Za-z_]\w+", r) if len(w) > 2 and w not in {"True", "False", "None"}}


def _terms(h: dict) -> set[str]:
    """Code-looking words of the hypothesis: backticked, snake_case, CamelCase, and anchor names."""
    text = " ".join([h["claim"], h["refute_if"], *(p["text"] for p in h["predictions"])])
    words = set(re.findall(r"`([A-Za-z_][\w.]*)`", text)) | set(re.findall(r"\b[a-z]+_\w+\b|\b[A-Z][a-z]+[A-Z]\w*\b", text))
    words |= {a["node"].split(":")[-1].split(".")[-1] for a in h["anchors"]}
    return {w.split(".")[-1] for w in words if len(w) > 2}


def _lex(text: str, terms: set[str]) -> int:
    return min(3, sum(1 for t in terms if re.search(rf"\b{re.escape(t)}\b", text)))


def _render_h(st: dict, bystander: bool = False) -> str:
    preds = [f"  {pid} [{p['kind']}] {p['text']}" for pid, p in st["preds"].items() if _open(st, pid)]
    note = " (not searching here: only check its predictions)" if bystander else " (supported so far: does this node also have to change?)" if st["expanding"] else ""
    head = f"{st['id']}: {st['claim']}{note}"
    return "\n".join([head, f"  refuted if: {st['refute_if']}", *(preds or ["  (all predictions already checked)"])])


def _out_hypothesis(st: dict, graph: _Graph) -> dict:
    best = max(st["deviations"] or [r["node"] for r in st["reads"]] or [None], key=lambda n: st["tree"].get(n, {}).get("R", 0))
    return {
        "id": st["id"], "status": st["status"], "rule_status": st["status"], "claim": st["claim"],
        "mechanism": st["mechanism"], "targets": st["targets"],
        "predictions": {pid: _pred(st, pid) for pid in st["preds"]},
        "prediction_text": {pid: p["text"] for pid, p in st["preds"].items()},
        "core_confirmed": sum(_pred(st, pid) == "confirmed" for pid, p in st["preds"].items() if p["kind"] == "core"),
        "belief": round(st["belief"], 3), "posterior": round(1 / (1 + math.exp(-st["belief"])), 3), "outcomes": st["outcomes"],
        "deviations": list(dict.fromkeys(st["deviations"])), "co_change": list(dict.fromkeys(st["co_change"])),
        "refuted_by": st["refutes"][0] if st["refutes"] else None, "evidence": st["evidence"], "reads": st["reads"], "checked_at": st["checked_at"],
        "chain": _chain(st, best, graph) if best else None, "pruned": st["pruned"], "prior": st["prior"], "stopped": st.get("stopped"),
    }
