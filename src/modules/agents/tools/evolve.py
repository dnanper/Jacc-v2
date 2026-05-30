from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

GENERATED_TOOL_ARTIFACT_PREFIX = "generated_tool_request:"


class CreateToolInput(BaseModel):
    name: str = Field(description="Unique snake_case tool name.")
    description: str = Field(
        description="Clear description of when to use the generated tool."
    )
    code: str = Field(
        description=(
            "Python source code. Must define DESCRIPTION and callable run(...). "
            "The run function signature becomes the tool schema."
        )
    )


def build_create_tool() -> BaseTool:
    """Create the default self-evolution tool."""

    @tool(args_schema=CreateToolInput)
    def create_tool(name: str, description: str, code: str) -> str:
        """Request creation of a Python tool for the current task.

        The runtime writes the tool code to the task workspace, validates it,
        registers it as a LangChain tool, rebuilds the graph, then resumes the
        same task state.
        """

        import json

        payload = {"name": name, "description": description, "code": code}
        return GENERATED_TOOL_ARTIFACT_PREFIX + json.dumps(payload, ensure_ascii=True)

    return create_tool
