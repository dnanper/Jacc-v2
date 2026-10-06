from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.ranking import FEATURES_V4, FEATURES_V5, FEATURES_V6, candidates, restrict_samples
from src.modules.verifier import CoEdit, Completion, Verdict, Verification, complete, completion_candidates, verify

NODES = [f"Function:pkg/m.py:f{i}" for i in range(20)]


def fake_query(cypher, params=None):
    return [{"code": f"def {params['id'].rsplit(':', 1)[1]}():\n    return 1\n", "start": 1, "end_line": 2}]


class Stub:
    def __init__(self, result):
        self.result, self.prompts = result, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.result


class VerifierTest(unittest.TestCase):
    def test_shows_top_candidates_shuffled_and_maps_aliases(self) -> None:
        llm = Stub(Verification(verdicts=[Verdict(candidate="C1", label="edited", reason="r"), Verdict(candidate="C99", label="edited", reason="r"),
                                          Verdict(candidate="C2", label="maybe", reason="r")], ranking=["C2", "C1", "C42"], edited_count=3))
        out = verify("issue text", NODES, fake_query, {"f1"}, Path("/nonexistent"), llm, seed="inst-1", max_shown=15)
        self.assertEqual(len(verify("issue text", NODES, fake_query, set(), Path("/nonexistent"), Stub(llm.result), seed="x")["shown"]), 20)  # v2 default shows up to 40
        self.assertEqual(len(out["shown"]), 15)
        self.assertEqual(set(out["shown"]), set(NODES[:15]))  # only the prior top 15
        self.assertNotEqual(out["shown"], NODES[:15])  # shown in a shuffled order
        self.assertEqual(out["labels"], {out["shown"][0]: "edited", out["shown"][1]: "maybe"})  # unknown alias C99 ignored
        self.assertEqual(out["ranking"], [out["shown"][1], out["shown"][0]])
        self.assertEqual(verify("issue text", NODES, fake_query, set(), Path("/nonexistent"), Stub(llm.result), seed="inst-1", max_shown=15)["shown"], out["shown"])
        self.assertEqual(out["edited_count"], 3)
        self.assertNotIn("hypothes", llm.prompts[0].split("<issue>")[1].lower())

    def test_verifier_features(self) -> None:
        a3 = {"samples": 1, "dropped": [], "hypotheses": [{"id": "H1", "sample_ids": [0], "anchors": [{"node": NODES[0], "role": "target", "via": "self"}]}]}
        a2 = {"seeds": [{"id": NODES[1], "verdict": "relevant"}, {"id": NODES[2], "verdict": "maybe"}]}
        v = {"shown": NODES[:2], "labels": {NODES[0]: "edited", NODES[1]: "maybe"}, "ranking": [NODES[1], NODES[0]], "edited_count": 7}
        f = {r["node"]: r["features"] for r in candidates(a3, a2, verifier=v)}
        self.assertEqual(set(f[NODES[0]]), set(FEATURES_V4) | set(FEATURES_V6))
        self.assertEqual((f[NODES[0]]["v_est"], f[NODES[0]]["v_est_edited"], f[NODES[1]]["v_est_edited"]), (1.0, 1.0, 0.0))  # count capped at 5
        self.assertEqual((f[NODES[0]]["v_edited"], f[NODES[0]]["v_rank_inv"], f[NODES[1]]["v_maybe"], f[NODES[1]]["v_rank_inv"]), (1.0, 0.5, 1.0, 1.0))
        self.assertEqual((f[NODES[2]]["v_shown"], f[NODES[2]]["v_edited"]), (0.0, 0.0))


    def test_restrict_samples_keeps_only_hypotheses_the_first_samples_proposed(self) -> None:
        h = lambda i, ids: {"id": f"H{i}", "sample_ids": ids, "anchors": []}
        a3 = {"samples": 5, "dropped": [{"reason": "merged into H1"}], "hypotheses": [h(1, [0, 3]), h(2, [3]), h(3, [1]), h(4, [4, 1])]}
        out = restrict_samples(a3, 2)
        self.assertEqual([(x["id"], x["sample_ids"]) for x in out["hypotheses"]], [("H1", [0]), ("H3", [1]), ("H4", [1])])
        self.assertEqual((out["samples"], out["dropped"]), (2, []))


    def test_completion_shows_class_file_and_same_name_mates_and_feeds_features(self) -> None:
        P = "Method:pkg/eng.py:Eng.call"
        mate, filefn, other, test = "Method:pkg/eng.py:Eng.stop", "Function:pkg/eng.py:call_helper", "Method:pkg/aws.py:Aws.call", "Method:tests/t.py:T.call"

        def q(cypher, params=None):
            if "HAS_METHOD" in cypher:
                return [{"id": P}, {"id": mate}]
            if "n.filePath = $path" in cypher:
                return [{"id": mate, "start": 9}, {"id": filefn, "start": 30}, {"id": P, "start": 1}]
            if "n.name = $name" in cypher:
                return [{"id": other}, {"id": test}]
            return [{"code": "def call(self):\n    run()\n", "start": 1, "end_line": 2}]

        self.assertEqual(completion_candidates(P, q, {"call"}), [mate, filefn, other])  # primary and tests excluded
        llm = Stub(Completion(decisions=[CoEdit(candidate="K3", label="also", reason="r"), CoEdit(candidate="K1", label="maybe", reason="r")]))
        out = complete("issue", P, q, {"call"}, Path("/nonexistent"), llm)
        self.assertEqual((out["status"], out["labels"]), ("ok", {other: "also", mate: "maybe"}))
        self.assertIn("<primary>", llm.prompts[0])
        a3 = {"samples": 1, "dropped": [], "hypotheses": [{"id": "H1", "sample_ids": [0], "anchors": [{"node": P, "role": "target", "via": "self"}]}]}
        rows = candidates(a3, {"seeds": []}, completion=out)
        f = {r["node"]: r["features"] for r in rows}
        self.assertEqual([r["node"] for r in rows], [P, mate, filefn, other])  # completion nodes appended
        self.assertEqual((f[other]["c_also"], f[mate]["c_maybe"], f[filefn]["c_shown"], f[P]["c_shown"]), (1.0, 1.0, 1.0, 0.0))


if __name__ == "__main__":
    unittest.main()
