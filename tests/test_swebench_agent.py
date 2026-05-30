from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.agents.tools import build_bash_tool, build_ckg_tools


class SwebenchToolTest(unittest.TestCase):
    def test_docker_tools_expose_only_bash_and_execute_in_task_container(self) -> None:
        class FakeEnvironment:
            config = MagicMock(cwd="/testbed")

            def __init__(self) -> None:
                self.actions = []

            def execute(self, action, cwd="", *, timeout=None):
                self.actions.append((action, cwd, timeout))
                return {"output": "ok", "returncode": 0, "exception_info": ""}

        env = FakeEnvironment()
        tools = build_bash_tool(env, max_output_chars=1000)
        bash = next(tool for tool in tools if tool.name == "bash")

        command_result = bash.invoke({"command": "pytest -q", "timeout": 7})

        self.assertEqual([tool.name for tool in tools], ["bash"])
        self.assertEqual(command_result["output"], "ok")
        self.assertEqual(env.actions[0], ({"command": "pytest -q"}, "/testbed", 7))

    def test_bash_tool_description_explains_usage_boundaries(self) -> None:
        env = MagicMock()
        tools = build_bash_tool(env, max_output_chars=1000)
        bash = tools[0]

        self.assertIn("/testbed", bash.description)
        self.assertIn("inspect", bash.description)
        self.assertIn("edit", bash.description)
        self.assertIn("verify", bash.description)
        self.assertIn("non-interactive", bash.description)
        self.assertIn("Do not prefix", bash.description)

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
        self.assertIn("before editing", descriptions["ckg_contract"])
        self.assertIn("cross-file", descriptions["ckg_crosscut"])
        self.assertIn("Use bash", descriptions["ckg_search"])

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
        self.assertIn("Use bash", " ".join(result["_ckg_usage"]["next_steps"]))


if __name__ == "__main__":
    unittest.main()
