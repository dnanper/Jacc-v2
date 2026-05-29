from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agents import AgentConfig, BaseCodingAgent, OnlineEvolveConfig, OnlineEvolveRuntime


class _EvolvingLLM:
    def __init__(self) -> None:
        self.tool_names: list[str] = []

    def bind_tools(self, tools):
        bound = _EvolvingLLM()
        bound.tool_names = [tool.name for tool in tools]
        return bound

    def invoke(self, messages):
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        if tool_messages and "generated_echo" in self.tool_names:
            if any(message.name == "generated_echo" for message in tool_messages):
                return AIMessage(content="done")
            return AIMessage(
                content="calling generated tool",
                tool_calls=[
                    {
                        "name": "generated_echo",
                        "args": {"text": "hello"},
                        "id": "call_generated_echo",
                        "type": "tool_call",
                    }
                ],
            )

        return AIMessage(
            content="need generated tool",
            tool_calls=[
                {
                    "name": "create_tool",
                    "args": {
                        "name": "generated_echo",
                        "description": "Echo generated text.",
                        "code": (
                            "DESCRIPTION = 'Echo generated text.'\n\n"
                            "def run(text: str) -> dict:\n"
                            "    return {'generated_echo': text}\n"
                        ),
                    },
                    "id": "call_create_tool",
                    "type": "tool_call",
                }
            ],
        )


class OnlineEvolveRuntimeTest(unittest.TestCase):
    def test_create_tool_registers_generated_tool_and_resumes_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = BaseCodingAgent(
                llm=_EvolvingLLM(),
                tools=[],
                config=AgentConfig(max_steps=4),
            )
            runtime = OnlineEvolveRuntime(
                agent=agent,
                config=OnlineEvolveConfig(workspace_root=Path(tmp), max_cycles=3),
            )
            self.assertIsNotNone(agent.tools[0].args_schema)

            result = runtime.solve({"task_id": "task-1", "issue": "make echo tool"})

            workspace = Path(tmp) / "task-1"
            self.assertEqual(result.final_answer, "done")
            self.assertTrue((workspace / "generated_tools" / "generated_echo.py").exists())
            self.assertTrue((workspace / "logs" / "cycle_000.json").exists())
            self.assertIn("create_tool", [tool.name for tool in agent.tools])
            self.assertIn("generated_echo", [tool.name for tool in agent.tools])
            self.assertIn("make echo tool", result.state["messages"][1].content)


if __name__ == "__main__":
    unittest.main()
