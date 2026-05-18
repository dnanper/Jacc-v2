"""Regex-based fallback parser for languages without tree-sitter grammars.

For Tier 3 languages (RPG, ABAP, MUMPS, Assembly, Tcl, ALGOL, Forth,
PostScript), this module provides a lightweight regex-based parser that
extracts definitions, calls, and imports from source code using
configurable pattern sets.

Returns WASMNode/WASMTree mock objects compatible with the tree-sitter
pipeline, so no changes are needed in downstream processing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .wasm_bridge import WASMNode, WASMTree

logger = logging.getLogger(__name__)


# ── Regex config definition ──────────────────────────────────────────


@dataclass(frozen=True)
class RegexPattern:
    """A single extraction pattern."""

    node_type: str  # AST node type to emit (e.g. "function_definition")
    pattern: re.Pattern  # Compiled regex with named groups
    name_group: str = "name"  # Named group for the symbol name
    target_group: str | None = None  # Named group for call target / import source


@dataclass(frozen=True)
class RegexLanguageConfig:
    """Complete regex configuration for a language."""

    language_key: str
    definitions: list[RegexPattern] = field(default_factory=list)
    calls: list[RegexPattern] = field(default_factory=list)
    imports: list[RegexPattern] = field(default_factory=list)
    comment_pattern: re.Pattern | None = None  # To strip comments before extraction
    line_continuation: str | None = None  # Character for line continuation


# ── Config registry ──────────────────────────────────────────────────

_REGEX_CONFIGS: dict[str, RegexLanguageConfig] = {}


def register_regex_config(lang_value: str, config: RegexLanguageConfig) -> None:
    """Register a regex parser configuration for a language."""
    _REGEX_CONFIGS[lang_value] = config


def _ensure_configs_loaded() -> None:
    """Lazily import regex_configs package to auto-register all configs."""
    if not _REGEX_CONFIGS:
        from . import regex_configs  # noqa: F401


def get_regex_config(lang_value: str) -> RegexLanguageConfig | None:
    """Get the regex parser config for a language."""
    _ensure_configs_loaded()
    return _REGEX_CONFIGS.get(lang_value)


# ── Regex parser ─────────────────────────────────────────────────────


def _extract_matches(
    content: str,
    patterns: list[RegexPattern],
) -> list[WASMNode]:
    """Run regex patterns against content and produce WASMNode list."""
    nodes: list[WASMNode] = []
    # lines = content.split("\n")

    for rp in patterns:
        for match in rp.pattern.finditer(content):
            name = (
                match.group(rp.name_group) if rp.name_group in match.groupdict() else ""
            )
            start_offset = match.start()
            end_offset = match.end()

            # Calculate line/col from offset
            start_line = content[:start_offset].count("\n")
            start_col = start_offset - content[:start_offset].rfind("\n") - 1
            end_line = content[:end_offset].count("\n")
            end_col = end_offset - content[:end_offset].rfind("\n") - 1

            # Find the end of the definition block (heuristic: scan for end keyword)
            block_end_line = end_line

            # Create a name child node
            name_node = WASMNode(
                type="identifier",
                text=name.encode("utf-8"),
                start_point=(start_line, start_col),
                end_point=(start_line, start_col + len(name)),
                is_named=True,
            )

            # Create the definition node with name as a field
            node = WASMNode(
                type=rp.node_type,
                text=match.group(0).encode("utf-8"),
                start_point=(start_line, start_col),
                end_point=(block_end_line, end_col),
                is_named=True,
                children=[name_node],
            )
            name_node.parent = node
            node._fields["name"] = name_node

            # If there's a target group (for calls/imports), add it as a field
            if rp.target_group and rp.target_group in match.groupdict():
                target = match.group(rp.target_group) or ""
                target_node = WASMNode(
                    type="identifier",
                    text=target.encode("utf-8"),
                    start_point=(start_line, start_col),
                    end_point=(start_line, start_col + len(target)),
                    is_named=True,
                    parent=node,
                )
                node._fields["target"] = target_node
                node.children.append(target_node)

            nodes.append(node)

    return nodes


def parse_regex(
    content: str,
    language_key: str,
    file_path: str | None = None,
) -> WASMTree:
    """Parse source code using regex patterns.

    Args:
        content: Source code as a string.
        language_key: Language identifier matching a registered regex config.
        file_path: Optional file path (unused, for API compatibility).

    Returns:
        A WASMTree with a root WASMNode containing extracted definitions,
        calls, and imports as children.

    Raises:
        RuntimeError: If no regex config is registered for the language.
    """
    _ensure_configs_loaded()
    config = _REGEX_CONFIGS.get(language_key)
    if config is None:
        raise RuntimeError(f"No regex parser registered for language: {language_key}")

    # Handle line continuations
    processed = content
    if config.line_continuation:
        processed = processed.replace(config.line_continuation + "\n", " ")

    # Extract all pattern matches
    definition_nodes = _extract_matches(processed, config.definitions)
    call_nodes = _extract_matches(processed, config.calls)
    import_nodes = _extract_matches(processed, config.imports)

    # Build a root "program" node containing all extracted nodes
    all_children = definition_nodes + call_nodes + import_nodes
    # Sort by position
    all_children.sort(key=lambda n: (n.start_point[0], n.start_point[1]))

    total_lines = content.count("\n")
    root = WASMNode(
        type="program",
        text=content.encode("utf-8")[:300],
        start_point=(0, 0),
        end_point=(total_lines, 0),
        is_named=True,
        children=all_children,
    )

    for child in all_children:
        child.parent = root

    return WASMTree(root_node=root)
