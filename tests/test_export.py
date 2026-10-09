from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.export import export, export_a3, export_ranked

METHOD = "Method:src/app/bp.py:Blueprint.__init__"
FUNC = "Function:src/app/util.py:helper"
CLASS = "Class:src/app/state.py:State"


def query(cypher: str, params: dict | None = None) -> list[dict]:
    assert "HAS_METHOD" in cypher
    return [{"m": METHOD, "c": "Class:src/app/bp.py:Blueprint"}] if METHOD in params["ids"] else []


def h(hid: str, *deviations: str, status: str = "partial", belief: float = 0.1, targets: tuple = (), co: tuple = ()) -> dict:
    return {"id": hid, "rule_status": status, "status": status, "belief": belief, "core_confirmed": 0,
            "deviations": list(deviations), "co_change": list(co), "targets": list(targets or deviations)}


def a4(*nodes: str) -> dict:
    """One hypothesis per node, in rank order (equal belief: A3 order decides)."""
    return {"hypotheses": [h(f"H{i}", n) for i, n in enumerate(nodes, 1)]}


class ExportTest(unittest.TestCase):
    def test_v6_exports_the_answer_and_keeps_the_ranked_function_order(self) -> None:
        a3v = {"answer": [METHOD], "ranked": [{"node": METHOD, "p": 0.8}, {"node": CLASS, "p": 0.3}, {"node": FUNC, "p": 0.2}]}
        out = export_ranked(a3v, query)
        self.assertEqual((out["source"], out["found_functions"], out["found_modules"], out["found_files"]),
                         ("A3V", ["src/app/bp.py::Blueprint.__init__"], ["src/app/bp.py::Blueprint"], ["src/app/bp.py"]))
        self.assertEqual(out["ranked_functions"], ["src/app/bp.py::Blueprint.__init__", "src/app/util.py::helper"])
        self.assertEqual(out["recall_answer"]["found_functions"], ["src/app/bp.py::Blueprint.__init__", "src/app/util.py::helper"])
        self.assertEqual(out["recall_answer"]["found_files"], ["src/app/bp.py", "src/app/state.py", "src/app/util.py"])

    def test_three_levels_with_class_from_the_graph(self) -> None:
        out = export(a4(METHOD, FUNC, CLASS), None, query)
        self.assertEqual(out["found_functions"], ["src/app/bp.py::Blueprint.__init__", "src/app/util.py::helper"])
        self.assertEqual(out["found_modules"], ["src/app/bp.py::Blueprint", "src/app/state.py::State"])  # a module function has no class
        self.assertEqual(out["found_files"], ["src/app/bp.py", "src/app/util.py", "src/app/state.py"])
        self.assertEqual(out["source"], "A4")

    def test_uses_a5_only_when_it_changed_the_answer_and_keeps_rank(self) -> None:
        self.assertEqual(export(a4(FUNC), {"changed": False, **a4(METHOD)}, query)["found_functions"], ["src/app/util.py::helper"])
        out = export(a4(FUNC), {"changed": True, **a4(METHOD, FUNC)}, query, top_k=1)
        self.assertEqual((out["source"], out["found_functions"]), ("A5", ["src/app/bp.py::Blueprint.__init__"]))

    def test_frozen_a3_answer_is_every_target_of_the_first_hypothesis(self) -> None:
        a3 = {"hypotheses": [
            {"anchors": [{"node": FUNC, "role": "target"}, {"node": CLASS, "role": "entry"}, {"node": METHOD, "role": "target"}]},
            {"anchors": [{"node": CLASS, "role": "target"}]},
        ]}
        out = export_a3(a3, query)
        self.assertEqual(out["found_functions"], ["src/app/util.py::helper", "src/app/bp.py::Blueprint.__init__"])  # entry anchors are not edit sites
        self.assertNotIn("src/app/state.py::State", out["found_modules"])  # a later hypothesis competes, it does not add
        self.assertEqual(export_a3({"hypotheses": []}, query)["found_functions"], [])

    def test_region_export_uses_exact_selected_functions_and_files(self) -> None:
        a3 = {"hypotheses": [{"anchors": [{"node": FUNC, "role": "target"}]}]}
        a3r = {"picks": [METHOD, "File:src/settings.py"]}
        out = export_a3(a3, query, a3r=a3r)
        self.assertEqual(out["source"], "A3R")
        self.assertEqual(out["found_functions"], ["src/app/bp.py::Blueprint.__init__"])
        self.assertEqual(out["found_files"], ["src/app/bp.py", "src/settings.py"])
        self.assertNotIn("src/app/util.py::helper", out["found_functions"])

    def test_no_hypothesis_is_an_empty_answer(self) -> None:
        out = export(a4(), None, query)
        self.assertEqual((out["found_files"], out["found_modules"], out["found_functions"]), ([], [], []))

    def test_no_candidate_falls_back_to_the_best_standing_hypothesis_targets(self) -> None:
        # sklearn-14087: A3's target was gold, every hypothesis ended inconclusive, the answer was empty.
        hyps = [h("H1", status="refuted", belief=1.0, targets=(CLASS,)), h("H2", belief=-1.5, targets=(METHOD,)), h("H3", belief=-0.9, targets=(FUNC,))]
        out = export({"hypotheses": hyps}, None, query)
        self.assertEqual((out["found_functions"], out["fallback"]), (["src/app/util.py::helper"], True))  # best belief among non-refuted

    def test_a_co_change_vote_does_not_lend_its_belief_to_a_deviation(self) -> None:
        # pylint-7114: H1 (supported, deviation at gold) also called another node co_change; H2 cited that
        # node as its deviation. v12 ranked it first on H1's belief and two votes.
        hyps = [h("H1", FUNC, status="supported", belief=0.11, co=(METHOD,)), h("H2", METHOD, belief=-1.81)]
        self.assertEqual(export({"hypotheses": hyps}, None, query)["found_functions"][0], "src/app/util.py::helper")

    def test_the_leaders_other_edit_sites_follow_its_cited_candidates(self) -> None:
        # A multi-site fix: H1 cites FUNC as the defect and also names METHOD as an edit site.
        lead = h("H1", FUNC, status="supported", belief=0.8, targets=(FUNC, METHOD))
        other = h("H2", status="partial", belief=0.1, targets=(CLASS,))
        out = export({"hypotheses": [lead, other]}, None, query)
        self.assertEqual(out["found_functions"], ["src/app/util.py::helper", "src/app/bp.py::Blueprint.__init__"])
        self.assertNotIn("src/app/state.py::State", out["found_modules"])  # not the leader: competes, does not complete
        # a target the leader read and judged unrelated is left out
        lead["reads"] = [{"node": METHOD, "role": "unrelated"}]
        self.assertEqual(export({"hypotheses": [lead, other]}, None, query)["found_functions"], ["src/app/util.py::helper"])

    def test_equal_belief_is_broken_by_a3_rank_not_vote_count(self) -> None:
        hyps = [h("H1", FUNC), h("H2", METHOD), h("H3", METHOD)]
        self.assertEqual(export({"hypotheses": hyps}, None, query)["found_functions"][0], "src/app/util.py::helper")


if __name__ == "__main__":
    unittest.main()
