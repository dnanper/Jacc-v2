from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.hypotheses import PROMPT, Anchor, _render_issue, Basis, Hypothesis, HypothesisSet, Prediction, generate_hypotheses
from src.modules.issue_model import IssueModel, Scenario

DIOP = "Function:pkg/diophantine.py:diophantine"
MERGE = "Function:pkg/diophantine.py:merge_solution"
SIGNS = "Function:pkg/iterables.py:permute_signs"
SOLS = "Function:pkg/diophantine.py:_permute_sols"
CLASSIFY = "Function:pkg/diophantine.py:classify_diop"
CODE = '''def diophantine(eq, syms=None,
                permute=False):
    """Solve.

    syms is described here, in the docstring.
    """
    # syms comment
    if syms != var:
        return {t for t in diophantine(eq)}
    secret_line_without_terms = 1
'''


def fake_query(cypher: str, params: dict | None = None) -> list[dict]:
    if "n.filePath IN $p" in cypher:  # functions of the files holding a relevant seed
        rows = [(DIOP, 10), (CLASSIFY, 40), (MERGE, 60), (SOLS, 80)]
        return [{"id": i, "path": i.split(":")[1], "sig": i.rsplit(":", 1)[1] + "(eq,\n  t)", "start": n} for i, n in rows if i.split(":")[1] in params["p"]]
    if "n.signature AS sig" in cypher:
        return [{"id": DIOP, "sig": "diophantine(eq, syms=None, permute=False)", "code": CODE, "start": 10},
                {"id": MERGE, "sig": "merge_solution(var, t)", "code": "def merge_solution(var, t):\n    sol = []\n    return sol\n", "start": 60}]
    if "r.type IN $types" in cypher:
        edges = [(DIOP, MERGE), (DIOP, DIOP), (DIOP, SOLS)]
        return [{"a": a, "t": "CALLS", "b": b} for a, b in edges if a in params["ids"] and b in params["ids"]]
    return []


class Stub:
    """Returns `out` for every sample, or the i-th of `outs` for sample i."""

    def __init__(self, out, *outs):
        self.outs, self.prompt, self.calls = [out, *outs], "", 0

    def batch(self, prompts):
        self.prompt, self.calls = prompts[0], self.calls + len(prompts)
        return [self.outs[i % len(self.outs)] for i in range(len(prompts))]


ISSUE = IssueModel(
    title="diophantine loses solutions", issue_type="bug", report_class="code_identifiers",
    summary="permute=True ignored when syms reordered", scenario=Scenario(precondition="", action="", path=""),
    reproduction_steps=[], observed="{(3, 2)}", expected="8 solutions", error_messages=[], stack_trace="",
    code_snippets=[], environment=[], reporter_hypotheses=[], key_concepts=[], explicit_code_refs=["diophantine", "syms"],
    assumptions=["GUESS_SHOULD_NOT_APPEAR"], unknowns=[],
)
SEEDS = {
    "seeds": [
        {"id": DIOP, "verdict": "relevant", "concept": "permute ignored"},
        {"id": MERGE, "verdict": "maybe", "concept": "solution set"},
        {"id": SIGNS, "verdict": "maybe", "concept": ""},
    ],
    "queries": {"code": ["permute"]},
    "profile_links": [],
}


def hyp(mechanism="wrong_argument", target="S1", entry="S1", core=True, refute="passes permute", seed="S1") -> Hypothesis:
    return Hypothesis(
        claim=f"{mechanism} at {target}", mechanism=mechanism, explains=["observed"],
        anchors=[Anchor(seed=entry, role="entry", via="self"), Anchor(seed=target, role="target", via="self")],
        basis=[Basis(seed="S1", fact="L17 if syms != var")],
        predictions=[Prediction(text="recursive call drops permute before S2", kind="core" if core else "aux", seed=seed, via="self")],
        refute_if=refute,
    )


class HypothesesTest(unittest.TestCase):
    def test_prompt_shows_seed_aliases_edges_and_matching_lines_only(self) -> None:
        llm = Stub(HypothesisSet(hypotheses=[hyp()]))
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, llm, samples=1)
        p = llm.prompt
        self.assertIn("S1 pkg/diophantine.py::diophantine [relevant]", p)
        self.assertIn("S1 -CALLS-> S2", p)
        self.assertIn("L17 if syms != var:", p)
        self.assertIn("L18 return {t for t in diophantine(eq)}", p)
        self.assertNotIn("L11", p)  # multi-line def header
        self.assertNotIn("in the docstring", p)
        self.assertNotIn("syms comment", p)
        self.assertNotIn("secret_line_without_terms", p)  # never full code
        self.assertNotIn("GUESS_SHOULD_NOT_APPEAR", p)  # assumptions stay out
        self.assertEqual(out["prompt_chars"], len(p))

    def test_checks_drop_unknown_and_incomplete_then_merge_duplicates(self) -> None:
        llm = Stub(HypothesisSet(hypotheses=[
            hyp(),                                       # H1
            hyp(core=False),                             # no core prediction
            hyp(refute=" "),                             # no refute condition
            hyp(target="S9"),                            # target alias unknown, so no target left
            hyp(seed="S2"),                              # same target + mechanism as H1: merged
            hyp(mechanism="wrong_mapping", target="S2"), # H2
        ]))
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, llm, samples=1)
        self.assertEqual([h["id"] for h in out["hypotheses"]], ["H1", "H2"])
        reasons = [d["reason"] for d in out["dropped"]]
        self.assertEqual(reasons, ["missing core prediction", "missing refute_if", "unknown seed in anchors: S9", "missing target anchor", "merged into H1"])
        h1 = out["hypotheses"][0]
        self.assertEqual([p["node"] for p in h1["predictions"]], [DIOP, MERGE])  # merged predictions, aliases resolved
        self.assertEqual([p["id"] for p in h1["predictions"]], ["H1.P1", "H1.P2"])
        self.assertEqual(out["seed_index"], {DIOP: ["H1", "H2"], MERGE: ["H2"]})
        self.assertEqual(out["reserve"], [SIGNS])
        self.assertEqual(out["uncovered"], ["expected"])
        self.assertFalse(out["low_diversity"])


    def test_target_without_entry_is_kept(self) -> None:
        # Real run (sympy-18189): the model gave target/path anchors only; all 3 were dropped.
        h = hyp()
        h.anchors = [Anchor(seed="S1", role="target", via="self")]
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, Stub(HypothesisSet(hypotheses=[h])), samples=1)
        self.assertEqual([x["id"] for x in out["hypotheses"]], ["H1"])
        self.assertIn("needs a `target` anchor", PROMPT)
        self.assertIn("that the fix would change", Prediction.model_json_schema()["properties"]["text"]["description"].replace("\n", " "))

    def test_the_contract_is_edit_sites_not_mechanisms(self) -> None:
        # v6 asked for the defect mechanism; with seed code visible A3 chose the caller that explains the
        # symptom over the callee the fix edits (pytest-5495, pytest-9359). The target is now the edit site.
        role = Anchor.model_json_schema()["properties"]["role"]["description"]
        self.assertTrue(role.startswith("target: code the fix edits"))
        self.assertIn("the callee is the target", PROMPT)
        self.assertIn("lists each as a target in one hypothesis", PROMPT)  # multi-location fixes
        self.assertIn("For a feature or enhancement", Prediction.model_json_schema()["properties"]["text"]["description"])
        self.assertIn('"issue_type": "bug"', _render_issue(ISSUE))

    def test_predictions_capped_and_must_point_at_readable_code(self) -> None:
        h = hyp()
        h.predictions = [Prediction(text=f"aux {i}", kind="aux", seed="S1", via="self") for i in range(3)] + [
            Prediction(text="core", kind="core", seed="S1", via="self"),
            Prediction(text="inside a class body", kind="core", seed="S4", via="self"),
            Prediction(text="a method of that class", kind="aux", seed="S4", via="members"),
        ]
        seeds = {**SEEDS, "seeds": [*SEEDS["seeds"], {"id": "Class:pkg/k.py:K", "verdict": "maybe", "concept": ""}]}
        out = generate_hypotheses(ISSUE, seeds, fake_query, Stub(HypothesisSet(hypotheses=[h])), samples=1)
        preds = out["hypotheses"][0]["predictions"]
        self.assertEqual([p["text"] for p in preds], ["core", "aux 0", "aux 1"])  # core first, then capped at 3
        self.assertIn("prediction at unreadable node: S4", [d["reason"] for d in out["dropped"]])

    def test_two_samples_are_pooled_interleaved_and_duplicates_merged(self) -> None:
        first = HypothesisSet(hypotheses=[hyp(), hyp(mechanism="wrong_mapping", target="S2")])
        second = HypothesisSet(hypotheses=[hyp(seed="S2"), hyp(mechanism="missing_step", target="S2")])
        llm = Stub(first, second)
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, llm)
        self.assertEqual(llm.calls, 2)
        self.assertEqual((out["samples"], out["sampled"]), (2, 4))
        # interleaved: s1#1, s2#1 (duplicate of s1#1, merged), s1#2, s2#2
        self.assertEqual([h["mechanism"] for h in out["hypotheses"]], ["wrong_argument", "wrong_mapping", "missing_step"])
        self.assertEqual([p["node"] for p in out["hypotheses"][0]["predictions"]], [DIOP, MERGE])
        self.assertIn("merged into H1", [d["reason"] for d in out["dropped"]])
        self.assertEqual([h["sample_ids"] for h in out["hypotheses"]], [[0, 1], [0], [1]])  # H1 proposed by both samples

    def test_relevant_function_without_matching_line_shows_its_first_lines(self) -> None:
        # Held-out 4: 5 of 11 wrong first targets were picked with no code line shown (no issue term in the body).
        seeds = {**SEEDS, "seeds": [SEEDS["seeds"][0], {**SEEDS["seeds"][1], "verdict": "relevant"}, SEEDS["seeds"][2]]}
        llm = Stub(HypothesisSet(hypotheses=[hyp()]))
        generate_hypotheses(ISSUE, seeds, fake_query, llm, samples=1)
        self.assertIn("   L61 sol = []\n   L62 return sol", llm.prompt)
        self.assertNotIn("secret_line_without_terms", llm.prompt)  # a seed with matching lines still shows only those

    def test_other_functions_of_relevant_seed_files_are_listed_and_targetable(self) -> None:
        # Held-out 4: 9 of 10 instances whose gold was not a seed had a seed in the gold file.
        h = hyp(target="S5")
        llm = Stub(HypothesisSet(hypotheses=[h]))
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, llm, samples=1)
        block = llm.prompt.split("<functions_in_seed_files>")[1].split("</functions_in_seed_files>")[0]
        # seeds are not repeated; a maybe seed's file (iterables.py) is not expanded; source order
        self.assertEqual(block.strip().splitlines(), ["S4 pkg/diophantine.py::classify_diop(eq, t)", "S5 pkg/diophantine.py::_permute_sols(eq, t)"])
        self.assertIn("S1 -CALLS-> S5", llm.prompt)
        self.assertEqual([a["node"] for a in out["hypotheses"][0]["anchors"] if a["role"] == "target"], [SOLS])
        self.assertIn("at _permute_sols", out["hypotheses"][0]["claim"])
        with patch("src.modules.hypotheses.MAX_FILE_FUNCS", 1):  # a big file keeps the names sharing issue words
            generate_hypotheses(ISSUE, SEEDS, fake_query, llm, samples=1)
        self.assertIn("S4 pkg/diophantine.py::_permute_sols(eq, t)", llm.prompt)
        self.assertNotIn("classify_diop", llm.prompt)

    def test_explains_drops_parts_the_issue_lacks(self) -> None:
        h = hyp()
        h.explains = ["observed", "trace"]  # real run: 'trace' claimed, issue had no stack trace
        out = generate_hypotheses(ISSUE, SEEDS, fake_query, Stub(HypothesisSet(hypotheses=[h])), samples=1)
        self.assertEqual(out["hypotheses"][0]["explains"], ["observed"])


if __name__ == "__main__":
    unittest.main()
