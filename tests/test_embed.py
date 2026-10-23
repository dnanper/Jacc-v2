from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

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


if __name__ == "__main__":
    unittest.main()
