"""C# type extractor.

Handles:
- variable_declaration with explicit type
- parameter with type
- var keyword with constructor inference (new Foo())
"""

from __future__ import annotations

from .shared import (
    child_by_field,
    extract_constructor_type_from_node,
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

    if ntype in (
        "local_variable_declaration",
        "field_declaration",
        "variable_declaration",
    ):
        type_node = child_by_field(node, "type")
        if type_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_text = node_text(type_node)
            if type_text not in ("var", "dynamic"):
                type_name = extract_simple_type_name(type_node)
                if type_name:
                    for child in named_children(node):
                        if child.type == "variable_declarator":
                            name_node = child_by_field(child, "name") or child_by_field(
                                child, "identifier"
                            )
                            if name_node:
                                results.append(
                                    TypeBinding(node_text(name_node), type_name, tier=0)
                                )

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

    if ntype in ("local_variable_declaration",):
        type_node = child_by_field(node, "type")
        type_text = node_text(type_node) if type_node else ""
        if type_text in ("var", "dynamic"):
            for child in named_children(node):
                if child.type == "variable_declarator":
                    name_node = child_by_field(child, "name") or child_by_field(
                        child, "identifier"
                    )
                    value_node = child_by_field(child, "value")
                    if name_node and value_node:
                        ctor_type = extract_constructor_type_from_node(value_node)
                        if ctor_type:
                            from . import TypeBinding

                            results.append(
                                TypeBinding(node_text(name_node), ctor_type, tier=1)
                            )

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "local_variable_declaration",
                "field_declaration",
                "variable_declaration",
                "parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
