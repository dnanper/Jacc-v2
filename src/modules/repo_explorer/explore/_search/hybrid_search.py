"""Hybrid search with Reciprocal Rank Fusion (RRF).

Port of GitNexus search/hybrid-search.ts.

Combines BM25 (keyword) and semantic (embedding) search results using
RRF to merge rankings without needing score normalization.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bm25_search import BM25SearchResult

# Standard RRF smoothing constant — higher values reduce the penalty for
# lower-ranked items, producing more uniform fusion.  60 is the default
# from the original RRF paper (Cormack et al., 2009).
RRF_K = 60


@dataclass
class SemanticSearchResult:
    node_id: str
    name: str
    label: str
    file_path: str
    distance: float
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class HybridSearchResult:
    file_path: str
    score: float
    rank: int
    sources: list[str]

    node_id: str | None = None
    name: str | None = None
    label: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    bm25_score: float | None = None
    semantic_score: float | None = None


def merge_with_rrf(
    bm25_results: list[BM25SearchResult],
    semantic_results: list[SemanticSearchResult],
    limit: int = 10,
) -> list[HybridSearchResult]:
    """Merge BM25 and semantic results using Reciprocal Rank Fusion.

    RRF score = sum(1 / (K + rank)) across all sources.
    """
    merged: dict[str, HybridSearchResult] = {}

    for i, r in enumerate(bm25_results):
        rrf_score = 1 / (RRF_K + i + 1)
        merged[r.file_path] = HybridSearchResult(
            file_path=r.file_path,
            score=rrf_score,
            rank=0,
            sources=["bm25"],
            bm25_score=r.score,
        )

    for i, r in enumerate(semantic_results):
        rrf_score = 1 / (RRF_K + i + 1)

        existing = merged.get(r.file_path)
        if existing:
            existing.score += rrf_score
            existing.sources.append("semantic")
            existing.semantic_score = 1 - r.distance
            existing.node_id = r.node_id
            existing.name = r.name
            existing.label = r.label
            existing.start_line = r.start_line
            existing.end_line = r.end_line
        else:
            merged[r.file_path] = HybridSearchResult(
                file_path=r.file_path,
                score=rrf_score,
                rank=0,
                sources=["semantic"],
                semantic_score=1 - r.distance,
                node_id=r.node_id,
                name=r.name,
                label=r.label,
                start_line=r.start_line,
                end_line=r.end_line,
            )

    sorted_results = sorted(merged.values(), key=lambda r: r.score, reverse=True)[
        :limit
    ]

    for i, r in enumerate(sorted_results):
        r.rank = i + 1

    return sorted_results
