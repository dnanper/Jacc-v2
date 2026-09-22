"""Small terminal logging and optional Langfuse integration."""

from __future__ import annotations

import logging
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.runnables import Runnable

logger = logging.getLogger("jacc")


@dataclass
class RunObserver:
    task_id: str
    started: float
    flush: Callable[[], None]

    def step(self, message: str, *, style: str = "cyan") -> None:
        del style
        elapsed = time.monotonic() - self.started
        logger.info("task=%s elapsed=%.1fs %s", self.task_id, elapsed, message)

    def close(self) -> None:
        with suppress(Exception):
            self.flush()


def start_observer(task_id: str) -> RunObserver:
    return RunObserver(task_id=task_id, started=time.monotonic(), flush=lambda: None)


def instrument_llm(
    llm: Runnable,
    *,
    task_id: str,
    benchmark: str,
    model: str,
) -> tuple[Runnable, Callable[[], None]]:
    """Attach Langfuse callbacks when credentials are configured."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return llm, lambda: None
    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler()
        configured = llm.with_config(
            {
                "callbacks": [handler],
                "metadata": {
                    "langfuse_session_id": task_id,
                    "langfuse_tags": ["jacc", "localization", benchmark],
                    "jacc_model": model,
                },
            }
        )
        return configured, get_client().flush
    except Exception as exc:
        logger.warning("langfuse disabled: %s", exc)
        return llm, lambda: None
