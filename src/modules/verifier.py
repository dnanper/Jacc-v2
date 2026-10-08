"""Design v3 Phase 2 (DESIGN_PROBABILISTIC_EDITSET.vn.md, amendments A4, A5): a listwise verifier, one LLM call per instance.

It sees the issue and the code of the top candidates of the Ranked-prior list, never the hypotheses that ranked
them (so it cannot inherit A3's framing), in an order shuffled by the instance id (so it cannot read the prior
rank from the position). It labels each candidate as edited / maybe / not_edited by the patch that resolves the
issue, counting consistency edits in related functions, ranks up to five, and (v2) estimates how many functions the
patch changes in total. Its output is evidence for the calibrator, not an answer. v1 showed the top 15, v2 the top 40.

`complete` (amendment A5b) is v2's second call: given the function the verifier ranked first, it asks which of that
function's class mates, file mates and same-named methods elsewhere the same patch also changes.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.hypotheses import _words
from src.modules.region_sites import MAX_PROMPT_CHARS, _view
from src.modules.repo_profile import Query, _is_test, _loc

VERIFIER_VERSION = 2
MAX_SHOWN = 40  # v1: 15


class Verdict(BaseModel):
    candidate: str = Field(description="Candidate alias, e.g. C3.")
    label: Literal["edited", "maybe", "not_edited"] = Field(description="Whether the patch that resolves the issue most likely changes this function.")
    reason: str = Field(description="One sentence grounded in the shown code.")


class Verification(BaseModel):
    verdicts: list[Verdict] = Field(description="One verdict per shown candidate.")
    ranking: list[str] = Field(description="Up to 5 aliases, the most likely edited first.")
    edited_count: int = Field(description="How many functions in total the patch most likely changes, shown or not.")


PROMPT = """A developer wrote one patch that resolves the issue below. Decide which of the shown functions that patch \
changes.

Rules:
- Judge each function by its shown code and the issue, not by its name alone.
- A patch often also changes related functions for consistency: sibling overrides, every caller whose call must \
change, a helper and its user. Label those edited too when the issue implies the change reaches them.
- edited: the patch most likely changes this function; maybe: plausible but not clear from what is shown; \
not_edited: the function is only related to the issue.
- Give one verdict for every candidate, then rank up to five aliases, the most likely edited first.
- Estimate how many functions in total the patch changes, including any not shown.

<issue>
{issue}
</issue>

<candidates>
{candidates}
</candidates>"""


def verify(issue: str, nodes: list[str], query: Query, terms: set[str], snapshot_root: Path, llm: Runnable, seed: str,
           max_shown: int = MAX_SHOWN) -> dict[str, Any]:
    """`llm` must be `chat.with_structured_output(Verification, strict=True)`; `nodes` are already in prior order."""
    shown = list(dict.fromkeys(nodes))[:max_shown]
    random.Random(seed).shuffle(shown)
    alias = {f"C{i + 1}": n for i, n in enumerate(shown)}
    cache: dict = {}
    blocks = [f"{a} {_loc(n)}\n{_view(n, query, terms, snapshot_root, cache=cache)[0]}" for a, n in alias.items()]
    prompt = PROMPT.format(issue=issue, candidates="\n\n".join(blocks))
    out: dict[str, Any] = {"artifact": "V", "version": VERIFIER_VERSION, "shown": shown, "prompt_chars": len(prompt),
                           "labels": {}, "ranking": [], "calls": 0}
    if len(prompt) > MAX_PROMPT_CHARS:
        out["status"] = "input_budget"
        return out
    result = llm.invoke(prompt)
    out["calls"] = 1
    for v in result.verdicts:
        if v.candidate in alias and alias[v.candidate] not in out["labels"]:
            out["labels"][alias[v.candidate]] = v.label
    out["ranking"] = list(dict.fromkeys(alias[a] for a in result.ranking if a in alias))[:5]
    out["edited_count"] = max(0, result.edited_count)
    out["status"] = "ok"
    return out


MAX_COMPLETION, MAX_SAME_NAME, PRIMARY_LINES = 30, 10, 60
_FUNCS = "(label(n) = 'Function' OR label(n) = 'Method' OR label(n) = 'Constructor')"


class CoEdit(BaseModel):
    candidate: str = Field(description="Candidate alias, e.g. K3.")
    label: Literal["also", "maybe", "no"] = Field(description="Whether the same patch also changes this function.")
    reason: str = Field(description="One sentence grounded in the shown code.")


class Completion(BaseModel):
    decisions: list[CoEdit] = Field(description="One decision per shown candidate.")


COMPLETE_PROMPT = """A developer wrote one patch that resolves the issue below, and it changes the primary function. \
Decide which of the other shown functions the same patch also changes.

Rules:
- Patches often repeat the same fix in sibling methods or overrides, update callers whose call must change, or \
keep related methods of the same class consistent. Answer also for those.
- also: the same patch most likely changes it too; maybe: plausible; no: it can stay as it is.
- Judge by the shown code and the issue. Give one decision for every candidate.

<issue>
{issue}
</issue>

<primary>
{primary}
</primary>

<candidates>
{candidates}
</candidates>"""


def completion_candidates(primary: str, query: Query, terms: set[str]) -> list[str]:
    """Class mates, then file mates by issue-word overlap, then same-named methods elsewhere; tests excluded."""
    path = primary.split(":", 2)[1]
    mates = [r["id"] for r in query("MATCH (c)-[h:CodeRelation]->(p) WHERE p.id = $id AND h.type = 'HAS_METHOD' "
                                     "MATCH (c)-[r:CodeRelation]->(m) WHERE r.type = 'HAS_METHOD' RETURN m.id AS id ORDER BY m.startLine LIMIT 200", {"id": primary})]
    want = _words(" ".join(terms))
    rows = query(f"MATCH (n) WHERE n.filePath = $path AND {_FUNCS} RETURN n.id AS id, n.startLine AS start LIMIT 400", {"path": path})
    same_file = [r["id"] for r in sorted(rows, key=lambda r: (-len(_words(_loc(r["id"]).split("::")[-1]) & want), r["start"] or 0))]
    name = primary.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
    same_name = [r["id"] for r in query(f"MATCH (n) WHERE n.name = $name AND n.filePath <> $path AND {_FUNCS} RETURN n.id AS id ORDER BY n.id LIMIT 50",
                                        {"name": name, "path": path}) if not _is_test(r["id"].split(":", 2)[1])][:MAX_SAME_NAME]
    out = [n for n in dict.fromkeys([*mates, *same_file, *same_name]) if n != primary and not _is_test(n.split(":", 2)[1])]
    return out[:MAX_COMPLETION]


def complete(issue: str, primary: str, query: Query, terms: set[str], snapshot_root: Path, llm: Runnable) -> dict[str, Any]:
    """`llm` must be `chat.with_structured_output(Completion, strict=True)`."""
    nodes = completion_candidates(primary, query, terms)
    alias = {f"K{i + 1}": n for i, n in enumerate(nodes)}
    rows = query("MATCH (n) WHERE n.id = $id RETURN n.content AS code, n.startLine AS start LIMIT 1", {"id": primary})
    body = (rows[0].get("code") or "").splitlines()[:PRIMARY_LINES] if rows else []
    start = (rows[0].get("start") or 1) if rows else 1
    cache: dict = {}
    prompt = COMPLETE_PROMPT.format(issue=issue, primary=_loc(primary) + "\n" + "\n".join(f"{start + i:>5} {t[:120]}" for i, t in enumerate(body)),
                                    candidates="\n\n".join(f"{a} {_loc(n)}\n{_view(n, query, terms, snapshot_root, cache=cache)[0]}" for a, n in alias.items()))
    out: dict[str, Any] = {"artifact": "C", "version": VERIFIER_VERSION, "primary": primary, "shown": nodes,
                           "prompt_chars": len(prompt), "labels": {}, "calls": 0}
    if not nodes or len(prompt) > MAX_PROMPT_CHARS:
        out["status"] = "no_candidates" if not nodes else "input_budget"
        return out
    result = llm.invoke(prompt)
    out["calls"] = 1
    for d in result.decisions:
        if d.candidate in alias and alias[d.candidate] not in out["labels"]:
            out["labels"][alias[d.candidate]] = d.label
    out["status"] = "ok"
    return out
