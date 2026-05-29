"""Online tool synthesis runtime for the base coding agent."""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool

from .base_agent import BaseCodingAgent
from .state import AgentState, SolveResult, Task
from .tools import GENERATED_TOOL_ARTIFACT_PREFIX, build_create_tool


@dataclass(slots=True)
class OnlineEvolveConfig:
    """Runtime limits and paths for task-local generated tools."""

    workspace_root: Path = Path(".agent_runs")
    max_cycles: int = 5


class OnlineEvolveRuntime:
    """Run an agent, detect generated tool requests, register tools, resume."""

    def __init__(
        self,
        *,
        agent: BaseCodingAgent,
        config: OnlineEvolveConfig | None = None,
    ) -> None:
        self.agent = agent
        self.config = config or OnlineEvolveConfig()
        self._ensure_create_tool_registered()

    def solve(self, task: Task) -> SolveResult:
        task_workspace = self._task_workspace(task)
        task_workspace.mkdir(parents=True, exist_ok=True)
        (task_workspace / "generated_tools").mkdir(exist_ok=True)
        (task_workspace / "logs").mkdir(exist_ok=True)

        task = dict(task)
        task["workspace_path"] = str(task_workspace)

        state: AgentState | None = None
        result: SolveResult | None = None
        processed: set[str] = set()

        for cycle in range(self.config.max_cycles):
            result = self.agent.solve(task, state=state)
            state = result.state
            self._write_state_log(task_workspace, cycle, state)

            requests = [
                request
                for request in extract_generated_tool_requests(state)
                if request.get("name") not in processed
            ]
            if not requests:
                return result

            for request in requests:
                tool_file = write_generated_tool(task_workspace, request)
                generated_tool = load_generated_tool(tool_file, request["name"])
                self.agent.add_tool(generated_tool)
                processed.add(request["name"])
                state.setdefault("messages", []).append(
                    SystemMessage(
                        content=(
                            f"New tool registered: {generated_tool.name}\n"
                            f"Path: {tool_file}\n"
                            f"Description: {generated_tool.description}"
                        )
                    )
                )

        assert result is not None
        return result

    def create_tool_tool(self) -> BaseTool:
        """Official base tool exposed to the LLM for task-local tool synthesis."""
        return build_create_tool()

    def _ensure_create_tool_registered(self) -> None:
        if any(tool.name == "create_tool" for tool in self.agent.tools):
            return
        self.agent.add_tool(self.create_tool_tool())

    def _task_workspace(self, task: Task) -> Path:
        task_id = task.get("task_id") or "manual"
        return self.config.workspace_root / _safe_name(task_id)

    @staticmethod
    def _write_state_log(path: Path, cycle: int, state: AgentState) -> None:
        log_file = path / "logs" / f"cycle_{cycle:03d}.json"
        log_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def extract_generated_tool_requests(state: AgentState) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for message in state.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue
        content = str(message.content)
        if not content.startswith(GENERATED_TOOL_ARTIFACT_PREFIX):
            continue
        raw = content[len(GENERATED_TOOL_ARTIFACT_PREFIX) :]
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if _valid_request(request):
            requests.append(request)
    return requests


def write_generated_tool(task_workspace: Path, request: dict[str, Any]) -> Path:
    tool_dir = task_workspace / "generated_tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool_path = tool_dir / f"{_safe_name(request['name'])}.py"
    source = request["code"].strip() + "\n"
    tool_path.write_text(source, encoding="utf-8")
    return tool_path


def load_generated_tool(tool_path: Path, name: str) -> BaseTool:
    module_name = f"generated_tool_{_safe_name(name)}_{abs(hash(tool_path))}"
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import generated tool: {tool_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "run", None)
    if not callable(fn):
        raise RuntimeError("Generated tool must define callable run(...).")
    description = getattr(module, "DESCRIPTION", f"Generated tool {name}.")
    return StructuredTool.from_function(
        func=fn,
        name=name,
        description=description,
    )


def _valid_request(request: dict[str, Any]) -> bool:
    return all(isinstance(request.get(key), str) for key in ("name", "description", "code"))


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "tool"
