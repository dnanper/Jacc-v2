"""Python type extractor.

Handles:
- PEP 484 typed assignments: x: Type = ...
- Typed parameters: def foo(x: Type)
- Constructor inference: x = Foo() where Foo starts with uppercase
"""

from __future__ import annotations

from .shared import (
    child_by_field,
    named_children,
    node_text,
)


def _extract_annotations(root_node, language) -> list:
    """Extract explicit type annotations from Python AST."""
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_annotations(root_node, results, 0)
    return results


def _walk_annotations(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "assignment":
        type_node = child_by_field(node, "type")
        if type_node:
            left = child_by_field(node, "left")
            if left:
                from . import (
                    TypeBinding,
                    extract_simple_type_name,
                )

                var_name = node_text(left)
                type_name = extract_simple_type_name(type_node)
                if var_name and type_name:
                    results.append(TypeBinding(var_name, type_name, tier=0))
                    return

    if ntype == "typed_parameter":
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

    if ntype == "typed_default_parameter":
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

    for child in named_children(node):
        _walk_annotations(child, results, depth + 1)


def _extract_constructors(root_node, language) -> list:
    """Extract constructor-inferred types from Python AST."""
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_constructors(root_node, results, 0)
    return results


def _walk_constructors(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "assignment":
        type_node = child_by_field(node, "type")
        if not type_node:
            left = child_by_field(node, "left")
            right = child_by_field(node, "right")
            if left and right and right.type == "call":
                func = child_by_field(right, "function")
                if func and func.type == "identifier":
                    func_name = node_text(func)
                    if func_name and func_name[0].isupper():
                        from . import TypeBinding

                        results.append(TypeBinding(node_text(left), func_name, tier=1))
                        return

    for child in named_children(node):
        _walk_constructors(child, results, depth + 1)


def _scan_constructor_binding(node):
    """Scan for x = Foo() patterns."""
    if node.type != "assignment":
        return None

    type_node = child_by_field(node, "type")
    if type_node:
        return None

    left = child_by_field(node, "left")
    right = child_by_field(node, "right")
    if left and right and right.type == "call":
        func = child_by_field(right, "function")
        if func and func.type == "identifier":
            callee = node_text(func)
            if callee and callee[0].isupper():
                return (node_text(left), callee)

    return None


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "assignment",
                "typed_parameter",
                "typed_default_parameter",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
        scan_constructor_binding=_scan_constructor_binding,
    )


TYPE_CONFIG = _make_config()
