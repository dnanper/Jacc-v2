from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.region_sites import Pick, Decision, RegionSites, find_region_sites, _roots, _round_robin, _view, _calls
from src.modules.issue_model import IssueModel, Scenario

H1 = "Method:pkg/doc.py:Doc.render"
ALT = "Method:pkg/doc.py:Doc.finish"
SIB = "Method:pkg/doc.py:Doc.helper"
FAMILY = "Method:pkg/other.py:OtherDoc.render"
CALL1 = "Function:pkg/call.py:call_render"
CALL2 = "Function:pkg/call2.py:dispatch"
FILE = "File:pkg/config.py"
TEST = "Function:tests/test_doc.py:test_render"
CODE = {n: (f"def {n.rsplit(':', 1)[-1].split('.')[-1]}():\n    return overloads", 10 + i * 10) for i, n in enumerate((H1, ALT, SIB, FAMILY, CALL1, CALL2, TEST))}


def query(cypher: str, params: dict | None = None) -> list[dict]:
    if "n.content AS code" in cypher:
        node = params["id"]
        code, start = CODE.get(node, ("", 1))
        return [{"code": code, "start": start}]
    if "n.filePath = $path" in cypher:
        return [{"id": n, "start": start} for n, (_, start) in CODE.items() if n.split(":")[1] == params["path"]]
    if "m.id = $id AND r.type = 'HAS_METHOD'" in cypher:
        return [{"id": "Class:pkg/doc.py:Doc"}] if params["id"] == H1 else []
    if "c.id = $id AND r.type = 'HAS_METHOD'" in cypher:
        return [{"id": H1, "start": CODE[H1][1]}, {"id": SIB, "start": CODE[SIB][1]}] if params["id"] == "Class:pkg/doc.py:Doc" else []
    if "e.type IN ['EXTENDS','IMPLEMENTS']" in cypher:
        return [{"id": FAMILY}] if params["id"] == H1 else []
    if "r.type = 'CALLS'" in cypher:
        node = params["id"]
        if node == H1:
            return [{"id": CALL1, "path": "pkg/call.py", "w": .9}, {"id": TEST, "path": "tests/test_doc.py", "w": .9}]
        if node == CALL1:
            return [{"id": CALL2, "path": "pkg/call2.py", "w": .9}]
        return []
    if "r.type = 'IMPORTS'" in cypher:
        return [{"id": FILE}]
    return []


class Stub:
    def __init__(self, out: RegionSites) -> None:
        self.out, self.prompt, self.calls = out, "", 0

    def invoke(self, prompt: str) -> RegionSites:
        self.prompt, self.calls = prompt, self.calls + 1
        return self.out


ISSUE = IssueModel(title="overloads", issue_type="bug", report_class="code_identifiers", summary="overloads ignored", scenario=Scenario(precondition="", action="", path=""), reproduction_steps=[], observed="", expected="", error_messages=[], stack_trace="", code_snippets=[], environment=[], reporter_hypotheses=[], key_concepts=[], explicit_code_refs=["overloads"], assumptions=[], unknowns=[])
A3 = {"hypotheses": [
    {"id": "H1", "claim": "render ignores overloads", "refute_if": "", "predictions": [], "anchors": [{"node": H1, "role": "target", "via": "self"}]},
    {"id": "H2", "claim": "finish misses overloads", "refute_if": "", "predictions": [], "anchors": [{"node": ALT, "role": "target", "via": "self"}]},
]}
SEEDS = {"seeds": [{"id": "Class:pkg/doc.py:Doc", "verdict": "relevant"}, {"id": FILE, "verdict": "relevant"}], "queries": {}}


class RegionSitesTest(unittest.TestCase):
    def test_discovers_regions_family_two_hops_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "pkg"; path.mkdir()
            (path / "config.py").write_text("setting = 'overloads'\n")
            llm = Stub(RegionSites(picks=[]))
            out = find_region_sites(ISSUE, SEEDS, A3, query, llm, Path(root))
        self.assertEqual(llm.calls, 1)
        by_node = {c["node"]: c["sources"] for c in out["candidates"]}
        self.assertIn("H1 target", by_node[H1])
        self.assertIn("alternate hypothesis", by_node[ALT])
        self.assertIn("region container", by_node[SIB])
        self.assertIn("implementation family", by_node[FAMILY])
        self.assertIn("call hop 1", by_node[CALL1])
        self.assertIn("call hop 2", by_node[CALL2])
        self.assertIn("region file/import", by_node[FILE])
        self.assertNotIn(TEST, by_node)
        self.assertIn("setting = 'overloads'", llm.prompt)
        self.assertIn("claimed h1 targets are not automatic", llm.prompt.lower())

    def test_only_valid_citations_select_the_complete_set_and_can_reject_h1(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "pkg"; path.mkdir()
            (path / "config.py").write_text("setting = 'overloads'\n")
            probe = find_region_sites(ISSUE, SEEDS, A3, query, Stub(RegionSites(picks=[])), Path(root))
            aliases = {c["node"]: c["alias"] for c in probe["candidates"]}
            llm = Stub(RegionSites(picks=[
                Pick(candidate=aliases[FAMILY], line=41, quote="return overloads", reason="same implementation contract"),
                Pick(candidate=aliases[FILE], line=1, quote="setting = 'overloads'", reason="module setting changes"),
                Pick(candidate=aliases[ALT], line=999, quote="made up", reason="invalid"),
            ], decisions=[Decision(candidate=aliases[H1], status="rejected", reason="wrong claimed target")]))
            out = find_region_sites(ISSUE, SEEDS, A3, query, llm, Path(root))
        self.assertEqual(out["picks"], [FAMILY, FILE])
        self.assertEqual(out["rejected_h1"], [H1])
        self.assertEqual(out["dropped"][0]["reason"], "citation not among the shown lines")
        self.assertFalse(out["complete_patch_proven"])
        self.assertTrue(out["incomplete"])

    def test_many_hypothesis_targets_do_not_starve_an_a2_region(self):
        hypothesis = {**A3["hypotheses"][0], "anchors": [{"node": f"Function:many.py:f{i}", "role": "target"} for i in range(30)]}
        seeds = {"seeds": [{"id": "Function:elsewhere.py:entry", "verdict": "maybe"}]}
        roots, dropped = _roots(seeds, [hypothesis])
        self.assertIn("Function:elsewhere.py:entry", [r["node"] for r in roots])
        self.assertLessEqual(len(roots), 16)
        self.assertTrue(dropped)

    def test_duplicate_sites_do_not_consume_the_new_candidate_budget(self):
        fetch = lambda root: [H1, H1, root]
        got = _round_robin([ALT, SIB], fetch, 2, seen={H1})
        self.assertEqual(got, [ALT, SIB])

    def test_zero_confidence_is_not_replaced_with_a_positive_prior(self):
        fetch = lambda *args: [{"id": CALL1, "path": "pkg/call.py", "w": 0.0}]
        self.assertEqual(_calls(H1, fetch, "g"), [])

    def test_file_evidence_excludes_function_body_and_blocks_escape(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            root = Path(root)
            (root / "safe.py").write_text("setting = 'overloads'\ndef run():\n    secret = 'overloads'\n")
            text, lines = _view("File:safe.py", query, {"overloads"}, root)
            self.assertIn("setting", text)
            self.assertNotIn("secret", text)
            (Path(outside) / "private.py").write_text("secret = 'overloads'\n")
            (root / "link.py").symlink_to(Path(outside) / "private.py")
            self.assertEqual(_view("File:link.py", query, {"overloads"}, root)[1], {})
            self.assertEqual(_view("File:" + str(Path(outside) / "private.py"), query, {"overloads"}, root)[1], {})

    def test_global_budget_keeps_multiple_sources_and_reuses_container_queries(self):
        from unittest.mock import patch
        from src.modules.region_sites import _candidates
        seen_queries = []
        def counted(cypher, params=None):
            seen_queries.append((cypher, str(params)))
            return query(cypher, params)
        roots, _ = _roots(SEEDS, A3["hypotheses"])
        with patch("src.modules.region_sites.MAX_CANDIDATES", 7):
            cands, dropped = _candidates(roots, A3["hypotheses"], counted, {"overloads"})
        self.assertLessEqual(len(cands), 7)
        self.assertTrue(any(c["node"].startswith("File:") for c in cands))
        containers = [x for x in seen_queries if "n.filePath = $path" in x[0]]
        self.assertEqual(len(containers), len(set(containers)))
        self.assertTrue(any(d["reason"] == "global budget" for d in dropped))

    def test_input_budget_prevents_a_selection_call(self):
        from unittest.mock import patch
        llm = Stub(RegionSites(picks=[]))
        with tempfile.TemporaryDirectory() as root, patch('src.modules.region_sites.MAX_PROMPT_CHARS', 1):
            out = find_region_sites(ISSUE, SEEDS, A3, query, llm, Path(root))
        self.assertEqual(llm.calls, 0)
        self.assertEqual(out['calls'], 0)
        self.assertEqual(out['status'], 'input_budget')
        self.assertTrue(out['incomplete'])

    def test_evidence_query_parses_in_ladybug_not_only_in_a_mock(self):
        import real_ladybug as lb
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'pkg').mkdir()
            (root / 'pkg/doc.py').write_text('def render():\n    return overloads\n')
            db = lb.Database(str(root / 'tiny-db'), buffer_pool_size=16 << 20, max_db_size=1 << 30)
            conn = lb.Connection(db)
            conn.execute('CREATE NODE TABLE Fn(id STRING, content STRING, startLine INT64, endLine INT64, PRIMARY KEY(id))')
            conn.execute('CREATE (:Fn {id: $id, content: $code, startLine: 1, endLine: 2})',
                         {'id': H1, 'code': 'def render():\n    return overloads'})
            with self.assertRaises(RuntimeError):
                conn.execute('MATCH (n) RETURN n.endLine AS end LIMIT 1')
            def real_query(cypher, params=None):
                result = conn.execute(cypher, params or {})
                names = result.get_column_names()
                rows = []
                while result.has_next():
                    rows.append(dict(zip(names, result.get_next())))
                return rows
            text, lines = _view(H1, real_query, {'overloads'}, root)
            self.assertIn('return overloads', text)
            self.assertEqual(lines[2], '    return overloads')
            del conn, db

    def test_omitted_decision_is_unresolved_not_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            out = find_region_sites(ISSUE, SEEDS, A3, query, Stub(RegionSites(picks=[])), Path(root))
        self.assertEqual(out["rejected_h1"], [])
        self.assertIn(H1, out["unselected_h1"])
        self.assertTrue(all(d["status"] == "unresolved" for d in out["decisions"]))


if __name__ == "__main__":
    unittest.main()
