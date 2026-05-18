"""LadybugDB (KuzuDB) adapter — schema, bulk load, queries, FTS, vector search.

Replaces the Neo4j adapter. Uses KuzuDB as an embedded graph database
stored centrally under data/repos/{hash}/lbug.
"""

from __future__ import annotations

import logging
import math
import os
import shutil

import kuzu
from graph.core.knowledge_graph import KnowledgeGraph
from graph.schema.code_schema import (
    EMBEDDING_SCHEMA_QUERY,
    FTS_INDEXES,
    NODE_SCHEMA_QUERIES,
    NODE_TABLES,
    REL_SCHEMA_QUERY,
    escape_table_name,
)

logger = logging.getLogger(__name__)

SEARCH_TABLES: list[str] = [
    "Function",
    "Class",
    "Method",
    "Interface",
    "File",
    "Struct",
    "Enum",
    "Trait",
    "Impl",
    "Property",
    "Constructor",
    "TypeAlias",
    "Const",
    "Static",
    "Record",
    "Delegate",
    "Macro",
    "Module",
    "Section",
]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class LadybugAdapter:
    """KuzuDB (LadybugDB) database adapter for CSG."""

    def __init__(self, db_path: str, repo_source_path: str | None = None) -> None:
        self._db_path = db_path
        self.repo_source_path: str | None = repo_source_path
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None
        self._name_cache: dict[tuple[str, int], list[dict]] = {}
        self._name_cache_max = 256

    @property
    def is_read_only(self) -> bool:
        """True if the database was opened read-only (lock held by another process)."""
        from graph.storage.kuzu_pool import KuzuPool

        return KuzuPool.get().is_read_only(self._db_path)

    def _require_writable(self) -> None:
        """Raise if database is read-only."""
        if self.is_read_only:
            raise RuntimeError(
                f"Database at {self._db_path} is read-only "
                "(another process holds the write lock)"
            )

    def connect(self, read_only: bool = False) -> None:
        """Open (or create) the KuzuDB database via the shared KuzuPool.

        Args:
            read_only: If True, open in read-only mode. If False, attempt
                read-write; falls back to read-only if another process
                holds the write lock.
        """
        from graph.storage.kuzu_pool import KuzuPool

        pool = KuzuPool.get()
        self._db = pool.get_database(self._db_path, read_only=read_only)
        self._conn = kuzu.Connection(self._db)

        mode = "read-only" if self.is_read_only else "read-write"
        logger.info("Connected to KuzuDB at %s (%s, via pool)", self._db_path, mode)

    def close(self) -> None:
        """Release the connection and database handles."""
        self._conn = None
        self._db = None
        logger.debug("KuzuDB connection closed")

    def create_schema(self) -> None:
        """Execute all schema-creation queries (node tables, rels, embeddings).

        Errors are logged and swallowed — tables may already exist from a
        previous run.
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        self._require_writable()

        for query in NODE_SCHEMA_QUERIES:
            try:
                self._conn.execute(query)
            except Exception as exc:
                logger.debug("Node schema (may already exist): %s", exc)

        try:
            self._conn.execute(REL_SCHEMA_QUERY)
        except Exception as exc:
            logger.debug("Rel schema (may already exist): %s", exc)

        try:
            self._conn.execute(EMBEDDING_SCHEMA_QUERY)
        except Exception as exc:
            logger.debug("Embedding schema (may already exist): %s", exc)

        logger.info(
            "Schema created (%d node tables + CodeRelation + CodeEmbedding)",
            len(NODE_TABLES),
        )

    def create_fts_indexes(self) -> None:
        """Create full-text search indexes defined in ``lbug_schema``."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        self._require_writable()

        for index_name, table_name, properties in FTS_INDEXES:
            props_str = ", ".join(f"'{p}'" for p in properties)
            cypher = (
                f"CALL CREATE_FTS_INDEX('{table_name}', '{index_name}', "
                f"[{props_str}], stemmer := 'porter')"
            )
            try:
                self._conn.execute(cypher)
            except Exception as exc:
                logger.debug("FTS index %s (may already exist): %s", index_name, exc)

        logger.info("FTS indexes created (%d indexes)", len(FTS_INDEXES))

    def create_vector_index(self) -> None:
        """Create a vector similarity index on CodeEmbedding.embedding."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        self._require_writable()

        try:
            self._conn.execute(
                "CALL CREATE_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', "
                "'embedding', metric := 'cosine')"
            )
        except Exception as exc:
            logger.debug("Vector index (may already exist): %s", exc)

        logger.info("Vector index created on CodeEmbedding")

    def clear_database(self) -> None:
        """Destroy and recreate the database, then reconnect."""
        self._require_writable()
        self.close()

        # Evict from pool BEFORE deleting files — pool holds the Database reference
        try:
            from graph.storage.kuzu_pool import KuzuPool

            KuzuPool.get().close(self._db_path)
        except Exception:
            pass

        if os.path.isdir(self._db_path):
            shutil.rmtree(self._db_path)
        elif os.path.exists(self._db_path):
            os.remove(self._db_path)
        self._name_cache.clear()
        self.connect()
        logger.info("Database cleared and reconnected at %s", self._db_path)

    def load_graph(self, graph: KnowledgeGraph, csv_dir: str) -> dict:
        """Export *graph* to CSV then bulk-load into KuzuDB.

        Parameters
        ----------
        graph:
            The in-memory knowledge graph to load.
        csv_dir:
            Scratch directory for intermediate CSV files.

        Returns
        -------
        dict
            ``{"node_count": int, "relationship_count": int}``
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        self._require_writable()

        from graph.storage.csv_generator import generate_csvs

        result = generate_csvs(graph, csv_dir)

        node_total = 0
        failed_tables: list[dict] = []
        for table_name, csv_path in result.files.items():
            if table_name == "CodeRelation":
                continue
            row_count = result.row_counts.get(table_name, 0)
            if row_count <= 0:
                continue
            escaped = escape_table_name(table_name)
            norm_path = csv_path.replace("\\", "/")
            try:
                self._conn.execute(
                    f"COPY {escaped} FROM '{norm_path}' "
                    f"(HEADER=true, ESCAPE='\"', DELIM=',', QUOTE='\"', "
                    f"auto_detect=false, PARALLEL=false)"
                )
                node_total += row_count
                logger.debug("Loaded %d rows into %s", row_count, table_name)
            except Exception as exc:
                failed_tables.append(
                    {
                        "table": table_name,
                        "rows": row_count,
                        "error": str(exc),
                    }
                )
                logger.error(
                    "Failed to load %s (%d rows): %s", table_name, row_count, exc
                )

        if failed_tables:
            lost = sum(f["rows"] for f in failed_tables)
            names = ", ".join(f"{f['table']}({f['rows']})" for f in failed_tables)
            logger.warning(
                "NODE COPY FAILURES: %d table(s) failed, %d rows lost: %s",
                len(failed_tables),
                lost,
                names,
            )

        # KuzuDB multi-pair rel tables don't support COPY — use
        # prepared statements grouped by (src_label, tgt_label) to avoid
        # re-parsing Cypher for every relationship.
        from collections import defaultdict

        rel_loaded = 0
        rel_failed = 0
        rel_fail_by_pair: dict[tuple[str, str], int] = defaultdict(int)

        # Group relationships by (src_label, tgt_label) for prepared stmts.
        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for rel in graph.iter_relationships():
            src = graph.get_node(rel.source_id)
            tgt = graph.get_node(rel.target_id)
            if not src or not tgt:
                rel_failed += 1
                continue
            src_lbl = escape_table_name(
                src.label.value if hasattr(src.label, "value") else str(src.label)
            )
            tgt_lbl = escape_table_name(
                tgt.label.value if hasattr(tgt.label, "value") else str(tgt.label)
            )
            groups[(src_lbl, tgt_lbl)].append(
                {
                    "s": rel.source_id,
                    "t": rel.target_id,
                    "id": rel.id,
                    "tp": str(rel.type),
                    "conf": float(rel.confidence),
                    "reason": rel.reason or "",
                    "step": str(rel.step) if rel.step is not None else "",
                    "cyc": bool(rel.in_cycle) if rel.in_cycle is not None else False,
                }
            )

        # Prepare one statement per (src_label, tgt_label) pair and batch-execute.
        for (src_lbl, tgt_lbl), params_list in groups.items():
            cypher = (
                f"MATCH (s:{src_lbl} {{id: $s}}), (t:{tgt_lbl} {{id: $t}}) "
                f"CREATE (s)-[:CodeRelation {{id: $id, type: $tp, "
                f"confidence: $conf, reason: $reason, step: $step, "
                f"inCycle: $cyc}}]->(t)"
            )
            try:
                prepared = self._conn.prepare(cypher)
            except Exception as exc:
                logger.error(
                    "Failed to prepare rel stmt (%s->%s): %s",
                    src_lbl,
                    tgt_lbl,
                    exc,
                )
                rel_failed += len(params_list)
                continue

            for params in params_list:
                try:
                    self._conn.execute(prepared, params)
                    rel_loaded += 1
                except Exception as exc:
                    rel_failed += 1
                    rel_fail_by_pair[(src_lbl, tgt_lbl)] += 1
                    logger.debug(
                        "Rel insert failed (%s->%s): %s",
                        src_lbl,
                        tgt_lbl,
                        exc,
                    )

        if rel_failed:
            top_failures = sorted(
                rel_fail_by_pair.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            pairs_str = ", ".join(f"{s}->{t}({c})" for (s, t), c in top_failures)
            logger.warning(
                "REL INSERT FAILURES: %d loaded, %d failed. Top: %s",
                rel_loaded,
                rel_failed,
                pairs_str,
            )

        logger.info(
            "Graph loaded: %d nodes, %d relationships",
            node_total,
            rel_loaded,
        )
        return {
            "node_count": node_total,
            "relationship_count": rel_loaded,
            "failed_tables": failed_tables,
        }

    def execute_query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a Cypher query and return results as a list of dicts."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        result = self._conn.execute(cypher, params or {})
        columns = result.get_column_names()
        rows: list[dict] = []
        while result.has_next():
            values = result.get_next()
            rows.append(dict(zip(columns, values)))
        return rows

    def match_by_name(self, name: str, limit: int = 5) -> list[dict]:
        """Find nodes across multiple tables by exact name match.

        Iterates over ``SEARCH_TABLES`` in priority order and stops once
        *limit* results have been collected.  Solves KuzuDB's lack of a
        single cross-label ``MATCH``.

        Results are cached (up to 256 entries) to avoid repeated cross-label
        iteration for the same symbol during layered retrieval sessions.
        """
        cache_key = (name, limit)
        if cache_key in self._name_cache:
            return self._name_cache[cache_key]

        results: list[dict] = []
        for table in SEARCH_TABLES:
            if len(results) >= limit:
                break
            escaped = escape_table_name(table)
            try:
                rows = self.execute_query(
                    f"MATCH (n:{escaped}) WHERE n.name = $name "
                    f"RETURN n.id AS id, n.name AS name, '{table}' AS type, "
                    f"n.filePath AS filePath, n.startLine AS startLine, "
                    f"n.endLine AS endLine "
                    f"LIMIT {limit - len(results)}",
                    {"name": name},
                )
                results.extend(rows)
            except Exception as exc:
                logger.debug("match_by_name query failed for %s: %s", table, exc)
                continue
        result = results[:limit]

        if len(self._name_cache) >= self._name_cache_max:
            first_key = next(iter(self._name_cache))
            del self._name_cache[first_key]
        self._name_cache[cache_key] = result
        return result

    def match_by_file(self, file_path: str, limit: int = 20) -> list[dict]:
        """Find all nodes belonging to a given file path.

        Same pattern as :meth:`match_by_name` but filters on ``filePath``.
        """
        results: list[dict] = []
        for table in SEARCH_TABLES:
            if len(results) >= limit:
                break
            escaped = escape_table_name(table)
            try:
                rows = self.execute_query(
                    f"MATCH (n:{escaped}) WHERE n.filePath = $fp "
                    f"RETURN n.id AS id, n.name AS name, '{table}' AS type, "
                    f"n.filePath AS filePath "
                    f"LIMIT {limit - len(results)}",
                    {"fp": file_path},
                )
                results.extend(rows)
            except Exception as exc:
                logger.debug("match_by_file query failed for %s: %s", table, exc)
                continue
        return results[:limit]

    def load_cached_embeddings(self) -> list[dict]:
        """Read all existing embeddings for incremental re-use.

        Returns a list of dicts with keys matching the CodeEmbedding columns.
        Returns an empty list if the table doesn't exist or is empty.
        """
        try:
            rows = self.execute_query(
                "MATCH (e:CodeEmbedding) RETURN "
                "e.id AS id, e.nodeId AS nodeId, e.name AS name, "
                "e.label AS label, e.filePath AS filePath, "
                "e.startLine AS startLine, e.endLine AS endLine, "
                "e.embedding AS embedding"
            )
            logger.info(
                "Cached %d existing embeddings for incremental re-use", len(rows)
            )
            return rows
        except Exception:
            return []

    def store_embeddings(self, csv_path: str) -> int:
        """Bulk-load embeddings from a pre-generated CSV file.

        Returns the total number of embedding rows in the table.
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        self._require_writable()

        norm_path = csv_path.replace("\\", "/")
        self._conn.execute(
            f"COPY CodeEmbedding FROM '{norm_path}' "
            f"(HEADER=true, ESCAPE='\"', DELIM=',', QUOTE='\"', "
            f"auto_detect=false, PARALLEL=false)"
        )

        result = self.execute_query("MATCH (e:CodeEmbedding) RETURN count(e) AS cnt")
        count = result[0]["cnt"] if result else 0
        logger.info("Stored embeddings — %d total rows in CodeEmbedding", count)
        return count

    def _brute_force_vector_search(
        self,
        query_vector: list[float],
        limit: int = 10,
        max_distance: float = 0.5,
        include_embedding: bool = False,
    ) -> list[dict]:
        """Fallback vector search using brute-force cosine similarity in Python.

        Fetches all CodeEmbedding rows (up to 2000) and computes cosine
        similarity against *query_vector* in pure Python.  Used when the
        KuzuDB HNSW vector index is unavailable or returns no results.

        Parameters
        ----------
        query_vector:
            The query embedding vector.
        limit:
            Maximum number of results to return.
        max_distance:
            Discard results with cosine distance above this threshold.
        include_embedding:
            If True, include the ``embedding`` field in each result row.

        Returns
        -------
        list[dict]
            Rows with keys: ``nodeId``, ``name``, ``label``, ``filePath``,
            ``startLine``, ``endLine``, ``distance``, and optionally
            ``embedding``.
        """
        embedding_col = ", e.embedding AS embedding" if include_embedding else ""
        try:
            rows = self.execute_query(
                "MATCH (e:CodeEmbedding) RETURN e.nodeId AS nodeId, "
                "e.name AS name, e.label AS label, e.filePath AS filePath, "
                "e.startLine AS startLine, e.endLine AS endLine, "
                f"e.embedding AS _embedding{embedding_col} LIMIT 2000"
            )
        except Exception as exc:
            logger.warning(
                "Brute-force vector search failed to fetch embeddings: %s", exc
            )
            return []

        if not rows:
            return []

        scored: list[tuple[float, dict]] = []
        for row in rows:
            emb = row.pop("_embedding", None)
            if emb is None:
                continue
            vec = list(emb) if not isinstance(emb, list) else emb
            if len(vec) != len(query_vector):
                continue
            similarity = _cosine_similarity(query_vector, vec)
            distance = 1.0 - similarity
            if distance <= max_distance:
                row["distance"] = distance
                scored.append((distance, row))

        scored.sort(key=lambda x: x[0])
        results = [row for _, row in scored[:limit]]
        logger.info(
            "Brute-force vector search returned %d results (scanned %d embeddings)",
            len(results),
            len(rows),
        )
        return results

    def search_vector(
        self,
        query_vector: list[float],
        limit: int = 10,
        max_distance: float = 0.5,
    ) -> list[dict]:
        """Find nearest neighbours via the vector index on CodeEmbedding.

        Falls back to brute-force cosine similarity scan if the HNSW vector
        index is unavailable or returns no results.

        Parameters
        ----------
        query_vector:
            The query embedding (must match ``EMBEDDING_DIMS``).
        limit:
            Maximum number of results to return.
        max_distance:
            Discard results with cosine distance above this threshold.

        Returns
        -------
        list[dict]
            Rows with keys: ``nodeId``, ``name``, ``label``, ``filePath``,
            ``startLine``, ``endLine``, ``distance``.
        """
        fetch_limit = limit * 2
        vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        cypher = (
            f"CALL QUERY_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', "
            f"CAST({vec_str} AS DOUBLE[{len(query_vector)}]), {fetch_limit}) "
            f"RETURN node.nodeId AS nodeId, node.name AS name, "
            f"node.label AS label, node.filePath AS filePath, "
            f"node.startLine AS startLine, node.endLine AS endLine, distance "
            f"ORDER BY distance"
        )
        try:
            rows = self.execute_query(cypher)
            results = [r for r in rows if r.get("distance", 1.0) <= max_distance][
                :limit
            ]
            if results:
                return results
            # Index query succeeded but returned 0 usable results — try brute-force
            logger.debug(
                "QUERY_VECTOR_INDEX returned %d rows, 0 after distance filter; "
                "falling back to brute-force scan",
                len(rows),
            )
        except Exception as exc:
            logger.warning(
                "QUERY_VECTOR_INDEX failed (index may not exist): %s; "
                "falling back to brute-force scan",
                exc,
            )

        return self._brute_force_vector_search(
            query_vector,
            limit=limit,
            max_distance=max_distance,
        )

    def _search_vector_with_embeddings(
        self,
        query_vector: list[float],
        limit: int = 10,
        max_distance: float = 0.5,
    ) -> list[dict]:
        """Like search_vector but also returns the embedding vector per row.

        Falls back to brute-force cosine similarity scan if the HNSW vector
        index is unavailable or returns no results.
        """
        fetch_limit = limit * 2
        vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        cypher = (
            f"CALL QUERY_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', "
            f"CAST({vec_str} AS DOUBLE[{len(query_vector)}]), {fetch_limit}) "
            f"RETURN node.nodeId AS nodeId, node.name AS name, "
            f"node.label AS label, node.filePath AS filePath, "
            f"node.startLine AS startLine, node.endLine AS endLine, "
            f"node.embedding AS embedding, distance "
            f"ORDER BY distance"
        )
        try:
            rows = self.execute_query(cypher)
            results = [r for r in rows if r.get("distance", 1.0) <= max_distance][
                :limit
            ]
            if results:
                return results
            logger.debug(
                "QUERY_VECTOR_INDEX (with embeddings) returned %d rows, 0 after "
                "distance filter; falling back to brute-force scan",
                len(rows),
            )
        except Exception as exc:
            logger.warning(
                "QUERY_VECTOR_INDEX failed (index may not exist): %s; "
                "falling back to brute-force scan",
                exc,
            )

        return self._brute_force_vector_search(
            query_vector,
            limit=limit,
            max_distance=max_distance,
            include_embedding=True,
        )

    # def vector_search(
    #     self,
    #     query_text: str,
    #     top_k: int = 10,
    #     use_mmr: bool = True,
    #     mmr_lambda: float = 0.7,
    # ) -> list[dict]:
    #     """Embed *query_text* on the fly and return nearest code symbols.

    #     This is a convenience wrapper around :meth:`search_vector` that
    #     handles text -> embedding conversion and distance -> similarity.
    #     When *use_mmr* is True, applies Maximal Marginal Relevance reranking
    #     to balance relevance and diversity.

    #     Returns rows with ``similarity`` (1 - distance) instead of raw
    #     ``distance``, matching what :mod:`semantic_linker` expects.
    #     """
    #     from csg.embeddings.embedding_pipeline import QUERY_PREFIX, get_or_create_model

    #     model = get_or_create_model()
    #     query_vector = model.embed_query(QUERY_PREFIX + query_text)

    #     if not use_mmr:
    #         rows = self.search_vector(query_vector, limit=top_k)
    #         for row in rows:
    #             row["similarity"] = 1.0 - row.pop("distance", 0.0)
    #         return rows

    #     from csg.search.mmr import MMRCandidate, mmr_rerank

    #     raw = self._search_vector_with_embeddings(query_vector, limit=top_k * 3)
    #     if not raw:
    #         return []

    #     candidates = []
    #     for row in raw:
    #         emb = row.get("embedding")
    #         if not emb:
    #             continue
    #         vec = list(emb) if not isinstance(emb, list) else emb
    #         candidates.append(
    #             MMRCandidate(
    #                 id=row.get("nodeId", ""),
    #                 vector=vec,
    #                 similarity=1.0 - row.get("distance", 0.0),
    #                 metadata={
    #                     "nodeId": row.get("nodeId", ""),
    #                     "name": row.get("name", ""),
    #                     "label": row.get("label", ""),
    #                     "filePath": row.get("filePath", ""),
    #                     "startLine": row.get("startLine"),
    #                     "endLine": row.get("endLine"),
    #                 },
    #             )
    #         )

    #     reranked = mmr_rerank(candidates, k=top_k, lambda_param=mmr_lambda)

    #     results = []
    #     for cand in reranked:
    #         result = dict(cand.metadata)
    #         result["similarity"] = cand.similarity
    #         results.append(result)
    #     return results
