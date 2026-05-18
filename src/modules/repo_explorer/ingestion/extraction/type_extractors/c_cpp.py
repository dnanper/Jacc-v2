"""C/C++ type extractor.

Handles:
- declaration: Type* varName = ...
- init_declarator with type specifier
- parameter_declaration
"""

from __future__ import annotations

from .shared import (
    child_by_field,
    named_children,
    node_text,
)


def _extract_annotations(root_node, language) -> list:
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk(root_node, results, 0)
    return results


def _walk(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "declaration":
        type_node = child_by_field(node, "type")
        if type_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            if type_name:
                for child in named_children(node):
                    if child.type == "init_declarator":
                        decl = child_by_field(child, "declarator")
                        if decl:
                            var_name = node_text(decl).lstrip("*&").strip()
                            if var_name and not var_name.startswith("("):
                                results.append(TypeBinding(var_name, type_name, tier=0))
                    elif child.type in ("identifier", "pointer_declarator"):
                        var_name = node_text(child).lstrip("*&").strip()
                        if var_name:
                            results.append(TypeBinding(var_name, type_name, tier=0))

    if ntype == "parameter_declaration":
        type_node = child_by_field(node, "type")
        decl = child_by_field(node, "declarator")
        if type_node and decl:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            var_name = node_text(decl).lstrip("*&").strip()
            if type_name and var_name:
                results.append(TypeBinding(var_name, type_name, tier=0))

    for child in named_children(node):
        _walk(child, results, depth + 1)


def _extract_constructors(root_node, language) -> list:
    """C/C++ constructor inference (new Type())."""
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_ctors(root_node, results, 0)
    return results


def _walk_ctors(node, results: list, depth: int):
    if depth > 30:
        return

    if node.type == "declaration":
        type_node = child_by_field(node, "type")
        type_text = node_text(type_node) if type_node else ""
        if type_text in ("auto", "var"):
            from . import TypeBinding
            from .shared import (
                extract_constructor_type_from_node,
            )

            for child in named_children(node):
                if child.type == "init_declarator":
                    value = child_by_field(child, "value")
                    decl = child_by_field(child, "declarator")
                    if value and decl:
                        ctor_type = extract_constructor_type_from_node(value)
                        if ctor_type:
                            results.append(
                                TypeBinding(node_text(decl).strip(), ctor_type, tier=1)
                            )

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "declaration",
                "init_declarator",
                "parameter_declaration",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
