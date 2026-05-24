"""MCP backend — tool implementations.

Implements the 9 MCP tools + 6-layer retrieval via LadybugDB (KuzuDB) Cypher.

The Backend class is composed from focused mixins:
- ExploreMixin  — 6-layer retrieval (topology through implementation)
- ContextMixin  — symbol 360-degree view
- ImpactMixin   — blast-radius analysis
- SearchMixin   — hybrid and semantic search
- MutationsMixin — rename, cypher, repo management, ingestion
- BackendBase   — core adapter management and Cypher access
"""

from ._base import BackendBase
from .context import ContextMixin
from .explore import ExploreMixin
from .impact import ImpactMixin
from .mutations import MutationsMixin
from .search import SearchMixin


class Backend(
    ExploreMixin,
    ContextMixin,
    ImpactMixin,
    SearchMixin,
    MutationsMixin,
    BackendBase,
):
    """MCP backend with tool implementations."""

    pass


__all__ = ["Backend"]
