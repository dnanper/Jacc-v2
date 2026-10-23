from __future__ import annotations

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules import embed as embed_mod
from src.modules.embed import Embedder, add_dense, code_text, cosine, issue_queries, node_texts
from src.utils.llm_guard import ENV_VAR


class FakeClient:
    """Deterministic 4-d vectors from character counts; records every request."""

    def __init__(self):
        self.requests = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, model, input):
        self.requests.append(list(input))
        data = [SimpleNamespace(embedding=[t.count("a") + 1, t.count("b"), t.count("c"), len(t) % 3]) for t in input]
        return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=sum(len(t) for t in input)))


class EmbedTest(unittest.TestCase):
    def test_vectors_are_unit_cached_and_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            client = FakeClient()
            e = Embedder(Path(d) / "c.sqlite", client=client)
            v = e.embed(["aab", "ccc", "aab"])
            self.assertEqual(v.shape, (3, 4))
            np.testing.assert_allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-3)
            np.testing.assert_allclose(v[0], v[2], atol=1e-3)
            self.assertEqual(client.requests, [["aab", "ccc"]])  # duplicates sent once
            again = Embedder(Path(d) / "c.sqlite", client=client).embed(["ccc", "aab"])  # a new process reads the cache
            self.assertEqual(len(client.requests), 1)
            np.testing.assert_allclose(again[1], v[0], atol=1e-3)

    def test_offline_never_calls_and_zero_fills(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Embedder(Path(d) / "c.sqlite", client=None).embed(["never embedded"], offline=True)
            self.assertFalse(v.any())

    def test_real_path_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            saved = os.environ.pop(ENV_VAR, None)
            try:
                with self.assertRaises(RuntimeError):
                    Embedder(Path(d) / "c.sqlite", client=None).embed(["needs the API"])
            finally:
                if saved is not None:
                    os.environ[ENV_VAR] = saved

    def test_code_text_and_cosine(self) -> None:
        t = code_text("a.py::F.g", "g(self, x)", "Doc.", "def g(self, x):\n    return x\n")
        self.assertTrue(t.startswith("a.py::F.g\ng(self, x)\nDoc."))
        np.testing.assert_allclose(cosine(np.array([1.0, 0.0]), np.array([[1.0, 0.0], [0.0, 1.0]])), [1.0, 0.0])

    def test_dense_features_rank_candidates_by_issue_similarity(self) -> None:
        issue = SimpleNamespace(title="aaa", summary="", observed="", expected="", explicit_code_refs=[], error_messages=["E"])
        queries = issue_queries("aaaa issue", issue)
        self.assertEqual(queries, ["aaaa issue", "aaa\nE"])
        graph = {"Function:x.py:f": {"id": "Function:x.py:f", "sig": "f()", "code": "aaaa"},
                 "Function:x.py:g": {"id": "Function:x.py:g", "sig": "g()", "code": "cccc"}}
        texts = node_texts(lambda cy, p: [graph[i] for i in p["ids"] if i in graph], list(graph))
        self.assertIn("aaaa", texts["Function:x.py:f"])
        rows = [{"node": n, "features": {}} for n in ("Function:x.py:g", "Function:x.py:f")]
        with tempfile.TemporaryDirectory() as d:
            add_dense(rows, queries, texts, Embedder(Path(d) / "c.sqlite", client=FakeClient()))
        g, f = (r["features"] for r in rows)
        self.assertGreater(f["dense_sim"], g["dense_sim"])
        self.assertEqual((f["dense_rank_inv"], g["dense_rank_inv"]), (1.0, 0.5))

    def test_api_reply_is_matched_by_index_and_must_be_complete(self) -> None:
        def reply(data):
            return SimpleNamespace(embeddings=SimpleNamespace(create=lambda model, input: SimpleNamespace(data=data, usage=None)))
        with tempfile.TemporaryDirectory() as d:
            swapped = [SimpleNamespace(embedding=[0, 1], index=1), SimpleNamespace(embedding=[1, 0], index=0)]
            v = Embedder(Path(d) / "a.sqlite", client=reply(swapped)).embed(["x", "y"])
            np.testing.assert_allclose(v, [[1, 0], [0, 1]], atol=1e-3)  # by index, not by arrival order
            with self.assertRaises(RuntimeError):  # a short reply never becomes a zero vector
                Embedder(Path(d) / "b.sqlite", client=reply(swapped[:1])).embed(["x", "y"])

    def test_offline_with_an_empty_cache_keeps_the_model_size(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(Embedder(Path(d) / "c.sqlite").embed(["x"], offline=True).shape, (1, embed_mod.DIM))


class LoadOrVerifyDenseTest(unittest.TestCase):
    """The pipeline embeds the candidates before the paid verifier call and keeps the dense features after it."""

    F, G = "Function:pkg/a.py:aaa", "Function:pkg/b.py:ccc"

    def run_step(self, d: Path, embedder):
        import src.run_localize as rl
        from src.modules.issue_model import IssueModel, Scenario
        issue = IssueModel(title="aaa", issue_type="bug", report_class="code_identifiers", summary="aaa", scenario=Scenario(precondition="", action="", path=""),
                           reproduction_steps=[], observed="", expected="", error_messages=[], stack_trace="", code_snippets=[], environment=[],
                           reporter_hypotheses=[], key_concepts=[], explicit_code_refs=[], assumptions=[], unknowns=[])
        (d / "a2.json").write_text(json.dumps({"seeds": [{"id": self.F, "verdict": "relevant", "score": 1.0, "hit_by": ["aaa"]}]}))
        (d / "a3.json").write_text(json.dumps({"samples": 1, "dropped": [], "hypotheses": [
            {"id": "H1", "anchors": [{"node": self.F, "role": "target", "via": "self"}], "sample_ids": [0]}]}))
        state = {"artifacts": {"A2": str(d / "a2.json"), "A3": str(d / "a3.json")}, "issue_model": issue.model_dump(), "snapshot": {"path": str(d)}}
        inst = SimpleNamespace(instance_id="t-1", problem_statement="aaa is broken", language="python", repo="r", base_commit="c")
        cal = {"version": "test_dense", "features": ["dense_sim", "dense_rank_inv"], "weights": [0.0, 4.0, 1.0], "recall_p": 0.5}
        order = []
        verify = MagicMock(side_effect=lambda *a, **k: order.append("verify") or {"shown": [self.F, self.G], "labels": {}, "ranking": [], "edited_count": 0})
        self.verify = verify
        def make_embedder():
            order.append("embed")
            return embedder
        with patch.object(rl, "load_calibrator", return_value=cal), \
             patch.object(rl, "discover", return_value=([], [{"node": self.G, "sources": ["call hop 1"]}], [], set())), \
             patch.object(rl, "node_texts", side_effect=lambda q, ids: {n: n.split(":")[-1] for n in ids}), \
             patch.object(rl, "Embedder", side_effect=make_embedder), \
             patch.object(rl, "instrument_llm", return_value=(None, None)), \
             patch.object(rl, "verify", verify):
            path = rl.load_or_verify(d, inst, MagicMock(), "m", state, query=None, force=True)
        return path, order, verify

    def test_dense_features_reach_the_calibrator(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path, order, _ = self.run_step(Path(d), Embedder(Path(d) / "c.sqlite", client=FakeClient()))
            out = json.loads(path.read_text())
        self.assertEqual(order, ["embed", "verify"])
        self.assertGreaterEqual(out["embed"]["calls"], 1)
        self.assertEqual([r["node"] for r in out["ranked"]], [self.F, self.G])  # 'aaa' is closer to the issue than 'ccc'

    def test_an_embedding_failure_costs_no_verifier_call(self) -> None:
        broken = SimpleNamespace(embeddings=SimpleNamespace(create=MagicMock(side_effect=RuntimeError("API down"))))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                self.run_step(Path(d), Embedder(Path(d) / "c.sqlite", client=broken))
            self.assertFalse(any(Path(d).glob("A3V_verify*.json")))
        self.assertEqual(self.verify.call_count, 0)


if __name__ == "__main__":
    unittest.main()
