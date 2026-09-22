"""LangGraph best-practice tool-calling workflow."""

from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .state import AgentState
from src.utils.log import logger


class BaseAgentWorkflow:
    """LLM -> ToolNode -> LLM loop.

    The LLM is bound to the provided tools. It emits tool calls as part of an
    AIMessage; LangGraph's ToolNode executes those calls and appends ToolMessage
    outputs automatically.
    """

    def __init__(self, *, llm: Runnable, tools: Sequence[BaseTool]) -> None:
        self.tools = list(tools)
        # bind_tools rebuilds from the underlying model, dropping any callbacks
        # and metadata attached with with_config (e.g. Langfuse tracing).
        config = getattr(llm, "config", None)
        bound = llm.bind_tools(self.tools)
        self.llm = bound.with_config(config) if config else bound
        self.graph = self._compile_graph()

    def invoke(self, state: AgentState) -> AgentState:
        return self.graph.invoke(state)

    def call_model(self, state: AgentState) -> AgentState:
        phase = _detect_phase(state)
        iteration = state.get("iterations", 0) + 1
        logger.info("agent node=call_model iteration=%d phase=%s", iteration, phase or "none")
        response = self.llm.invoke(_prepare_messages(state, phase=phase))
        logger.info("agent node=call_model complete iteration=%d tool_calls=%d", iteration, len(getattr(response, "tool_calls", []) or []))
        return {
            "messages": [response],
            "iterations": state.get("iterations", 0) + 1,
            "final_answer": _message_text(response) if not _has_tool_calls(response) else "",
            "status": "running",
            "phase": phase,
        }

    def finalize(self, state: AgentState) -> AgentState:
        logger.info("agent node=finalize iterations=%d", state.get("iterations", 0))
        state = dict(state)
        state["status"] = "complete"
        last = state["messages"][-1] if state.get("messages") else None
        max_steps_reached = state.get("iterations", 0) >= state["config"].max_steps
        incomplete_after_limit = max_steps_reached and (
            _has_tool_calls(last)
            or isinstance(last, ToolMessage)
            or not state.get("final_answer")
        )
        if incomplete_after_limit:
            state["status"] = "failed"
            errors = list(state.get("errors", []))
            if "max_steps_reached" not in errors:
                errors.append("max_steps_reached")
            state["errors"] = errors
        else:
            state["status"] = "complete"
        if not state.get("final_answer") and not isinstance(last, ToolMessage):
            state["final_answer"] = _message_text(last) if last else ""
        return state

    def should_continue(self, state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if _has_tool_calls(last) else "finalize"

    def after_tools(self, state: AgentState) -> str:
        if state.get("iterations", 0) >= state["config"].max_steps:
            return "finalize"
        return "call_model"

    def _compile_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("call_model", self.call_model)
        graph.add_node("tools", ToolNode(self.tools))
        graph.add_node("finalize", self.finalize)

        graph.set_entry_point("call_model")
        graph.add_conditional_edges(
            "call_model",
            self.should_continue,
            {"tools": "tools", "finalize": "finalize"},
        )
        graph.add_conditional_edges(
            "tools",
            self.after_tools,
            {"call_model": "call_model", "finalize": "finalize"},
        )
        graph.add_edge("finalize", END)
        return graph.compile()


def _has_tool_calls(message: Any) -> bool:
    return isinstance(message, AIMessage) and bool(message.tool_calls)


def _message_text(message: Any) -> str:
    """Text of a message; Responses-API content is a block list, not a string."""

    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else ""


def _prepare_messages(
    state: AgentState,
    *,
    phase: str | None = None,
) -> list[BaseMessage]:
    """Prepare a coherent LLM input from state history.

    Keep durable context (system prompt + original task) and a recent valid
    interaction tail. The tail limit is intentionally generous by default; it
    exists to avoid unbounded growth, not to hide useful context.
    """

    messages = list(state.get("messages", []))
    if not messages:
        return []

    durable: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            durable.append(message)
        elif isinstance(message, HumanMessage):
            durable.append(message)
            break

    durable_ids = {id(message) for message in durable}
    tail_source = [message for message in messages if id(message) not in durable_ids]
    recent_limit = max(4, state["config"].recent_message_limit)
    tail = tail_source[-recent_limit:]

    # Never start an LLM input tail with a ToolMessage lacking its AI tool call.
    while tail and isinstance(tail[0], ToolMessage):
        tail = tail[1:]

    phase_hint = _phase_hint(phase) if phase else None
    if phase_hint:
        return [*durable, SystemMessage(content=phase_hint), *tail]
    return [*durable, *tail]


def _detect_phase(state: AgentState) -> str | None:
    config = state["config"]
    if not getattr(config, "enable_ckg_phase_policy", False):
        return None

    messages = list(state.get("messages", []))
    if not _has_ckg_signal(messages):
        return "explore"
    if _recent_bash_error_count(messages) >= 2:
        return "recover"
    return "targeted"


def _has_ckg_signal(messages: list[BaseMessage]) -> bool:
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        if not (message.name or "").startswith("ckg_"):
            continue
        content = str(message.content)
        if "container_path" in content or '"signal": "strong"' in content:
            return True
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if payload.get("signal") == "strong" or _contains_key(payload, "container_path"):
            return True
    return False


def _recent_bash_error_count(messages: list[BaseMessage], limit: int = 8) -> int:
    count = 0
    for message in messages[-limit:]:
        if not isinstance(message, ToolMessage) or message.name != "bash":
            continue
        content = str(message.content)
        if content.startswith("Error invoking tool"):
            count += 1
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        returncode = payload.get("returncode")
        if returncode not in (None, 0):
            count += 1
    return count


def _contains_key(value: Any, target_key: str) -> bool:
    if isinstance(value, dict):
        return target_key in value or any(
            _contains_key(item, target_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target_key) for item in value)
    return False


def _phase_hint(phase: str | None) -> str:
    if phase == "explore":
        return (
            "PHASE: explore. Start with ckg_search using a focused issue-shaped "
            "query. Do not perform broad repository exploration."
        )
    if phase == "targeted":
        return (
            "PHASE: targeted. CKG has identified likely files or symbols. Stop "
            "repository-wide exploration. Use ckg_file_context or "
            "ckg_symbol_context for local evidence, ckg_contract for callers, "
            "callees, inheritance, and overrides, then ckg_crosscut or ckg_impact "
            "only when needed. Finish with the required JSON once evidence is sufficient."
        )
    if phase == "recover":
        return (
            "PHASE: recover. Return to CKG with one focused ckg_search or "
            "ckg_crosscut call. Do not repeat a weak query; return JSON if no "
            "additional evidence is available."
        )
    return ""
