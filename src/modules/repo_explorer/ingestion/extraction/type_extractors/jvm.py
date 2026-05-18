"""Java/Kotlin type extractor.

Handles:
- Java: Type varName = ..., local_variable_declaration, field_declaration
- Java: var keyword with constructor inference
- Kotlin: property_declaration, val/var with type annotation
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

            type_name = extract_simple_type_name(type_node)
            if type_name:
                for child in named_children(node):
                    if child.type == "variable_declarator":
                        name_node = child_by_field(child, "name")
                        if name_node:
                            results.append(
                                TypeBinding(node_text(name_node), type_name, tier=0)
                            )

    if ntype == "formal_parameter":
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

    if ntype == "property_declaration":
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

    if ntype == "simple_parameter":
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

    if ntype == "local_variable_declaration":
        type_node = child_by_field(node, "type")
        type_text = node_text(type_node) if type_node else ""
        if type_text in ("var", "final var", "val"):
            for child in named_children(node):
                if child.type == "variable_declarator":
                    name_node = child_by_field(child, "name")
                    value_node = child_by_field(child, "value")
                    if name_node and value_node:
                        ctor_type = extract_constructor_type_from_node(value_node)
                        if ctor_type:
                            from . import TypeBinding

                            results.append(
                                TypeBinding(node_text(name_node), ctor_type, tier=1)
                            )

    if ntype == "property_declaration":
        type_node = child_by_field(node, "type")
        if not type_node:
            name_node = child_by_field(node, "name")
            for child in named_children(node):
                if child.type == "call_expression":
                    func = child_by_field(child, "function") or (
                        child.named_children[0] if child.named_children else None
                    )
                    if func:
                        callee = node_text(func)
                        if callee and callee[0].isupper() and name_node:
                            from . import TypeBinding

                            results.append(
                                TypeBinding(node_text(name_node), callee, tier=1)
                            )
                            break

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
                "formal_parameter",
                "property_declaration",
                "simple_parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
