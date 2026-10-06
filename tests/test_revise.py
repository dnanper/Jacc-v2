from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.exploration import Check, Cite, ExplainCheck, NodeReview, Record, Refute
from src.modules.revise import Anchor, Basis, Change, Hypothesis, Prediction, Revision, revise
from tests.test_exploration import CODE, ISSUE, MERGE, TOP, fake_query

A3 = {"hypotheses": [
    {"id": "H1", "mechanism": "wrong_argument", "anchors": [{"node": TOP, "role": "target", "via": "self"}],
     "predictions": [{"id": "H1.P1", "kind": "core", "text": "p", "node": TOP, "via": "self"}]},
]}


def a4(status: str, candidates: list | None = None, core: int = 0, anomalies: list | None = None) -> dict:
    return {"hypotheses": [{
        "id": "H1", "status": status, "rule_status": status, "claim": "c", "mechanism": "wrong_argument", "targets": [TOP],
        "predictions": {"H1.P1": "confirmed" if core else "unchecked"}, "prediction_text": {"H1.P1": "p"},
        "core_confirmed": core, "deviations": [TOP] if core else [], "refuted_by": None, "evidence": [],
        "reads": [{"node": TOP, "role": "supports", "R": 1.0}], "checked_at": [], "chain": None, "pruned": [],
    }], "candidates": candidates or [], "anomalies": anomalies or []}


def change(op: str, sources: list[str], target: str = "V1", mechanism: str = "missing_step") -> Change:
    return Change(op=op, sources=sources, hypothesis=Hypothesis(
        claim=f"{op} {target} {mechanism}", mechanism=mechanism, explains=["observed"],
        anchors=[Anchor(seed=target, role="target", via="self")], basis=[Basis(seed=target, fact="f")],
        predictions=[Prediction(text="the call omits x", kind="core", seed=target, via="self")], refute_if="r"))


class Reviser:
    def __init__(self, *rounds):
        self.rounds, self.prompts = list(rounds), []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return Revision(changes=self.rounds.pop(0) if self.rounds else [])


class Node:
    """Confirms every new hypothesis's core prediction at TOP with a real line, when `confirm`."""

    def __init__(self, confirm: bool):
        self.confirm, self.calls = confirm, 0

    def invoke(self, prompt):
        self.calls += 1
        hs = re.findall(r"^(R\d+\.\d+): ", prompt.split("<hypotheses>")[1], re.M)
        on_top = 'id="pkg/d.py::diophantine"' in prompt
        recs = [Record(h=h, checks=[Check(pid=f"{h}.P1", status="for", cites=[Cite(line=12, quote="diophantine(eq)")], reason="r")]
                       if self.confirm and on_top else [], refute=Refute(met=False, line=0, quote=""),
                       role="deviation" if self.confirm and on_top else "transit",
                       cite=Cite(line=12, quote="diophantine(eq)") if self.confirm and on_top else Cite(line=0, quote=""), next=[], also_change=[]) for h in hs]
        return NodeReview(records=recs, observations=[], new_terms=[])


class Explain:
    def invoke(self, prompt):
        return ExplainCheck(items=[])


def run(state: dict, reviser: Reviser, confirm: bool = True) -> dict:
    return revise(ISSUE, A3, state, fake_query, reviser, Node(confirm), Explain())


class ReviseTest(unittest.TestCase):
    def test_any_candidate_means_no_revision(self) -> None:
        for status in ("supported", "partial", "contested"):
            reviser = Reviser([change("refine", ["H1"])])
            out = run(a4(status, [{"node": TOP, "hypotheses": ["H1"]}], core=1), reviser)
            self.assertEqual((out["rounds"], out["calls"], out["changed"]), ([], 0, False))
            self.assertEqual(reviser.prompts, [])

    def test_no_candidate_triggers_refine_that_replaces_source_with_evidence(self) -> None:
        out = run(a4("inconclusive"), Reviser([change("refine", ["H1"])]))
        self.assertEqual(out["rounds"][0]["triggers"], ["NO_CANDIDATE"])
        new = [h for h in out["hypotheses"] if h["origin"] != "A3"]
        self.assertEqual([(h["id"], h["origin"], h["status"]) for h in new], [("R1.1", "refine(H1)", "supported")])
        self.assertEqual(new[0]["claim"], "refine diophantine missing_step")  # alias V1 resolved in free text
        self.assertEqual(out["hypotheses"][0]["replaced_by"], "R1.1")
        self.assertEqual([c["hypotheses"] for c in out["candidates"]], [["R1.1"]])

    def test_failed_refinement_keeps_the_source(self) -> None:
        out = run(a4("inconclusive"), Reviser([change("refine", ["H1"])]), confirm=False)
        self.assertNotIn("replaced_by", out["hypotheses"][0])
        self.assertEqual(out["candidates"], [])

    def test_weaker_replacement_does_not_erase_stronger_evidence(self) -> None:
        # Real run (flask-4045): one tiebreak replaced two sources that each had 2 core confirmations with a
        # hypothesis that had 1, and gold fell from rank 1 to 3.
        state = a4("partial", core=2)
        state["hypotheses"][0]["predictions"]["H1.P2"] = "confirmed"
        state["hypotheses"][0]["prediction_text"]["H1.P2"] = "q"
        state["candidates"] = []  # force the trigger; the rule under test is the replacement guard
        out = run(state, Reviser([change("refine", ["H1"])]))
        self.assertNotIn("replaced_by", out["hypotheses"][0])  # the new one has 1 core confirmation < 2
        self.assertEqual({tuple(c["hypotheses"]) for c in out["candidates"]}, {("H1", "R1.1")})

    def test_spawn_must_cite_a_real_anomaly_and_refine_a_real_hypothesis(self) -> None:
        anomaly = [{"node": TOP, "line": 12, "quote": "diophantine(eq)", "text": "drops permute", "touches": "observed"}]
        reviser = Reviser([change("spawn", ["O1"]), change("spawn", ["O9"], mechanism="wrong_mapping"), change("refine", ["H7"], mechanism="other")])
        out = run(a4("inconclusive", anomalies=anomaly), reviser)
        self.assertIn("<anomalies>", reviser.prompts[0])
        self.assertEqual(out["rounds"][0]["new"], ["R1.1"])
        self.assertEqual(sorted(r["reason"] for r in out["rounds"][0]["rejected"]), ["refine must name the hypothesis it replaces", "spawn must cite an anomaly"])
        self.assertEqual(out["candidates"][0]["node"], TOP)

    def test_basis_may_cite_anomalies_and_hypotheses_not_unknown_ids(self) -> None:
        # Real run: 6 ops logged 'unknown seed in basis: O2' though a basis is reasoning, not a node to read.
        anomaly = [{"node": TOP, "line": 12, "quote": "diophantine(eq)", "text": "drops permute", "touches": "observed"}]
        c = change("spawn", ["O1"])
        c.hypothesis.basis = [Basis(seed="O1", fact="the anomaly"), Basis(seed="H1", fact="refuted before"), Basis(seed="Z9", fact="?")]
        out = run(a4("inconclusive", anomalies=anomaly), Reviser([c]))
        self.assertEqual([r["reason"] for r in out["rounds"][0]["rejected"]], ["unknown seed in basis: Z9"])
        spec = next(h for h in out["hypotheses"] if h["id"] == "R1.1")
        self.assertEqual(spec["origin"], "spawn(O1)")

    def test_prediction_ids_are_renamed_by_owner_not_by_substring(self) -> None:
        from src.modules.revise import _validate
        from src.modules.hypotheses import _check
        hs = [change("refine", ["H1"], mechanism=m).hypothesis for m in ("missing_step", "wrong_argument", "wrong_mapping", "other",
              "wrong_condition", "exception_path", "wrong_dispatch", "state_mutation", "missing_feature", "missing_step")]
        hs[-1].anchors[0].via = "calls"  # tenth hypothesis: distinct key, id H10
        kept, _ = _check(hs, {"V1": TOP})
        self.assertEqual(kept[9]["id"], "H10")
        changes = [Change(op="refine", sources=["H1"], hypothesis=h) for h in hs]
        out, _ = _validate(changes, a4("inconclusive")["hypotheses"], [], {"V1": TOP}, 1)
        self.assertTrue(all(p["id"].startswith(h["id"] + ".P") for h, _ in out for p in h["predictions"]))

    def test_refuted_target_and_mechanism_cannot_come_back(self) -> None:
        state = a4("refuted")
        state["hypotheses"][0]["evidence"] = [{"pid": "H1.P1", "status": "violated", "node": TOP, "line": 11, "quote": "if syms != var"}]
        out = run(state, Reviser([change("refine", ["H1"], target="V1", mechanism="wrong_argument")]))
        self.assertEqual(out["rounds"][0]["rejected"][0]["reason"], "repeats a refuted hypothesis")

    def test_one_round_and_prompt_lists_read_nodes_as_aliases(self) -> None:
        reviser = Reviser([change("refine", ["H1"])], [change("refine", ["H1"], mechanism="other")])
        out = run(a4("inconclusive"), reviser, confirm=False)
        self.assertEqual(len(out["rounds"]), 1)  # MAX_ROUNDS
        self.assertIn("V1 pkg/d.py::diophantine (read)", reviser.prompts[0])
        self.assertIn("pkg/d.py::merge_solution (neighbour)", reviser.prompts[0])


if __name__ == "__main__":
    unittest.main()
