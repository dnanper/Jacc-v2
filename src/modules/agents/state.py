"""Shared state objects for the mini-swe-agent style base loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .prompt import SYSTEM_PROMPT


class Task(TypedDict, total=False):
    """A SWE-bench style task."""

    task_id: str
    repo_path: str
    workspace_path: str
    issue: str
    failing_tests: list[str]
    traceback: str | None
    test_command: str | None


@dataclass(slots=True)
class AgentConfig:
    """Base loop runtime limits."""

    max_steps: int = 20
    system_prompt: str = SYSTEM_PROMPT
    recent_message_limit: int = 50


class AgentState(TypedDict, total=False):
    """LangGraph-compatible state."""

    task: Task
    config: AgentConfig
    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int
    errors: list[str]
    final_answer: str
    status: Literal["running", "complete", "failed"]


@dataclass(slots=True)
class SolveResult:
    """Base agent output."""

    status: str
    state: AgentState = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    final_answer: str = ""
