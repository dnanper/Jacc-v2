"""Run the generic LangGraph tool-calling base agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

ROOT = Path(__file__).resolve().parents[1]
SRC_MODULES = ROOT / "src" / "modules"
if str(SRC_MODULES) not in sys.path:
    sys.path.insert(0, str(SRC_MODULES))

from agents import AgentConfig, BaseCodingAgent


@tool
def echo_issue(issue: str) -> dict:
    """Echo issue text."""

    return {"issue": issue}


class _EchoToolCallingLLM:
    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        if any(isinstance(message, ToolMessage) for message in messages):
            return AIMessage(content="Base loop completed.")
        human = next(message for message in messages if isinstance(message, HumanMessage))
        return AIMessage(
            content="Calling echo_issue.",
            tool_calls=[
                {
                    "name": "echo_issue",
                    "args": {"issue": human.content},
                    "id": "call_echo_issue",
                    "type": "tool_call",
                }
            ],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BaseCodingAgent generic loop.")
    parser.add_argument("--issue", required=True, help="SWE-style issue text.")
    parser.add_argument("--max-steps", type=int, default=4)
    args = parser.parse_args()

    agent = BaseCodingAgent(
        llm=_EchoToolCallingLLM(),
        tools=[echo_issue],
        config=AgentConfig(max_steps=args.max_steps),
    )
    result = agent.solve({"task_id": "manual", "issue": args.issue})
    print(json.dumps(result.state, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
