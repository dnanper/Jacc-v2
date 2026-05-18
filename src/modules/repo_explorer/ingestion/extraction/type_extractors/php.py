"""PHP type extractor.

Handles:
- Typed properties: public Type $var
- Parameter type hints: function foo(Type $param)
- Constructor inference: $x = new Foo()
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

    if ntype == "property_declaration":
        type_node = child_by_field(node, "type")
        if type_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            if type_name:
                for child in named_children(node):
                    if child.type == "property_element":
                        var_node = child_by_field(child, "name")
                        if var_node:
                            var_name = node_text(var_node).lstrip("$")
                            results.append(TypeBinding(var_name, type_name, tier=0))

    if ntype == "simple_parameter":
        type_node = child_by_field(node, "type")
        name_node = child_by_field(node, "name")
        if type_node and name_node:
            from . import (
                TypeBinding,
                extract_simple_type_name,
            )

            type_name = extract_simple_type_name(type_node)
            var_name = node_text(name_node).lstrip("$")
            if type_name and var_name:
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

    if ntype == "assignment_expression":
        left = child_by_field(node, "left")
        right = child_by_field(node, "right")
        if left and right and right.type == "object_creation_expression":
            type_node = child_by_field(right, "type") or child_by_field(right, "class")
            if type_node:
                from . import (
                    TypeBinding,
                    extract_simple_type_name,
                )

                type_name = extract_simple_type_name(type_node)
                var_name = node_text(left).lstrip("$")
                if type_name and var_name:
                    results.append(TypeBinding(var_name, type_name, tier=1))

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "property_declaration",
                "simple_parameter",
                "assignment_expression",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
