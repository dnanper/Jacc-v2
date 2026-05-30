"""LangGraph best-practice tool-calling workflow."""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .state import AgentState


class BaseAgentWorkflow:
    """LLM -> ToolNode -> LLM loop.

    The LLM is bound to the provided tools. It emits tool calls as part of an
    AIMessage; LangGraph's ToolNode executes those calls and appends ToolMessage
    outputs automatically.
    """

    def __init__(self, *, llm: Runnable, tools: Sequence[BaseTool]) -> None:
        self.tools = list(tools)
        self.llm = llm.bind_tools(self.tools)
        self.graph = self._compile_graph()

    def invoke(self, state: AgentState) -> AgentState:
        return self.graph.invoke(state)

    def call_model(self, state: AgentState) -> AgentState:
        response = self.llm.invoke(_prepare_messages(state))
        return {
            "messages": [response],
            "iterations": state.get("iterations", 0) + 1,
            "final_answer": response.content if not _has_tool_calls(response) else "",
            "status": "running",
        }

    def finalize(self, state: AgentState) -> AgentState:
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
            state["final_answer"] = getattr(last, "content", "") if last else ""
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


def _prepare_messages(state: AgentState) -> list[BaseMessage]:
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

    return [*durable, *tail]
