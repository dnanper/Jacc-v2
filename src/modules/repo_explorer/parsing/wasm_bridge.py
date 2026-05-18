"""Generic WASM parser bridge — delegates parsing to Node.js + web-tree-sitter.

Generalizes the VB6 bridge pattern for any language that has a tree-sitter
WASM grammar but no native Python binding. Calls a generic JS bridge script
which loads the specified WASM grammar and returns a JSON AST.

The JSON AST is converted to mock tree-sitter node objects (WASMNode/WASMTree)
that integrate with CSG's existing pipeline.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_JS_BRIDGE_DIR = Path(__file__).resolve().parent / "js_bridge"
_PARSE_SCRIPT = _JS_BRIDGE_DIR / "parse_generic.mjs"
_NODE_BIN: str | None = None


def _find_node() -> str | None:
    """Find the Node.js binary."""
    global _NODE_BIN
    if _NODE_BIN is not None:
        return _NODE_BIN
    _NODE_BIN = shutil.which("node")
    return _NODE_BIN


# ── Mock tree-sitter node ────────────────────────────────────────────


@dataclass
class WASMNode:
    """A mock tree-sitter node reconstructed from the JS bridge JSON output."""

    type: str
    text: bytes
    start_point: tuple[int, int]
    end_point: tuple[int, int]
    children: list[WASMNode] = field(default_factory=list)
    parent: WASMNode | None = field(default=None, repr=False)
    is_named: bool = True
    _fields: dict[str, WASMNode] = field(default_factory=dict, repr=False)
    start_byte: int = 0

    def child_by_field_name(self, name: str) -> WASMNode | None:
        return self._fields.get(name)

    @property
    def prev_named_sibling(self) -> WASMNode | None:
        if self.parent is None:
            return None
        siblings = self.parent.children
        idx = None
        for i, s in enumerate(siblings):
            if s is self:
                idx = i
                break
        if idx is None or idx == 0:
            return None
        for i in range(idx - 1, -1, -1):
            if siblings[i].is_named:
                return siblings[i]
        return None

    @property
    def named_children(self) -> list[WASMNode]:
        return [c for c in self.children if c.is_named]

    @property
    def child_count(self) -> int:
        return len(self.children)

    def child(self, idx: int) -> WASMNode | None:
        if 0 <= idx < len(self.children):
            return self.children[idx]
        return None

    @property
    def is_missing(self) -> bool:
        return self.type == "MISSING"


@dataclass
class WASMTree:
    """A mock tree-sitter Tree wrapping the root node."""

    root_node: WASMNode


def _json_to_node(data: dict, parent: WASMNode | None = None) -> WASMNode:
    """Recursively convert a JSON AST dict to a WASMNode tree."""
    sp = data.get("startPosition", {})
    ep = data.get("endPosition", {})
    text = data.get("text", "")
    if isinstance(text, str):
        text = text.encode("utf-8")

    node = WASMNode(
        type=data.get("type", "unknown"),
        text=text,
        start_point=(sp.get("row", 0), sp.get("column", 0)),
        end_point=(ep.get("row", 0), ep.get("column", 0)),
        is_named=data.get("isNamed", True),
        parent=parent,
        start_byte=0,
    )

    for child_data in data.get("children", []):
        child = _json_to_node(child_data, parent=node)
        node.children.append(child)

    for fname, fdata in data.get("fields", {}).items():
        fsp = fdata.get("startPosition", {})
        fep = fdata.get("endPosition", {})
        ftext = fdata.get("text", "")
        if isinstance(ftext, str):
            ftext = ftext.encode("utf-8")

        matched = _find_child_at(node, fsp.get("row", -1), fsp.get("column", -1))
        if matched:
            node._fields[fname] = matched
        else:
            node._fields[fname] = WASMNode(
                type=fdata.get("type", "identifier"),
                text=ftext,
                start_point=(fsp.get("row", 0), fsp.get("column", 0)),
                end_point=(fep.get("row", 0), fep.get("column", 0)),
                parent=node,
            )

    return node


def _find_child_at(node: WASMNode, row: int, col: int) -> WASMNode | None:
    """Find a descendant node at the given position."""
    for child in node.children:
        if child.start_point == (row, col):
            return child
        found = _find_child_at(child, row, col)
        if found:
            return found
    return None


# ── Language-specific preprocessors ──────────────────────────────────

# Registry: language_key → preprocessor function (content, file_path) → processed_content
# Languages that don't need preprocessing simply aren't registered here.
_PREPROCESSORS: dict[str, Callable[[str, str], str]] = {}


def register_preprocessor(language_key: str, fn: Callable[[str, str], str]) -> None:
    """Register a preprocessing function for a WASM-bridged language."""
    _PREPROCESSORS[language_key] = fn


# ── WASM grammar registry ───────────────────────────────────────────


@dataclass(frozen=True)
class WASMGrammarConfig:
    """Configuration for a WASM-bridged language grammar."""

    language_key: str
    wasm_filename: str
    grammar_name: str | None = None  # npm package name (for parse_generic.mjs)

    @property
    def wasm_path(self) -> Path:
        return _JS_BRIDGE_DIR / self.wasm_filename

    @property
    def is_available(self) -> bool:
        return self.wasm_path.exists()


# Registry of WASM grammar configs keyed by SupportedLanguages string value
_WASM_CONFIGS: dict[str, WASMGrammarConfig] = {}


def register_wasm_grammar(lang_value: str, config: WASMGrammarConfig) -> None:
    """Register a WASM grammar configuration for a language."""
    _WASM_CONFIGS[lang_value] = config


def get_wasm_config(lang_value: str) -> WASMGrammarConfig | None:
    """Get the WASM grammar config for a language."""
    return _WASM_CONFIGS.get(lang_value)


# ── Bridge call ──────────────────────────────────────────────────────


def parse_wasm(
    content: str,
    language_key: str,
    file_path: str | None = None,
) -> WASMTree:
    """Parse source code via the Node.js WASM bridge.

    Args:
        content: Source code as a string.
        language_key: Language identifier matching a registered WASM config.
        file_path: Optional file path (used for preprocessing heuristics).

    Returns:
        A WASMTree with a root WASMNode, compatible with tree-sitter API.

    Raises:
        RuntimeError: If Node.js is not available, grammar not found, or parsing fails.
    """
    node_bin = _find_node()
    if node_bin is None:
        raise RuntimeError(
            "Node.js not found. Install Node.js to enable WASM-bridged parsing.\n"
            "WASM-bridged languages use web-tree-sitter via a Node.js bridge."
        )

    config = _WASM_CONFIGS.get(language_key)
    if config is None:
        raise RuntimeError(f"No WASM grammar registered for language: {language_key}")

    if not config.is_available:
        raise RuntimeError(
            f"WASM grammar not found: {config.wasm_path}\n"
            f"Download or build the WASM grammar for {language_key}."
        )

    # Apply language-specific preprocessing
    preprocessor = _PREPROCESSORS.get(language_key)
    if preprocessor is not None:
        content = preprocessor(content, file_path or "")

    fake_name = file_path or f"module.{language_key}"

    try:
        result = subprocess.run(
            [
                node_bin,
                str(_PARSE_SCRIPT),
                "--wasm",
                str(config.wasm_path),
                "--stdin",
                fake_name,
            ],
            input=content,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_JS_BRIDGE_DIR),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"WASM parser timed out for {file_path} ({language_key})")
    except FileNotFoundError:
        raise RuntimeError(f"Node.js not found at {node_bin}")

    if result.returncode != 0:
        logger.warning(
            "WASM parse error for %s (%s): %s",
            file_path,
            language_key,
            result.stderr[:500],
        )
        raise RuntimeError(
            f"WASM parser failed ({language_key}): {result.stderr[:200]}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"WASM parser returned invalid JSON ({language_key}): {exc}")

    ast_data = data.get("ast", {})
    errors = data.get("errors", [])

    if errors:
        logger.debug(
            "WASM parse: %d errors in %s (%s)", len(errors), file_path, language_key
        )

    root = _json_to_node(ast_data)
    return WASMTree(root_node=root)


def is_wasm_available(language_key: str) -> bool:
    """Check if WASM parsing is available for a language."""
    node = _find_node()
    if node is None:
        return False
    config = _WASM_CONFIGS.get(language_key)
    if config is None:
        return False
    return config.is_available


# ── Pre-registered WASM grammars ─────────────────────────────────────
# These configs are registered at import time. The WASM binaries may or
# may not be present — is_wasm_available() checks for the files.

register_wasm_grammar(
    "perl",
    WASMGrammarConfig(
        language_key="perl",
        wasm_filename="tree-sitter-perl.wasm",
        grammar_name="tree-sitter-perl",
    ),
)

register_wasm_grammar(
    "cobol",
    WASMGrammarConfig(
        language_key="cobol",
        wasm_filename="tree-sitter-cobol.wasm",
        grammar_name="tree-sitter-cobol",
    ),
)

register_wasm_grammar(
    "erlang",
    WASMGrammarConfig(
        language_key="erlang",
        wasm_filename="tree-sitter-erlang.wasm",
        grammar_name="tree-sitter-erlang",
    ),
)

register_wasm_grammar(
    "apex",
    WASMGrammarConfig(
        language_key="apex",
        wasm_filename="tree-sitter-sfapex.wasm",
        grammar_name="tree-sitter-sfapex",
    ),
)

register_wasm_grammar(
    "pascal",
    WASMGrammarConfig(
        language_key="pascal",
        wasm_filename="tree-sitter-pascal.wasm",
        grammar_name="tree-sitter-pascal",
    ),
)

register_wasm_grammar(
    "prolog",
    WASMGrammarConfig(
        language_key="prolog",
        wasm_filename="tree-sitter-prolog.wasm",
        grammar_name="tree-sitter-prolog",
    ),
)

register_wasm_grammar(
    "delphi",
    WASMGrammarConfig(
        language_key="delphi",
        wasm_filename="tree-sitter-delphi.wasm",
        grammar_name="tree-sitter-delphi",
    ),
)
