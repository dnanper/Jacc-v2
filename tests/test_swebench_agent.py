from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.agents.tools import build_bash_tool


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


if __name__ == "__main__":
    unittest.main()
