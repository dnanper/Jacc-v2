"""Docstring extractor — pull doc comments from AST nodes per language.

Extracts docstrings/doc-comments from function, class, and method
definitions so they can be turned into Section nodes during Phase 3.
Each language has its own convention for where the docstring lives
relative to the definition AST node.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...config import SupportedLanguages

MIN_DOCSTRING_LENGTH = 20


@dataclass
class ExtractedDocstring:
    """A docstring extracted from an AST definition node."""

    content: str
    start_line: int
    end_line: int


def _node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


_STRIP_BLOCK_RE = re.compile(r"^\s*/?[*]+\s?", re.MULTILINE)
_STRIP_TRAILING_STAR_SLASH = re.compile(r"\s*\*+/\s*$")


def _strip_block_comment(text: str) -> str:
    """Strip /** ... */ delimiters and leading * from each line."""
    text = text.strip()
    if text.startswith("/**"):
        text = text[3:]
    elif text.startswith("/*"):
        text = text[2:]
    text = _STRIP_TRAILING_STAR_SLASH.sub("", text)
    text = _STRIP_BLOCK_RE.sub("", text)
    return text.strip()


def _strip_line_comments(text: str, prefix: str) -> str:
    """Strip a line-comment prefix (e.g. '///', '//') from each line."""
    lines = text.split("\n")
    stripped = []
    for line in lines:
        s = line.strip()
        if s.startswith(prefix):
            s = s[len(prefix) :]
            if s.startswith(" "):
                s = s[1:]
        stripped.append(s)
    return "\n".join(stripped).strip()


def _collect_preceding_comments(
    defn_node, *, prefixes: tuple[str, ...] | None = None
) -> ExtractedDocstring | None:
    """Collect contiguous comment siblings immediately before *defn_node*.

    Works for languages where doc-comments sit above the definition
    as sibling nodes (Go, Rust, C#, Ruby, etc.).

    If *prefixes* is given, only include comment lines starting with
    one of those prefixes (e.g. ``("///",)`` for Rust/C#).
    """
    comments: list = []
    sibling = defn_node.prev_named_sibling

    while sibling is not None:
        stype = sibling.type
        if stype not in (
            "comment",
            "line_comment",
            "block_comment",
            "multiline_comment",
        ):
            break
        text = _node_text(sibling).strip()
        if prefixes and not any(text.startswith(p) for p in prefixes):
            break

        next_start = (
            comments[0].start_point[0] if comments else defn_node.start_point[0]
        )
        if next_start - sibling.end_point[0] > 2:
            break

        comments.insert(0, sibling)
        sibling = sibling.prev_named_sibling

    if not comments:
        return None

    full_text = "\n".join(_node_text(c) for c in comments)
    return ExtractedDocstring(
        content=full_text,
        start_line=comments[0].start_point[0],
        end_line=comments[-1].end_point[0],
    )


def _collect_preceding_block_comment(defn_node) -> ExtractedDocstring | None:
    """Collect a /** ... */ block comment immediately before *defn_node*."""
    sibling = defn_node.prev_named_sibling
    if sibling is None:
        return None

    stype = sibling.type
    if stype not in ("comment", "block_comment", "multiline_comment"):
        return None

    text = _node_text(sibling).strip()
    if not text.startswith("/**"):
        return None

    if defn_node.start_point[0] - sibling.end_point[0] > 2:
        return None

    return ExtractedDocstring(
        content=text,
        start_line=sibling.start_point[0],
        end_line=sibling.end_point[0],
    )


def _extract_python(defn_node) -> ExtractedDocstring | None:
    """Python: first expression_statement > string in the body block."""
    body = defn_node.child_by_field_name("body")
    if body is None:
        return None

    for child in body.children:
        if not child.is_named:
            continue
        if child.type == "expression_statement":
            inner = child.children[0] if child.children else None
            if inner is not None and inner.type == "string":
                text = _node_text(inner)
                for q in ('"""', "'''"):
                    if text.startswith(q) and text.endswith(q):
                        text = text[3:-3]
                        break
                else:
                    return None
                return ExtractedDocstring(
                    content=text.strip(),
                    start_line=inner.start_point[0],
                    end_line=inner.end_point[0],
                )
            break
        elif child.type == "comment":
            continue
        else:
            break
    return None


def _extract_jsdoc(defn_node) -> ExtractedDocstring | None:
    """JS/TS/Java/Kotlin/PHP: /** ... */ block comment before definition."""
    return _collect_preceding_block_comment(defn_node)


def _extract_go(defn_node) -> ExtractedDocstring | None:
    """Go: contiguous // comments immediately before definition."""
    return _collect_preceding_comments(defn_node, prefixes=("//",))


def _extract_rust(defn_node) -> ExtractedDocstring | None:
    """Rust: /// line comments or /** block comment before definition."""
    result = _collect_preceding_comments(defn_node, prefixes=("///",))
    if result:
        return result
    return _collect_preceding_block_comment(defn_node)


def _extract_csharp(defn_node) -> ExtractedDocstring | None:
    """C#: /// XML doc comments before definition."""
    return _collect_preceding_comments(defn_node, prefixes=("///",))


def _extract_c_cpp(defn_node) -> ExtractedDocstring | None:
    """C/C++: /** block comment or // comments before definition."""
    result = _collect_preceding_block_comment(defn_node)
    if result:
        return result
    return _collect_preceding_comments(defn_node, prefixes=("//",))


def _extract_ruby(defn_node) -> ExtractedDocstring | None:
    """Ruby: # comments (Yard-style) before definition."""
    return _collect_preceding_comments(defn_node, prefixes=("#",))


def _extract_swift(defn_node) -> ExtractedDocstring | None:
    """Swift: /// line comments or /** block comment before definition."""
    result = _collect_preceding_comments(defn_node, prefixes=("///",))
    if result:
        return result
    return _collect_preceding_block_comment(defn_node)


def _extract_vb6(defn_node) -> ExtractedDocstring | None:
    """VB6: collect ' comment lines preceding definition."""
    return _collect_preceding_comments(defn_node, prefixes=("'",))


def _extract_fortran(defn_node) -> ExtractedDocstring | None:
    """Fortran: ! comment lines preceding definition."""
    return _collect_preceding_comments(defn_node, prefixes=("!",))


def _extract_scala(defn_node) -> ExtractedDocstring | None:
    """Scala: /** ... */ ScalaDoc block comment before definition."""
    return _collect_preceding_block_comment(defn_node)


def _extract_objc(defn_node) -> ExtractedDocstring | None:
    """Objective-C: /** block comment or /// comments before definition."""
    result = _collect_preceding_block_comment(defn_node)
    if result:
        return result
    return _collect_preceding_comments(defn_node, prefixes=("///",))


def _extract_solidity(defn_node) -> ExtractedDocstring | None:
    """Solidity: /// NatSpec comments or /** block comment before definition."""
    result = _collect_preceding_comments(defn_node, prefixes=("///",))
    if result:
        return result
    return _collect_preceding_block_comment(defn_node)


DOCSTRING_EXTRACTORS = {
    SupportedLanguages.VB6: _extract_vb6,
    SupportedLanguages.PYTHON: _extract_python,
    SupportedLanguages.JAVASCRIPT: _extract_jsdoc,
    SupportedLanguages.TYPESCRIPT: _extract_jsdoc,
    SupportedLanguages.JAVA: _extract_jsdoc,
    SupportedLanguages.KOTLIN: _extract_jsdoc,
    SupportedLanguages.PHP: _extract_jsdoc,
    SupportedLanguages.GO: _extract_go,
    SupportedLanguages.RUST: _extract_rust,
    SupportedLanguages.C: _extract_c_cpp,
    SupportedLanguages.C_PLUS_PLUS: _extract_c_cpp,
    SupportedLanguages.C_SHARP: _extract_csharp,
    SupportedLanguages.RUBY: _extract_ruby,
    SupportedLanguages.SWIFT: _extract_swift,
    # ── Wave 1 ───────────────────────────────────────────────────────
    SupportedLanguages.FORTRAN: _extract_fortran,
    SupportedLanguages.SCALA: _extract_scala,
    SupportedLanguages.OBJECTIVE_C: _extract_objc,
    SupportedLanguages.SOLIDITY: _extract_solidity,
    SupportedLanguages.PERL: _extract_ruby,  # Perl: # comments before subs
    SupportedLanguages.COBOL: _extract_fortran,  # COBOL: * comments (column 7)
    # ── Wave 2 ───────────────────────────────────────────────────────
    SupportedLanguages.ADA: _extract_go,  # Ada: -- comments before declarations
    SupportedLanguages.MATLAB: _extract_ruby,  # MATLAB: % comments after signature
    SupportedLanguages.COMMON_LISP: _extract_ruby,  # Lisp: ; comments (docstring in body handled separately)
    SupportedLanguages.DELPHI: _extract_c_cpp,  # Delphi: { } or /// comments
    # ── Wave 3 ───────────────────────────────────────────────────────
    SupportedLanguages.ERLANG: _extract_ruby,  # Erlang: %% @doc comments
    SupportedLanguages.APEX: _extract_jsdoc,  # Apex: /** ... */ JavaDoc-style
    SupportedLanguages.PASCAL: _extract_c_cpp,  # Pascal: { } or (* *) comments
    SupportedLanguages.PROLOG: _extract_ruby,  # Prolog: % comments
    # ── Wave 4-5: Tier 3 ─────────────────────────────────────────────
    SupportedLanguages.RPG: _extract_go,  # RPG: // comments
    SupportedLanguages.ABAP: _extract_ruby,  # ABAP: * or " comments
    SupportedLanguages.MUMPS: _extract_ruby,  # MUMPS: ; comments
    SupportedLanguages.ASSEMBLY: _extract_ruby,  # Assembly: ; or # comments
    SupportedLanguages.TCL: _extract_ruby,  # Tcl: # comments
    SupportedLanguages.ALGOL: _extract_ruby,  # ALGOL: comment keyword
    SupportedLanguages.FORTH: _extract_ruby,  # Forth: \ comments
    SupportedLanguages.POSTSCRIPT: _extract_ruby,  # PostScript: % comments
}


def clean_docstring(raw: str, lang: SupportedLanguages) -> str:
    """Strip language-specific delimiters from a raw docstring."""
    if lang == SupportedLanguages.PYTHON:
        return raw

    if lang in (
        SupportedLanguages.RUST,
        SupportedLanguages.SWIFT,
        SupportedLanguages.C_SHARP,
    ):
        if raw.lstrip().startswith("///"):
            return _strip_line_comments(raw, "///")
        return _strip_block_comment(raw)

    if lang == SupportedLanguages.VB6:
        return _strip_line_comments(raw, "'")

    if lang == SupportedLanguages.GO:
        return _strip_line_comments(raw, "//")

    if lang == SupportedLanguages.RUBY:
        return _strip_line_comments(raw, "#")

    if raw.lstrip().startswith("/**") or raw.lstrip().startswith("/*"):
        return _strip_block_comment(raw)
    return _strip_line_comments(raw, "//")


def extract_docstring(defn_node, lang: SupportedLanguages) -> ExtractedDocstring | None:
    """Extract and clean a docstring from *defn_node* for the given language.

    Returns None if no docstring is found or if it's too short.
    """
    extractor = DOCSTRING_EXTRACTORS.get(lang)
    if extractor is None:
        return None

    result = extractor(defn_node)
    if result is None:
        return None

    cleaned = clean_docstring(result.content, lang)
    if len(cleaned) < MIN_DOCSTRING_LENGTH:
        return None

    return ExtractedDocstring(
        content=cleaned,
        start_line=result.start_line,
        end_line=result.end_line,
    )
