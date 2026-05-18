"""Rust type extractor.

Handles:
- let x: Type = ...
- let x = Struct { ... } (constructor inference)
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

    if ntype == "let_declaration":
        name_node = child_by_field(node, "pattern")
        type_node = child_by_field(node, "type")
        if name_node and type_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            var_name = node_text(name_node)
            type_name = extract_simple_type_name(type_node)
            if var_name and type_name:
                results.append(TypeBinding(var_name, type_name, tier=0))

    if ntype == "parameter":
        name_node = child_by_field(node, "pattern")
        type_node = child_by_field(node, "type")
        if name_node and type_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            var_name = node_text(name_node)
            type_name = extract_simple_type_name(type_node)
            if var_name and type_name:
                results.append(TypeBinding(var_name, type_name, tier=0))

    for child in named_children(node):
        _walk(child, results, depth + 1)


def _extract_constructors(root_node, language) -> list:
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_ctors(root_node, results, 0)
    return results


def _walk_ctors(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "let_declaration":
        type_node = child_by_field(node, "type")
        if not type_node:
            value_node = child_by_field(node, "value")
            if value_node and value_node.type == "struct_expression":
                name_field = child_by_field(value_node, "name")
                if name_field:
                    from . import (
                        TypeBinding,
                        extract_simple_type_name,
                    )

                    struct_name = extract_simple_type_name(name_field)
                    pattern_node = child_by_field(node, "pattern")
                    if struct_name and pattern_node:
                        results.append(
                            TypeBinding(node_text(pattern_node), struct_name, tier=1)
                        )

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "let_declaration",
                "parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
