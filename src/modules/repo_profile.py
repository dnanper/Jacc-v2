"""Artifact A0.5: compact, issue-independent semantic knowledge about a repository.

Deterministic Cypher over the persisted CKG (A0); no LLM. The whole artifact is meant to fit
in a prompt (~2k tokens), so it keeps only statements of meaning, each anchored to a graph id:

- packages: what each package says it does (its __init__ docstring)
- families: base class -> the hooks its subclasses implement (behaviour lives there)
- dispatch: name-built calls (getattr(x, "_print_" + name)) that CALLS edges cannot see
- errors: repo-defined exceptions -> where raised, a message, where caught
- blind_spots: directories whose call edges are mostly name guesses

Counts only choose what to show. Undocumented code is skipped, never described by a model.
Test code, test infrastructure and non-library scripts are out of scope.
See research/codekg-survey/REPO_PROFILE_A05.vn.md.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from src.modules.repo_explorer.ingestion.support.entry_point_scoring import is_test_file

PROFILE_VERSION = 3
PROFILE_FILE = "A0.5_repo_profile.json"
MAX_PACKAGES, MAX_FAMILIES, MAX_DISPATCH, MAX_ERRORS, MAX_WEAK_DIRS = 60, 12, 8, 20, 5

Query = Callable[[str, dict | None], list[dict]]

CAVEAT = "Absent edges may be unparsed code; reflection and plugin registries beyond the dispatch list are not captured."

_EXCEPTION_NAME = re.compile(r"(Error|Exception|Warning|Exit|Interrupt|Throwable|Failed|Failure)$")
_DISPATCH = re.compile(
    r"""getattr\(\s*[\w.]+\s*,\s*(?:['"](\w+)['"]\s*\+|f['"](\w+)\{|['"](\w+)%s['"]\s*%)"""
)
# Name built into a variable first: m = '_print_' + cls.__name__; getattr(self, m)
_NAME_VAR = re.compile(r"""(\w+)\s*=\s*(?:['"](\w+)['"]\s*\+|f['"](\w+)\{|['"](\w+)%s['"]\s*%)""")
# ponytail: fixed list of non-library top-level dirs; make it per-repo config if a benchmark repo keeps library code there.
_NON_LIBRARY_TOP = frozenset({"bin", "release", "examples", "example", "doc", "docs", "benchmarks", "scripts"})
_TEST_INFRA_FILES = frozenset({"pytest.py", "runtests.py", "conftest.py"})


def build_repo_profile(query: Query, *, repo: str, commit: str) -> dict[str, Any]:
    return {
        "artifact": "A0.5",
        "version": PROFILE_VERSION,
        "repo": repo,
        "commit": commit,
        "created_at": datetime.now(UTC).isoformat(),
        "packages": _packages(query),
        "families": _families(query),
        "dispatch": _dispatch(query),
        "errors": _errors(query),
        "blind_spots": _blind_spots(query),
        "caveat": CAVEAT,
    }


def load_or_build_repo_profile(
    artifact_dir: Path, query: Query, *, repo: str, commit: str, force: bool = False
) -> Path:
    """Build once per (repo, commit); reruns reuse the file unless forced or stale."""
    path = artifact_dir / PROFILE_FILE
    if path.exists() and not force:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("version") == PROFILE_VERSION and cached.get("commit") == commit:
            return path
    write_json(path, build_repo_profile(query, repo=repo, commit=commit))
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


# --- sections -----------------------------------------------------------------


def _packages(query: Query) -> list[dict[str, str]]:
    rows = query(
        "MATCH (s:Section)-[r:CodeRelation]->(f:File) WHERE r.type = 'DESCRIBES' AND f.filePath ENDS WITH '__init__.py' "
        "RETURN f.filePath AS path, s.content AS doc",
        None,
    )
    out = [
        {"package": posixpath.dirname(row["path"]) or ".", "purpose": _first_sentence(row["doc"], 90)}
        for row in rows
        if not _out_of_scope(row["path"]) and _first_sentence(row["doc"], 90)
    ]
    return sorted(out, key=lambda p: p["package"])[:MAX_PACKAGES]


def _families(query: Query, min_members: int = 3) -> list[dict[str, Any]]:
    """Base class -> hook prefixes that >=3 of its subclasses implement. Kept only with a docstring or hooks."""
    subs = query(
        "MATCH (c:Class)-[r:CodeRelation]->(p) WHERE r.type IN ['EXTENDS', 'IMPLEMENTS'] "
        "AND p.filePath IS NOT NULL AND p.filePath <> '' "
        "RETURN p.id AS base, c.id AS sub, c.filePath AS path",
        None,
    )
    members: dict[str, list[str]] = defaultdict(list)
    for row in subs:
        if not _out_of_scope(row["path"] or "") and not _out_of_scope(_path_of(row["base"])):
            members[row["base"]].append(row["sub"])
    exceptions = _exception_ids(query)  # exception hierarchies belong to the error map
    bases = sorted((b for b in members if len(members[b]) >= min_members and b not in exceptions), key=lambda b: -len(members[b]))
    methods = query(
        "MATCH (c:Class)-[r:CodeRelation]->(m:Method) WHERE r.type = 'HAS_METHOD' AND c.id IN $ids "
        "RETURN c.id AS cls, m.name AS name",
        {"ids": [s for b in bases for s in members[b]]},
    )
    names_by_class: dict[str, set[str]] = defaultdict(set)
    for row in methods:
        names_by_class[row["cls"]].add(row["name"] or "")
    docs = _docs(query, bases)
    out = []
    for base in bases:
        hooks: Counter = Counter()
        for sub in members[base]:
            hooks.update({_hook_prefix(n) for n in names_by_class[sub]} - {""})
        shared = [f"{p}*" for p, n in hooks.most_common(4) if n >= min_members]
        doc = docs.get(base, "")
        if doc or shared:
            out.append({"base": base, "subclasses": len(members[base]), "hooks": shared, "doc": doc})
        if len(out) == MAX_FAMILIES:
            break
    return out


def _hook_prefix(method: str) -> str:
    """'_print_Add' -> '_print_', '_eval_is_real' -> '_eval_is_', 'doit' -> ''."""
    m = re.match(r"^(_{1,2}[a-z]+_(?:[a-z]+_)?)[A-Za-z0-9]", method)
    if not m or method.startswith("__") and method.endswith("__"):
        return ""
    return m.group(1)


def _dispatch(query: Query) -> list[dict[str, Any]]:
    """Name-built dispatch grouped by the method-name prefix it builds."""
    rows = query(
        "MATCH (n:Function:Method) WHERE n.content CONTAINS 'getattr' RETURN n.id AS id, n.filePath AS path, n.content AS code",
        None,
    )
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if _out_of_scope(row["path"] or ""):
            continue
        code = row["code"] or ""
        found = {p for groups in _DISPATCH.findall(code) for p in groups if p}
        for var, *groups in _NAME_VAR.findall(code):
            if re.search(rf"getattr\(\s*[\w.]+\s*,\s*{re.escape(var)}\b", code):
                found.update(p for p in groups if p)
        for prefix in found:
            if len(prefix.strip("_")) >= 2:  # '_' + name says nothing about the target family
                by_prefix[prefix].append(row["id"])
    ranked = sorted(by_prefix.items(), key=lambda item: (-len(item[1]), item[0]))[:MAX_DISPATCH]
    return [{"calls_methods_named": f"{p}<name>", "dispatchers": sorted(ids)[:3], "more": max(0, len(ids) - 3)} for p, ids in ranked]


def _errors(query: Query) -> list[dict[str, Any]]:
    """Repo-defined exception classes, most raised first. Builtins are left out: too common to locate anything."""
    rows = query(
        "MATCH (s)-[r:CodeRelation]->(c:Class) WHERE r.type IN ['RAISES', 'CATCHES'] AND c.filePath IS NOT NULL AND c.filePath <> '' "
        "RETURN c.id AS exc, r.type AS kind, s.id AS site, s.filePath AS path, r.detail AS message",
        None,
    )
    exceptions = _exception_ids(query)
    by_exc: dict[str, dict[str, list]] = defaultdict(lambda: {"RAISES": [], "CATCHES": [], "messages": []})
    for row in rows:
        is_exception = row["exc"] in exceptions or _EXCEPTION_NAME.search(_name_of(row["exc"]))
        if not is_exception or _out_of_scope(row["path"] or "") or _out_of_scope(_path_of(row["exc"])):
            continue
        entry = by_exc[row["exc"]]
        entry[row["kind"]].append(row["site"])
        if row["kind"] == "RAISES" and row["message"]:
            entry["messages"].append(row["message"])
    ranked = sorted((e for e in by_exc.items() if e[1]["RAISES"]), key=lambda e: (-len(e[1]["RAISES"]), e[0]))[:MAX_ERRORS]
    return [
        {
            "exception": exc,
            "raised_in": list(dict.fromkeys(e["RAISES"]))[:2],
            "raise_sites": len(e["RAISES"]),
            "message": _first_sentence(e["messages"][0], 80) if e["messages"] else "",
            "caught_in": list(dict.fromkeys(e["CATCHES"]))[:1],
        }
        for exc, e in ranked
    ]


def _blind_spots(query: Query) -> list[dict[str, Any]]:
    rows = query(
        "MATCH (a)-[r:CodeRelation]->(b) WHERE r.type = 'CALLS' RETURN a.filePath AS path, r.reason AS reason, count(*) AS n",
        None,
    )
    per_dir: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if _out_of_scope(row["path"] or ""):
            continue
        cell = per_dir[posixpath.dirname(row["path"] or "") or "."]
        cell[0] += row["n"]
        cell[1] += row["n"] if _weak_call((row["reason"] or "").split("+")[0]) else 0
    weak = [{"path": d, "guessed_call_share": round(w / n, 2)} for d, (n, w) in per_dir.items() if n >= 50 and w / n >= 0.5]
    return sorted(weak, key=lambda row: -row["guessed_call_share"])[:MAX_WEAK_DIRS]


# --- helpers ----------------------------------------------------------------------


def _exception_ids(query: Query) -> set[str]:
    """Classes whose own name, or any ancestor's name via EXTENDS, looks like an exception."""
    rows = query(
        "MATCH (c:Class)-[r:CodeRelation]->(p:Class) WHERE r.type = 'EXTENDS' RETURN c.id AS child, p.id AS parent",
        None,
    )
    parents: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        parents[row["child"]].append(row["parent"])
    memo: dict[str, bool] = {}

    def is_exc(node: str, seen: frozenset = frozenset()) -> bool:
        if node not in memo:
            memo[node] = bool(_EXCEPTION_NAME.search(_name_of(node))) or any(
                is_exc(p, seen | {node}) for p in parents.get(node, ()) if p not in seen
            )
        return memo[node]

    return {node for node in list(parents) if is_exc(node)}


def _docs(query: Query, ids: list[str]) -> dict[str, str]:
    rows = query(
        "MATCH (s:Section)-[r:CodeRelation]->(n) WHERE r.type = 'DESCRIBES' AND r.reason = 'docstring-direct' "
        "AND n.id IN $ids RETURN n.id AS id, s.content AS doc",
        {"ids": ids},
    )
    return {row["id"]: _first_sentence(row["doc"], 90) for row in rows}


def _first_sentence(doc: str | None, cap: int) -> str:
    text = " ".join((doc or "").split())
    # Stop at the first sentence end or the first docstring section (Examples, ====).
    text = re.split(r"(?<=[.!?])\s|\s(?:Parameters|Examples|Returns|Args|See Also|Notes)\b|={3,}|-{3,}", text, maxsplit=1)[0]
    return text if len(text) <= cap else text[: cap - 3].rsplit(" ", 1)[0] + "..."


def _weak_call(tier: str) -> bool:
    """MAY-grade call edges: global name match or ambiguous resolution (JACC_V2_GAP 4.5)."""
    return tier == "global" or tier.endswith("-ambiguous")


def _is_test(path: str) -> bool:
    """Tests and test infrastructure: never what an issue fix changes (no gold on the three benchmarks is a
    test file). Script dirs are `_out_of_scope` too, but stay searchable: 7 Loc-Bench instances have all
    their gold under examples/ or benchmarks/."""
    return _out_of_scope(path) and path.split("/")[0] not in _NON_LIBRARY_TOP


def _out_of_scope(path: str) -> bool:
    """Tests, test infrastructure, and top-level script dirs; none of it is library behaviour."""
    parts = path.split("/")
    return (
        is_test_file("/" + path)
        or parts[0] in _NON_LIBRARY_TOP
        or parts[-1] in _TEST_INFRA_FILES
        or any(p.startswith("test") or p.endswith("_tests") for p in parts[:-1])
    )


def _path_of(node_id: str) -> str:
    parts = node_id.split(":", 2)
    return parts[1] if len(parts) == 3 else ""


def _name_of(node_id: str) -> str:
    return node_id.split(":")[-1].split(".")[-1]


def _loc(node_id: str | None) -> str:
    """'Method:pkg/a.py:Cls.run' -> 'pkg/a.py::Cls.run', the localization output format."""
    parts = (node_id or "").split(":", 2)
    return f"{parts[1]}::{parts[2]}" if len(parts) == 3 else (node_id or "")


# --- rendering for downstream steps -------------------------------------------------


def render_repo_profile(profile: dict[str, Any]) -> str:
    lines = [
        f'<repo_profile artifact="A0.5" repo="{profile["repo"]}" commit="{profile["commit"]}">',
        "Issue-independent facts from the code graph. Symbols are path::Qualified.name.",
    ]
    if profile["packages"]:
        lines += ["## Packages", *(f"- {p['package']}: {p['purpose']}" for p in profile["packages"])]
    if profile["families"]:
        lines.append("## Extension families (type-specific behaviour lives in subclass hooks)")
        for f in profile["families"]:
            hooks = f"; hooks {', '.join(f['hooks'])}" if f["hooks"] else ""
            doc = f": {f['doc']}" if f["doc"] else ""
            lines.append(f"- {_loc(f['base'])} ({f['subclasses']} subclasses{hooks}){doc}")
    if profile["dispatch"]:
        lines.append("## Name-built dispatch (call graph cannot see these targets)")
        for d in profile["dispatch"]:
            more = f" +{d['more']}" if d["more"] else ""
            lines.append(f"- {d['calls_methods_named']}: {', '.join(_loc(i) for i in d['dispatchers'])}{more}")
    if profile["errors"]:
        lines.append("## Repo exceptions (raised in; message; caught in)")
        for e in profile["errors"]:
            raised = ", ".join(_loc(s) for s in e["raised_in"]) + (f" +{e['raise_sites'] - len(e['raised_in'])}" if e["raise_sites"] > len(e["raised_in"]) else "")
            parts = [raised, repr(e["message"]) if e["message"] else "", ("caught " + _loc(e["caught_in"][0])) if e["caught_in"] else ""]
            lines.append(f"- {_loc(e['exception'])}: " + "; ".join(p for p in parts if p))
    if profile["blind_spots"]:
        weak = ", ".join(f"{w['path']} {int(w['guessed_call_share'] * 100)}%" for w in profile["blind_spots"])
        lines += ["## Call edges mostly name guesses in", f"- {weak}"]
    lines += [f"Note: {profile['caveat']}", "</repo_profile>"]
    return "\n".join(lines)
