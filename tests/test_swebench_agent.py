from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.agents.tools import build_ckg_tools


class CkgToolTest(unittest.TestCase):
    def test_ckg_tools_are_read_only_and_map_paths_to_testbed(self) -> None:
        class FakeBackend:
            def __init__(self) -> None:
                self.calls = []

            def explore_auto(self, query="", scope="", layer=""):
                self.calls.append(("explore_auto", query, scope, layer))
                return {
                    "communities": [
                        {
                            "hits": [
                                {
                                    "name": "target",
                                    "filePath": "src/pkg/target.py",
                                }
                            ]
                        }
                    ]
                }

            def context_360(self, symbol_name):
                self.calls.append(("context_360", symbol_name))
                return {
                    "symbol": {
                        "name": symbol_name,
                        "filePath": "src/pkg/target.py",
                    },
                    "callers": [{"name": "caller", "file": "src/pkg/caller.py"}],
                }

            def impact(self, target, direction="upstream", min_confidence=0.4):
                self.calls.append(("impact", target, direction, min_confidence))
                return {
                    "target": {"name": target, "filePath": "src/pkg/target.py"},
                    "affected": [
                        {"name": "caller", "filePath": "src/pkg/caller.py"}
                    ],
                    "risk": "LOW",
                    "stats": {"total": 1},
                }

            def crosscut(self, query="", scope=""):
                self.calls.append(("crosscut", query, scope))
                return {
                    "cycles": [],
                    "shared_symbols": [
                        {"name": "shared", "filePath": "src/pkg/shared.py"}
                    ],
                }

            def contract(self, symbols):
                self.calls.append(("contract", symbols))
                return {
                    "symbols": [
                        {
                            "name": symbols[0],
                            "filePath": "src/pkg/target.py",
                            "signature": "target(value)",
                        }
                    ]
                }

        backend = FakeBackend()
        tools = build_ckg_tools(
            backend,
            snapshot_root=Path(".agent_runs/swebench/demo/ckg_snapshot/testbed"),
            container_root="/testbed",
        )
        names = [tool.name for tool in tools]

        self.assertEqual(
            names,
            [
                "ckg_search",
                "ckg_file_context",
                "ckg_symbol_context",
                "ckg_contract",
                "ckg_crosscut",
                "ckg_impact",
                "ckg_overview",
            ],
        )
        descriptions = {tool.name: tool.description for tool in tools}
        self.assertTrue(all("read-only" in description for description in descriptions.values()))
        self.assertIn("localization", descriptions["ckg_contract"])
        self.assertIn("cross-file", descriptions["ckg_crosscut"])
        self.assertIn("read-only", descriptions["ckg_search"])

        search = next(tool for tool in tools if tool.name == "ckg_search")
        result = search.invoke({"query": "target behavior", "limit": 5})

        hit = result["communities"][0]["hits"][0]
        self.assertEqual(hit["filePath"], "src/pkg/target.py")
        self.assertEqual(hit["container_path"], "/testbed/src/pkg/target.py")

        context = next(tool for tool in tools if tool.name == "ckg_symbol_context")
        context_result = context.invoke({"symbol_name": "target"})

        self.assertEqual(
            context_result["symbol"]["container_path"],
            "/testbed/src/pkg/target.py",
        )
        self.assertEqual(
            context_result["callers"][0]["container_path"],
            "/testbed/src/pkg/caller.py",
        )

        contract = next(tool for tool in tools if tool.name == "ckg_contract")
        contract_result = contract.invoke({"symbols": ["target"]})
        self.assertEqual(
            contract_result["symbols"][0]["container_path"],
            "/testbed/src/pkg/target.py",
        )

        crosscut = next(tool for tool in tools if tool.name == "ckg_crosscut")
        crosscut_result = crosscut.invoke({"query": "shared parser"})
        self.assertEqual(
            crosscut_result["shared_symbols"][0]["container_path"],
            "/testbed/src/pkg/shared.py",
        )

    def test_ckg_outputs_are_compact_and_include_usage_guidance(self) -> None:
        class FakeBackend:
            def explore_auto(self, query="", scope="", layer=""):
                return {
                    "symbols": [
                        {
                            "name": f"symbol_{index}",
                            "type": "Function",
                            "filePath": f"src/pkg/mod_{index}.py",
                            "content": "x = 1\n" * 500,
                        }
                        for index in range(25)
                    ],
                    "processes": [
                        {
                            "name": "flow",
                            "steps": [
                                {
                                    "name": f"step_{index}",
                                    "filePath": f"src/pkg/step_{index}.py",
                                }
                                for index in range(20)
                            ],
                        }
                    ],
                }

        tools = build_ckg_tools(
            FakeBackend(),
            snapshot_root=Path(".agent_runs/swebench/demo/ckg_snapshot/testbed"),
            container_root="/testbed",
        )
        context = next(tool for tool in tools if tool.name == "ckg_file_context")
        result = context.invoke({"file_path": "src/pkg/mod_0.py"})

        self.assertLessEqual(len(result["symbols"]), 10)
        self.assertLess(len(result["symbols"][0]["content"]), 1300)
        self.assertEqual(
            result["symbols"][0]["container_path"],
            "/testbed/src/pkg/mod_0.py",
        )
        self.assertIn("_ckg_usage", result)
        self.assertIn("Return the required JSON", " ".join(result["_ckg_usage"]["next_steps"]))


if __name__ == "__main__":
    unittest.main()
