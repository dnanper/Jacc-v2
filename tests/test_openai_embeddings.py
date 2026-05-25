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


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.data = [_FakeEmbeddingItem(v) for v in vectors]


class _FakeEmbeddingsResource:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        inputs = kwargs["input"]
        if isinstance(inputs, str):
            return _FakeEmbeddingResponse([[3.0, 4.0]])
        return _FakeEmbeddingResponse([[3.0, 4.0] for _ in inputs])


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsResource()


class OpenAIEmbeddingModelTest(unittest.TestCase):
    def tearDown(self) -> None:
        embedding_pipeline.dispose_model()

    def test_openai_embedding_model_uses_configured_model_and_dimensions(self) -> None:
        client = _FakeOpenAIClient()

        with patch.object(embedding_pipeline, "OpenAI", return_value=client):
            model = embedding_pipeline.get_or_create_model()
            vectors = model.embed_documents(["alpha", "beta"])

        self.assertEqual(vectors, [[0.6, 0.8], [0.6, 0.8]])
        self.assertEqual(
            client.embeddings.calls,
            [
                {
                    "model": "text-embedding-3-small",
                    "input": ["alpha", "beta"],
                    "dimensions": 768,
                }
            ],
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
