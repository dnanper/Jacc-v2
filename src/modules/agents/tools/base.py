"""Base tools that are always available to coding agents."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

GENERATED_TOOL_ARTIFACT_PREFIX = "generated_tool_request:"


class ListDirInput(BaseModel):
    path: str = Field(default=".", description="Directory path relative to repo root.")


class ReadFileInput(BaseModel):
    path: str = Field(description="File path relative to repo root.")
    start_line: int = Field(default=1, ge=1, description="1-based start line.")
    end_line: int | None = Field(
        default=None,
        ge=1,
        description="1-based inclusive end line.",
    )
    max_chars: int = Field(
        default=20000,
        ge=1,
        le=100000,
        description="Maximum returned chars.",
    )


class SearchTextInput(BaseModel):
    query: str = Field(description="Literal text to search for.")
    path: str = Field(default=".", description="File or directory path relative to repo root.")
    max_results: int = Field(default=50, ge=1, le=500, description="Maximum matches.")


class WriteFileInput(BaseModel):
    path: str = Field(description="File path relative to repo root.")
    content: str = Field(description="Full file content to write.")


class ReplaceInFileInput(BaseModel):
    path: str = Field(description="File path relative to repo root.")
    old: str = Field(description="Exact text to replace.")
    new: str = Field(description="Replacement text.")
    expected_replacements: int = Field(
        default=1,
        ge=1,
        description="Expected replacement count.",
    )


class RunCommandInput(BaseModel):
    command: str = Field(description="Non-interactive shell command to run in repo root.")
    timeout: int = Field(default=60, ge=1, le=600, description="Timeout seconds.")


class CreateToolInput(BaseModel):
    name: str = Field(description="Unique snake_case tool name.")
    description: str = Field(description="Clear description of when to use the generated tool.")
    code: str = Field(
        description=(
            "Python source code. Must define DESCRIPTION and callable run(...). "
            "The run function signature becomes the tool schema."
        )
    )


def build_base_tools(
    repo_root: str | Path,
    *,
    timeout_seconds: int = 60,
    max_output_chars: int = 20000,
) -> list[BaseTool]:
    """Create repo-scoped file/search/command tools."""

    root = Path(repo_root).resolve()

    @tool(args_schema=ListDirInput)
    def list_dir(path: str = ".") -> dict[str, Any]:
        """List a directory under the repository root."""

        target = _resolve_inside(root, path)
        if not target.is_dir():
            raise ValueError(f"Not a directory: {path}")
        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name)):
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"path": _rel(root, target), "entries": entries}

    @tool(args_schema=ReadFileInput)
    def read_file(
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        max_chars: int = 20000,
    ) -> dict[str, Any]:
        """Read a text file under the repository root."""

        target = _resolve_inside(root, path)
        if not target.is_file():
            raise ValueError(f"Not a file: {path}")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start_line)
        end = end_line if end_line is not None else len(lines)
        end = min(len(lines), max(start, end))
        content = "\n".join(lines[start - 1 : end])
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        return {
            "path": _rel(root, target),
            "start_line": start,
            "end_line": end,
            "content": content,
            "truncated": truncated,
        }

    @tool(args_schema=SearchTextInput)
    def search_text(
        query: str,
        path: str = ".",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Search text in repository files."""

        target = _resolve_inside(root, path)
        matches: list[dict[str, Any]] = []
        for file_path in _iter_files(target):
            try:
                for line_number, line in enumerate(
                    file_path.read_text(encoding="utf-8", errors="replace").splitlines(),
                    start=1,
                ):
                    if query in line:
                        matches.append(
                            {
                                "path": _rel(root, file_path),
                                "line": line_number,
                                "text": line,
                            }
                        )
                        if len(matches) >= max_results:
                            return {"query": query, "matches": matches, "truncated": True}
            except OSError:
                continue
        return {"query": query, "matches": matches, "truncated": False}

    @tool(args_schema=WriteFileInput)
    def write_file(path: str, content: str) -> dict[str, Any]:
        """Write a text file under the repository root."""

        target = _resolve_inside(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": _rel(root, target),
            "written": True,
            "bytes": len(content.encode("utf-8")),
        }

    @tool(args_schema=ReplaceInFileInput)
    def replace_in_file(
        path: str,
        old: str,
        new: str,
        expected_replacements: int = 1,
    ) -> dict[str, Any]:
        """Replace exact text in a repository file."""

        target = _resolve_inside(root, path)
        if not target.is_file():
            raise ValueError(f"Not a file: {path}")
        content = target.read_text(encoding="utf-8", errors="replace")
        count = content.count(old)
        if count != expected_replacements:
            raise ValueError(
                f"Expected {expected_replacements} replacement(s), found {count}."
            )
        target.write_text(content.replace(old, new), encoding="utf-8")
        return {"path": _rel(root, target), "replacements": count, "written": True}

    @tool(args_schema=RunCommandInput)
    def run_command(command: str, timeout: int = timeout_seconds) -> dict[str, Any]:
        """Run a non-interactive shell command in the repository root."""

        _validate_command(command)
        env = os.environ.copy()
        env.setdefault("PAGER", "cat")
        env.setdefault("MANPAGER", "cat")
        env.setdefault("PIP_PROGRESS_BAR", "off")
        completed = subprocess.run(
            command,
            cwd=root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=min(timeout, timeout_seconds),
            env=env,
        )
        stdout, stdout_truncated = _truncate(completed.stdout, max_output_chars)
        stderr, stderr_truncated = _truncate(completed.stderr, max_output_chars)
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": stdout_truncated or stderr_truncated,
        }

    return [
        list_dir,
        read_file,
        search_text,
        write_file,
        replace_in_file,
        run_command,
    ]


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


def _resolve_inside(root: Path, path: str) -> Path:
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Path escapes repository root: {path}")
    return target


def _rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _iter_files(path: Path):
    if path.is_file():
        yield path
        return
    for child in path.rglob("*"):
        if child.is_file() and not _is_binary_like(child):
            yield child


def _is_binary_like(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:1024]
    except OSError:
        return True
    return b"\x00" in sample


def _truncate(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    head = max_chars // 2
    tail = max_chars - head
    return value[:head] + "\n...[truncated]...\n" + value[-tail:], True


def _validate_command(command: str) -> None:
    denied = [
        r"\brm\s+-rf\b",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-fd",
        r"\bsudo\b",
        r"\bssh\b",
        r"\bscp\b",
        r"\bvim?\b",
        r"\bnano\b",
    ]
    for pattern in denied:
        if re.search(pattern, command):
            raise ValueError(f"Command denied by automatic safety policy: {pattern}")
