from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MODULES = ROOT / "src" / "modules"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from embeddings import embedding_pipeline
from repo_explorer.graph.storage.code_adapter import LadybugAdapter


class _FakeOpenAIEmbeddings:
    instances: list["_FakeOpenAIEmbeddings"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.document_inputs: list[list[str]] = []
        self.query_inputs: list[str] = []
        self.instances.append(self)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_inputs.append(texts)
        return [[3.0, 4.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_inputs.append(text)
        return [3.0, 4.0]


class OpenAIEmbeddingsTest(unittest.TestCase):
    def tearDown(self) -> None:
        embedding_pipeline.dispose_model()
        _FakeOpenAIEmbeddings.instances.clear()

    def test_get_or_create_model_uses_langchain_openai_embeddings(self) -> None:
        with patch.object(
            embedding_pipeline,
            "OpenAIEmbeddings",
            _FakeOpenAIEmbeddings,
            create=True,
        ):
            model = embedding_pipeline.get_or_create_model()
            vectors = model.embed_documents(["alpha", "beta"])

        self.assertIsInstance(model, _FakeOpenAIEmbeddings)
        self.assertEqual(vectors, [[3.0, 4.0], [3.0, 4.0]])
        self.assertEqual(model.document_inputs, [["alpha", "beta"]])
        self.assertEqual(
            model.kwargs,
            {"model": "text-embedding-3-small", "dimensions": 768},
        )


class LadybugVectorSearchTest(unittest.TestCase):
    def test_vector_search_embeds_query_and_returns_similarity(self) -> None:
        adapter = LadybugAdapter.__new__(LadybugAdapter)
        adapter.search_vector = lambda vector, limit: [
            {
                "nodeId": "n1",
                "name": "search_users",
                "label": "Function",
                "filePath": "src/users.py",
                "distance": 0.25,
            }
        ]

        class FakeModel:
            def __init__(self) -> None:
                self.queries: list[str] = []

            def embed_query(self, query: str) -> list[float]:
                self.queries.append(query)
                return [0.6, 0.8]

        fake_model = FakeModel()
        fake_mmr = types.SimpleNamespace(
            MMRCandidate=lambda id, vector, similarity, metadata: types.SimpleNamespace(
                id=id,
                vector=vector,
                similarity=similarity,
                metadata=metadata,
            ),
            mmr_rerank=lambda candidates, k, lambda_param: candidates[:k],
        )

        with (
            patch.object(embedding_pipeline, "get_or_create_model", return_value=fake_model),
            patch.dict(sys.modules, {"repo_explorer.explore._search.mmr": fake_mmr}),
        ):
            rows = adapter.vector_search("find user lookup", top_k=3, use_mmr=False)

        self.assertEqual(
            fake_model.queries,
            [embedding_pipeline.QUERY_PREFIX + "find user lookup"],
        )
        self.assertEqual(rows[0]["similarity"], 0.75)
        self.assertNotIn("distance", rows[0])


if __name__ == "__main__":
    unittest.main()
