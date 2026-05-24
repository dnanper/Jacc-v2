"""Backend base — core infrastructure shared by all mixins."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager

from ..graph.storage.code_adapter import LadybugAdapter

logger = logging.getLogger(__name__)


class BackendBase:
    """Core adapter management, scoped-repo switching, and Cypher access."""

    def __init__(self, adapter: LadybugAdapter) -> None:
        self._default_adapter = adapter
        self._adapter_cache: dict[str, LadybugAdapter] = {}
        self._repo_lock = threading.Lock()
        self._local = threading.local()

        # Subscribe to change events for automatic cache invalidation
        try:
            from ..graph.storage.kuzu_pool import KuzuPool

            pool = KuzuPool.get()
            pool.event_bus.subscribe("repo_changed", self._on_repo_changed)
            pool.event_bus.subscribe("repo_deleted", self._on_repo_deleted)
        except Exception:
            logger.debug("Could not subscribe to KuzuPool events", exc_info=True)

    @property
    def _adapter(self) -> LadybugAdapter:
        """Return the thread-local adapter, falling back to the default."""
        return getattr(self._local, "adapter", None) or self._default_adapter

    @contextmanager
    def _scoped_repo(self, repo: str | None):
        """Temporarily switch to a different repo's adapter, if specified.

        Uses thread-local storage so concurrent calls on different repos
        don't interfere with each other.
        """
        if not repo:
            yield
            return

        from repo_explorer.repository.repo_manager import get_repo_by_name

        entry = get_repo_by_name(repo)
        if not entry:
            raise ValueError(
                f"Repository '{repo}' not found. "
                "Use repo_explorer.repository.repo_manager.list_repos to see available repos."
            )

        db_path = os.path.join(entry.storage_path, "lbug")

        with self._repo_lock:
            if repo not in self._adapter_cache:
                new_adapter = LadybugAdapter(
                    db_path=db_path, repo_source_path=entry.path
                )
                new_adapter.connect(read_only=True)
                self._adapter_cache[repo] = new_adapter
                logger.info("Opened adapter for repo '%s' at %s", repo, db_path)

            scoped_adapter = self._adapter_cache[repo]

        prev = getattr(self._local, "adapter", None)
        self._local.adapter = scoped_adapter
        try:
            yield
        finally:
            self._local.adapter = prev

    def _on_repo_changed(self, data: dict) -> None:
        """Invalidate cached adapters when a repo's data changes.

        Called by EventBus after pipeline writes. The adapter reconnects
        lazily on the next query, picking up the new data.
        """
        changed_path = data.get("db_path", "")
        with self._repo_lock:
            for name, adapter in list(self._adapter_cache.items()):
                if (
                    adapter._db_path
                    and os.path.abspath(adapter._db_path) == changed_path
                ):
                    adapter.close()
                    adapter._name_cache.clear()
                    del self._adapter_cache[name]
                    logger.info("Cache invalidated for repo '%s' (data changed)", name)

    def _on_repo_deleted(self, data: dict) -> None:
        """Remove cached adapter for a deleted repo."""
        deleted_path = data.get("db_path", "")
        with self._repo_lock:
            for name, adapter in list(self._adapter_cache.items()):
                if (
                    adapter._db_path
                    and os.path.abspath(adapter._db_path) == deleted_path
                ):
                    adapter.close()
                    del self._adapter_cache[name]
                    logger.info("Cache removed for deleted repo '%s'", name)

    def _query(self, cypher: str, params: dict | None = None) -> list[dict]:
        return self._adapter.execute_query(cypher, params)

    @staticmethod
    def _confidence_envelope(score: float, gap: float = 1.0) -> dict:
        """Build a confidence envelope from a score and optional gap."""
        if score > 0.8 and gap > 0.3:
            signal, recommendation = "strong", "drill_down"
        elif score > 0.4:
            signal, recommendation = "moderate", "drill_down"
        else:
            signal, recommendation = "weak", "explore_multiple"
        return {
            "confidence": round(score, 3),
            "confidence_gap": round(gap, 3),
            "signal": signal,
            "recommendation": recommendation,
        }
