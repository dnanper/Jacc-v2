"""Artifact A3: competing hypotheses about where the fix must edit code, anchored to A2 seed nodes.

One LLM call reads the whole seed pool at once, so it sees how seeds relate (the call edges
between them) and does not write the same hypothesis twice. The harness controls both ends:

- input: A1 facts, every seed under a short alias (S1..Sn), and, for relevant seeds only, the
  few body lines that contain an issue identifier (the first body lines when none does, so a
  target is never picked on its signature alone). Then the signatures of the other functions in
  files that hold a relevant seed, aliased after the seeds: the edit site is often a sibling of
  the seed A2 found. Then the graph edges among all of them. Never full code.
- output: a strict schema. Each hypothesis separates `basis` (facts seen in the input, the
  abduction) from `predictions` (what unseen code must show if it is true, the deduction left
  to exploration), and each prediction names the seed and the edge type to follow from it.
- checks: unknown aliases are dropped, a hypothesis without a target anchor, a core prediction,
  or a refute condition is dropped, and duplicates (same targets + mechanism) are merged. Every
  drop is recorded. No scores: list order is the model's ranking, used only to break ties.

See research/codekg-survey/HYPOTHESES_A3.vn.md.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from itertools import zip_longest
from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.issue_model import IssueModel
from src.modules.repo_profile import Query, _docs, _loc

HYPOTHESES_VERSION = 8
MAX_SEEDS, MAX_LINES, MAX_PREDICTIONS, SAMPLES = 40, 6, 3, 2
MAX_FILE_FUNCS = 40  # signatures listed per file that holds a relevant seed
_READABLE = ("Function:", "Method:", "Constructor:")  # node kinds whose body a later step can read
_EDGES = ("CALLS", "EXTENDS", "IMPLEMENTS", "OVERRIDES", "HAS_METHOD", "RAISES")

Via = Literal["self", "calls", "called_by", "overrides", "extends", "members", "raises"]
_VIA = "self: the seed itself; calls/called_by: its callees/callers; overrides, extends, members, raises: those edges from it."


class Anchor(BaseModel):
    seed: str = Field(description="Seed alias, e.g. S3.")
    role: Literal["entry", "target", "path"] = Field(
        description=(
            "target: code the fix edits (a function whose body changes, or where new code is added); "
            "entry: where the issue scenario enters code; path: passed through between them."
        )
    )
    via: Via = Field(description=f"Which node the anchor means. {_VIA} Use a non-self value when the defect is next to the seed, not in it.")


class Basis(BaseModel):
    seed: str = Field(description="Seed alias.")
    fact: str = Field(description="A fact shown in the input (a quoted line, signature, or edge) that suggests this hypothesis.")


class Prediction(BaseModel):
    text: str = Field(
        description=(
            "One atomic fact (no 'and') about code NOT shown in the input, checkable at one line, that the fix "
            "would change. For a bug: the faulty line itself, e.g. 'the retry loop compares attempts with <= instead of <', "
            "not code that is right either way; for something missing, the line where it belongs. For a feature or "
            "enhancement: the current limitation at the place the new behaviour must go, e.g. 'the format branch "
            "handles only csv and json'."
        )
    )
    kind: Literal["core", "aux"] = Field(description="core: must hold if the hypothesis is true; aux: usually holds.")
    seed: str = Field(description="Seed alias where checking starts; with via=self it must be a function or method seed.")
    via: Via = Field(description=f"Where to look from that seed. {_VIA}")


class Hypothesis(BaseModel):
    claim: str = Field(description="One sentence: what must change, in which function(s), and why the issue follows from the current code.")
    mechanism: Literal[
        "wrong_condition", "wrong_argument", "missing_step", "exception_path", "wrong_mapping",
        "wrong_dispatch", "state_mutation", "missing_feature", "other",
    ]
    explains: list[Literal["observed", "expected", "error", "trace"]] = Field(description="Parts of the issue this hypothesis accounts for.")
    anchors: list[Anchor] = Field(description="Every function the fix edits is a target, most important first; add entry/path anchors only if they help reading.")
    basis: list[Basis]
    predictions: list[Prediction] = Field(description=f"At most {MAX_PREDICTIONS}, core first.")
    refute_if: str = Field(description="An observation in the code that would prove this hypothesis wrong.")


class HypothesisSet(BaseModel):
    hypotheses: list[Hypothesis] = Field(description="2 to 7 hypotheses, the most likely edit sites first.")


class LeanHypothesis(BaseModel):
    """Design v3 amendment A6 (`--mode v6`): only what V6 reads; no basis, predictions, refute_if or explains."""
    claim: str = Field(description="One sentence: what must change, where.")
    mechanism: Hypothesis.model_fields["mechanism"].annotation  # type: ignore[valid-type]
    anchors: list[Anchor] = Field(description="Every function the fix edits is a target, most important first.")


class LeanHypothesisSet(BaseModel):
    hypotheses: list[LeanHypothesis] = Field(description="2 to 7 hypotheses, the most likely edit sites first.")


PROMPT = """You localize an issue in a code graph: find the functions a fix must edit. Write competing \
hypotheses, each naming the edit sites as `target` anchors on the nodes below: the seeds a search \
found, and the other functions of the files those seeds are in.

Rules:
- A target is where the code changes, not where the symptom shows. When a caller passes data to a \
callee that does the faulty work (formats, compares, converts, builds), the callee is the target, \
unless the fix belongs in the caller itself (it calls the wrong function or passes the wrong value).
- A fix that changes several functions (sibling overrides, every call site, a helper and its user) \
lists each as a target in one hypothesis.
- For a feature or enhancement, the target is where the new behaviour must be added or wired in.
- basis is what you see below; predictions are about code you have not seen, which a later step reads.
- Predictions of different hypotheses should differ, so reading code can tell them apart.
- One seed may anchor several hypotheses and one hypothesis several seeds. If the defect sits \
next to a seed (caller, callee, override, member), anchor that seed with the matching `via`.
- Every hypothesis needs a `target` anchor, a `core` prediction, and `refute_if`, or it is discarded.
- Leave out seeds no hypothesis needs.

<issue>
{issue}
</issue>

<seeds>
{seeds}
</seeds>

<functions_in_seed_files>
{file_funcs}
</functions_in_seed_files>

<edges>
{edges}
</edges>
{links}"""


LEAN_PROMPT = """Find the functions a fix for this issue must edit. Write competing hypotheses; each names its edit \
sites as `target` anchors on the nodes below (search hits and the other functions of their files).

- A target is where the code changes, not where the symptom shows: when a caller passes data to a callee that \
does the faulty work, the callee is the target, unless the caller calls the wrong function or passes the wrong value.
- A fix that changes several functions (sibling overrides, every call site, a helper and its user) lists each as \
a target of one hypothesis. For a feature, the target is where the new behaviour is added or wired in.
- If the defect sits next to a node (caller, callee, override, member), anchor that node with the matching `via`.
""" + PROMPT[PROMPT.index("<issue>"):]


def generate_hypotheses(issue: IssueModel, seeds: dict[str, Any], query: Query, llm: Runnable, *, samples: int = SAMPLES, lean: bool = False) -> dict[str, Any]:
    """`llm` must be `chat.with_structured_output(LeanHypothesisSet if lean else HypothesisSet, strict=True)`.
    `lean` (amendment A6) asks only for claim, mechanism and anchors with a shorter prompt.

    The same prompt is sampled `samples` times in parallel and the sets are pooled: one sample
    often misses the hypothesis that matters. Duplicates (same targets + mechanism) merge in
    `_check`. Sampling only diversifies on a model that samples (temperature > 0).
    """
    pool = [s["id"] for s in seeds["seeds"]][:MAX_SEEDS]
    alias = {f"S{i + 1}": node for i, node in enumerate(pool)}
    by_id = {s["id"]: s for s in seeds["seeds"]}
    terms = _terms(issue, seeds)
    seed_text = _render_seeds(query, alias, by_id, terms)
    funcs = _file_functions(query, [n for n in pool if by_id[n]["verdict"] == "relevant"], set(pool), terms)
    for node, _ in funcs:  # same alias space, so the checks and resolve_aliases need nothing new
        alias[f"S{len(alias) + 1}"] = node
    back = {node: name for name, node in alias.items()}
    prompt = (LEAN_PROMPT if lean else PROMPT).format(
        issue=_render_issue(issue),
        seeds=seed_text,
        file_funcs="\n".join(f"{back[node]} {text}" for node, text in funcs) or "(none)",
        edges=_render_edges(query, alias) or "(none)",
        links=("\n<repo_facts>\n" + "\n".join(seeds["profile_links"]) + "\n</repo_facts>") if seeds.get("profile_links") else "",
    )
    sets = [out.hypotheses for out in llm.batch([prompt] * samples)]
    # Interleave the samples so each one's top-ranked hypotheses come first; list order is the ranking.
    tagged = [[(k, h) for h in s] for k, s in enumerate(sets)]
    pooled = [x for rank in zip_longest(*tagged) for x in rank if x is not None]
    kept, dropped = _check([h for _, h in pooled], alias, origin=[k for k, _ in pooled], lean=lean)
    for h in kept:
        resolve_aliases(h, alias)
    index: dict[str, list[str]] = defaultdict(list)
    for h in kept:
        for node in dict.fromkeys(a["node"] for a in h["anchors"]):
            index[node].append(h["id"])
    parts = {"observed": issue.observed, "expected": issue.expected, "error": issue.error_messages, "trace": issue.stack_trace}
    for h in kept:  # a hypothesis cannot explain a part the issue does not have
        h["explains"] = [e for e in h["explains"] if parts[e]]
    explained = {e for h in kept for e in h["explains"]}
    return {
        "artifact": "A3",
        "version": HYPOTHESES_VERSION,
        "hypotheses": kept,
        "dropped": dropped,
        "seed_index": dict(index),
        "reserve": [node for node in pool if node not in index],
        "uncovered": [] if lean else [p for p, value in parts.items() if value and p not in explained],
        "low_diversity": len(kept) > 1 and len({h["mechanism"] for h in kept}) == 1,
        "prompt_chars": len(prompt),
        "samples": samples,
        "sampled": sum(len(x) for x in sets),
        "lean": lean,
    }


def resolve_aliases(h: dict, alias: dict[str, str]) -> None:
    """Aliases back to graph ids in place, also inside free text (claim, refute_if, facts, predictions)."""
    name = lambda m: _loc(alias[m.group(0)]).split("::")[-1] if m.group(0) in alias else m.group(0)
    unalias = lambda text: re.sub(r"\b[A-Z]\d+\b", name, text)
    h["claim"], h["refute_if"] = unalias(h["claim"]), unalias(h["refute_if"])
    for field in ("anchors", "basis", "predictions"):
        h[field] = [{"node": alias.get(x["seed"], x["seed"]), **{k: unalias(v) if k in ("fact", "text") else v for k, v in x.items() if k != "seed"}} for x in h[field]]


# --- output checks ---------------------------------------------------------------------


def _check(raw: list[Hypothesis], alias: dict[str, str], basis_refs: frozenset[str] = frozenset(), origin: list[int] | None = None,
           lean: bool = False) -> tuple[list[dict], list[dict]]:
    """Drop unknown aliases and incomplete hypotheses, merge duplicates, then number H1..Hn.

    `basis_refs` are extra ids a basis may cite (A5: anomalies O..); a basis is reasoning, not a node to read.
    `origin[n]` is the sample raw[n] came from; when given, each kept hypothesis lists the samples that
    proposed it, merged duplicates included (`sample_ids`), so sample agreement can be scored later.
    `lean` hypotheses carry no basis, predictions, refute_if or explains: they get empty values and only the
    target anchor is required.
    """
    kept: list[dict] = []
    dropped: list[dict] = []
    by_key: dict[tuple, dict] = {}
    for n, h in enumerate(raw, 1):
        d = {"basis": [], "predictions": [], "refute_if": "", "explains": [], **h.model_dump()}
        for field in ("anchors", "basis", "predictions"):
            known = alias.keys() | basis_refs if field == "basis" else alias.keys()
            bad = [x["seed"] for x in d[field] if x["seed"] not in known]
            if bad:
                dropped.append({"hypothesis": n, "reason": f"unknown seed in {field}: {', '.join(bad)}"})
            d[field] = [x for x in d[field] if x["seed"] in known]
        # A class or file body cannot be read as one window; such a prediction must point through an edge.
        unreadable = [p["seed"] for p in d["predictions"] if p["via"] == "self" and not alias[p["seed"]].startswith(_READABLE)]
        if unreadable:
            dropped.append({"hypothesis": n, "reason": f"prediction at unreadable node: {', '.join(unreadable)}"})
        d["predictions"] = [p for p in d["predictions"] if not (p["via"] == "self" and not alias[p["seed"]].startswith(_READABLE))]
        d["predictions"] = sorted(d["predictions"], key=lambda p: p["kind"] != "core")[:MAX_PREDICTIONS]
        missing = [
            what for what, ok in (
                ("target anchor", any(a["role"] == "target" for a in d["anchors"])),
                ("core prediction", lean or any(p["kind"] == "core" for p in d["predictions"])),
                ("refute_if", lean or d["refute_if"].strip()),
            ) if not ok
        ]
        if missing:
            dropped.append({"hypothesis": n, "reason": "missing " + ", ".join(missing), "raw": h.model_dump()})
            continue
        targets = frozenset((a["seed"], a["via"]) for a in d["anchors"] if a["role"] == "target")
        key = (targets, d["mechanism"])
        if key in by_key:  # same place, same mechanism: one hypothesis with both prediction sets
            first = by_key[key]
            for field in ("anchors", "basis", "predictions", "explains"):
                first[field] += [x for x in d[field] if x not in first[field]]
            first["predictions"] = sorted(first["predictions"], key=lambda p: p["kind"] != "core")[:MAX_PREDICTIONS]
            dropped.append({"hypothesis": n, "reason": f"merged into {first['id']}", "claim": d["claim"]})
            if origin is not None:
                first["sample_ids"].append(origin[n - 1])
            continue
        d["id"] = f"H{len(kept) + 1}"
        if origin is not None:
            d["sample_ids"] = [origin[n - 1]]
        by_key[key] = d
        kept.append(d)
    for h in kept:
        for i, p in enumerate(h["predictions"], 1):
            p["id"] = f"{h['id']}.P{i}"
    return kept, dropped


# --- input rendering -------------------------------------------------------------------


def _render_issue(issue: IssueModel) -> str:
    """Facts only: the model's own assumptions and unknowns would anchor it to its first guess."""
    keep = ("title", "issue_type", "summary", "scenario", "observed", "expected", "error_messages", "stack_trace", "code_snippets", "reporter_hypotheses")
    data = issue.model_dump(include=set(keep))
    return json.dumps({k: data[k] for k in keep if data[k]}, indent=1)


def _terms(issue: IssueModel, seeds: dict[str, Any]) -> set[str]:
    """Identifiers the issue names, split into words, for picking body lines worth showing."""
    raw = [*issue.explicit_code_refs, *seeds.get("queries", {}).get("code", [])]
    return {w for r in raw for w in re.findall(r"[A-Za-z_]\w+", r) if len(w) > 2 and w not in {"True", "False", "None"}}


def _render_seeds(query: Query, alias: dict[str, str], by_id: dict[str, dict], terms: set[str]) -> str:
    ids = list(alias.values())
    rows = {r["id"]: r for r in query("MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, n.signature AS sig, n.content AS code, n.startLine AS start", {"ids": ids})}
    docs = _docs(query, ids)
    lines = []
    for name, node in alias.items():
        seed, row = by_id[node], rows.get(node, {})
        sig = " ".join((row.get("sig") or "").split())[:160]
        head = f"{name} {_loc(node)} [{seed['verdict']}]" + (f" {sig}" if sig else "")
        body = [f"   concept: {seed['concept']}"] if seed.get("concept") else []
        body += [f"   doc: {docs[node]}"] if docs.get(node) else []
        if seed["verdict"] == "relevant":
            body += [f"   L{n} {text}" for n, text in _matching_lines(row.get("code") or "", row.get("start") or 1, terms, node.startswith(_READABLE))]
        lines += [head, *body]
    return "\n".join(lines)


def _matching_lines(code: str, start: int, terms: set[str], first: bool = False) -> list[tuple[int, str]]:
    """Up to MAX_LINES body lines (no header, docstring, or comment) containing an issue identifier;
    with `first`, the first body lines when none does."""
    word = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(terms))) + r")\b" if terms else r"(?!)")
    lines = code.splitlines()
    header = next((i for i, line in enumerate(lines) if line.rstrip().endswith(":")), 0)  # a def may span lines
    out, in_doc = [], False
    body = []
    for offset, line in enumerate(lines):
        text = line.strip()
        quotes = text.count('"""') + text.count("'''")
        if in_doc or quotes:
            in_doc ^= quotes % 2 == 1  # ponytail: odd triple-quote count toggles; breaks on quotes inside strings
            continue
        if offset <= header or not text or text.startswith("#"):
            continue
        body.append((start + offset, text[:120]))
        if word.search(text):
            out.append((len(set(word.findall(text))), start + offset, text[:120]))
    # Lines naming more distinct issue terms first, then shown in source order; else the body's first lines.
    return sorted((n, t) for _, n, t in sorted(out, key=lambda r: -r[0])[:MAX_LINES]) or body[: MAX_LINES * first]


def _file_functions(query: Query, relevant: list[str], seen: set[str], terms: set[str]) -> list[tuple[str, str]]:
    """(node, 'path::name(params)') for the functions of files holding a relevant seed, not already seeds.

    A file with more than MAX_FILE_FUNCS functions keeps the names sharing the most words with the
    issue terms. Files in seed order, functions in source order.
    """
    files = list(dict.fromkeys(node.split(":", 2)[1] for node in relevant))
    rows = query(
        "MATCH (n) WHERE n.filePath IN $p AND (label(n) = 'Function' OR label(n) = 'Method' OR label(n) = 'Constructor') "
        "RETURN n.id AS id, n.filePath AS path, n.signature AS sig, n.startLine AS start",
        {"p": files},
    )
    want = _words(" ".join(terms))
    out = []
    for path in files:
        mine = [r for r in rows if r["path"] == path and r["id"] not in seen]
        mine = sorted(mine, key=lambda r: (-len(_words(_loc(r["id"]).split("::")[-1]) & want), r["start"] or 0))[:MAX_FILE_FUNCS]
        for r in sorted(mine, key=lambda r: r["start"] or 0):
            sig = " ".join((r["sig"] or "").split())
            out.append((r["id"], f"{_loc(r['id'])}{sig[sig.find('('):][:100] if '(' in sig else ''}"))
    return out


def _words(text: str) -> set[str]:
    """Lower-case identifier parts: 'getOutput_size' -> {'get', 'output', 'size'}."""
    return {w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", text) if len(w) > 2}


def _render_edges(query: Query, alias: dict[str, str]) -> str:
    back = {node: name for name, node in alias.items()}
    rows = query(
        "MATCH (a)-[r:CodeRelation]->(b) WHERE a.id IN $ids AND b.id IN $ids AND r.type IN $types RETURN a.id AS a, r.type AS t, b.id AS b",
        {"ids": list(alias.values()), "types": list(_EDGES)},
    )
    return "\n".join(sorted({f"{back[r['a']]} -{r['t']}-> {back[r['b']]}" for r in rows}))
