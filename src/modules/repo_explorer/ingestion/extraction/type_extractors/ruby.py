"""Ruby type extractor.

Ruby is dynamically typed so extraction is limited to:
- Constructor inference: x = Foo.new (uppercase callee)
"""

from __future__ import annotations

from .shared import (
    child_by_field,
    named_children,
    node_text,
)


def _extract_annotations(root_node, language) -> list:
    """Ruby has no static type annotations (YARD/Sorbet not parsed)."""
    return []


def _extract_constructors(root_node, language) -> list:
    from . import TypeBinding

    results: list[TypeBinding] = []
    _walk_ctors(root_node, results, 0)
    return results


def _walk_ctors(node, results: list, depth: int):
    if depth > 30:
        return

    ntype = node.type

    if ntype == "assignment":
        left = child_by_field(node, "left")
        right = child_by_field(node, "right")
        if left and right and right.type == "call":
            method = child_by_field(right, "method")
            receiver = child_by_field(right, "receiver")
            if method and receiver:
                method_name = node_text(method)
                if method_name == "new":
                    class_name = node_text(receiver)
                    if class_name and class_name[0].isupper():
                        from . import TypeBinding

                        results.append(TypeBinding(node_text(left), class_name, tier=1))

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset({"assignment"}),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
