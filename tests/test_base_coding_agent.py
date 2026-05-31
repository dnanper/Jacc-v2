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


@tool
def ckg_search(query: str) -> dict:
    """Search CKG."""

    return {
        "signal": "strong",
        "communities": [
            {
                "hits": [
                    {
                        "name": "target",
                        "container_path": "/testbed/pkg/target.py",
                    }
                ]
            }
        ],
    }


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

    def test_ckg_phase_policy_switches_to_targeted_after_strong_ckg_hit(self) -> None:
        class CkgPhaseLLM:
            def __init__(self) -> None:
                self.inputs = []

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.inputs.append(messages)
                if any(
                    isinstance(message, ToolMessage)
                    and message.name == "ckg_search"
                    for message in messages
                ):
                    return AIMessage(content="done")
                return AIMessage(
                    content="searching",
                    tool_calls=[
                        {
                            "name": "ckg_search",
                            "args": {"query": "target bug"},
                            "id": "call_ckg",
                            "type": "tool_call",
                        }
                    ],
                )

        llm = CkgPhaseLLM()
        agent = BaseCodingAgent(
            llm=llm,
            tools=[ckg_search],
            config=AgentConfig(max_steps=3, enable_ckg_phase_policy=True),
        )

        result = agent.solve({"task_id": "demo-4", "issue": "target bug"})

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.state["phase"], "targeted")
        targeted_input = llm.inputs[-1]
        self.assertTrue(
            any(
                message.type == "system"
                and "PHASE: targeted" in message.content
                and "Stop repository-wide exploration" in message.content
                for message in targeted_input
            )
        )

    def test_ckg_phase_policy_recovers_after_repeated_bash_errors(self) -> None:
        class CaptureLLM:
            def __init__(self) -> None:
                self.inputs = []

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.inputs.append(messages)
                return AIMessage(content="done")

        llm = CaptureLLM()
        agent = BaseCodingAgent(
            llm=llm,
            tools=[echo],
            config=AgentConfig(max_steps=3, enable_ckg_phase_policy=True),
        )
        state = agent._initial_state({"task_id": "demo-5", "issue": "target bug"})
        state["messages"].extend(
            [
                AIMessage(
                    content="search",
                    tool_calls=[
                        {
                            "name": "ckg_search",
                            "args": {"query": "target"},
                            "id": "call_ckg",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    name="ckg_search",
                    tool_call_id="call_ckg",
                    content='{"signal":"strong","container_path":"/testbed/pkg/target.py"}',
                ),
                AIMessage(
                    content="bad bash",
                    tool_calls=[
                        {
                            "name": "bash",
                            "args": {"command": "bad"},
                            "id": "call_bash_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    name="bash",
                    tool_call_id="call_bash_1",
                    content='{"returncode":127,"output":"command not found"}',
                ),
                AIMessage(
                    content="bad bash again",
                    tool_calls=[
                        {
                            "name": "bash",
                            "args": {"command": "bad2"},
                            "id": "call_bash_2",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    name="bash",
                    tool_call_id="call_bash_2",
                    content="Error invoking tool 'bash' with kwargs {}",
                ),
            ]
        )

        update = agent.workflow.call_model(state)

        self.assertEqual(update["phase"], "recover")
        self.assertTrue(
            any(
                message.type == "system"
                and "PHASE: recover" in message.content
                and "Return to CKG" in message.content
                for message in llm.inputs[-1]
            )
        )

    def test_ckg_phase_policy_switches_to_edit_after_source_read(self) -> None:
        class CaptureLLM:
            def __init__(self) -> None:
                self.inputs = []

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.inputs.append(messages)
                return AIMessage(content="done")

        llm = CaptureLLM()
        agent = BaseCodingAgent(
            llm=llm,
            tools=[echo],
            config=AgentConfig(max_steps=3, enable_ckg_phase_policy=True),
        )
        state = agent._initial_state({"task_id": "demo-6", "issue": "target bug"})
        state["messages"].extend(
            [
                AIMessage(
                    content="search",
                    tool_calls=[
                        {
                            "name": "ckg_search",
                            "args": {"query": "target"},
                            "id": "call_ckg",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    name="ckg_search",
                    tool_call_id="call_ckg",
                    content='{"signal":"strong","container_path":"/testbed/pkg/target.py"}',
                ),
                AIMessage(
                    content="read source",
                    tool_calls=[
                        {
                            "name": "bash",
                            "args": {
                                "command": "nl -ba pkg/target.py | sed -n '1,80p'"
                            },
                            "id": "call_bash_read",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    name="bash",
                    tool_call_id="call_bash_read",
                    content='{"returncode":0,"output":"1\\tdef target():\\n2\\t    return 1\\n"}',
                ),
            ]
        )

        update = agent.workflow.call_model(state)

        self.assertEqual(update["phase"], "edit")
        self.assertTrue(
            any(
                message.type == "system"
                and "PHASE: edit" in message.content
                and "smallest" in message.content
                for message in llm.inputs[-1]
            )
        )


if __name__ == "__main__":
    unittest.main()
