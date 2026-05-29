from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.explore.impact import ImpactMixin


class _FakeAdapter:
    def match_by_name(self, target: str, limit: int = 5) -> list[dict]:
        return [
            {
                "id": f"Function:app.py:{target}",
                "name": target,
                "type": "Function",
                "filePath": "app.py",
            }
        ]


class _ImpactBackend(ImpactMixin):
    def __init__(self) -> None:
        self._adapter = _FakeAdapter()
        self.rel_types_seen: list[str] = []

    def _query(self, _query: str, params: dict) -> list[dict]:
        if "relTypes" in params:
            self.rel_types_seen = sorted(params["relTypes"])
        return []


class ImpactPolicyTest(unittest.TestCase):
    def test_impact_traversal_uses_edit_risk_relations_by_default(self) -> None:
        backend = _ImpactBackend()

        backend.impact("save", direction="upstream")

        self.assertEqual(
            backend.rel_types_seen,
            sorted(
                [
                    "ACCESSES",
                    "CALLS",
                    "EXTENDS",
                    "IMPLEMENTS",
                    "OVERRIDES",
                ]
            ),
        )
        self.assertNotIn("CONTAINS", backend.rel_types_seen)
        self.assertNotIn("DEFINES", backend.rel_types_seen)
        self.assertNotIn("HAS_METHOD", backend.rel_types_seen)
        self.assertNotIn("IMPORTS", backend.rel_types_seen)


if __name__ == "__main__":
    unittest.main()
