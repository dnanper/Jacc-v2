from __future__ import annotations

import sys
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agents import AgentConfig, BaseCodingAgent


@tool
def echo(text: str) -> dict:
    """Echo text."""

    return {"echo": text}


class _FakeToolCallingLLM:
    def __init__(self) -> None:
        self.inputs = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        if any(isinstance(message, ToolMessage) for message in messages):
            return AIMessage(content="done")
        human = next(message for message in messages if isinstance(message, HumanMessage))
        return AIMessage(
            content="calling echo",
            tool_calls=[
                {
                    "name": "echo",
                    "args": {"text": human.content},
                    "id": "call_echo",
                    "type": "tool_call",
                }
            ],
        )


class BaseCodingAgentTest(unittest.TestCase):
    def test_base_agent_uses_bound_llm_and_toolnode(self) -> None:
        llm = _FakeToolCallingLLM()
        agent = BaseCodingAgent(
            llm=llm,
            tools=[echo],
            config=AgentConfig(max_steps=4),
        )

        result = agent.solve(
            {
                "task_id": "demo-1",
                "issue": "chat stream duplicates provisional message",
            }
        )

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.state["iterations"], 2)
        self.assertEqual([msg.type for msg in result.state["messages"]], ["system", "human", "ai", "tool", "ai"])
        self.assertEqual([msg.type for msg in llm.inputs[0]], ["system", "human"])
        self.assertEqual([msg.type for msg in llm.inputs[1]], ["system", "human", "ai", "tool"])
        self.assertEqual(result.state["messages"][2].tool_calls[0]["name"], "echo")
        self.assertIn("chat stream duplicates", result.state["messages"][3].content)
        self.assertEqual(result.final_answer, "done")

    def test_rebuild_after_adding_tool_continues_existing_state(self) -> None:
        class DynamicLLM:
            def __init__(self) -> None:
                self.tool_names: list[str] = []

            def bind_tools(self, tools):
                bound = DynamicLLM()
                bound.tool_names = [tool.name for tool in tools]
                return bound

            def invoke(self, messages):
                if any(isinstance(message, ToolMessage) for message in messages):
                    return AIMessage(content="continued")
                if "echo" in self.tool_names:
                    human = next(
                        message for message in messages if isinstance(message, HumanMessage)
                    )
                    return AIMessage(
                        content="calling echo",
                        tool_calls=[
                            {
                                "name": "echo",
                                "args": {"text": human.content},
                                "id": "call_echo",
                                "type": "tool_call",
                            }
                        ],
                    )
                return AIMessage(content="need tool")

        agent = BaseCodingAgent(
            llm=DynamicLLM(),
            tools=[],
            config=AgentConfig(max_steps=4),
        )
        first = agent.solve({"task_id": "demo-2", "issue": "needs echo"})

        agent.add_tool(echo)
        second = agent.solve({"task_id": "demo-2", "issue": "needs echo"}, state=first.state)

        self.assertEqual(first.final_answer, "need tool")
        self.assertEqual(second.final_answer, "continued")
        self.assertEqual([msg.type for msg in second.state["messages"]], ["system", "human", "ai", "ai", "tool", "ai"])
        self.assertIn("needs echo", second.state["messages"][1].content)

    def test_tool_call_at_step_limit_is_executed_and_marked_failed(self) -> None:
        class ToolAtLimitLLM:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return AIMessage(
                    content="calling echo",
                    tool_calls=[
                        {
                            "name": "echo",
                            "args": {"text": "last command"},
                            "id": "call_echo",
                            "type": "tool_call",
                        }
                    ],
                )

        agent = BaseCodingAgent(
            llm=ToolAtLimitLLM(),
            tools=[echo],
            config=AgentConfig(max_steps=1),
        )

        result = agent.solve({"task_id": "demo-3", "issue": "run one command"})

        self.assertEqual(result.status, "failed")
        self.assertIn("max_steps_reached", result.errors)
        self.assertEqual([msg.type for msg in result.state["messages"]], ["system", "human", "ai", "tool"])
        self.assertIn("last command", result.state["messages"][-1].content)


if __name__ == "__main__":
    unittest.main()
