"""Named binding extraction — extract {local, exported} pairs from import AST nodes.

Port of GitNexus ingestion/named-binding-extraction.ts.

Each language has a function that receives the full import AST node and
returns a list of NamedBinding dicts. These are NOT tree-sitter queries —
they use hand-written AST traversal on the already-captured import node.

Languages with bindings: TS/JS, Python, Java, Kotlin, C#, Rust, PHP
Languages without (whole-module imports): C, C++, Go, Ruby, Swift
"""

from __future__ import annotations

from typing import TypedDict

from ...config import SupportedLanguages


class NamedBinding(TypedDict):
    local: str
    exported: str


def _node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def _named_children(node) -> list:
    """Get named children of a node (works across tree-sitter versions)."""
    if hasattr(node, "named_children"):
        return list(node.named_children)
    return [c for c in node.children if c.is_named]


def _child_by_field(node, field_name):
    """Get child by field name, returns None if not found."""
    if hasattr(node, "child_by_field_name"):
        return node.child_by_field_name(field_name)
    return None


def extract_ts_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from TS/JS import/export statements.

    Patterns:
      import { User } from './models'           → [{local: User, exported: User}]
      import { Foo as Bar } from './models'      → [{local: Bar, exported: Foo}]
      export { Repo as Repository } from './db'  → [{local: Repository, exported: Repo}]
    """
    bindings: list[NamedBinding] = []

    for child in _named_children(import_node):
        if child.type == "import_clause":
            _walk_ts_clause(child, bindings)
        elif child.type == "export_clause":
            _walk_ts_clause(child, bindings)
        elif child.type == "named_imports":
            _walk_ts_clause(child, bindings)

    return bindings


def _walk_ts_clause(node, bindings: list[NamedBinding]):
    """Walk import_clause/export_clause/named_imports to find specifiers."""
    for child in _named_children(node):
        if child.type in ("import_specifier", "export_specifier"):
            idents = [
                _node_text(c) for c in _named_children(child) if c.type == "identifier"
            ]
            if len(idents) == 1:
                bindings.append({"local": idents[0], "exported": idents[0]})
            elif len(idents) >= 2:
                bindings.append({"local": idents[1], "exported": idents[0]})
        elif child.type in ("named_imports", "import_clause"):
            _walk_ts_clause(child, bindings)


def extract_python_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from Python import_from_statement.

    Patterns:
      from x import User                → [{local: User, exported: User}]
      from x import Repo as R           → [{local: R, exported: Repo}]
      from x import User, Repo as R     → [{...}, {...}]
    """
    bindings: list[NamedBinding] = []

    if import_node.type != "import_from_statement":
        return bindings

    module_name_node = _child_by_field(import_node, "module_name")

    for child in _named_children(import_node):
        if child == module_name_node:
            continue

        if child.type == "dotted_name":
            name = _node_text(child)
            bindings.append({"local": name, "exported": name})
        elif child.type == "aliased_import":
            parts = _named_children(child)
            if len(parts) >= 2:
                exported = _node_text(parts[0])
                local = _node_text(parts[1])
                bindings.append({"local": local, "exported": exported})
            elif len(parts) == 1:
                name = _node_text(parts[0])
                bindings.append({"local": name, "exported": name})

    return bindings


def extract_java_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from Java import_declaration.

    Pattern: import com.example.models.User; → [{local: User, exported: User}]
    No aliases in Java.
    """
    bindings: list[NamedBinding] = []

    for child in _named_children(import_node):
        if child.type == "scoped_identifier":
            full_text = _node_text(child)
            parts = full_text.rsplit(".", 1)
            name = parts[-1] if parts else full_text
            if name == "*" or (name and name[0].islower()):
                continue
            bindings.append({"local": name, "exported": name})

    return bindings


def extract_kotlin_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from Kotlin import.

    Patterns:
      import com.example.User          → [{local: User, exported: User}]
      import com.example.User as U     → [{local: U, exported: User}]
    """
    bindings: list[NamedBinding] = []

    qualified = None
    alias = None

    for child in _named_children(import_node):
        if child.type == "qualified_identifier":
            qualified = _node_text(child)
        elif child.type == "import_alias":
            alias_children = _named_children(child)
            if alias_children:
                alias = _node_text(alias_children[0])

    if qualified:
        parts = qualified.rsplit(".", 1)
        exported = parts[-1] if parts else qualified
        if exported == "*" or (exported and exported[0].islower()):
            return bindings
        local = alias if alias else exported
        bindings.append({"local": local, "exported": exported})

    return bindings


def extract_csharp_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from C# using_directive.

    Patterns:
      using Alias = NS.Type;   → [{local: Alias, exported: Type}]
      using static NS.Type;    → [{local: Type, exported: Type}]
      using NS;                → [] (namespace import, no per-symbol binding)
    """
    bindings: list[NamedBinding] = []

    alias_ident = None
    qualified = None

    for child in _named_children(import_node):
        if child.type == "identifier" and qualified is None:
            alias_ident = _node_text(child)
        elif child.type == "qualified_name":
            qualified = _node_text(child)

    if qualified:
        parts = qualified.rsplit(".", 1)
        exported = parts[-1] if parts else qualified
        if alias_ident:
            bindings.append({"local": alias_ident, "exported": exported})
        elif exported and exported[0].isupper():
            bindings.append({"local": exported, "exported": exported})

    return bindings


def extract_rust_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from Rust use_declaration.

    Patterns:
      use crate::models::User;                    → [{local: User, exported: User}]
      use crate::models::User as U;               → [{local: U, exported: User}]
      use crate::models::{User, Repo};             → [{...}, {...}]
      use crate::models::{User, Repo as R};        → [{...}, {...}]
    """
    bindings: list[NamedBinding] = []
    _walk_rust_use(import_node, bindings)
    return bindings


def _walk_rust_use(node, bindings: list[NamedBinding]):
    """Recursively walk Rust use_declaration tree."""
    for child in _named_children(node):
        if child.type == "use_as_clause":
            idents = []
            for c in _named_children(child):
                if c.type == "identifier":
                    idents.append(_node_text(c))
                elif c.type == "scoped_identifier":
                    name_child = _child_by_field(c, "name")
                    if name_child:
                        idents.append(_node_text(name_child))
            if len(idents) >= 2:
                bindings.append({"local": idents[1], "exported": idents[0]})
            elif len(idents) == 1:
                bindings.append({"local": idents[0], "exported": idents[0]})

        elif child.type == "use_list":
            _walk_rust_use(child, bindings)

        elif child.type == "scoped_use_list":
            _walk_rust_use(child, bindings)

        elif child.type == "identifier" and node.type in (
            "use_list",
            "scoped_use_list",
        ):
            name = _node_text(child)
            bindings.append({"local": name, "exported": name})

        elif child.type == "scoped_identifier" and node.type in (
            "use_declaration",
            "use_list",
            "scoped_use_list",
        ):
            name_child = _child_by_field(child, "name")
            if name_child:
                name = _node_text(name_child)
                bindings.append({"local": name, "exported": name})


def extract_php_named_bindings(import_node) -> list[NamedBinding]:
    """Extract named bindings from PHP namespace_use_declaration.

    Patterns:
      use App\\Models\\User;                   → [{local: User, exported: User}]
      use App\\Models\\Repo as R;              → [{local: R, exported: Repo}]
      use App\\Models\\{User, Repo as R};       → [{...}, {...}]
    """
    bindings: list[NamedBinding] = []

    for child in _named_children(import_node):
        if child.type == "namespace_use_clause":
            _extract_php_clause(child, bindings)
        elif child.type == "namespace_use_group":
            for gc in _named_children(child):
                if gc.type == "namespace_use_clause":
                    _extract_php_clause(gc, bindings)

    return bindings


def _extract_php_clause(clause, bindings: list[NamedBinding]):
    """Extract binding from a single namespace_use_clause."""
    qualified = None
    alias = None

    for child in _named_children(clause):
        if child.type == "qualified_name":
            qualified = _node_text(child)
        elif child.type == "name":
            if qualified is None:
                qualified = _node_text(child)
            else:
                alias = _node_text(child)

    if qualified:
        parts = qualified.rsplit("\\", 1)
        exported = parts[-1] if parts else qualified
        local = alias if alias else exported
        bindings.append({"local": local, "exported": exported})


NAMED_BINDING_EXTRACTORS: dict[SupportedLanguages, callable] = {
    SupportedLanguages.JAVASCRIPT: extract_ts_named_bindings,
    SupportedLanguages.TYPESCRIPT: extract_ts_named_bindings,
    SupportedLanguages.PYTHON: extract_python_named_bindings,
    SupportedLanguages.JAVA: extract_java_named_bindings,
    SupportedLanguages.KOTLIN: extract_kotlin_named_bindings,
    SupportedLanguages.C_SHARP: extract_csharp_named_bindings,
    SupportedLanguages.RUST: extract_rust_named_bindings,
    SupportedLanguages.PHP: extract_php_named_bindings,
}
