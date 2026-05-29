"""Base LangGraph tool-calling coding agent."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from .prompt import render_instance_prompt
from .state import AgentConfig, AgentState, SolveResult, Task
from .workflow import BaseAgentWorkflow


class BaseCodingAgent:
    """Generic LLM + ToolNode loop.

    Base agent owns no domain behavior. Capabilities come from tools bound to
    the LLM and executed by LangGraph's ToolNode.
    """

    def __init__(
        self,
        *,
        llm: Runnable,
        tools: Sequence[BaseTool],
        config: AgentConfig | None = None,
    ) -> None:
        self.raw_llm = llm
        self.tools = list(tools)
        self.config = config or AgentConfig()
        self.workflow = self._build_workflow()

    def add_tool(self, tool: BaseTool) -> None:
        self.tools.append(tool)
        self.workflow = self._build_workflow()

    def solve(self, task: Task, state: AgentState | None = None) -> SolveResult:
        run_state = self._initial_state(task) if state is None else self._resume_state(task, state)
        try:
            final_state = self.workflow.invoke(run_state)
        except Exception as exc:
            errors = list(run_state.get("errors", []))
            errors.append(str(exc))
            return SolveResult(status="failed", state=run_state, errors=errors)

        return SolveResult(
            status=final_state.get("status", "complete"),
            state=final_state,
            errors=final_state.get("errors", []),
            final_answer=final_state.get("final_answer", ""),
        )

    def _build_workflow(self) -> BaseAgentWorkflow:
        return BaseAgentWorkflow(llm=self.raw_llm, tools=self.tools)

    def _initial_state(self, task: Task) -> AgentState:
        return {
            "task": task,
            "config": self.config,
            "messages": [
                SystemMessage(content=self.config.system_prompt),
                HumanMessage(content=render_instance_prompt(_task_to_user_message(task))),
            ],
            "iterations": 0,
            "errors": [],
            "status": "running",
        }

    def _resume_state(self, task: Task, state: AgentState) -> AgentState:
        resumed = dict(state)
        resumed["task"] = task
        resumed["config"] = self.config
        resumed.setdefault("messages", [])
        resumed["iterations"] = 0
        resumed.setdefault("errors", [])
        resumed["status"] = "running"
        resumed["final_answer"] = ""
        return resumed


def _task_to_user_message(task: Task) -> str:
    parts = [task.get("issue", "")]
    failing_tests = task.get("failing_tests") or []
    if failing_tests:
        parts.append("Failing tests:\n" + "\n".join(failing_tests))
    traceback = task.get("traceback")
    if traceback:
        parts.append("Traceback:\n" + traceback)
    return "\n\n".join(part for part in parts if part)
