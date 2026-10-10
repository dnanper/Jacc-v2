"""A3R: bounded region discovery, then one evidence-based edit-set selection.

Budgets count unique new sites, not repeated roots. Discovery nodes and displayed sites are distinct:
a displayed first-hop node may still lead to hop two. Relations propose candidates, never prove edits.
No graph writes, history mining, variable-length paths, or instance-specific rules.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from itertools import zip_longest
from pathlib import Path
from typing import Any, Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.modules.exploration import _cited, _issue_terms, _terms
from src.modules.hypotheses import _matching_lines, _render_issue, _words
from src.modules.issue_model import IssueModel
from src.modules.repo_profile import Query, _is_test, _loc

EDIT_REGIONS_VERSION = 2
_FUNCTIONS = ("Function:", "Method:", "Constructor:")
_ROOTS = (*_FUNCTIONS, "File:", "Class:", "Interface:", "Struct:", "Record:")
MAX_HYPOTHESES, MAX_A2_ROOTS, MAX_ROOTS = 3, 6, 16
MAX_ALTERNATE, MAX_MEMBERS, MAX_FAMILY, MAX_CALL_1, MAX_CALL_2, MAX_FILES, MAX_CANDIDATES = 12, 12, 12, 12, 8, 8, 48
MAX_FILE_LINES, MAX_CONTEXT_LINES, DB_LIMIT = 8, 20, 200
MAX_PROMPT_CHARS = 128000  # hard input-cost ceiling; never silently clip the issue


class Pick(BaseModel):
    candidate: str = Field(description="Candidate alias, e.g. R4.")
    line: int = Field(description="One numbered line shown for that exact candidate.")
    quote: str = Field(description="Exact text copied from that line.")
    reason: str = Field(description="Why this site must change in this patch, not merely why it is related.")


class Decision(BaseModel):
    candidate: str
    status: Literal["rejected", "unresolved"]
    reason: str = Field(description="Why this shown site is not needed, or which missing context prevents a decision.")


class RegionSites(BaseModel):
    picks: list[Pick]
    decisions: list[Decision] = Field(default_factory=list, description="Classify each shown candidate not picked as rejected or unresolved. Missing decisions remain unresolved, never proven irrelevant.")


PROMPT = """Select the edit sites for one patch from these bounded regions. Hypotheses compete; sites in one region need not all change.

Rules:
- Claimed H1 targets are not automatic: reject one if the shown evidence does not support it.
- Check whether the same obligation applies to another implementation, caller/helper, or module-level site.
- Related, nearby, same-name and same-class code is not by itself evidence of an edit.
- Each pick cites a numbered line shown for that exact candidate: what changes or where missing code belongs.
- A File pick means a module/import/config edit, not a second label for a function edit.
- For each unpicked candidate state rejected or unresolved and why. Partial snippets/capped regions cannot prove completeness.
- Empty picks is valid. Do not invent code, unshown sites, or treat a real citation as proof that your explanation is correct.

<issue>
{issue}
</issue>
<hypotheses>
{hypotheses}
</hypotheses>
<region_memberships>
{groups}
</region_memberships>
<candidates>
{candidates}
</candidates>"""


def input_digest(issue: IssueModel, seeds: dict, a3: dict) -> str:
    text = json.dumps([issue.model_dump(), seeds, a3], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def discover(issue: IssueModel, seeds: dict[str, Any], a3: dict[str, Any], query: Query) -> tuple[list[dict], list[dict], list[dict], set[str]]:
    """The no-LLM part of A3R: bounded regions, their graph candidates with provenance, cap drops, and the issue
    terms used to order members. Design v3 (amendment A3) reads the same candidates as features."""
    hyps = a3["hypotheses"]
    regions, drops = _roots(seeds, hyps)
    if not regions:
        return regions, [], drops, set()
    terms = _issue_terms(issue) | _words(issue.summary) | set().union(*(_terms(h) for h in hyps[:MAX_HYPOTHESES]))
    cands, more = _candidates(regions, hyps, query, terms)
    return regions, cands, drops + more, terms


def find_region_sites(issue: IssueModel, seeds: dict[str, Any], a3: dict[str, Any], query: Query, llm: Runnable, snapshot_root: Path) -> dict[str, Any]:
    hyps = a3["hypotheses"]
    regions, cands, drops, terms = discover(issue, seeds, a3, query)
    out = {"artifact": "A3R", "version": EDIT_REGIONS_VERSION, "input_hash": input_digest(issue, seeds, a3),
           "regions": regions, "candidates": [], "picks": [], "dropped": [], "cap_drops": drops,
           "calls": 0, "complete_patch_proven": False, "incomplete": True}
    if not cands:
        return out
    cache, views = {}, {}
    shown = {c["node"]: _view(c["node"], query, terms, snapshot_root, cache=cache, info=views) for c in cands}
    alias = {f"R{i + 1}": c["node"] for i, c in enumerate(cands)}
    groups = defaultdict(list)
    for name, c in zip(alias, cands):
        for g in c["groups"]:
            groups[g].append(name)
    prompt = PROMPT.format(issue=_render_issue(issue),
        hypotheses="\n".join(f"{h['id']}: {h['claim']}" for h in hyps),
        groups="\n".join(f"{g}: {', '.join(names)}" for g, names in groups.items()),
        candidates="\n\n".join(f"{name} {_loc(c['node'])} ({'; '.join(c['sources'])})\n{shown[c['node']][0]}" for name, c in zip(alias, cands)))
    out.update(prompt_chars=len(prompt), groups=dict(groups), views=views,
               candidates=[{"alias": name, **c} for name, c in zip(alias, cands)])
    if len(prompt) > MAX_PROMPT_CHARS:
        out['status'] = 'input_budget'
        out['decisions'] = [{'node': n, 'status': 'unresolved', 'reason': 'input budget exceeded'} for n in alias.values()]
        return out
    result = llm.invoke(prompt)
    out['calls'] = 1
    stats = {"citation_failures": 0}
    for p in result.picks:
        node = alias.get(p.candidate)
        reason = "unknown candidate" if not node else "repeated" if node in out["picks"] else None
        if not reason and not _cited(p.line, p.quote, shown[node][1], stats):
            reason = "citation not among the shown lines"
        if reason:
            out["dropped"].append({**p.model_dump(), "reason": reason})
        else:
            out["picks"].append(node)
            out.setdefault("evidence", []).append({**p.model_dump(), "node": node})
    decisions = {}
    for d in result.decisions:
        node = alias.get(d.candidate)
        if not node or node in out["picks"] or node in decisions:
            out["dropped"].append({**d.model_dump(), "reason": "unknown, selected or repeated decision"})
        else:
            decisions[node] = {"node": node, "status": d.status, "reason": d.reason}
    out["decisions"] = [decisions.get(n, {"node": n, "status": "unresolved", "reason": "no decision supplied"})
                        for n in alias.values() if n not in out["picks"]]
    h1 = {a["node"] for a in hyps[0]["anchors"] if a["role"] == "target"} if hyps else set()
    out["rejected_h1"] = sorted(n for n in h1 if decisions.get(n, {}).get("status") == "rejected")
    out["unselected_h1"] = sorted(h1 - set(out["picks"]))
    out["incomplete"] = bool(out["cap_drops"] or any(v["partial"] for v in views.values()) or
                             any(d["status"] == "unresolved" for d in out["decisions"]))
    return out


def _interleave(lists: list[list[str]]) -> list[str]:
    return list(dict.fromkeys(n for row in zip_longest(*lists) for n in row if n))


def _region_key(node: str) -> str:
    if node.startswith(("Method:", "Constructor:")) and '.' in _loc(node).split('::')[-1]:
        return _loc(node).rsplit(".", 1)[0]
    if node.startswith(("Class:", "Interface:", "Struct:", "Record:")):
        return _loc(node)
    return "File:" + _path(node)


def _roots(seeds: dict[str, Any], hyps: list[dict]) -> tuple[list[dict], list[dict]]:
    sources, anchors = defaultdict(list), defaultdict(list)
    streams = []
    for i, h in enumerate(hyps[:MAX_HYPOTHESES], 1):
        nodes = [a["node"] for a in h["anchors"] if a["role"] == "target"]
        streams.append(nodes)
        for n in nodes:
            sources[n].append(f"H{i} target")
    a2 = []
    seen_groups = set()
    for verdict in ("relevant", "maybe"):
        for s in seeds["seeds"][:40]:
            n = s["id"]
            if s["verdict"] != verdict or not n.startswith(_ROOTS) or _is_test(_path(n)):
                continue
            g = _region_key(n)
            anchors[g].append(n)
            if g not in seen_groups:
                seen_groups.add(g)
                a2.append(n)
            sources[n].append(f"A2 {verdict}")
    a2_kept = a2[:MAX_A2_ROOTS]
    order = [n for n in _interleave([_interleave(streams), a2_kept]) if n.startswith(_ROOTS) and not _is_test(_path(n))]
    regions = [{"node": n, "sources": list(dict.fromkeys(sources[n])), "group": _region_key(n),
                "anchors": list(dict.fromkeys([n, *anchors[_region_key(n)]]))} for n in order[:MAX_ROOTS]]
    drops = [{"node": n, "source": "A2 region", "reason": "A2 region budget"} for n in a2[MAX_A2_ROOTS:]]
    drops += [{"node": n, "source": "; ".join(sources[n]), "reason": "root budget"} for n in order[MAX_ROOTS:]]
    return regions, drops


def _round_robin(roots: list[str], fetch, cap: int, seen=frozenset()) -> list[str]:
    """Only unique eligible new nodes consume this source budget."""
    return [n for n in _interleave([fetch(r) for r in roots]) if n not in seen][:cap]


def _candidates(regions: list[dict], hyps: list[dict], query: Query, terms: set[str]) -> tuple[list[dict], list[dict]]:
    pools = defaultdict(dict)
    drops, cache = [], {}
    roots = [r["node"] for r in regions]
    caps = {"root": MAX_ROOTS, "alternate hypothesis": MAX_ALTERNATE, "region container": MAX_MEMBERS,
            "implementation family": MAX_FAMILY, "call hop 1": MAX_CALL_1, "call hop 2": MAX_CALL_2, "region file/import": MAX_FILES}

    def fetch(cypher, params, group, source):
        key = (cypher, json.dumps(params, sort_keys=True))
        if key not in cache:
            cache[key] = query(cypher, params)
        rows = cache[key]
        if len(rows) >= DB_LIMIT:
            warning = {"source": source, "group": group, "reason": "database limit", "observed": len(rows), "unknown_remaining": True}
            if warning not in drops:
                drops.append(warning)
        return rows

    def propose(node, source, group):
        if not (node.startswith(_FUNCTIONS) or node.startswith("File:")) or _is_test(_path(node)):
            return
        item = pools[source].setdefault(node, {"node": node, "sources": [], "groups": []})
        if source not in item["sources"]:
            item["sources"].append(source)
        if group not in item["groups"]:
            item["groups"].append(group)

    for r in regions:
        for n in r["anchors"]:
            propose(n, "root", r["group"])
            if n in pools["root"]:
                pools["root"][n]["sources"] += [s for s in r["sources"] if s not in pools["root"][n]["sources"]]
    for h in hyps[1:]:
        for a in h["anchors"]:
            if a["role"] == "target":
                propose(a["node"], "alternate hypothesis", _region_key(a["node"]))

    hop1, anchor_groups = [], defaultdict(list)
    for r in regions:
        n, group = r["node"], r["group"]
        rows = fetch("MATCH (n) WHERE n.filePath = $path AND (label(n) = 'Function' OR label(n) = 'Method' OR label(n) = 'Constructor') RETURN n.id AS id, n.startLine AS start ORDER BY n.startLine, n.id LIMIT 200", {"path": _path(n)}, group, "region container")
        want = _words(" ".join(terms))
        members = sorted(rows, key=lambda x: (-len(_words(_loc(x['id']).split('::')[-1]) & want), x.get('start') or 0, x['id']))
        for m in members:
            propose(m['id'], "region container", group)
        functions = [x for x in r['anchors'] if x.startswith(_FUNCTIONS)]
        if not functions:
            functions = [m['id'] for m in members[:MAX_MEMBERS]]
        anchor_groups[group] += functions
        if n.startswith('File:'):
            anchor_groups[group].append(n)  # module-level calls are valid entry points too
        propose("File:" + _path(n), "region file/import", group)
        for direction in ("a.filePath = $path", "b.filePath = $path"):
            target = "b" if direction.startswith("a") else "a"
            rows = fetch(f"MATCH (a:File)-[r:CodeRelation]->(b:File) WHERE {direction} AND r.type = 'IMPORTS' RETURN {target}.id AS id ORDER BY {target}.id LIMIT 200", {"path": _path(n)}, group, "region file/import")
            for m in rows:
                propose(m['id'], "region file/import", group)
    # Container roots contribute their actual callable anchors, still within the fixed root budget.
    all_anchors = _interleave(list(anchor_groups.values()))
    selected_anchors = set(all_anchors[:MAX_ROOTS])
    for group, anchors in anchor_groups.items():
        for n in dict.fromkeys(anchors):
            if n not in selected_anchors:
                drops.append({'node': n, 'group': group, 'source': 'call/family anchor', 'reason': 'traversal root budget'})
                continue
            if n.startswith(_FUNCTIONS):
                rows = fetch("MATCH (c)-[h:CodeRelation]->(n) WHERE n.id = $id AND h.type = 'HAS_METHOD' MATCH (c)-[e:CodeRelation]->(p) WHERE e.type IN ['EXTENDS','IMPLEMENTS'] MATCH (s)-[e2:CodeRelation]->(p) WHERE e2.type IN ['EXTENDS','IMPLEMENTS'] MATCH (s)-[r:CodeRelation]->(m) WHERE r.type = 'HAS_METHOD' AND m.name = n.name RETURN m.id AS id ORDER BY m.id LIMIT 200", {'id': n}, group, 'implementation family')
                for m in rows:
                    propose(m['id'], 'implementation family', group)
            for m in _calls(n, fetch, group):
                propose(m, 'call hop 1', group)
                if (m, group) not in hop1:
                    hop1.append((m, group))
    # Bound traversal separately from display. A node already shown is not removed from this frontier.
    by_group = defaultdict(list)
    for n, g in hop1:
        by_group[g].append(n)
    traversed = _interleave(list(by_group.values()))[:MAX_CALL_1]
    for n, g in hop1:
        if n not in traversed:
            drops.append({"node": n, "group": g, "source": "call hop 2", "reason": "traversal budget"})
        else:
            for m in _calls(n, fetch, g):
                propose(m, "call hop 2", g)

    # Round robin over source AND region, accounting only for unique newly displayed sites.
    streams = {}
    for source, pool in pools.items():
        grouped = defaultdict(list)
        for n, item in pool.items():
            grouped[item['groups'][0]].append(n)
        streams[source] = iter(_interleave(list(grouped.values())))
    chosen, used = {}, defaultdict(int)
    active = list(streams)
    while active:
        for source in list(active):
            n = next(streams[source], None)
            while n in chosen:
                n = next(streams[source], None)
            if n is None:
                active.remove(source)
                continue
            if used[source] >= caps[source] or len(chosen) >= MAX_CANDIDATES:
                drops.append({"node": n, "source": source, "reason": "source budget" if used[source] >= caps[source] else "global budget"})
                continue
            chosen[n] = {"node": n, "sources": [], "groups": []}
            used[source] += 1
    for source, pool in pools.items():
        for n, item in pool.items():
            if n in chosen:
                for key in ("sources", "groups"):
                    chosen[n][key] = list(dict.fromkeys([*chosen[n][key], *item[key]]))
    return list(chosen.values()), drops


MAX_FILE_MATES, MATE_FILES = 20, 15


def file_mates(issue: IssueModel, seeds: dict[str, Any], query: Query, exclude: set[str], k: int = MAX_FILE_MATES) -> list[str]:
    """exp/gpt-4o-mini (A16): functions of the files holding A2 seeds, without the model, ranked by issue words in the
    name (x3) and the body; tests and nodes already listed are left out. 35 of 55 gold missing from gpt-4o-mini's candidates
    sat in such files; the top 20 by this score held 12 of them (held-out 6, offline)."""
    files = list(dict.fromkeys(s["id"].split(":")[1] for s in seeds.get("seeds", [])))[:MATE_FILES]
    if not files:
        return []
    split = lambda t: {w.lower() for w in re.findall(r"[A-Za-z]{3,}", re.sub(r"([a-z])([A-Z])", r"\1 \2", t or ""))}
    want = split(" ".join([issue.title, issue.summary, issue.observed, issue.expected, *issue.key_concepts, *issue.explicit_code_refs]))
    rows = query("MATCH (n) WHERE n.filePath IN $f AND (label(n) = 'Function' OR label(n) = 'Method') RETURN n.id AS id, n.name AS name, n.content AS code",
                 {"f": files})
    order = {f: i for i, f in enumerate(files)}
    rows = [r for r in rows if r["id"] not in exclude and not _is_test(r["id"].split(":")[1])]
    rows.sort(key=lambda r: (-(3 * len(split(r["name"]) & want) + len(split(r["code"]) & want)), order[r["id"].split(":")[1]], r["id"]))
    return [r["id"] for r in rows[:k]]


def _calls(node, fetch, group):
    lists = []
    for pattern in ("(n)-[r:CodeRelation]->(m)", "(m)-[r:CodeRelation]->(n)"):
        rows = fetch(f"MATCH {pattern} WHERE n.id = $id AND r.type = 'CALLS' RETURN m.id AS id, m.filePath AS path, r.confidence AS w ORDER BY r.confidence DESC, m.id LIMIT 200", {"id": node}, group, "calls")
        lists.append([r['id'] for r in rows if r['id'].startswith(_FUNCTIONS) and not _is_test(r['path'] or '')
                      and (.9 if r['w'] is None else r['w']) >= .4 and r['id'] != node])
    return _interleave(lists)


def _read_source(root, path, cache):
    if path not in cache:
        try:
            if Path(path).is_absolute():
                raise ValueError('absolute source path')
            full = (root / path).resolve()
            if not full.is_relative_to(root.resolve()):
                raise ValueError('source outside snapshot')
            cache[path] = full.read_text(encoding='utf-8', errors='replace').splitlines()
        except (OSError, ValueError, RuntimeError):
            cache[path] = None
    return cache[path]


def _view(node: str, query: Query, terms: set[str], snapshot_root: Path, *, cache=None, info=None) -> tuple[str, dict[int, str]]:
    cache = {} if cache is None else cache
    path, partial = _path(node), False
    source = _read_source(snapshot_root, path, cache)
    if node.startswith('File:'):
        body = source or []
        eligible = set(range(1, len(body) + 1))
        if path.endswith('.py') and body:
            try:
                tree = ast.parse('\n'.join(body))
                for n in ast.walk(tree):
                    if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        begin = min([n.lineno, *(d.lineno for d in n.decorator_list)])
                        eligible.difference_update(range(begin, n.end_lineno + 1))
            except SyntaxError:
                eligible = {i for i, t in enumerate(body, 1) if t.startswith(('import ', 'from '))}
                partial = True
        elif Path(path).suffix in {'.java', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.c', '.cpp', '.h'}:
            # No module AST for these languages here: imports/package directives only, never method bodies.
            eligible = {i for i, t in enumerate(body, 1) if t.startswith(('import ', 'package ', '#include ', 'use '))}
            partial = True
        want = _words(' '.join(terms))
        nonempty = [i for i in sorted(eligible) if body[i - 1].strip()]
        matching = [i for i in nonempty if _words(body[i - 1]) & want]
        keep = list(dict.fromkeys([*matching, *nonempty]))[:MAX_FILE_LINES]
        lines = {i: body[i - 1][:120] for i in sorted(keep)}
        partial |= len(nonempty) > len(lines)
    else:
        rows = query('MATCH (n) WHERE n.id = $id RETURN n.content AS code, n.startLine AS start, n.endLine AS end_line LIMIT 1', {'id': node})
        row = rows[0] if rows else {}
        start, end = row.get('start') or 1, row.get('end_line')
        code = row.get('code') or ''
        if source is not None and end:
            code = '\n'.join(source[start - 1:end])
        body = code.splitlines()
        hits = _matching_lines(code, start, terms, True)
        offsets = {0} if body else set()
        for line, _ in hits:
            offsets.update(range(max(0, line - start - 1), min(len(body), line - start + 2)))
        keep = sorted(offsets)[:MAX_CONTEXT_LINES]
        lines = {start + i: body[i][:120] for i in keep}
        partial = len(body) > len(lines) or source is None
    if info is not None:
        info[node] = {'partial': partial or not lines, 'shown_lines': sorted(lines), 'source_available': bool(lines)}
    text, previous = [], None
    for line, value in sorted(lines.items()):
        if previous is not None and line > previous + 1:
            text.append('  ...')
        text.append(f'{line:>5} {value}')
        previous = line
    return '\n'.join(text) or '(no source available)', lines


def _path(node: str) -> str:
    return node.split(':', 2)[1] if node.count(':') >= 1 else ''
