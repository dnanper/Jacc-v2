"""BM25 search via LadybugDB full-text search indexes.

Port of GitNexus search/bm25-index.ts.

Queries multiple node tables (File, Function, Class, Method, Interface)
and merges results by filePath, summing scores for the same file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .tokenizer import split_identifier

logger = logging.getLogger(__name__)


_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "or",
        "a",
        "an",
        "in",
        "of",
        "to",
        "is",
        "for",
        "how",
        "does",
        "what",
        "which",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "not",
        "but",
        "if",
        "then",
        "than",
        "when",
        "where",
        "why",
    }
)


# Common compound words in code that should be split for recall.
# Maps compound form to its parts.
_COMPOUND_SPLITS: dict[str, list[str]] = {
    "websocket": ["web", "socket"],
    "websockets": ["web", "socket"],
    "middleware": ["middle", "ware"],
    # "middleware": ["middle", "ware"],
    "leaderboard": ["leader", "board"],
    "realtime": ["real", "time"],
    "database": ["data", "base"],
    "username": ["user", "name"],
    "password": ["pass", "word"],
    "filename": ["file", "name"],
    "filepath": ["file", "path"],
    "callback": ["call", "back"],
    "timestamp": ["time", "stamp"],
    "endpoint": ["end", "point"],
    "namespace": ["name", "space"],
    "lifecycle": ["life", "cycle"],
    "dashboard": ["dash", "board"],
    "codebase": ["code", "base"],
    "workflow": ["work", "flow"],
    "frontend": ["front", "end"],
    "backend": ["back", "end"],
    "startup": ["start", "up"],
    "shutdown": ["shut", "down"],
    "teardown": ["tear", "down"],
    "lookup": ["look", "up"],
    "rollback": ["roll", "back"],
    "hotfix": ["hot", "fix"],
    "runtime": ["run", "time"],
    "timeout": ["time", "out"],
    "localhost": ["local", "host"],
    "playground": ["play", "ground"],
    "whitelist": ["white", "list"],
    "blacklist": ["black", "list"],
    "blocklist": ["block", "list"],
    "allowlist": ["allow", "list"],
}


def _escape_fts_query(query: str) -> str:
    """Escape a query string for safe use as a literal in FTS CALL statements.

    KuzuDB CALL procedures do not support parameter binding ($query),
    so the query must be inlined as a string literal.  Single quotes
    are doubled and backslashes are escaped.
    """
    return query.replace("\\", "\\\\").replace("'", "''")


def _preprocess_query(query: str) -> str:
    """Expand query terms with identifier subwords for better recall.

    "authentication flow" → "authentication auth flow"
    "getLeaderboard" → "getLeaderboard get leaderboard"
    "websocket connection" → "websocket web socket connection"

    Four strategies:
    1. camelCase/snake_case splitting via ``split_identifier``
    2. For plain words > 5 chars, generate a truncated prefix (first 4 chars)
       so "authentication" adds "auth", matching indexed "auth" tokens
    3. Compound word splitting ("websocket" → "web socket")
    4. Remove common stop words to reduce noise

    Since FTS uses ``conjunctive := false`` (OR), extra terms only add recall.
    """
    words = query.split()
    expanded: list[str] = []
    seen: set[str] = set()

    for word in words:
        low = word.lower()
        if low in _STOP_WORDS:
            continue
        if low not in seen:
            seen.add(low)
            expanded.append(word)

        # Strategy 1: identifier splitting (camelCase, snake_case, etc.)
        parts = split_identifier(word).split()
        for part in parts[1:]:
            p = part.lower()
            if p not in seen and len(p) >= 3:
                seen.add(p)
                expanded.append(p)

        # Strategy 2: prefix truncation for long plain words that
        # didn't split via identifier splitting (no camelCase/snake_case).
        # "authentication" → "auth" (4-char prefix)
        has_splits = len(parts) > 2  # parts[0] is original, >2 means it split
        if not has_splits and low.isalpha() and len(low) > 10:
            prefix = low[:4]
            if prefix not in seen:
                seen.add(prefix)
                expanded.append(prefix)

        # Strategy 3: compound word splitting from dictionary
        compound_parts = _COMPOUND_SPLITS.get(low)
        if compound_parts:
            for cp in compound_parts:
                if cp not in seen and len(cp) >= 3:
                    seen.add(cp)
                    expanded.append(cp)

    return " ".join(expanded) if expanded else query


@dataclass
class BM25SearchResult:
    file_path: str
    score: float
    rank: int


_FTS_TABLES = [
    ("file_fts", "File"),
    ("function_fts", "Function"),
    ("class_fts", "Class"),
    ("method_fts", "Method"),
    ("interface_fts", "Interface"),
    ("section_fts", "Section"),
    ("struct_fts", "`Struct`"),
    ("enum_fts", "`Enum`"),
    ("trait_fts", "`Trait`"),
    ("const_fts", "`Const`"),
    ("record_fts", "`Record`"),
]

_TABLE_FOR_INDEX = {
    "file_fts": "File",
    "function_fts": "Function",
    "class_fts": "Class",
    "method_fts": "Method",
    "interface_fts": "Interface",
    "section_fts": "Section",
    "struct_fts": "`Struct`",
    "enum_fts": "`Enum`",
    "trait_fts": "`Trait`",
    "const_fts": "`Const`",
    "record_fts": "`Record`",
}

_LABEL_FOR_INDEX = {
    "file_fts": "File",
    "function_fts": "Function",
    "class_fts": "Class",
    "method_fts": "Method",
    "interface_fts": "Interface",
    "section_fts": "Section",
    "struct_fts": "Struct",
    "enum_fts": "Enum",
    "trait_fts": "Trait",
    "const_fts": "Const",
    "record_fts": "Record",
}


def search_fts(
    execute_query: callable,
    query: str,
    limit: int = 20,
) -> list[BM25SearchResult]:
    """Search using LadybugDB's full-text search indexes.

    Queries all FTS indexes and merges results by filePath.

    Args:
        execute_query: Function that takes (cypher, params) and returns list[dict].
        query: Search query string.
        limit: Maximum results to return.

    Returns:
        Ranked search results from FTS indexes.
    """
    query = _preprocess_query(query)
    safe_query = _escape_fts_query(query)
    merged: dict[str, float] = {}

    for index_name, _label in _FTS_TABLES:
        table_name = _TABLE_FOR_INDEX.get(index_name, "File")
        cypher = (
            f"CALL QUERY_FTS_INDEX('{table_name}', '{index_name}', '{safe_query}', conjunctive := false) "
            f"RETURN node.filePath AS filePath, score "
            f"ORDER BY score DESC LIMIT {limit}"
        )
        try:
            rows = execute_query(cypher)
        except Exception as exc:
            logger.debug("BM25 search query failed: %s", exc)
            rows = []

        for row in rows:
            fp = row.get("filePath", "")
            sc = row.get("score", 0)
            if fp:
                merged[fp] = merged.get(fp, 0) + sc

    sorted_results = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:limit]

    return [
        BM25SearchResult(file_path=fp, score=sc, rank=idx + 1)
        for idx, (fp, sc) in enumerate(sorted_results)
    ]


@dataclass
class BM25SymbolResult:
    """Symbol-level search result with node metadata."""

    node_id: str
    name: str
    label: str
    file_path: str
    score: float
    start_line: int | None = None
    end_line: int | None = None


def search_fts_symbols(
    execute_query: callable,
    query: str,
    limit: int = 20,
) -> list[BM25SymbolResult]:
    """Search using FTS indexes and return symbol-level results.

    Unlike :func:`search_fts` which merges by filePath, this returns
    individual symbol hits with their node ID and label.  Used by
    the layered retrieval engine (Layer 1 — Relevance) which needs
    to map search hits to communities via MEMBER_OF edges.
    """
    query = _preprocess_query(query)
    safe_query = _escape_fts_query(query)
    results: list[BM25SymbolResult] = []

    for index_name, _label in _FTS_TABLES:
        if len(results) >= limit * 3:
            break
        table_name = _TABLE_FOR_INDEX.get(index_name, "File")
        clean_label = _LABEL_FOR_INDEX.get(index_name, "File")

        cypher = (
            f"CALL QUERY_FTS_INDEX('{table_name}', '{index_name}', '{safe_query}', conjunctive := false) "
            f"RETURN node.id AS id, node.name AS name, node.filePath AS filePath, "
            f"node.startLine AS startLine, node.endLine AS endLine, score "
            f"ORDER BY score DESC LIMIT {limit}"
        )
        try:
            rows = execute_query(cypher)
        except Exception as exc:
            logger.debug("BM25 symbol search failed for %s: %s", index_name, exc)
            continue

        for row in rows:
            node_id = row.get("id", "")
            if not node_id:
                continue
            results.append(
                BM25SymbolResult(
                    node_id=node_id,
                    name=row.get("name", ""),
                    label=clean_label,
                    file_path=row.get("filePath", ""),
                    score=row.get("score", 0),
                    start_line=row.get("startLine"),
                    end_line=row.get("endLine"),
                )
            )

    seen: set[str] = set()
    deduped: list[BM25SymbolResult] = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        if r.node_id not in seen:
            seen.add(r.node_id)
            deduped.append(r)

    return deduped[:limit]
