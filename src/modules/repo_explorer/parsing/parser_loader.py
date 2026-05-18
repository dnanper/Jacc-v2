"""Tree-sitter parser loader — per-language grammar packages.

Uses individual ``tree-sitter-<lang>`` packages (v0.24+) which expose
a ``language()`` function returning a capsule for the new tree-sitter
v0.25 ``Language(ptr)`` constructor.
"""

from __future__ import annotations

import importlib
import logging
from functools import lru_cache

from ..config import (
    TREE_SITTER_GRAMMAR_MAP,
    TSX_GRAMMAR,
    SupportedLanguages,
    is_tsx_file,
)
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

_GRAMMAR_TO_MODULE = {
    # ── Original 14 ──────────────────────────────────────────────────
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "tsx": "tree_sitter_typescript",
    "java": "tree_sitter_java",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
    "c_sharp": "tree_sitter_c_sharp",
    "go": "tree_sitter_go",
    "ruby": "tree_sitter_ruby",
    "rust": "tree_sitter_rust",
    "php": "tree_sitter_php",
    "kotlin": "tree_sitter_kotlin",
    "swift": "tree_sitter_swift",
    # ── Tier 1: Native PyPI packages ─────────────────────────────────
    "fortran": "tree_sitter_fortran",
    "scala": "tree_sitter_scala",
    "objc": "tree_sitter_objc",
    "solidity": "tree_sitter_solidity",
    "matlab": "tree_sitter_matlab",
    "commonlisp": "tree_sitter_commonlisp",
    # "delphi" — no standard tree-sitter binding; uses WASM bridge instead
    "ada": "tree_sitter_ada",
}


@lru_cache(maxsize=16)
def _load_language(grammar_name: str) -> Language:
    """Load a tree-sitter Language by grammar name (cached)."""
    module_name = _GRAMMAR_TO_MODULE.get(grammar_name)
    if module_name is None:
        raise ValueError(f"No module mapping for grammar: {grammar_name}")

    mod = importlib.import_module(module_name)

    if grammar_name == "tsx":
        lang_fn = getattr(mod, "language_tsx", None) or getattr(mod, "language")
    elif grammar_name == "typescript":
        lang_fn = getattr(mod, "language_typescript", None) or getattr(mod, "language")
    elif grammar_name == "php":
        lang_fn = getattr(mod, "language_php", None) or getattr(mod, "language")
    else:
        lang_fn = mod.language

    return Language(lang_fn())


def load_language(lang: SupportedLanguages, file_path: str | None = None) -> Language:
    """Load and return the tree-sitter Language for the given language."""
    if lang == SupportedLanguages.TYPESCRIPT and file_path and is_tsx_file(file_path):
        return _load_language(TSX_GRAMMAR)

    grammar_name = TREE_SITTER_GRAMMAR_MAP.get(lang)
    if grammar_name is None:
        raise ValueError(f"No tree-sitter grammar for language: {lang}")
    return _load_language(grammar_name)


def is_language_available(lang: SupportedLanguages) -> bool:
    """Check if a language grammar is available at runtime."""
    if lang == SupportedLanguages.VB6:
        from .vb6_bridge import is_vb6_available

        return is_vb6_available()

    # Check generic WASM bridge for languages without native Python bindings
    from .wasm_bridge import is_wasm_available

    if is_wasm_available(lang.value):
        return True

    # Check regex parser for languages without any tree-sitter grammar
    from .regex_parser import get_regex_config

    if get_regex_config(lang.value) is not None:
        return True

    try:
        load_language(lang)
        return True
    except Exception as exc:
        logger.debug("Language %s not available: %s", lang, exc)
        return False


def parse_file(content: str, lang: SupportedLanguages, file_path: str | None = None):
    """Parse source code and return the tree-sitter Tree."""
    if lang == SupportedLanguages.VB6:
        from .vb6_bridge import parse_vb6

        return parse_vb6(content, file_path)

    # Check generic WASM bridge for languages without native Python bindings
    from .wasm_bridge import get_wasm_config, parse_wasm

    if get_wasm_config(lang.value) is not None:
        return parse_wasm(content, lang.value, file_path)

    # Check regex parser for languages without any tree-sitter grammar
    from .regex_parser import get_regex_config, parse_regex

    if get_regex_config(lang.value) is not None:
        return parse_regex(content, lang.value, file_path)

    language = load_language(lang, file_path)
    parser = Parser(language)
    return parser.parse(content.encode("utf-8"))
