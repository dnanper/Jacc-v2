"""Dense similarity between an issue and code nodes, computed only for the nodes a step already holds.

The graph stores no embeddings (its CodeEmbedding table is unused) and none are written to it. A step that ranks a set
it already has (A2's retrieved pool, the explore pool around seeds, verifier candidates) asks for the vectors of just
those nodes. Vectors are cached on disk by a hash of (model, text), so the same function text is embedded once across
instances and commits of a repository. Every API call goes through llm_guard.guard (paid call path).
See docs/compare-4omini-luna/EMBEDDING_DESIGN.md.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import numpy as np

MODEL = "text-embedding-3-small"
DIM = 1536                # MODEL's vector size; only used to shape zero rows when nothing is cached (offline)
CACHE = Path(".agent_runs/embed_cache.sqlite")
BATCH = 256
MAX_CHARS = 6000          # one input; text-embedding-3 accepts 8191 tokens
BODY_LINES, BODY_CHARS, DOC_CHARS = 30, 1500, 300


def code_text(loc: str, signature: str = "", doc: str = "", code: str = "") -> str:
    """'path::Qualified.name' + signature + docstring + the first lines of the body."""
    body = "\n".join(code.splitlines()[:BODY_LINES])[:BODY_CHARS]
    parts = [loc, " ".join(signature.split())[:300], doc.strip()[:DOC_CHARS], body]
    return "\n".join(p for p in parts if p)[:MAX_CHARS]


def _key(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


class Embedder:
    """`client` is an openai.OpenAI (or a stand-in with .embeddings.create); built on first real need."""

    def __init__(self, cache: Path | str = CACHE, model: str = MODEL, client: Any = None):
        self.model, self.client = model, client
        self.path = Path(cache)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=120)  # pipeline workers share one cache file
        self.db.execute("CREATE TABLE IF NOT EXISTS vec (key TEXT PRIMARY KEY, dim INTEGER, data BLOB)")
        self.tokens = 0       # prompt tokens billed by this instance
        self.calls = 0

    def cached(self, texts: Iterable[str]) -> dict[str, np.ndarray]:
        keys = {_key(self.model, t[:MAX_CHARS]): t for t in texts}
        out = {}
        items = list(keys)
        for i in range(0, len(items), 900):
            chunk = items[i:i + 900]
            rows = self.db.execute(f"SELECT key, dim, data FROM vec WHERE key IN ({','.join('?' * len(chunk))})", chunk).fetchall()
            for k, dim, data in rows:
                out[keys[k]] = np.frombuffer(data, dtype=np.float16).astype(np.float32).reshape(dim)
        return out

    def embed(self, texts: list[str], offline: bool = False) -> np.ndarray:
        """Unit vectors, one row per text, in order. `offline`: never call the API (missing rows are zero)."""
        texts = [t[:MAX_CHARS] or " " for t in texts]
        have = self.cached(texts)
        missing = list(dict.fromkeys(t for t in texts if t not in have))
        if missing and not offline:
            if self.client is None:
                from src.utils.llm_guard import guard
                guard("embed")
                from openai import OpenAI
                self.client = OpenAI(max_retries=8)  # rate limits back off and retry; each finished batch is already cached
            for i in range(0, len(missing), BATCH):
                batch = missing[i:i + BATCH]
                res = self.client.embeddings.create(model=self.model, input=batch)
                self.calls += 1
                self.tokens += getattr(getattr(res, "usage", None), "prompt_tokens", 0) or 0
                data = sorted(res.data, key=lambda d: getattr(d, "index", 0))  # one item per input, tagged with its position
                if len(data) != len(batch):
                    raise RuntimeError(f"embedding API returned {len(data)} vectors for {len(batch)} inputs")
                rows = []
                for t, d in zip(batch, data):
                    v = np.asarray(d.embedding, dtype=np.float32)
                    v /= np.linalg.norm(v) or 1.0
                    v = v.astype(np.float16).astype(np.float32)  # as stored, so a fresh and a cached vector score the same
                    have[t] = v
                    rows.append((_key(self.model, t), len(v), v.astype(np.float16).tobytes()))
                self.db.executemany("INSERT OR REPLACE INTO vec VALUES (?, ?, ?)", rows)
                self.db.commit()
        dim = next((len(v) for v in have.values()), DIM)
        return np.vstack([have.get(t, np.zeros(dim, dtype=np.float32)) for t in texts]) if texts else np.zeros((0, dim))


def cosine(query: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Rows and query are unit vectors (Embedder.embed); a zero row (not embedded) scores 0."""
    return rows @ query if len(rows) else np.zeros(0)


def issue_queries(issue_text: str, issue: Any) -> list[str]:
    """Q1 the cleaned issue text, Q2 the IssueModel fields; a node scores the max cosine over both."""
    q2 = [issue.title, issue.summary, f"Observed: {issue.observed}" if issue.observed else "",
          f"Expected: {issue.expected}" if issue.expected else "",
          "Code: " + ", ".join(issue.explicit_code_refs) if issue.explicit_code_refs else "", *issue.error_messages]
    return [issue_text[:MAX_CHARS], "\n".join(x for x in q2 if x)[:MAX_CHARS]]


def node_texts(query: Any, ids: list[str]) -> dict[str, str]:
    """code_text of each graph node, from its signature and source (one Cypher query per 500 ids)."""
    from src.modules.repo_profile import _loc
    cy = "MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, n.signature AS sig, n.content AS code"
    info = {r["id"]: r for i in range(0, len(ids), 500) for r in query(cy, {"ids": ids[i:i + 500]})}
    return {n: code_text(n.split(":", 1)[1] if n.startswith("File:") else _loc(n), (info.get(n) or {}).get("sig") or "", "",
                         (info.get(n) or {}).get("code") or "") for n in ids}


def add_dense(rows: list[dict], queries: list[str], texts: dict[str, str], embedder: Embedder) -> None:
    """Adds dense_sim (max cosine to the queries) and dense_rank_inv (1 / (1 + rank by dense_sim among the rows))."""
    if not rows:
        return
    s = (embedder.embed([texts[r["node"]] for r in rows]) @ embedder.embed(queries).T).max(axis=1)
    for k, i in enumerate(np.argsort(-s, kind="stable")):
        rows[i]["features"].update(dense_sim=float(s[i]), dense_rank_inv=1 / (1 + k))
