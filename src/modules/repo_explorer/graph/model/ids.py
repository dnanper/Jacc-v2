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
