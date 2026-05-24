"""Maximal Marginal Relevance (MMR) reranking.

MMR balances relevance to the query with diversity among selected results,
reducing redundancy when multiple hits come from the same file or module.

Score: MMR(d) = lambda * sim(query, d) - (1 - lambda) * max(sim(d, s) for s in selected)

References:
    Carbonell & Goldstein, "The Use of MMR, Diversity-Based Reranking for
    Reordering Documents and Producing Summaries", SIGIR 1998.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


@dataclass
class MMRCandidate:
    """A candidate for MMR reranking."""

    id: str
    vector: list[float]
    similarity: float
    metadata: dict


DEFAULT_LAMBDA = 0.7


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure-Python fallback)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def mmr_rerank(
    candidates: list[MMRCandidate],
    k: int = 10,
    lambda_param: float = DEFAULT_LAMBDA,
) -> list[MMRCandidate]:
    """Rerank candidates using Maximal Marginal Relevance.

    Uses numpy-vectorized cosine similarity when available (10-100x faster).

    Args:
        candidates: Pre-scored candidates with vectors and similarity.
        k: Number of results to return.
        lambda_param: Trade-off between relevance (1.0) and diversity (0.0).

    Returns:
        Top-k reranked candidates balancing relevance and diversity.
    """
    if not candidates or k <= 0:
        return []

    if len(candidates) <= k:
        return sorted(candidates, key=lambda c: c.similarity, reverse=True)

    if _HAS_NUMPY:
        return _mmr_rerank_numpy(candidates, k, lambda_param)
    return _mmr_rerank_pure(candidates, k, lambda_param)


def _mmr_rerank_numpy(
    candidates: list[MMRCandidate],
    k: int,
    lambda_param: float,
) -> list[MMRCandidate]:
    """MMR reranking using numpy for vectorized cosine similarity."""
    n = len(candidates)

    vectors = np.array([c.vector for c in candidates], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    vectors = vectors / norms

    relevance = np.array([c.similarity for c in candidates], dtype=np.float32)

    selected_indices: list[int] = []
    remaining = set(range(n))

    for _ in range(k):
        if not remaining:
            break

        best_score = -float("inf")
        best_idx = -1

        for i in remaining:
            if selected_indices:
                sel_vecs = vectors[selected_indices]
                sims = sel_vecs @ vectors[i]
                max_sim = float(sims.max())
            else:
                max_sim = 0.0

            mmr_score = lambda_param * relevance[i] - (1 - lambda_param) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected_indices.append(best_idx)
        remaining.discard(best_idx)

    return [candidates[i] for i in selected_indices]


def _mmr_rerank_pure(
    candidates: list[MMRCandidate],
    k: int,
    lambda_param: float,
) -> list[MMRCandidate]:
    """MMR reranking using pure Python (fallback when numpy unavailable)."""
    selected: list[MMRCandidate] = []
    remaining = list(candidates)

    for _ in range(k):
        best_score = -float("inf")
        best_idx = 0

        for i, cand in enumerate(remaining):
            relevance = cand.similarity

            if selected:
                max_sim_to_selected = max(
                    _cosine_similarity(cand.vector, s.vector) for s in selected
                )
            else:
                max_sim_to_selected = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected
