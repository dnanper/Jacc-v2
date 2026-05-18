"""Go type extractor.

Handles:
- var_spec with explicit type: var x Type
- short_var_declaration with composite literal: x := Type{...}
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

    if ntype in ("var_spec", "short_var_declaration"):
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

    if ntype == "parameter_declaration":
        name_node = child_by_field(node, "name")
        type_node = child_by_field(node, "type")
        if name_node and type_node:
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

    if ntype == "short_var_declaration":
        type_node = child_by_field(node, "type")
        if not type_node:
            for child in named_children(node):
                if child.type == "composite_literal":
                    type_field = child_by_field(child, "type")
                    if type_field:
                        from . import (
                            TypeBinding,
                            extract_simple_type_name,
                        )

                        type_name = extract_simple_type_name(type_field)
                        name_node = child_by_field(node, "name")
                        if type_name and name_node:
                            results.append(
                                TypeBinding(node_text(name_node), type_name, tier=1)
                            )

    for child in named_children(node):
        _walk_ctors(child, results, depth + 1)


def _make_config():
    from . import LanguageTypeConfig

    return LanguageTypeConfig(
        declaration_node_types=frozenset(
            {
                "var_spec",
                "short_var_declaration",
                "parameter_declaration",
            }
        ),
        extract_annotations=_extract_annotations,
        extract_constructors=_extract_constructors,
    )


TYPE_CONFIG = _make_config()
