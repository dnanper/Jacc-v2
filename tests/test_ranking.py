from __future__ import annotations

import itertools
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.ranking import (FEATURES, FEATURES_V2, FEATURES_V3, FEATURES_V4, FEATURES_V5, average_precision, decide, load_calibrator, candidates, crc_threshold, expected_f1, expected_f1_prefix,
                                 fit_conditional_logit, fit_logistic, matrix, ndcg, predict, set_metrics)

A = "Method:pkg/a.py:K.f"
B = "Method:pkg/a.py:K.g"
C = "Function:pkg/b.py:h"
D = "Function:pkg/c.py:seed_only"


def hyp(hid, targets, other=(), sample_ids=None):
    h = {"id": hid, "anchors": [{"node": n, "role": "target", "via": "self"} for n in targets]
         + [{"node": n, "role": "path", "via": "self"} for n in other]}
    if sample_ids is not None:
        h["sample_ids"] = sample_ids
    return h


A2 = {"seeds": [{"id": D, "verdict": "relevant"}, {"id": B, "verdict": "maybe"}, {"id": "Class:pkg/a.py:K", "verdict": "relevant"}]}


class RankingTest(unittest.TestCase):
    def test_candidates_follow_prior_order_and_read_votes(self) -> None:
        a3 = {"samples": 2, "dropped": [], "hypotheses": [hyp("H1", [A], [C], [0, 1]), hyp("H2", [B, A], sample_ids=[1])]}
        rows = candidates(a3, A2)
        self.assertEqual([r["node"] for r in rows], [A, B, D, C])  # targets in A3 order, then seeds, then other anchors
        f = {r["node"]: r["features"] for r in rows}
        self.assertEqual(set(f[A]), set(FEATURES_V4) | {'v_est', 'v_est_edited', 'c_shown', 'c_also', 'c_maybe'})
        self.assertEqual((f[A]["in_h1"], f[A]["vote"], f[A]["hyp_share"]), (1.0, 1.0, 1.0))
        self.assertEqual((f[B]["target_rank_inv"], f[B]["vote"], f[B]["seed_maybe"], f[B]["same_class_h1"]), (0.5, 0.5, 1.0, 1.0))
        self.assertEqual((f[C]["anchor_only"], f[C]["same_file_h1"], f[C]["vote"]), (1.0, 0.0, 0.0))
        self.assertEqual((f[D]["seed_rank_inv"], f[D]["seed_relevant"], f[D]["target_rank_inv"]), (1.0, 1.0, 0.0))
        self.assertEqual(matrix(rows).shape, (4, len(FEATURES)))

    def test_issue_trace_and_seed_features(self) -> None:
        parse = "Method:pkg/parser.py:Parser.parse_line"
        other = "Function:pkg/util.py:helper_func"
        a3 = {"samples": 1, "dropped": [], "hypotheses": [hyp("H1", [parse], sample_ids=[0])]}
        a2 = {"seeds": [{"id": other, "verdict": "relevant", "score": 2.0, "hit_by": ["a", "b"]},
                        {"id": parse, "verdict": "maybe", "score": 1.0, "hit_by": ["a"]}]}
        f = {r["node"]: r["features"] for r in candidates(a3, a2, issue="Parser breaks in parser.py", trace="in helper_func")}
        self.assertEqual((f[parse]["named_in_issue"], f[parse]["class_named"], f[parse]["file_named"], f[parse]["in_trace"]), (0.0, 1.0, 1.0, 0.0))
        self.assertEqual((f[other]["in_trace"], f[other]["seed_score"], f[other]["seed_hits"], f[parse]["seed_score"]), (1.0, 1.0, 1.0, 0.5))

    def test_conditional_logit_ranks_gold_first_within_each_instance(self) -> None:
        rng = np.random.default_rng(1)
        groups = []
        for _ in range(200):
            x = rng.uniform(size=(6, 2))
            y = np.zeros(6)
            y[np.argmax(x[:, 0] + 0.3 * rng.normal(size=6))] = 1
            groups.append((x, y))
        w = fit_conditional_logit(groups, l2=0.1)
        self.assertGreater(w[0], 3 * abs(w[1]))
        self.assertEqual(len(fit_conditional_logit([(np.ones((2, 2)), np.zeros(2))] + groups[:5])), 2)  # no-gold instance skipped

    def test_graph_discovery_appends_new_functions_and_flags_sources(self) -> None:
        a3 = {"samples": 1, "dropped": [], "hypotheses": [hyp("H1", [A], sample_ids=[0])]}
        new = "Function:pkg/z.py:callee"
        graph = [{"node": A, "sources": ["root"]}, {"node": new, "sources": ["call hop 1"]}, {"node": "File:pkg/z.py", "sources": ["region file/import"]}]
        rows = candidates(a3, A2, graph=graph)
        self.assertEqual([r["node"] for r in rows][-1], new)  # appended after the A2/A3 candidates; File nodes skipped
        f = {r["node"]: r["features"] for r in rows}
        self.assertEqual((f[A]["g_root"], f[A]["g_call1"], f[new]["g_call1"], f[new]["target_rank_inv"]), (1.0, 0.0, 1.0, 0.0))
        self.assertEqual([r['node'] for r in rows[:-1]], [r['node'] for r in candidates(a3, A2)])  # prior order unchanged

    def test_decide_orders_by_calibrated_probability_and_answers_the_expected_f1_prefix(self) -> None:
        rows = [{"node": "a", "features": {"in_h1": 0.0}}, {"node": "b", "features": {"in_h1": 1.0}}, {"node": "c", "features": {"in_h1": 1.0}}]
        ranked, k = decide(rows, {"features": ["in_h1"], "weights": [-3.0, 6.0]})
        self.assertEqual(([n for n, _ in ranked], k), (["b", "c", "a"], 2))  # p = .95, .95, .05
        frozen = load_calibrator()
        self.assertEqual((frozen["features"], len(frozen["weights"])), (list(FEATURES_V5), len(FEATURES_V5) + 1))

    def test_old_artifacts_count_merges_as_votes(self) -> None:
        a3 = {"samples": 2, "dropped": [{"reason": "merged into H1"}], "hypotheses": [hyp("H1", [A]), hyp("H2", [B])]}
        f = {r["node"]: r["features"] for r in candidates(a3, A2)}
        self.assertEqual((f[A]["vote"], f[B]["vote"]), (1.0, 0.5))

    def test_expected_f1_matches_enumeration(self) -> None:
        p = [0.9, 0.6, 0.3, 0.05]
        for k, got in enumerate(expected_f1(p), 1):
            want = 0.0
            for labels in itertools.product((0, 1), repeat=len(p)):
                prob = math.prod(q if y else 1 - q for q, y in zip(p, labels))
                tp, g = sum(labels[:k]), sum(labels)
                want += prob * (2 * tp / (k + g) if tp else 0.0)
            self.assertAlmostEqual(got, want, places=12)
        self.assertEqual(expected_f1_prefix([0.95, 0.9, 0.02]), 2)
        self.assertEqual(expected_f1_prefix([0.6, 0.1, 0.1]), 1)

    def test_crc_threshold_meets_its_bound_and_shrinks_with_alpha(self) -> None:
        cal = [([0.9, 0.5, 0.2], [True, False, True], 2), ([0.8, 0.4], [False, True], 1), ([0.7, 0.3], [True, False], 2)]
        n = len(cal)
        for alpha in (0.6, 0.8):
            lam = crc_threshold(cal, alpha)
            loss = sum(1 - sum(g for s, g in zip(sc, gl) if s >= lam) / ng for sc, gl, ng in cal) / n
            self.assertLessEqual(n / (n + 1) * loss + 1 / (n + 1), alpha)
        self.assertLessEqual(crc_threshold(cal, 0.6), crc_threshold(cal, 0.8))  # stricter recall, lower threshold
        self.assertEqual(crc_threshold(cal, 0.1), -math.inf)  # the third instance's second gold is never a candidate

    def test_ranking_and_set_metrics(self) -> None:
        g = {"f"}
        self.assertEqual([average_precision(x, g) for x in (["f"], ["f", "a", "b"], ["a", "f"], [])], [1.0, 1.0, 0.5, 0.0])
        self.assertAlmostEqual(ndcg(["a", "f"], {"f", "x"}), (1 / math.log2(3)) / (1 + 1 / math.log2(3)))
        self.assertEqual(set_metrics(["f", "a", "b", "c", "d"], g)[:3], (1.0, 1.0, 0.2))
        self.assertEqual(set_metrics([], g), (0.0, 0.0, 0.0, 0.0))

    def test_logistic_recovers_a_monotone_signal(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(size=(2000, 2))
        y = (rng.uniform(size=2000) < 1 / (1 + np.exp(-(4 * x[:, 0] - 2)))).astype(float)
        w = fit_logistic(x, y, l2=0.1)
        self.assertGreater(w[1], 2.5)
        self.assertLess(abs(w[2]), 0.6)
        p = predict(w, x)
        self.assertTrue(((p > 0) & (p < 1)).all())


if __name__ == "__main__":
    unittest.main()
