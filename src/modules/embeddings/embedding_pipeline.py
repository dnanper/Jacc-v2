"""Embedding pipeline — OpenAI embeddings orchestration.

Uses OpenAI's embedding API with 768 output dimensions, then bulk-loads to
LadybugDB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import sqrt

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised only without dependency
    OpenAI = None  # type: ignore[assignment]

from modules.repo_explorer.graph.core.knowledge_graph import KnowledgeGraph

from .text_generator import (
    EMBEDDABLE_LABELS,
    EmbeddableNode,
    generate_embedding_text,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "text-embedding-3-small"
DEFAULT_BATCH_SIZE = 32
DEFAULT_DIMENSIONS = 768
DEFAULT_MAX_SNIPPET_LENGTH = 500

QUERY_PREFIX = "Represent this query for searching relevant code: "


def _esc_csv(val) -> str:
    """Escape a value for safe CSV embedding (RFC 4180)."""
    if val is None:
        return ""
    s = str(val)
    if '"' in s or "," in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s


class OpenAIEmbeddingModel:
    """Small LangChain-like wrapper around OpenAI embeddings."""

    def __init__(self, model_id: str, dimensions: int) -> None:
        if OpenAI is None:
            raise RuntimeError(
                "OpenAI embeddings require the 'openai' package. "
                "Install project dependencies before running embeddings."
            )
        self.model_id = model_id
        self.dimensions = dimensions
        self._client = OpenAI()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self.model_id,
            input=texts,
            dimensions=self.dimensions,
        )
        return [_normalize_vector(item.embedding) for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self.model_id,
            input=text,
            dimensions=self.dimensions,
        )
        return _normalize_vector(response.data[0].embedding)


_model_instance: OpenAIEmbeddingModel | None = None
_model_config: tuple[str, int] | None = None


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def get_or_create_model(
    model_id: str = DEFAULT_MODEL_ID,
    device: str = "auto",
    dimensions: int = DEFAULT_DIMENSIONS,
) -> OpenAIEmbeddingModel:
    """Return a cached OpenAI embedding model wrapper.

    ``device`` is retained for backward-compatible callers, but ignored because
    OpenAI embeddings are remote.
    """
    global _model_instance, _model_config

    key = (model_id, dimensions)

    if _model_instance is not None and _model_config == key:
        return _model_instance

    logger.info(
        "Initializing OpenAI embedding model %s with %d dimensions",
        model_id,
        dimensions,
    )
    _model_instance = OpenAIEmbeddingModel(model_id=model_id, dimensions=dimensions)
    _model_config = key
    return _model_instance


def dispose_model() -> None:
    """Release the cached embedding model."""
    global _model_instance, _model_config
    _model_instance = None
    _model_config = None
    logger.debug("Embedding model disposed")


@dataclass
class EmbeddingConfig:
    model_id: str = DEFAULT_MODEL_ID
    batch_size: int = DEFAULT_BATCH_SIZE
    dimensions: int = DEFAULT_DIMENSIONS
    max_snippet_length: int = DEFAULT_MAX_SNIPPET_LENGTH
    device: str = "auto"


@dataclass
class EmbeddingResult:
    total_embedded: int
    total_upserted: int


def restore_cached_embeddings(adapter, cached: list[dict]) -> int:
    """Re-insert previously cached embeddings into the CodeEmbedding table.

    Returns the number of restored rows.
    """
    if not cached:
        return 0

    import os
    import tempfile

    csv_dir = tempfile.mkdtemp(prefix="csg_embed_cache_")
    csv_path = os.path.join(csv_dir, "CodeEmbedding.csv")

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("id,nodeId,name,label,filePath,startLine,endLine,embedding\n")
            for row in cached:
                emb = row.get("embedding", [])
                vec_str = "[" + ",".join(str(v) for v in emb) + "]"

                f.write(
                    f"{_esc_csv(row.get('nodeId', ''))},{_esc_csv(row.get('nodeId', ''))},"
                    f"{_esc_csv(row.get('name', ''))},{_esc_csv(row.get('label', ''))},"
                    f"{_esc_csv(row.get('filePath', ''))},"
                    f"{row.get('startLine') or ''},"
                    f"{row.get('endLine') or ''},"
                    f'"{vec_str}"\n'
                )

        count = adapter.store_embeddings(csv_path)
    finally:
        import shutil

        shutil.rmtree(csv_dir, ignore_errors=True)

    logger.info("Restored %d cached embeddings", count)
    return count


def run_embedding_pipeline(
    graph: KnowledgeGraph,
    repo_name: str,
    adapter,
    config: EmbeddingConfig | None = None,
    on_progress: callable = None,
    skip_node_ids: set[str] | None = None,
) -> EmbeddingResult:
    """Run the full embedding pipeline: extract nodes → embed → upsert.

    Args:
        graph: In-memory knowledge graph with nodes to embed.
        repo_name: Repository name for the LadybugDB database.
        adapter: LadybugAdapter instance (duck-typed).
        config: Embedding configuration.
        on_progress: Optional (message, percent) callback.
        skip_node_ids: Node IDs to skip (already have cached embeddings).

    Returns:
        EmbeddingResult with counts.
    """
    cfg = config or EmbeddingConfig()

    if on_progress:
        on_progress("Loading embedding model...", 0)

    embeddings_model = get_or_create_model(
        cfg.model_id,
        cfg.device,
        dimensions=cfg.dimensions,
    )

    batch_size = cfg.batch_size

    if on_progress:
        on_progress("Collecting embeddable nodes...", 10)

    embeddable_nodes: list[EmbeddableNode] = []
    skipped = 0
    for node in graph.iter_nodes():
        if node.label not in EMBEDDABLE_LABELS:
            continue
        # Skip binary files — no useful text to embed
        if node.properties.get("binary"):
            continue
        content = node.properties.get("content", "")
        if not content and node.label != "File":
            continue
        if skip_node_ids and node.id in skip_node_ids:
            skipped += 1
            continue

        embeddable_nodes.append(
            EmbeddableNode(
                id=node.id,
                name=node.properties.get("name", ""),
                label=node.label,
                file_path=node.properties.get("filePath", ""),
                content=content,
                start_line=node.properties.get("startLine"),
                end_line=node.properties.get("endLine"),
            )
        )

    total = len(embeddable_nodes)
    if skipped:
        logger.info("Incremental: %d cached, %d new nodes to embed", skipped, total)
    if total == 0:
        logger.info("No new embeddable nodes found")
        return EmbeddingResult(total_embedded=0, total_upserted=0)

    logger.info("Embedding %d nodes with %s", total, cfg.model_id)

    if on_progress:
        on_progress(f"Embedding {total} nodes...", 20)

    all_points: list[dict] = []

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = embeddable_nodes[batch_start:batch_end]

        texts = [generate_embedding_text(n, cfg.max_snippet_length) for n in batch]

        vectors = embeddings_model.embed_documents(texts)

        for node, vector in zip(batch, vectors):
            if len(vector) != cfg.dimensions:
                raise ValueError(
                    f"Embedding for {node.id} has {len(vector)} dimensions; "
                    f"expected {cfg.dimensions}"
                )
            all_points.append(
                {
                    "vector": vector,
                    "payload": {
                        "nodeId": node.id,
                        "name": node.name,
                        "label": node.label,
                        "filePath": node.file_path,
                        "startLine": node.start_line,
                        "endLine": node.end_line,
                    },
                }
            )

        if on_progress:
            pct = 20 + int(70 * batch_end / total)
            on_progress(f"Embedded {batch_end}/{total} nodes...", pct)

    import os
    import tempfile

    if on_progress:
        on_progress("Uploading to LadybugDB...", 90)

    csv_dir = tempfile.mkdtemp(prefix="csg_embed_")
    csv_path = os.path.join(csv_dir, "CodeEmbedding.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("id,nodeId,name,label,filePath,startLine,endLine,embedding\n")
        for point in all_points:
            payload = point["payload"]
            vec_str = "[" + ",".join(str(v) for v in point["vector"]) + "]"
            f.write(
                f"{_esc_csv(payload.get('nodeId', ''))},{_esc_csv(payload.get('nodeId', ''))},"
                f"{_esc_csv(payload.get('name', ''))},{_esc_csv(payload.get('label', ''))},"
                f"{_esc_csv(payload.get('filePath', ''))},"
                f"{payload.get('startLine') or ''},"
                f"{payload.get('endLine') or ''},"
                f'"{vec_str}"\n'
            )

    upserted = adapter.store_embeddings(csv_path)

    try:
        adapter.create_vector_index()
    except Exception as exc:
        logger.debug("Vector index creation skipped (may already exist): %s", exc)

    import shutil

    shutil.rmtree(csv_dir, ignore_errors=True)

    if on_progress:
        on_progress("Embedding pipeline complete!", 100)

    logger.info("Embedded %d nodes, upserted %d points", total, upserted)
    return EmbeddingResult(total_embedded=total, total_upserted=upserted)
