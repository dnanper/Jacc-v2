"""Per-language export detection — determines if a symbol is exported/public.

Port of GitNexus ingestion/export-detection.ts.
Each language has different conventions for public visibility.
"""

from __future__ import annotations

from ...config import SupportedLanguages


def is_exported(node, name: str, language: SupportedLanguages) -> bool:
    """Determine if an AST node represents an exported/public symbol.

    Args:
        node: The tree-sitter definition AST node.
        name: The symbol name.
        language: The programming language.

    Returns:
        True if the symbol is considered exported/public.
    """
    checker = _EXPORT_CHECKERS.get(language)
    if checker is None:
        return True
    return checker(node, name)


def _check_python(node, name: str) -> bool:
    """Python: not exported if name starts with underscore."""
    return not name.startswith("_")


def _check_go(node, name: str) -> bool:
    """Go: exported if first character is uppercase."""
    return bool(name) and name[0].isupper()


def _check_typescript(node, name: str) -> bool:
    """TypeScript/JavaScript: exported if ancestor is export_statement,
    or if a sibling export_statement references this name (export default X)."""
    # Check 1: walk up for direct wrapping export_statement
    current = node.parent
    while current is not None:
        if current.type in ("export_statement", "export_declaration"):
            return True
        current = current.parent

    # Check 2: text starts with "export"
    text = node.text
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    if text.strip().startswith("export "):
        return True

    # Check 3: sibling "export default <name>" in same file
    # Handles pattern: class X {} ... export default X
    root = node
    while root.parent is not None:
        root = root.parent
    for i in range(root.child_count):
        child = root.child(i)
        if child.type == "export_statement":
            child_text = child.text
            if isinstance(child_text, bytes):
                child_text = child_text.decode("utf-8", errors="replace")
            if f"default {name}" in child_text:
                return True

    return False


def _check_java(node, name: str) -> bool:
    """Java: exported if has 'public' modifier."""
    return _has_modifier(node, "public")


def _check_csharp(node, name: str) -> bool:
    """C#: exported if has 'public' modifier."""
    return _has_modifier(node, "public")


def _check_rust(node, name: str) -> bool:
    """Rust: exported if has 'pub' visibility modifier."""
    current = node
    while current is not None:
        for child in current.children:
            if child.type == "visibility_modifier":
                text = child.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                if text.startswith("pub"):
                    return True
        if current.type in (
            "function_item",
            "struct_item",
            "enum_item",
            "trait_item",
            "impl_item",
        ):
            break
        current = current.parent
    return False


def _check_kotlin(node, name: str) -> bool:
    """Kotlin: public by default (exported unless explicitly private/internal)."""
    for child in node.children:
        if child.type == "modifiers":
            for mod in child.children:
                if mod.type == "visibility_modifier":
                    text = mod.text
                    if isinstance(text, bytes):
                        text = text.decode("utf-8")
                    if text in ("private", "internal"):
                        return False
    return True


def _check_c(node, name: str) -> bool:
    """C/C++: not exported if has 'static' linkage."""
    current = node
    while current is not None:
        for child in current.children:
            if child.type == "storage_class_specifier":
                text = child.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                if text == "static":
                    return False
        if current.type in ("function_definition", "declaration"):
            break
        current = current.parent
    return True


def _check_php(node, name: str) -> bool:
    """PHP: public by default for top-level; check visibility modifier for class members."""
    return _has_modifier(node, "public") or not _has_modifier(node, "private")


def _check_ruby(node, name: str) -> bool:
    """Ruby: all methods are public by default."""
    return True


def _check_swift(node, name: str) -> bool:
    """Swift: exported if has 'public' or 'open' modifier."""
    for child in node.children:
        if child.type == "modifiers":
            for mod in child.children:
                text = mod.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                if text in ("public", "open"):
                    return True
    return False


def _has_modifier(node, modifier: str) -> bool:
    """Check if any ancestor or sibling has the given modifier text."""
    current = node
    while current is not None:
        for child in current.children:
            if child.type in ("modifiers", "modifier"):
                text = child.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                if modifier in text:
                    return True
            if child.type == modifier:
                return True
        if current.type.endswith("_declaration") or current.type.endswith(
            "_definition"
        ):
            break
        current = current.parent
    return False


def _check_vb6(node, name: str) -> bool:
    """VB6: exported if has Public scope (or no explicit Private)."""
    text = node.text
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    first_line = text.split("\n")[0].strip().lower()
    return "private" not in first_line


def _check_fortran(node, name: str) -> bool:
    """Fortran: public by default in modules (unless PRIVATE statement)."""
    return True


def _check_scala(node, name: str) -> bool:
    """Scala: public by default (exported unless explicitly private)."""
    for child in node.children:
        if child.type == "modifiers":
            for mod in child.children:
                text = mod.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                if text.startswith("private"):
                    return False
    return True


def _check_objc(node, name: str) -> bool:
    """Objective-C: methods in @interface are public; @implementation-only = private."""
    current = node.parent
    while current is not None:
        if current.type == "class_interface":
            return True
        if current.type == "class_implementation":
            return False
        current = current.parent
    return True


def _check_solidity(node, name: str) -> bool:
    """Solidity: exported if has 'public' or 'external' visibility."""
    for child in node.children:
        if child.type == "visibility":
            text = child.text
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            if text in ("public", "external"):
                return True
            if text in ("private", "internal"):
                return False
    # State variables default to internal, functions to public
    return node.type != "state_variable_declaration"


_EXPORT_CHECKERS: dict[SupportedLanguages, callable] = {
    SupportedLanguages.VB6: _check_vb6,
    SupportedLanguages.PYTHON: _check_python,
    SupportedLanguages.JAVASCRIPT: _check_typescript,
    SupportedLanguages.TYPESCRIPT: _check_typescript,
    SupportedLanguages.JAVA: _check_java,
    SupportedLanguages.C_SHARP: _check_csharp,
    SupportedLanguages.GO: _check_go,
    SupportedLanguages.RUST: _check_rust,
    SupportedLanguages.KOTLIN: _check_kotlin,
    SupportedLanguages.C: _check_c,
    SupportedLanguages.C_PLUS_PLUS: _check_c,
    SupportedLanguages.PHP: _check_php,
    SupportedLanguages.RUBY: _check_ruby,
    SupportedLanguages.SWIFT: _check_swift,
    # ── Wave 1 ───────────────────────────────────────────────────────
    SupportedLanguages.FORTRAN: _check_fortran,
    SupportedLanguages.SCALA: _check_scala,
    SupportedLanguages.OBJECTIVE_C: _check_objc,
    SupportedLanguages.SOLIDITY: _check_solidity,
    SupportedLanguages.PERL: _check_ruby,  # Perl: all subs exported by default
    SupportedLanguages.COBOL: _check_ruby,  # COBOL: all paragraphs callable
    # ── Wave 2 ───────────────────────────────────────────────────────
    SupportedLanguages.ADA: _check_ruby,  # Ada: spec (.ads) = public by default
    SupportedLanguages.MATLAB: _check_ruby,  # MATLAB: first function = public
    SupportedLanguages.COMMON_LISP: _check_ruby,  # Lisp: defun at top-level = exported
    SupportedLanguages.DELPHI: _check_scala,  # Delphi: public by default unless private
    # ── Wave 3 ───────────────────────────────────────────────────────
    SupportedLanguages.ERLANG: _check_ruby,  # Erlang: -export controls visibility (handled at import level)
    SupportedLanguages.APEX: _check_java,  # Apex: public/global = exported
    SupportedLanguages.PASCAL: _check_ruby,  # Pascal: interface section = public
    SupportedLanguages.PROLOG: _check_ruby,  # Prolog: module exports controlled by directive
    # ── Wave 4-5: Tier 3 ─────────────────────────────────────────────
    SupportedLanguages.RPG: _check_ruby,  # RPG: EXPORT keyword (default exported)
    SupportedLanguages.ABAP: _check_ruby,  # ABAP: PUBLIC SECTION (default exported)
    SupportedLanguages.MUMPS: _check_ruby,  # MUMPS: all labels callable
    SupportedLanguages.ASSEMBLY: _check_ruby,  # Assembly: .globl controls (default exported)
    SupportedLanguages.TCL: _check_ruby,  # Tcl: namespace export (default exported)
    SupportedLanguages.ALGOL: _check_ruby,  # ALGOL: all procedures visible
    SupportedLanguages.FORTH: _check_ruby,  # Forth: all words visible
    SupportedLanguages.POSTSCRIPT: _check_ruby,  # PostScript: all defs visible
}
