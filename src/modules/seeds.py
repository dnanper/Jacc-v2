"""Artifact A2: seed nodes for one issue, and the issue-to-code vocabulary they reveal.

The graph has no embeddings or summaries, so an issue's plain words reach code only through
searchable text: names, code, and docstrings. One round:

  queries -> one ranked list per query (exact name, then BM25), searched in parallel
          -> RRF over the lists -> top K unjudged nodes -> LLM labels each node
          -> the labels name code terms the issue never used -> next round's queries

Round 1 queries come from the LLM (A1 IssueModel + A0.5) and, deterministically, from the issue's
code snippets, stack trace, and error messages. Recall over precision: 'maybe' nodes and
nodes the LLM skipped stay seeds, since a seed missed here removes its area from every later
step. The artifact also keeps the issue concept each seed implements and the A0.5 facts that
touch seed files, so hypotheses can be written in the code's own terms.
See research/codekg-survey/SEEDS_A2.vn.md.
"""

from __future__ import annotations

import builtins
import keyword
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.issue_model import IssueModel, render_issue_model
from src.modules.repo_explorer.explore._search.bm25_search import _escape_fts_query, _preprocess_query
from src.modules.repo_explorer.graph.schema.code_schema import FTS_INDEXES
from src.modules.repo_profile import Query, _docs, _first_sentence, _is_test, _loc, _name_of, _out_of_scope, _path_of, render_repo_profile

SEEDS_VERSION = 6
TOP_K, MAX_ROUNDS, MAX_CODE_QUERIES, MAX_NEW_QUERIES = 30, 3, 25, 8
# RRF constant. The usual k=60 assumes a few long lists; A2 fuses ~50 lists of <=20, where k=60 flattens
# rank so much that a node hit at rank 5 by three generic queries beats one each query ranks first.
# k=5 chosen on the 27 tuning instances (gold judged 24 -> 26), research/codekg-survey/ISSUES_A2_A3_A4.vn.md §7.
RRF_K = 5
PER_TABLE, PER_QUERY, WORKERS = 10, 20, 8
# A bare name with more exact matches than this (`__init__`, `save`) says little about where to look:
# keep the best few by fan-in so they do not fill the list ahead of BM25 hits.
MAX_EXACT = 3
_CODE_LABELS = frozenset({"File", "Function", "Class", "Method", "Interface", "Struct", "Enum", "Trait", "Const", "Record", "Constructor"})


class SeedQueries(BaseModel):
    queries: list[str] = Field(
        description=(
            "Up to 15 searches of 1-3 words each: identifiers the issue names or implies, and the terms the "
            "code most likely uses for concepts the issue states in plain words (e.g. 'retry backoff' for "
            "'waits longer after each failure')."
        )
    )


class Judgement(BaseModel):
    id: str = Field(description="Candidate alias, e.g. C3.")
    verdict: Literal["relevant", "maybe", "irrelevant"] = Field(
        description="relevant: implements an issue concept or sits on the described path; maybe: plausibly involved; irrelevant: shares words only."
    )
    concept: str = Field(description="The issue concept this node implements, in the issue's own words; empty if irrelevant.")
    reason: str = Field(description="One short clause citing the signature, doc, or calls.")


class Review(BaseModel):
    judgements: list[Judgement]
    new_queries: list[str] = Field(
        description=(
            f"4 to {MAX_NEW_QUERIES} code terms seen in relevant or maybe candidates (callee, parameter, "
            "or class names) that could lead to more involved code and are not in the searched list."
        )
    )


PROPOSE_PROMPT = """You map a bug report onto a code graph. The graph has no embeddings and no \
summaries: only names, code, and docstrings are searchable by keyword. Write search queries that \
will hit the code involved. Recall matters more than precision: an area no query reaches is lost \
to every later step.

{profile}

{issue}"""

REVIEW_PROMPT = """Label every candidate against the issue. Candidates come from keyword search, so \
many share only words with it. Keep recall high: say 'maybe' when unsure, 'irrelevant' only when \
the node cannot be involved.

{issue}

Already searched: {searched}

<candidates>
{candidates}
</candidates>"""


def find_seeds(
    issue: IssueModel,
    profile: dict[str, Any] | None,
    query: Query,
    propose: Runnable,
    review: Runnable,
    *,
    top_k: int = TOP_K,
    rounds: int = MAX_ROUNDS,
) -> dict[str, Any]:
    """`propose`/`review` are `chat.with_structured_output(SeedQueries|Review, strict=True)`."""
    issue_text = render_issue_model(issue)
    lists: dict[str, list[str]] = {}  # query -> ranked node ids
    judged: dict[str, dict[str, Any]] = {}
    calls = 1  # the propose call
    traces = []
    asked: dict[str, list[str]] = {"code": code_queries(issue)}
    with ThreadPoolExecutor(WORKERS) as pool:

        def submit(queries: list[str]) -> dict[str, Any]:
            return {q: pool.submit(search, query, q) for q in queries}

        pending = submit(asked["code"])  # code-derived searches run while the LLM writes its queries
        profile_text = render_repo_profile(profile) if profile else ""
        asked["llm"] = _fresh(propose.invoke(PROPOSE_PROMPT.format(profile=profile_text, issue=issue_text)).queries, asked["code"])
        pending |= submit(asked["llm"])
        for round_no in range(1, rounds + 1):
            batch = {q: f.result() for q, f in pending.items()}
            lists |= batch
            # Fuse every list so far: learned queries add hits, and old lists offer their next tier.
            fused = rrf_scores(lists.values())
            order = _window_order(lists, fused, fresh=batch if round_no > 1 else None, judged=set(judged))
            ranked = order[:top_k]
            fresh_heads = list(dict.fromkeys(next((n for n in hit if n not in judged), None) for hit in batch.values()))
            traces.append({"round": round_no, "retrieved": batch, "fresh_heads": [n for n in fresh_heads if n],
                           "reviewed": ranked, "window_dropped": order[top_k:]})
            if not ranked:
                break
            alias = {f"C{i + 1}": node for i, node in enumerate(ranked)}
            out = review.invoke(
                REVIEW_PROMPT.format(issue=issue_text, searched=", ".join(lists), candidates=_render_candidates(query, alias, lists))
            )
            calls += 1
            verdicts = {alias[j.id.strip()]: j for j in out.judgements if j.id.strip() in alias}
            # v3 asked for full ids and matched them exactly: 37% of seeds came back unmatched and stayed
            # unlabelled. Aliases are short; whatever is still missing is asked once more on its own.
            if missing := {a: n for a, n in alias.items() if n not in verdicts}:
                again = review.invoke(
                    REVIEW_PROMPT.format(issue=issue_text, searched=", ".join(lists), candidates=_render_candidates(query, missing, lists))
                )
                calls += 1
                verdicts |= {missing[j.id.strip()]: j for j in again.judgements if j.id.strip() in missing}
            for node in ranked:
                j = verdicts.get(node)  # a node the LLM skipped twice stays a 'maybe' seed
                judged[node] = {
                    "id": node,
                    "verdict": j.verdict if j else "maybe",
                    "concept": j.concept if j else "",
                    "reason": j.reason if j else "not labelled",
                    "round": round_no,
                    "score": round(fused[node], 5),
                    "hit_by": [q for q, ids in lists.items() if node in ids],
                }
            if round_no == rounds:
                break
            learned = _fresh(out.new_queries, list(lists))[:MAX_NEW_QUERIES]
            asked[f"round{round_no + 1}"] = learned
            pending = submit(learned)  # no new query: the next round still reviews the next fused window
    final_scores = rrf_scores(lists.values())
    for node, seed in judged.items():
        seed["review_score"] = seed["score"]
        seed["score"] = round(final_scores[node], 5)
        seed["hit_by"] = [q for q, ids in lists.items() if node in ids]
    seeds = [s for s in judged.values() if s["verdict"] != "irrelevant"]
    # Relevant before maybe; within each, by fused retrieval score (v3 sorted by round, so a round-3 hit
    # outranked the best hit of round 1). Later steps cut this list, so the order decides what they see.
    seeds.sort(key=lambda s: (s["verdict"] != "relevant", -s["score"]))
    concepts: dict[str, list[str]] = defaultdict(list)
    for s in seeds:
        concepts[s["concept"] or "(unlabelled)"].append(s["id"])
    return {
        "artifact": "A2",
        "version": SEEDS_VERSION,
        "queries": asked,
        "calls": calls,
        "rounds": traces,
        "seeds": seeds,
        "rejected": [s["id"] for s in judged.values() if s["verdict"] == "irrelevant"],
        "concepts": dict(concepts),
        "profile_links": _profile_links(profile or {}, {_path_of(s["id"]) for s in seeds}, issue_text),
    }


# --- queries ------------------------------------------------------------------------

_IDENT = re.compile(r"[A-Za-z_][\w.]*\w")
_FRAME = re.compile(r'File "[^"]*?(\w+)\.\w+", line \d+, in (\w+)|at ([\w$.]+)\(')
_NOISE = frozenset(keyword.kwlist) | frozenset(dir(builtins)) | {"self", "cls", "Out", "In"}


def code_queries(issue: IssueModel) -> list[str]:
    """Queries taken verbatim from the report: named refs, trace frames, error lines, snippet identifiers."""
    frames = [name for groups in _FRAME.findall(issue.stack_trace) for name in groups if name]
    errors = [e.strip()[:100] for e in issue.error_messages]  # a raise site's code contains its message
    idents = [i for s in issue.code_snippets for i in _IDENT.findall(s) if i not in _NOISE]
    return _fresh([*issue.explicit_code_refs, *frames, *errors, *idents], [])[:MAX_CODE_QUERIES]


def _fresh(queries: list[str], seen: list[str]) -> list[str]:
    """Strip, drop short and already-searched queries, dedupe case-insensitively."""
    keys = {q.lower() for q in seen}
    out = []
    for q in (q.strip() for q in queries):
        if len(q) > 2 and q.lower() not in keys:
            keys.add(q.lower())
            out.append(q)
    return out


# --- retrieval ----------------------------------------------------------------------


def search(query: Query, text: str) -> list[str]:
    """One ranked list for one query: exact-name matches first, then BM25 over every FTS index.

    Docstring (Section) hits count for the symbol they describe. Test and script code is dropped.
    A qualified query ('Owner.name') ranks the symbols whose qualified name ends with it first, so
    'TemplateCommand.handle' is not lost among every other 'handle'.
    """
    text = text.strip().strip("()")
    files = _file_hits(query, text)
    parts = re.split(r"[.:/#]+", text)
    names = {text, parts[-1]}
    tail = "." + ".".join(parts[-2:])
    try:
        exact = query("MATCH (n) WHERE n.name IN $names RETURN n.id AS id, n.filePath AS path, n.fanIn AS fan_in", {"names": sorted(names)})
    except RuntimeError:  # the driver reads a list-looking string ('[2]') as a list literal; no name can match it
        exact = []
    exact.sort(key=lambda r: (len(parts) > 1 and not ("." + r["id"].rsplit(":", 1)[-1]).endswith(tail), -(r["fan_in"] or 0)))
    owned = [r for r in exact if len(parts) > 1 and ("." + r["id"].rsplit(":", 1)[-1]).endswith(tail)]
    exact = owned or exact[:MAX_EXACT]  # a qualified match is specific; a bare name keeps only its best few
    fts = _escape_fts_query(_preprocess_query(text))
    scored: dict[str, float] = {}
    for index, table, _ in FTS_INDEXES:
        target = "t" if table == "Section" else "node"
        describes = " WITH node, score MATCH (node)-[r:CodeRelation]->(t) WHERE r.type = 'DESCRIBES'" if target == "t" else ""
        try:
            rows = query(
                f"CALL QUERY_FTS_INDEX('{table}', '{index}', '{fts}', conjunctive := false){describes} "
                f"RETURN {target}.id AS id, {target}.filePath AS path, score ORDER BY score DESC LIMIT {PER_TABLE}",
                None,
            )
        except Exception:  # tables empty for this language have no index
            continue
        for row in rows:
            if not _is_test(row["path"] or ""):
                scored[row["id"]] = max(scored.get(row["id"], 0.0), row["score"])
    ids = files + [r["id"] for r in exact if r["id"].split(":", 1)[0] in _CODE_LABELS and not _is_test(r["path"] or "")]
    ids += sorted(scored, key=lambda i: -scored[i])
    # Script dirs (examples/, benchmarks/, docs/) rank after library code instead of being dropped: 7 Loc-Bench
    # instances have all their gold there. Tests stay out (no gold on the three benchmarks is a test file).
    return sorted(dict.fromkeys(ids), key=lambda i: _out_of_scope(_path_of(i)))[:PER_QUERY]


def _file_hits(query: Query, text: str) -> list[str]:
    """File nodes a path or dotted module in the query names: 'requests/sessions.py', an absolute trace path
    '/usr/.../_pytest/runner.py', 'astropy.modeling.separable'. v3 split these on '/' and '.' and searched
    'py' or the last segment, so the reporter's own file reference never hit the file."""
    path = text.strip("`'\" ").replace("\\", "/").strip("/")
    if re.fullmatch(r"[\w./-]+\.(py|java)", path):  # a file path, or a bare file name
        path = path.rsplit(".", 1)[0]
    elif re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)+", path):  # a dotted module
        path = path.replace(".", "/")
    else:
        return []
    stem = path.rsplit("/", 1)[-1]
    if len(stem) < 3:
        return []
    rows = query("MATCH (n:File) WHERE n.name IN $names RETURN n.id AS id, n.filePath AS path",
                 {"names": [f"{stem}.py", f"{stem}.java", "__init__.py"]})
    # The file path must end the query path (absolute trace path) or be ended by it (partial path).
    want = [path + ".py", path + ".java", path + "/__init__.py"]
    hit = lambda f: any(("/" + w).endswith("/" + f) or f.endswith("/" + w) or f == w for w in want)
    hits = [r for r in rows if r["path"] and hit(r["path"]) and not _is_test(r["path"])]
    return [r["id"] for r in sorted(hits, key=lambda r: -len(r["path"]))[:MAX_EXACT]]



def rrf_scores(lists: Any) -> dict[str, float]:
    """Reciprocal rank fusion: a node hit by many queries beats one ranked first by a single query."""
    score: dict[str, float] = defaultdict(float)
    for ranked in lists:
        for rank, node in enumerate(ranked):
            score[node] += 1 / (RRF_K + rank + 1)
    return score


def _window_order(lists: dict[str, list[str]], fused: dict[str, float], *,
                  fresh: dict[str, list[str]] | None = None, judged: set[str] = frozenset()) -> list[str]:
    """Unique review slots. Later rounds reserve their fresh queries' strongest unjudged hits before
    old heads/RRF; the caller still applies the same top_k and round budgets."""
    first = lambda hits: next((n for n in hits if n not in judged), None)
    heads = dict.fromkeys(hit[0] for hit in lists.values() if hit)
    new = dict.fromkeys(n for hit in (fresh or {}).values() if (n := first(hit)))
    rank = lambda nodes: sorted(nodes, key=lambda n: -fused[n])
    return [n for n in dict.fromkeys([*rank(new), *rank(heads), *rank(fused)]) if n not in judged]


def rrf(lists: Any) -> list[str]:
    score = rrf_scores(lists)
    return sorted(score, key=lambda n: -score[n])


def _render_candidates(query: Query, alias: dict[str, str], batch: dict[str, list[str]]) -> str:
    ids = list(alias.values())
    rows = query("MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, n.signature AS sig, substring(n.content, 1, 200) AS code", {"ids": ids})
    sig = {r["id"]: r["sig"] or (r["code"] or "").strip().split("\n")[0] for r in rows}
    calls: dict[str, list[str]] = defaultdict(list)
    for r in query(
        "MATCH (n)-[r:CodeRelation]->(m) WHERE r.type = 'CALLS' AND n.id IN $ids RETURN n.id AS id, m.name AS callee", {"ids": ids}
    ):
        if r["callee"] not in calls[r["id"]]:
            calls[r["id"]].append(r["callee"])
    docs = _docs(query, ids)
    lines = []
    for a, node in alias.items():
        parts = [f"{a} {_loc(node)}", " ".join((sig.get(node) or "").split())[:160]]
        parts += [f"doc: {docs[node]}"] if docs.get(node) else []
        parts += [f"calls: {', '.join(calls[node][:6])}"] if calls[node] else []
        parts.append("hit by: " + ", ".join(q for q, hit in batch.items() if node in hit))
        lines.append("- " + " | ".join(p for p in parts if p))
    return "\n".join(lines)


def _profile_links(profile: dict[str, Any], files: set[str], issue_text: str) -> list[str]:
    """A0.5 facts that touch a seed file, or name an exception the issue mentions."""
    out = [
        f"family {_loc(f['base'])}: hooks {', '.join(f['hooks']) or 'none'}"
        for f in profile.get("families", [])
        if _path_of(f["base"]) in files
    ]
    out += [
        f"dispatch {d['calls_methods_named']} from {', '.join(_loc(i) for i in d['dispatchers'])}"
        for d in profile.get("dispatch", [])
        if any(_path_of(i) in files for i in d["dispatchers"])
    ]
    out += [
        f"exception {_loc(e['exception'])} raised in {', '.join(_loc(s) for s in e['raised_in'])}"
        for e in profile.get("errors", [])
        if _name_of(e["exception"]) in issue_text or any(_path_of(s) in files for s in e["raised_in"])
    ]
    return out


# --- rendering for downstream steps -------------------------------------------------


def render_seeds(seeds: dict[str, Any]) -> str:
    by_id = {s["id"]: s for s in seeds["seeds"]}
    lines = [
        '<issue_repo_map artifact="A2">',
        "Seed nodes from keyword search, labelled against the issue by an LLM. Unverified starting points, not answers.",
        "## Issue concept -> code",
    ]
    for concept, ids in seeds["concepts"].items():
        lines.append(f"- {concept}:")
        lines += [f"  - {_loc(i)} [{by_id[i]['verdict']}] {_first_sentence(by_id[i]['reason'], 120)}" for i in ids]
    if seeds["profile_links"]:
        lines += ["## Repo facts touching seed files", *(f"- {link}" for link in seeds["profile_links"])]
    searched = [q for qs in seeds["queries"].values() for q in qs]
    lines += [f"Searched: {', '.join(searched)}", "</issue_repo_map>"]
    return "\n".join(lines)
