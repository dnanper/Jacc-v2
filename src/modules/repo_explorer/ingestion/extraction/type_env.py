"""Type environment -- per-file variable -> type mappings for receiver resolution.

Port of GitNexus ingestion/type-env.ts.

Three tiers of type binding:
  Tier 0: Explicit type annotations (const user: User = ...)
  Tier 1: Constructor inference (const x = new Foo())
  Tier 2: Self/this/super resolution (walk AST to enclosing class)
  Tier 3: Seeded from cross-file propagation (imported types/return types)
"""

from __future__ import annotations

from .type_extractors import (
    extract_constructor_types,
    extract_type_annotations,
)

_SELF_KEYWORDS = frozenset({"self", "this", "$this"})
_SUPER_KEYWORDS = frozenset({"super", "base", "parent"})

_CLASS_CONTAINERS = frozenset(
    {
        "class_declaration",
        "class_definition",
        "class_specifier",
        "struct_specifier",
        "impl_item",
        "object_declaration",
        "module",
    }
)

_HERITAGE_FIELDS = {
    "class_heritage": "extends_clause",
    "superclasses": None,
    "superclass": None,
    "base_list": None,
    "base_clause": None,
    "delegation_specifiers": None,
    "base_class_clause": None,
}


class TypeEnv:
    """Per-file variable -> type mapping."""

    def __init__(self):
        self.bindings: dict[str, str] = {}
        self.constructor_types: dict[str, str] = {}
        self.seeded: dict[str, str] = {}
        self.return_types: dict[str, str] = {}

    def add_explicit(self, var_name: str, type_name: str):
        """Add an explicitly typed variable."""
        if var_name and type_name:
            self.bindings[var_name] = type_name

    def add_constructor(self, var_name: str, type_name: str):
        """Add a constructor-inferred type (lower priority than explicit)."""
        if var_name and type_name and var_name not in self.bindings:
            self.constructor_types[var_name] = type_name

    def seed(self, bindings: dict[str, str]):
        """Seed with cross-file bindings (exported type names via imports).

        These have lower priority than local annotations and constructors.
        """
        for var_name, type_name in bindings.items():
            if var_name and type_name:
                self.seeded[var_name] = type_name

    def seed_return_types(self, returns: dict[str, str]):
        """Seed with imported function return types.

        Used to resolve patterns like: const result = importedFunc()
        where importedFunc's return type is known from the exporting file.
        """
        for func_name, return_type in returns.items():
            if func_name and return_type:
                self.return_types[func_name] = return_type

    def lookup(self, var_name: str, call_node=None) -> str | None:
        """Resolve a variable name to its type.

        Priority: explicit > constructor > seeded > return_type
        For self/this/super, walks the AST to find the enclosing class.
        """
        if var_name in _SELF_KEYWORDS:
            return _find_enclosing_class_name(call_node) if call_node else None
        if var_name in _SUPER_KEYWORDS:
            return _find_enclosing_parent_class_name(call_node) if call_node else None
        return (
            self.bindings.get(var_name)
            or self.constructor_types.get(var_name)
            or self.seeded.get(var_name)
            or self.return_types.get(var_name)
        )

    def clone(self) -> TypeEnv:
        """Create a copy of this TypeEnv (for cross-file enrichment)."""
        env = TypeEnv()
        env.bindings = dict(self.bindings)
        env.constructor_types = dict(self.constructor_types)
        env.seeded = dict(self.seeded)
        env.return_types = dict(self.return_types)
        return env


def build_type_env(root_node, language) -> TypeEnv:
    """Build a TypeEnv for a file by walking its AST.

    Uses the per-language type extractor dispatch table.
    """
    env = TypeEnv()

    for var_name, type_name in extract_type_annotations(root_node, language):
        env.add_explicit(var_name, type_name)

    for var_name, type_name in extract_constructor_types(root_node, language):
        env.add_constructor(var_name, type_name)

    return env


def _node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def _find_enclosing_class_name(node) -> str | None:
    """Walk up AST from node to find the enclosing class name."""
    current = node.parent if node else None
    while current:
        if current.type in _CLASS_CONTAINERS:
            name_node = None
            if hasattr(current, "child_by_field_name"):
                name_node = current.child_by_field_name("name")
            if name_node:
                return _node_text(name_node)
            for child in (
                current.named_children
                if hasattr(current, "named_children")
                else current.children
            ):
                if child.type in ("identifier", "type_identifier"):
                    return _node_text(child)
        current = current.parent
    return None


def _find_enclosing_parent_class_name(node) -> str | None:
    """Walk up to enclosing class and extract its superclass name."""
    current = node.parent if node else None
    while current:
        if current.type in _CLASS_CONTAINERS:
            for child in (
                current.named_children
                if hasattr(current, "named_children")
                else current.children
            ):
                if child.type in _HERITAGE_FIELDS:
                    return _find_first_type_in_subtree(child)
                if child.type == "superclass":
                    return _find_first_type_in_subtree(child)
                if child.type == "argument_list" and current.type == "class_definition":
                    return _find_first_type_in_subtree(child)
        current = current.parent
    return None


def _find_first_type_in_subtree(node) -> str | None:
    """Find the first type identifier in a heritage subtree."""
    if node.type in ("type_identifier", "identifier"):
        text = _node_text(node)
        if text not in ("extends", "implements", "class", "struct", "super", "base"):
            return text
    for child in (
        node.named_children if hasattr(node, "named_children") else node.children
    ):
        result = _find_first_type_in_subtree(child)
        if result:
            return result
    return None
