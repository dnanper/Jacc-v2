"""AST traversal utilities for tree-sitter nodes.

Ports the key extraction functions from GitNexus ingestion/utils.ts:
- Call form detection (free / member / constructor)
- Receiver name extraction
- Argument counting
- Enclosing class detection
- Function name extraction
"""

from __future__ import annotations


def generate_id(label: str, name: str) -> str:
    """Generate a deterministic node ID: ``Label:name``."""
    return f"{label}:{name}"


FUNCTION_NODE_TYPES = frozenset(
    {
        # ── Original ─────────────────────────────────────────────────────
        "function_declaration",
        "function_definition",
        "async_function_declaration",
        "arrow_function",
        "function_expression",
        "method_definition",
        "method_declaration",
        "constructor_declaration",
        "local_function_statement",
        "function_item",
        "impl_item",
        "anonymous_function",
        "lambda_literal",
        "init_declaration",
        "deinit_declaration",
        "method",
        "singleton_method",
        "sub_declaration",
        # ── New languages ────────────────────────────────────────────────
        "subroutine",  # Fortran
        "subprogram_body",  # Ada
        "subprogram_declaration",  # Ada
        "procedure_declaration",  # Pascal, Delphi
        "function_clause",  # Erlang
        "clause",  # Prolog
        "defun",  # Common Lisp
        "defmacro",  # Common Lisp
        "defmethod",  # Common Lisp
        "defgeneric",  # Common Lisp
        "subroutine_declaration",  # Perl
        "paragraph",  # COBOL
        "trigger_declaration",  # Apex
        "modifier_definition",  # Solidity
        "event_definition",  # Solidity
        "proc_definition",  # Tcl
        "dcl_proc",  # RPG
        "begsr",  # RPG
        "form_definition",  # ABAP
        "word_definition",  # Forth
        "procedure_def",  # PostScript
    }
)

CONSTRUCTOR_CALL_NODE_TYPES = frozenset(
    {
        "new_expression",
        "object_creation_expression",
        "constructor_invocation",
        "implicit_object_creation_expression",
        "composite_literal",
        "struct_expression",
    }
)

MEMBER_ACCESS_NODE_TYPES = frozenset(
    {
        "member_expression",
        "attribute",
        "member_access_expression",
        "field_expression",
        "selector_expression",
        "navigation_suffix",
        "member_binding_expression",
    }
)

CALL_EXPRESSION_TYPES = frozenset(
    {
        "call_expression",
        "call",
        "method_invocation",
        "function_call_expression",
        "member_call_expression",
        "scoped_call_expression",
        "object_creation_expression",
        "new_expression",
        "constructor_invocation",
        "nullsafe_member_call_expression",
    }
)

CALL_ARGUMENT_LIST_TYPES = frozenset(
    {
        "arguments",
        "argument_list",
        "value_arguments",
    }
)

SIMPLE_RECEIVER_TYPES = frozenset(
    {
        "identifier",
        "simple_identifier",
        "variable_name",
        "name",
        "this",
        "self",
        "super",
        "base",
        "parent",
        "constant",
        "super_expression",
        "me",
    }
)

CLASS_LIKE_NODE_TYPES = frozenset(
    {
        "class_declaration",
        "class_definition",
        "class_specifier",
        "struct_specifier",
        "interface_declaration",
        "impl_item",
        "type_declaration",
        "method_declaration",
    }
)


def infer_call_form(call_node, name_node) -> str:
    """Determine if a call is 'free', 'member', or 'constructor'.

    Args:
        call_node: The call_expression (or equivalent) AST node.
        name_node: The captured @call.name node.

    Returns:
        One of 'free', 'member', 'constructor'.
    """
    if call_node.type in CONSTRUCTOR_CALL_NODE_TYPES:
        return "constructor"

    if name_node.parent and name_node.parent.type in MEMBER_ACCESS_NODE_TYPES:
        return "member"

    if call_node.type == "scoped_call_expression":
        return "member"

    if call_node.type == "method_invocation" and call_node.child_by_field_name(
        "object"
    ):
        return "member"

    if call_node.type == "call" and call_node.child_by_field_name("receiver"):
        return "member"

    return "free"


def extract_receiver_name(name_node) -> str | None:
    """Extract the receiver name from a member call (e.g., 'user' in user.save()).

    Args:
        name_node: The @call.name AST node.

    Returns:
        Receiver name string, or None if not a member call.
    """
    parent = name_node.parent
    if parent is None:
        return None

    for field_name in (
        "object",
        "value",
        "operand",
        "expression",
        "argument",
        "receiver",
    ):
        receiver = parent.child_by_field_name(field_name)
        if receiver is not None:
            break
    else:
        return None

    if receiver.type in SIMPLE_RECEIVER_TYPES:
        return (
            receiver.text.decode("utf-8")
            if isinstance(receiver.text, bytes)
            else receiver.text
        )

    return None


def count_call_arguments(call_node) -> int:
    """Count the number of arguments in a call expression."""
    args_node = call_node.child_by_field_name("arguments")

    if args_node is None:
        for child in call_node.children:
            if child.type in CALL_ARGUMENT_LIST_TYPES:
                args_node = child
                break

    if args_node is None:
        for child in call_node.children:
            for grandchild in child.children:
                if grandchild.type in CALL_ARGUMENT_LIST_TYPES:
                    args_node = grandchild
                    break
            if args_node is not None:
                break

    if args_node is None:
        return 0

    count = 0
    for child in args_node.children:
        if child.is_named and child.type != "comment":
            count += 1
    return count


def find_enclosing_class_id(node, file_path: str) -> str | None:
    """Walk up the AST to find the enclosing class/struct/interface.

    Returns the generated node ID for the enclosing class, or None.
    """
    current = node.parent
    while current is not None:
        if current.type in CLASS_LIKE_NODE_TYPES:
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(name_node)
                label = _label_from_class_node(current)
                return generate_id(label, f"{file_path}:{name}")

        if current.type == "method_declaration":
            receiver = current.child_by_field_name("receiver")
            if receiver is not None:
                type_node = _find_type_identifier(receiver)
                if type_node is not None:
                    name = _node_text(type_node)
                    return generate_id("Struct", f"{file_path}:{name}")

        current = current.parent
    return None


def extract_function_name(node) -> tuple[str, str]:
    """Extract function name and determine label (Function/Method/Constructor).

    Args:
        node: A function/method definition AST node.

    Returns:
        Tuple of (function_name, node_label).
    """
    name_node = node.child_by_field_name("name")

    if name_node is None:
        declarator = node.child_by_field_name("declarator")
        if declarator is not None:
            name_node = _unwrap_declarator(declarator)

    if name_node is None:
        return ("anonymous", "Function")

    name = _node_text(name_node)

    if node.type in ("constructor_declaration", "init_declaration"):
        return (name, "Constructor")

    if node.type in (
        "method_definition",
        "method_declaration",
        "method",
        "singleton_method",
    ):
        return (name, "Method")

    if node.type == "function_definition" and _has_enclosing_class(node):
        return (name, "Method")

    return (name, "Function")


def _has_enclosing_class(node) -> bool:
    """Return True if a function-like node is nested inside a class-like node."""
    current = node.parent
    while current is not None:
        if current.type in CLASS_LIKE_NODE_TYPES:
            return True
        current = current.parent
    return False


def _node_text(node) -> str:
    """Get text from a tree-sitter node."""
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def _label_from_class_node(node) -> str:
    """Determine the NodeLabel from a class-like AST node type."""
    type_map = {
        "class_declaration": "Class",
        "class_definition": "Class",
        "class_specifier": "Class",
        "struct_specifier": "Struct",
        "interface_declaration": "Interface",
        "impl_item": "Impl",
        "type_declaration": "Struct",
    }
    return type_map.get(node.type, "Class")


def _unwrap_declarator(declarator):
    """Unwrap C/C++ declarators (pointer_declarator → function_declarator → identifier)."""
    current = declarator
    while current is not None:
        if current.type == "identifier":
            return current
        name = current.child_by_field_name("declarator")
        if name is not None:
            current = name
        else:
            for child in current.children:
                if child.type == "identifier":
                    return child
            break
    return None


def _find_type_identifier(node):
    """Find a type_identifier node in a Go receiver parameter list."""
    if node.type == "type_identifier":
        return node
    for child in node.children:
        result = _find_type_identifier(child)
        if result is not None:
            return result
    return None
