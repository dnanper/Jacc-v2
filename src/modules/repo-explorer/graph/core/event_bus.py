"""Simple in-process event bus for database change notifications.

Allows MCP backend, web agent, and pipeline to stay in sync:
when one writes, others invalidate caches and get fresh data.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe in-process pub/sub for database change events.

    Events:
        repo_changed   — {db_path, phase, timestamp}
        repo_deleted   — {repo_name, db_path, timestamp}
        repo_indexed   — {repo_name, db_path, stats, timestamp}
        source_changed — {repo_path, reason, ...}  (triggers event-driven re-ingestion in MCP mode)
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, dict[str, Callable]] = defaultdict(dict)
        self._lock = threading.Lock()

    def subscribe(self, event: str, callback: Callable[[dict], None]) -> str:
        """Subscribe to an event. Returns subscription ID for unsubscribe."""
        sub_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._subscribers[event][sub_id] = callback
        logger.debug("EventBus: subscribed %s to '%s'", sub_id, event)
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscription by ID."""
        with self._lock:
            for event, subs in self._subscribers.items():
                if sub_id in subs:
                    del subs[sub_id]
                    logger.debug("EventBus: unsubscribed %s from '%s'", sub_id, event)
                    return

    def publish(self, event: str, data: dict) -> None:
        """Notify all subscribers of an event. Errors are logged, not raised."""
        with self._lock:
            callbacks = list(self._subscribers.get(event, {}).values())

        if not callbacks:
            return

        logger.info(
            "EventBus: publishing '%s' to %d subscriber(s)", event, len(callbacks)
        )
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                logger.warning(
                    "EventBus: subscriber error on '%s'", event, exc_info=True
                )
