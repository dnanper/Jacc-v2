"""Coding-agent scaffolding."""

from .base_agent import BaseCodingAgent
from .online_evolve import OnlineEvolveConfig, OnlineEvolveRuntime
from .state import AgentConfig, AgentState, SolveResult, Task
from .tools import build_bash_tool, build_create_tool

__all__ = [
    "AgentConfig",
    "AgentState",
    "BaseCodingAgent",
    "OnlineEvolveConfig",
    "OnlineEvolveRuntime",
    "SolveResult",
    "Task",
    "build_bash_tool",
    "build_create_tool",
]
