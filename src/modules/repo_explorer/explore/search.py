"""Search mixin — hybrid (BM25 + semantic) and pure semantic search."""

from __future__ import annotations

import logging

from ._search.bm25_search import search_fts
from ._search.hybrid_search import SemanticSearchResult, merge_with_rrf

logger = logging.getLogger(__name__)


class SearchMixin:
    """Hybrid and semantic search capabilities."""

    def query(self, query: str, limit: int = 10) -> dict:
        """Hybrid search -- BM25 + semantic."""
        from concurrent.futures import ThreadPoolExecutor

        bm25_results = []
        semantic_results: list[SemanticSearchResult] = []

        # Capture adapter before spawning threads — _adapter uses thread-local
        # storage which isn't visible to ThreadPoolExecutor workers.
        adapter = self._adapter
        execute_query = adapter.execute_query

        def _bm25():
            return search_fts(
                execute_query=execute_query,
                query=query,
                limit=limit,
            )

        def _semantic():
            rows = adapter.vector_search(query_text=query, top_k=limit)
            return [
                SemanticSearchResult(
                    node_id=row.get("nodeId", ""),
                    name=row.get("name", ""),
                    label=row.get("label", ""),
                    file_path=row.get("filePath", ""),
                    distance=1.0 - row.get("similarity", 0.0),
                    start_line=row.get("startLine"),
                    end_line=row.get("endLine"),
                )
                for row in rows
            ]

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_bm25 = pool.submit(_bm25)
            fut_sem = pool.submit(_semantic)

            try:
                bm25_results = fut_bm25.result()
            except Exception as exc:
                logger.debug("BM25 search failed: %s", exc)

            try:
                semantic_results = fut_sem.result()
            except Exception as exc:
                logger.debug("Semantic search unavailable: %s", exc)

        results = merge_with_rrf(bm25_results, semantic_results, limit)

        enriched = []
        for r in results:
            item = {
                "filePath": r.file_path,
                "score": r.score,
                "rank": r.rank,
                "sources": r.sources,
            }

            try:
                symbols = self._adapter.match_by_file(r.file_path, limit=10)
                item["symbols"] = symbols
            except Exception as exc:
                logger.debug("Symbol lookup failed for %s: %s", r.file_path, exc)
                item["symbols"] = []

            enriched.append(item)

        return {"results": enriched, "total": len(enriched)}

    def semantic_search(
        self, query: str, limit: int = 10, use_mmr: bool = False
    ) -> dict:
        """Pure semantic search using KuzuDB native vector index."""
        try:
            rows = self._adapter.vector_search(
                query_text=query,
                top_k=limit,
                use_mmr=use_mmr,
            )
        except Exception as exc:
            return {"error": f"Vector search not available: {exc}"}

        if not rows:
            return {"results": [], "total": 0}

        enriched = []
        for r in rows:
            item = {
                "nodeId": r.get("nodeId", ""),
                "name": r.get("name", ""),
                "label": r.get("label", ""),
                "filePath": r.get("filePath", ""),
                "score": r.get("similarity", 0),
                "startLine": r.get("startLine"),
                "endLine": r.get("endLine"),
            }

            try:
                symbols = self._adapter.match_by_file(r.get("filePath", ""), limit=10)
                item["symbols"] = symbols
            except Exception:
                item["symbols"] = []

            enriched.append(item)

        return {
            "results": enriched,
            "total": len(enriched),
        }
