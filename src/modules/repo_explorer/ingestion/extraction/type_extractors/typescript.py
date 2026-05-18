"""TypeScript/JavaScript type extractor.

Handles:
- Explicit type annotations on variables and parameters
- Constructor inference (new Foo(), Foo())
- Untyped constructor binding scanning for return-type inference
"""

from __future__ import annotations

from .shared import (
    child_by_field,
    extract_constructor_type_from_node,
    named_children,
    node_text,
)


def _extract_annotations(root_node, language) -> list:
    """Extract explicit type annotations from TS/JS AST."""
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_annotations(root_node, results, 0)
    return results


def _walk_annotations(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "variable_declarator":
        name_node = child_by_field(node, "name")
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
                return

    if ntype in ("required_parameter", "optional_parameter", "formal_parameter"):
        name_node = child_by_field(node, "name") or child_by_field(node, "pattern")
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
                return

    for child in named_children(node):
        _walk_annotations(child, results, depth + 1)


def _extract_constructors(root_node, language) -> list:
    """Extract constructor-inferred types from TS/JS AST."""
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_constructors(root_node, results, 0)
    return results


def _walk_constructors(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "variable_declarator":
        name_node = child_by_field(node, "name")
        value_node = child_by_field(node, "value")
        type_node = child_by_field(node, "type")
        if name_node and value_node and not type_node:
            ctor_type = extract_constructor_type_from_node(value_node)
            if ctor_type:
                from . import TypeBinding

                results.append(TypeBinding(node_text(name_node), ctor_type, tier=1))
                return

    for child in named_children(node):
        _walk_constructors(child, results, depth + 1)


def _scan_constructor_binding(node):
    """Scan for untyped var = Callee() patterns for return-type inference.

    Returns (var_name, callee_name) or None.
    """
    if node.type != "variable_declarator":
        return None

    name_node = child_by_field(node, "name")
    value_node = child_by_field(node, "value")
    type_node = child_by_field(node, "type")

    if not name_node or not value_node or type_node:
        return None

    if value_node.type == "call_expression":
        func = child_by_field(value_node, "function")
        if func and func.type == "identifier":
            callee = node_text(func)
            if callee and callee[0].isupper():
                return (node_text(name_node), callee)

    return None


TYPE_CONFIG = None


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "variable_declarator",
                "lexical_declaration",
                "required_parameter",
                "optional_parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
        scan_constructor_binding=_scan_constructor_binding,
    )


TYPE_CONFIG = _make_config()
