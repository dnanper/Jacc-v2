from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

MAX_CKG_LIST_ITEMS = 10
MAX_CKG_NESTED_LIST_ITEMS = 8
MAX_CKG_TEXT_CHARS = 1200


class CkgSearchInput(BaseModel):
    query: str = Field(
        description=(
            "Natural-language or code query for locating relevant files and "
            "symbols in the read-only initial /testbed snapshot."
        )
    )
    limit: int = Field(default=5, ge=1, le=10)


class CkgFileContextInput(BaseModel):
    file_path: str = Field(
        description=(
            "Relative file path from CKG results, e.g. src/pkg/module.py. "
            "The path maps to /testbed/<file_path> for bash."
        )
    )
    query: str = Field(default="", description="Optional focus query.")
    limit: int = Field(default=5, ge=1, le=10)


class CkgSymbolContextInput(BaseModel):
    symbol_name: str = Field(
        description="Function, class, method, or symbol name to inspect."
    )


class CkgContractInput(BaseModel):
    symbols: list[str] = Field(
        description=(
            "One to five symbol names found by CKG search/context, e.g. "
            "['Parser.parse', 'normalize_markers']."
        ),
        min_length=1,
        max_length=5,
    )


class CkgCrosscutInput(BaseModel):
    query: str = Field(
        default="",
        description=(
            "Optional focus query for cross-file concerns, e.g. shared parser, "
            "validation flow, serialization helpers."
        ),
    )
    scope: str = Field(
        default="",
        description="Optional scope such as file:src/pkg/module.py.",
    )


class CkgImpactInput(BaseModel):
    target: str = Field(description="Symbol name to analyze before editing.")
    direction: Literal["upstream", "downstream"] = Field(default="upstream")
    min_confidence: float = Field(default=0.4, ge=0.0, le=1.0)


def build_ckg_tools(
    backend: Any,
    *,
    snapshot_root: Path,
    container_root: str = "/testbed",
) -> list[BaseTool]:
    """Build read-only CKG tools over the initial SWE-Bench snapshot."""

    def normalize(value: Any) -> Any:
        return _finalize_ckg_result(
            value,
            snapshot_root=snapshot_root,
            container_root=container_root,
        )

    @tool(args_schema=CkgSearchInput)
    def ckg_search(query: str, limit: int = 5) -> dict[str, Any]:
        """Search the read-only CKG snapshot for likely files and symbols.

        Use this first for fault localization from the issue text. Ask a
        focused natural-language question, not a broad keyword dump. Results
        return repo-relative paths plus /testbed container paths. This graph
        was built before edits; Use bash for current source, edits, tests, and
        git diff.
        """

        try:
            result = backend.relevance(query, limit=limit)
        except AttributeError:
            result = backend.explore_auto(query=query, layer="relevance")
        return normalize(result)

    @tool(args_schema=CkgFileContextInput)
    def ckg_file_context(
        file_path: str,
        query: str = "",
        limit: int = 5,
    ) -> dict[str, Any]:
        """Inspect symbols and execution context for one file in the snapshot.

        Use after ckg_search identifies a likely file. This read-only result
        helps identify important symbols and flows in that file. It may be
        stale after edits. Use bash to read the authoritative current file at
        /testbed/<file_path> before changing it.
        """

        scope = f"file:{_relative_path(file_path, snapshot_root)}"
        try:
            result = backend.context_layer(scope, query=query, limit=limit)
        except AttributeError:
            result = backend.explore_auto(query=query, scope=scope, layer="context")
        return normalize(result)

    @tool(args_schema=CkgSymbolContextInput)
    def ckg_symbol_context(symbol_name: str) -> dict[str, Any]:
        """Get read-only callers, callees, signature, and snippet for a symbol.

        Use this when you know a specific function/class/method name and need
        surrounding call context before editing. Confirm exact current source
        with bash because CKG was built from the initial snapshot.
        """

        return normalize(backend.context_360(symbol_name))

    @tool(args_schema=CkgContractInput)
    def ckg_contract(symbols: list[str]) -> dict[str, Any]:
        """Inspect read-only contracts for known symbols before editing.

        Use this after ckg_search or ckg_symbol_context when the edit depends
        on signatures, return types, callers, callees, inheritance, or override
        relationships. Keep the list small and targeted. Use bash afterwards
        to verify the exact current implementation in /testbed.
        """

        limited_symbols = [symbol for symbol in symbols if symbol.strip()][:5]
        try:
            result = backend.contract(limited_symbols)
        except AttributeError:
            result = backend.explore_auto(
                query=", ".join(limited_symbols),
                layer="contract",
            )
        return normalize(result)

    @tool(args_schema=CkgCrosscutInput)
    def ckg_crosscut(query: str = "", scope: str = "") -> dict[str, Any]:
        """Find read-only cross-file patterns before choosing an edit site.

        Use this for shared utilities, import cycles, duplicated logic,
        framework hooks, or behavior spread across modules. It is useful before
        modifying common code. Use bash for exact file contents and tests.
        """

        normalized_scope = scope
        if scope.startswith("file:"):
            normalized_scope = f"file:{_relative_path(scope[5:], snapshot_root)}"
        try:
            result = backend.crosscut(query=query, scope=normalized_scope)
        except AttributeError:
            result = backend.explore_auto(
                query=query,
                scope=normalized_scope,
                layer="crosscut",
            )
        return normalize(result)

    @tool(args_schema=CkgImpactInput)
    def ckg_impact(
        target: str,
        direction: str = "upstream",
        min_confidence: float = 0.4,
    ) -> dict[str, Any]:
        """Estimate read-only blast radius for a symbol before editing.

        Use for shared functions/classes before editing them. Direction
        upstream shows dependents/callers; downstream shows dependencies. The
        result is guidance only; tests and git diff must be run with bash in
        /testbed.
        """

        result = backend.impact(
            target,
            direction=direction,
            min_confidence=min_confidence,
        )
        if isinstance(result, dict) and isinstance(result.get("affected"), list):
            result = dict(result)
            result["affected"] = result["affected"][:20]
        return normalize(result)

    @tool
    def ckg_overview() -> dict[str, Any]:
        """Show a compressed read-only map of repository communities.

        Use only when the repository layout is unfamiliar or search has weak
        signal. This is higher-level than ckg_search. Do not use CKG tools for
        edits; use bash for all current file contents, tests, and patches.
        """

        try:
            result = backend.topology()
        except AttributeError:
            result = backend.explore_auto(layer="topology")
        return normalize(result)

    return [
        ckg_search,
        ckg_file_context,
        ckg_symbol_context,
        ckg_contract,
        ckg_crosscut,
        ckg_impact,
        ckg_overview,
    ]


def _finalize_ckg_result(
    value: Any,
    *,
    snapshot_root: Path,
    container_root: str,
) -> Any:
    normalized = _normalize_paths(value, snapshot_root, container_root)
    compacted = _compact_ckg_result(normalized)
    if isinstance(compacted, dict):
        compacted.setdefault(
            "_ckg_usage",
            {
                "source": "read-only initial snapshot",
                "next_steps": [
                    "Use CKG only to choose likely files, symbols, and relationships.",
                    "Use bash to read current /testbed files before editing.",
                    "Use bash for edits, tests, git diff, and final verification.",
                ],
            },
        )
    return compacted


def _normalize_paths(value: Any, snapshot_root: Path, container_root: str) -> Any:
    if isinstance(value, list):
        return [_normalize_paths(item, snapshot_root, container_root) for item in value]
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"filePath", "file"} and isinstance(item, str):
            rel_path = _relative_path(item, snapshot_root)
            normalized[key] = rel_path
            normalized["container_path"] = _container_path(rel_path, container_root)
        else:
            normalized[key] = _normalize_paths(item, snapshot_root, container_root)
    return normalized


def _compact_ckg_result(value: Any, key: str = "") -> Any:
    if isinstance(value, list):
        limit = MAX_CKG_LIST_ITEMS
        if key in {"steps", "callers", "callees", "hits"}:
            limit = MAX_CKG_NESTED_LIST_ITEMS
        return [_compact_ckg_result(item, key) for item in value[:limit]]

    if isinstance(value, dict):
        return {
            item_key: _compact_ckg_result(item_value, item_key)
            for item_key, item_value in value.items()
        }

    if isinstance(value, str) and key in {"content", "source", "snippet"}:
        return _truncate_text(value, MAX_CKG_TEXT_CHARS)

    return value


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars].rfind("\n")
    if cut < max_chars // 2:
        cut = max_chars
    return value[:cut] + "\n...[ckg truncated]..."


def _relative_path(path: str, snapshot_root: Path) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("/testbed/"):
        return normalized[len("/testbed/") :]
    try:
        return (
            Path(normalized)
            .resolve()
            .relative_to(snapshot_root.resolve())
            .as_posix()
        )
    except (OSError, ValueError):
        return normalized.lstrip("/")


def _container_path(relative_path: str, container_root: str) -> str:
    root = container_root.rstrip("/")
    rel = PurePosixPath(relative_path.lstrip("/"))
    return f"{root}/{rel.as_posix()}"
