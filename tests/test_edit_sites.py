from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.edit_sites import EditSites, Pick, answer, find_edit_sites
from src.modules.export import export_a3
from src.modules.issue_model import IssueModel, Scenario

FUNC = "Method:pkg/doc.py:FunctionDocumenter.format_signature"
SIB = "Method:pkg/doc.py:MethodDocumenter.format_signature"
CALLER = "Function:pkg/run.py:render"
OTHER = "Function:pkg/util.py:stringify"
DOC = "Class:pkg/doc.py:FunctionDocumenter"
HELPER = "Function:pkg/util.py:uses_stringify"
FAR = "Function:pkg/doc.py:unrelated_helper"
TEST = "Function:tests/test_doc.py:test_format"
CODE = {
    FUNC: ("    def format_signature(self, **kwargs):\n        sig = super().format_signature(**kwargs)\n        if self.overloads:\n            return sig\n        return sig", 10),
    SIB: ("    def format_signature(self, **kwargs):\n        sig = super().format_signature(**kwargs)\n        if self.overloads:\n            return sig", 40),
    CALLER: ("def render(doc):\n    return doc.format_signature()", 5),
    OTHER: ("def stringify(x):\n    return str(x)", 1),
    HELPER: ("def uses_stringify(x):\n    return stringify(x)", 20),
    FAR: ("def unrelated_helper():\n    pass", 90),
    TEST: ("def test_format():\n    assert True", 1),
}


def fake_query(cypher: str, params: dict | None = None) -> list[dict]:
    if "n.content AS code" in cypher:
        return [{"id": i, "name": i.split(":")[-1].split(".")[-1], "sig": "", "code": CODE[i][0], "start": CODE[i][1]} for i in params["ids"] if i in CODE]
    if "n.filePath IN $p" in cypher:  # functions of the targets' files
        return [{"id": i, "start": CODE[i][1]} for i in CODE if i.split(":")[1] in params["p"]]
    if "m.name = n.name" in cypher and "e2" in cypher and params["id"] == FUNC:  # same-name lane: a sibling override
        return [{"id": SIB, "label": "Method", "name": "format_signature", "path": "pkg/doc.py", "w": 0.9}]
    if cypher.startswith("MATCH (m)-[r:CodeRelation]->(n)") and "CALLS" in cypher and params["id"] == FUNC:  # callers
        return [{"id": CALLER, "label": "Function", "name": "render", "path": "pkg/run.py", "w": 0.9},
                {"id": TEST, "label": "Function", "name": "test_format", "path": "tests/test_doc.py", "w": 0.9}]
    if cypher.startswith("MATCH (m)-[r:CodeRelation]->(n)") and "CALLS" in cypher and params["id"] == OTHER:
        return [{"id": HELPER, "label": "Function", "name": "uses_stringify", "path": "pkg/util.py", "w": 0.9}]
    if "x.type = 'EXTENDS'" in cypher and params["id"] == DOC:  # members lane of the class
        return [{"id": FUNC, "label": "Method", "name": "format_signature", "path": "pkg/doc.py", "w": 1.0}]
    return []


class Stub:
    def __init__(self, out: EditSites) -> None:
        self.out, self.prompt, self.calls = out, "", 0

    def invoke(self, prompt: str) -> EditSites:
        self.prompt, self.calls = prompt, self.calls + 1
        return self.out


ISSUE = IssueModel(
    title="overloads ignored", issue_type="bug", report_class="code_identifiers", summary="autodoc_typehints none ignores overloads",
    scenario=Scenario(precondition="", action="", path=""), reproduction_steps=[], observed="", expected="", error_messages=[],
    stack_trace="", code_snippets=[], environment=[], reporter_hypotheses=[], key_concepts=[], explicit_code_refs=["overloads"],
    assumptions=[], unknowns=[],
)


def a3(*others: str) -> dict:
    h1 = {"claim": "format_signature ignores the setting for overloads", "refute_if": "", "predictions": [],
          "anchors": [{"node": FUNC, "role": "target", "via": "self"}, {"node": CALLER, "role": "entry", "via": "self"}]}
    return {"hypotheses": [h1, *({"claim": "", "refute_if": "", "predictions": [], "anchors": [{"node": o, "role": "target", "via": "self"}]} for o in others)]}


class EditSitesTest(unittest.TestCase):
    def test_candidates_come_from_other_hypotheses_neighbours_and_the_same_file(self) -> None:
        llm = Stub(EditSites(picks=[]))
        out = find_edit_sites(ISSUE, a3(OTHER), fake_query, llm)
        self.assertEqual(llm.calls, 1)
        whys = {c["node"]: c["why"] for c in out["candidates"]}
        self.assertEqual(whys[OTHER], "target of another hypothesis")
        self.assertEqual(whys[SIB], "same_name of FunctionDocumenter.format_signature")
        self.assertEqual(whys[CALLER], "called_by of FunctionDocumenter.format_signature")
        self.assertEqual(whys[FAR], "same file")
        self.assertNotIn(TEST, whys)  # tests are never edit sites
        self.assertNotIn(FUNC, whys)  # a target is not its own candidate
        self.assertIn("   12         if self.overloads:\n   13             return sig", llm.prompt)  # the target is shown in full
        self.assertIn("   42 if self.overloads:", llm.prompt)  # a candidate shows its lines naming an issue term
        self.assertEqual(answer(out), [FUNC])  # no pick: the answer stays H1's targets

    def test_a_pick_needs_a_line_that_was_shown(self) -> None:
        alias = lambda out, node: next(c["alias"] for c in out["candidates"] if c["node"] == node)
        probe = find_edit_sites(ISSUE, a3(), fake_query, Stub(EditSites(picks=[])))
        sib, caller = alias(probe, SIB), alias(probe, CALLER)
        llm = Stub(EditSites(picks=[
            Pick(candidate=sib, line=42, quote="if self.overloads:", reason="same check in the sibling override"),
            Pick(candidate=caller, line=6, quote="return doc.format_signature(show=False)", reason="invented line"),
            Pick(candidate="C99", line=1, quote="x", reason="unknown"),
            Pick(candidate=sib, line=42, quote="if self.overloads:", reason="twice"),
        ]))
        out = find_edit_sites(ISSUE, a3(), fake_query, llm)
        self.assertEqual(out["picks"], [SIB])
        self.assertEqual([d["reason"] for d in out["dropped"]], ["citation not among the shown lines", "unknown candidate", "repeated"])
        self.assertEqual(answer(out), [FUNC, SIB])
        ans = export_a3(a3(), lambda c, p=None: [], out)
        self.assertEqual(ans["found_functions"], ["pkg/doc.py::FunctionDocumenter.format_signature", "pkg/doc.py::MethodDocumenter.format_signature"])
        self.assertEqual(ans["source"], "A3S")

    def test_a_class_target_asks_for_its_methods_and_a_file_target_makes_no_call(self) -> None:
        # Real runs (pylint-5859, sphinx-7975): H1's only target was a class, so the answer had no function.
        llm = Stub(EditSites(picks=[]))
        h = lambda node: {"hypotheses": [{"claim": "", "refute_if": "", "predictions": [], "anchors": [{"node": node, "role": "target", "via": "self"}]}]}
        out = find_edit_sites(ISSUE, h(DOC), fake_query, llm)
        self.assertEqual(llm.calls, 1)
        self.assertIn("pkg/doc.py::FunctionDocumenter (a class: the edit is in its methods)", llm.prompt)
        self.assertEqual({c["node"]: c["why"] for c in out["candidates"]}[FUNC], "members of FunctionDocumenter")
        out = find_edit_sites(ISSUE, h("File:pkg/doc.py"), fake_query, llm)
        self.assertEqual((llm.calls, out["calls"]), (1, 0))
        self.assertEqual(find_edit_sites(ISSUE, {"hypotheses": []}, fake_query, llm)["targets"], [])

    def test_duplicate_targets_and_one_targets_neighbours_do_not_use_up_the_caps(self) -> None:
        # Real runs (matplotlib-23476, django-18854): repeats of one node, or the first target's neighbours, filled a cap.
        others = [OTHER] * 3 + [SIB]
        with patch("src.modules.edit_sites.MAX_OTHER", 2), patch("src.modules.edit_sites.MAX_NEIGHBOURS", 1):
            out = find_edit_sites(ISSUE, a3(*others), fake_query, Stub(EditSites(picks=[])))
        self.assertEqual([c["node"] for c in out["candidates"] if c["why"] == "target of another hypothesis"], [OTHER, SIB])
        with patch("src.modules.edit_sites.MAX_NEIGHBOURS", 2):
            h = a3()
            h["hypotheses"][0]["anchors"] = [{"node": FUNC, "role": "target", "via": "self"}, {"node": OTHER, "role": "target", "via": "self"}]
            out = find_edit_sites(ISSUE, h, fake_query, Stub(EditSites(picks=[])))
        self.assertEqual([c["why"] for c in out["candidates"] if " of " in c["why"]], ["same_name of FunctionDocumenter.format_signature", "called_by of stringify"])


if __name__ == "__main__":
    unittest.main()
