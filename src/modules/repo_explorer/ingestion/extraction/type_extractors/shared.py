"""Shared type extraction utilities used by all per-language extractors.

Provides common AST traversal helpers and constructor detection.
"""

from __future__ import annotations


def node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def child_by_field(node, name):
    if hasattr(node, "child_by_field_name"):
        return node.child_by_field_name(name)
    return None


def named_children(node) -> list:
    if hasattr(node, "named_children"):
        return list(node.named_children)
    return [c for c in node.children if c.is_named]


CONSTRUCTOR_TYPES = frozenset(
    {
        "new_expression",
        "object_creation_expression",
        "constructor_invocation",
        "composite_literal",
    }
)

SKIP_TYPES = frozenset(
    {
        "arrow_function",
        "function_expression",
        "function_definition",
        "class_declaration",
        "class_definition",
        "call_expression",
    }
)


def extract_constructor_type_from_node(node, depth: int = 0) -> str | None:
    """Extract type name from a constructor expression (new Foo(), etc.)."""
    from . import extract_simple_type_name

    if depth > 5:
        return None

    if node.type in CONSTRUCTOR_TYPES:
        type_field = child_by_field(node, "type")
        if type_field:
            return extract_simple_type_name(type_field)
        ctor_field = child_by_field(node, "constructor")
        if ctor_field:
            return extract_simple_type_name(ctor_field)
        if node.named_children:
            return extract_simple_type_name(node.named_children[0])

    for child in named_children(node):
        if child.type in SKIP_TYPES:
            continue
        result = extract_constructor_type_from_node(child, depth + 1)
        if result:
            return result

    return None
