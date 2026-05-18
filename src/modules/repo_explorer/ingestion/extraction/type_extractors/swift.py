"""Swift type extractor.

Handles:
- let/var with type annotation: let x: Type = ...
- Parameter type annotations
- Constructor inference: let x = Type(...)
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

    if ntype in ("property_declaration", "constant_declaration"):
        type_node = child_by_field(node, "type")
        name_node = child_by_field(node, "name") or child_by_field(node, "pattern")
        if type_node and name_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            if type_name:
                results.append(TypeBinding(node_text(name_node), type_name, tier=0))

    if ntype == "parameter":
        type_node = child_by_field(node, "type")
        name_node = child_by_field(node, "name")
        if type_node and name_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            if type_name:
                results.append(TypeBinding(node_text(name_node), type_name, tier=0))

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

    if ntype in ("property_declaration", "constant_declaration"):
        type_node = child_by_field(node, "type")
        if not type_node:
            name_node = child_by_field(node, "name") or child_by_field(node, "pattern")
            value_node = child_by_field(node, "value")
            if name_node and value_node and value_node.type == "call_expression":
                func = child_by_field(value_node, "function")
                if func:
                    callee = node_text(func)
                    if callee and callee[0].isupper():
                        from . import TypeBinding

                        results.append(
                            TypeBinding(node_text(name_node), callee, tier=1)
                        )

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "property_declaration",
                "constant_declaration",
                "parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
