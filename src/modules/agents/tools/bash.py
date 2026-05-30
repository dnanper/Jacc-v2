from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from src.environments.docker import DockerEnvironment


class RunCommandInput(BaseModel):
    command: str = Field(
        description=(
            "Shell command to run inside the SWE-Bench repository at /testbed. "
            "Use commands such as ls, sed, grep, python, pytest, and git diff to inspect, edit, "
            "reproduce, verify, and review the solution. Commands must be non-interactive. "
            "Do not prefix commands with bash -lc; the tool already runs commands through bash."
        )
    )
    timeout: int = Field(
        default=60,
        ge=1,
        le=600,
        description="Command timeout seconds.",
    )


def build_bash_tool(
    environment: DockerEnvironment,
    *,
    max_output_chars: int = 20000,
) -> list[BaseTool]:
    """Build the minimal mini-swe-agent-style tool surface."""

    @tool(args_schema=RunCommandInput)
    def bash(command: str, timeout: int = 60) -> dict[str, Any]:
        """Run a non-interactive bash command in the SWE-Bench /testbed repo.

        Use this tool for all repository work: inspect files, search code, create
        or edit source files, run repro or test commands to verify behavior,
        and inspect git diff.
        The command executes in /testbed inside the task container. Avoid
        interactive programs and long-running background services. Do not prefix
        commands with bash -lc; pass the actual command, for example:
        grep -RIn "target" src tests | head.
        """

        return _truncate_output(
            environment.execute(
                {"command": command},
                cwd=environment.config.cwd,
                timeout=timeout,
            ),
            max_output_chars,
        )

    return [bash]


def _truncate_output(output: dict[str, Any], max_chars: int) -> dict[str, Any]:
    text = output.get("output", "")
    if len(text) <= max_chars:
        return output
    head = max_chars // 2
    tail = max_chars - head
    truncated = dict(output)
    truncated["output"] = text[:head] + "\n...[truncated]...\n" + text[-tail:]
    truncated["truncated"] = True
    return truncated
