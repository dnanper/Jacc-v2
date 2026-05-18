"""Per-language type extractors with dispatch table.

Each language defines a LanguageTypeConfig with extraction callbacks.
The dispatch table TYPE_CONFIGS maps languages to their configs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ....config import SupportedLanguages


@dataclass
class TypeBinding:
    """A variable-to-type binding extracted from AST."""

    var_name: str
    type_name: str
    tier: int = 0


TypeAnnotationExtractor = Callable
ConstructorExtractor = Callable
ConstructorBindingScanner = Callable


@dataclass
class LanguageTypeConfig:
    """Per-language type extraction configuration."""

    declaration_node_types: frozenset[str] = field(default_factory=frozenset)
    extract_annotations: TypeAnnotationExtractor | None = None
    extract_constructors: ConstructorExtractor | None = None
    scan_constructor_binding: ConstructorBindingScanner | None = None


def _node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def _child_by_field(node, name):
    if hasattr(node, "child_by_field_name"):
        return node.child_by_field_name(name)
    return None


def _named_children(node) -> list:
    if hasattr(node, "named_children"):
        return list(node.named_children)
    return [c for c in node.children if c.is_named]


NULLABLE_WRAPPERS = frozenset(
    {
        "Optional",
        "Option",
        "Maybe",
        "Nullable",
    }
)


def extract_simple_type_name(type_node) -> str | None:
    """Extract a simple type name from a type annotation node.

    Handles: type_identifier, generic_type (unwrap), nullable_type,
    union_type (strip null/undefined), scoped/qualified identifiers.
    """
    if type_node is None:
        return None

    ntype = type_node.type

    if ntype in ("type_identifier", "identifier", "simple_identifier", "constant"):
        return _node_text(type_node)

    if ntype == "generic_type":
        base = _child_by_field(type_node, "name") or _child_by_field(type_node, "type")
        if base:
            base_name = extract_simple_type_name(base)
            if base_name and base_name in NULLABLE_WRAPPERS:
                args = _child_by_field(type_node, "type_arguments")
                if args:
                    for c in _named_children(args):
                        inner = extract_simple_type_name(c)
                        if inner:
                            return inner
            return base_name

    if ntype == "nullable_type":
        inner = type_node.named_children[0] if type_node.named_children else None
        return extract_simple_type_name(inner)

    if ntype == "union_type":
        for child in _named_children(type_node):
            text = _node_text(child)
            if text not in ("null", "undefined", "void", "None"):
                return extract_simple_type_name(child)

    if ntype in ("scoped_identifier", "qualified_identifier", "scoped_type_identifier"):
        last = type_node.named_children[-1] if type_node.named_children else None
        if last:
            return _node_text(last)

    if ntype == "predefined_type":
        return None

    if type_node.named_children:
        return extract_simple_type_name(type_node.named_children[0])

    return None


from .c_cpp import TYPE_CONFIG as _c_config
from .csharp import TYPE_CONFIG as _cs_config
from .go import TYPE_CONFIG as _go_config
from .jvm import TYPE_CONFIG as _jvm_config
from .php import TYPE_CONFIG as _php_config
from .python_ext import TYPE_CONFIG as _py_config
from .ruby import TYPE_CONFIG as _ruby_config
from .rust import TYPE_CONFIG as _rust_config
from .swift import TYPE_CONFIG as _swift_config
from .typescript import TYPE_CONFIG as _ts_config

TYPE_CONFIGS: dict[SupportedLanguages, LanguageTypeConfig] = {
    SupportedLanguages.JAVASCRIPT: _ts_config,
    SupportedLanguages.TYPESCRIPT: _ts_config,
    SupportedLanguages.PYTHON: _py_config,
    SupportedLanguages.GO: _go_config,
    SupportedLanguages.JAVA: _jvm_config,
    SupportedLanguages.KOTLIN: _jvm_config,
    SupportedLanguages.RUST: _rust_config,
    SupportedLanguages.C: _c_config,
    SupportedLanguages.C_PLUS_PLUS: _c_config,
    SupportedLanguages.C_SHARP: _cs_config,
    SupportedLanguages.PHP: _php_config,
    SupportedLanguages.RUBY: _ruby_config,
    SupportedLanguages.SWIFT: _swift_config,
}


def extract_type_annotations(root_node, language) -> list[tuple[str, str]]:
    """Extract (var_name, type_name) pairs from explicit type annotations."""
    config = TYPE_CONFIGS.get(language)
    if config and config.extract_annotations:
        bindings = config.extract_annotations(root_node, language)
        return [(b.var_name, b.type_name) for b in bindings]
    return []


def extract_constructor_types(root_node, language) -> list[tuple[str, str]]:
    """Extract (var_name, type_name) from constructor initializers."""
    config = TYPE_CONFIGS.get(language)
    if config and config.extract_constructors:
        bindings = config.extract_constructors(root_node, language)
        return [(b.var_name, b.type_name) for b in bindings]
    return []
