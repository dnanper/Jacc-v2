from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.observability import instrument_llm, start_observer


class _Runnable:
    def __init__(self) -> None:
        self.config = None

    def with_config(self, config):
        self.config = config
        return self


class ObservabilityTest(unittest.TestCase):
    def test_tracing_is_disabled_without_keys(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            runnable = _Runnable()
            configured, flush = instrument_llm(
                runnable, task_id="task", benchmark="python", model="gpt-5-mini"
            )
        self.assertIs(configured, runnable)
        self.assertIsNone(runnable.config)
        flush()

    def test_observer_flush_is_safe(self) -> None:
        observer = start_observer("task")
        observer.step("test")
        observer.close()
