"""Tree-sitter S-expression query strings per language.

These queries extract definitions, imports, calls, heritage, and
assignments from ASTs. They are the same S-expression format as
the TypeScript version — tree-sitter queries are language-agnostic.

Each language has a DEFINITIONS query (classes, functions, methods)
and a CALLS query (function/method invocations). Import and heritage
queries are included where the language has distinct syntax for them.
"""

from __future__ import annotations

from ..config import SupportedLanguages


PYTHON_DEFINITIONS = """
(class_definition
  name: (identifier) @name) @definition.class

(function_definition
  name: (identifier) @name) @definition.function

(module
  (expression_statement
    (assignment
      left: (identifier) @name)) @definition.property)
"""

PYTHON_IMPORTS = """
(import_statement
  name: (dotted_name) @import.source) @import

(import_from_statement
  module_name: (dotted_name) @import.source) @import

(import_from_statement
  module_name: (relative_import) @import.source) @import
"""

PYTHON_CALLS = """
(call
  function: (identifier) @call.name) @call

(call
  function: (attribute
    attribute: (identifier) @call.name)) @call
"""

PYTHON_HERITAGE = """
(class_definition
  name: (identifier) @heritage.class
  superclasses: (argument_list
    (identifier) @heritage.extends)) @heritage
"""

PYTHON_ASSIGNMENTS = """
(assignment
  left: (attribute
    object: (_) @assignment.receiver
    attribute: (identifier) @assignment.property)
  right: (_)) @assignment
"""


JAVASCRIPT_DEFINITIONS = """
(class_declaration
  name: (_) @name) @definition.class

(function_declaration
  name: (identifier) @name) @definition.function

(method_definition
  name: (property_identifier) @name) @definition.method

(lexical_declaration
  (variable_declarator
    name: (identifier) @name
    value: [(arrow_function) (function_expression)])) @definition.function

(export_statement
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name))) @definition.property

(field_definition
  property: (property_identifier) @name) @definition.property
"""

JAVASCRIPT_HERITAGE = """
(class_declaration
  name: (_) @heritage.class
  (class_heritage
    (identifier) @heritage.extends)) @heritage
"""


TYPESCRIPT_DEFINITIONS = """
(class_declaration
  name: (_) @name) @definition.class

(function_declaration
  name: (identifier) @name) @definition.function

(method_definition
  name: (property_identifier) @name) @definition.method

(lexical_declaration
  (variable_declarator
    name: (identifier) @name
    value: [(arrow_function) (function_expression)])) @definition.function

(export_statement
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name))) @definition.property

(public_field_definition
  name: [(property_identifier) (private_property_identifier)] @name) @definition.property

(interface_declaration
  name: (type_identifier) @name) @definition.interface

(type_alias_declaration
  name: (type_identifier) @name) @definition.type_alias
"""

TYPESCRIPT_IMPORTS = """
(import_statement
  source: (string) @import.source) @import

(export_statement
  source: (string) @import.source) @import
"""

TYPESCRIPT_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (member_expression
    property: (property_identifier) @call.name)) @call

(new_expression
  constructor: (identifier) @call.name) @call
"""

TYPESCRIPT_HERITAGE = """
(class_declaration
  name: (_) @heritage.class
  (class_heritage
    (extends_clause
      value: (identifier) @heritage.extends))) @heritage

(class_declaration
  name: (_) @heritage.class
  (class_heritage
    (implements_clause
      (type_identifier) @heritage.implements))) @heritage.impl
"""

TYPESCRIPT_ASSIGNMENTS = """
(assignment_expression
  left: (member_expression
    object: (_) @assignment.receiver
    property: (property_identifier) @assignment.property)
  right: (_)) @assignment
"""


JAVA_DEFINITIONS = """
(class_declaration
  name: (identifier) @name) @definition.class

(interface_declaration
  name: (identifier) @name) @definition.interface

(method_declaration
  name: (identifier) @name) @definition.method

(constructor_declaration
  name: (identifier) @name) @definition.constructor
"""

JAVA_IMPORTS = """
(import_declaration
  (_) @import.source) @import
"""

JAVA_CALLS = """
(method_invocation
  name: (identifier) @call.name) @call

(object_creation_expression
  type: (type_identifier) @call.name) @call
"""

JAVA_ASSIGNMENTS = """
(assignment_expression
  left: (field_access
    object: (_) @assignment.receiver
    field: (identifier) @assignment.property)
  right: (_)) @assignment
"""

JAVA_HERITAGE = """
(class_declaration
  name: (identifier) @heritage.class
  (superclass
    (type_identifier) @heritage.extends)) @heritage

(class_declaration
  name: (identifier) @heritage.class
  (super_interfaces
    (type_list
      (type_identifier) @heritage.implements))) @heritage.impl
"""


GO_DEFINITIONS = """
(function_declaration
  name: (identifier) @name) @definition.function

(method_declaration
  name: (field_identifier) @name) @definition.method

(type_declaration
  (type_spec
    name: (type_identifier) @name
    type: (struct_type))) @definition.struct

(type_declaration
  (type_spec
    name: (type_identifier) @name
    type: (interface_type))) @definition.interface
"""

GO_IMPORTS = """
(import_declaration
  (import_spec
    path: (interpreted_string_literal) @import.source)) @import

(import_declaration
  (import_spec_list
    (import_spec
      path: (interpreted_string_literal) @import.source))) @import
"""

GO_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (selector_expression
    field: (field_identifier) @call.name)) @call

(composite_literal
  type: (type_identifier) @call.name) @call
"""

GO_HERITAGE = """
(type_declaration
  (type_spec
    name: (type_identifier) @heritage.class
    type: (struct_type
      (field_declaration_list
        (field_declaration
          type: (type_identifier) @heritage.extends))))) @heritage
"""

GO_ASSIGNMENTS = """
(assignment_statement
  left: (expression_list
    (selector_expression
      operand: (_) @assignment.receiver
      field: (field_identifier) @assignment.property))
  right: (_)) @assignment
"""


C_DEFINITIONS = """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name)) @definition.function

(function_definition
  declarator: (pointer_declarator
    declarator: (function_declarator
      declarator: (identifier) @name))) @definition.function

(struct_specifier
  name: (type_identifier) @name) @definition.struct

(enum_specifier
  name: (type_identifier) @name) @definition.enum

(type_definition
  declarator: (type_identifier) @name) @definition.type
"""

C_IMPORTS = """
(preproc_include
  path: [(string_literal) (system_lib_string)] @import.source) @import
"""

C_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (field_expression
    field: (field_identifier) @call.name)) @call
"""

C_ASSIGNMENTS = """
(assignment_expression
  left: (field_expression
    argument: (_) @assignment.receiver
    field: (field_identifier) @assignment.property)
  right: (_)) @assignment
"""


CPP_DEFINITIONS = """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name)) @definition.function

(function_definition
  declarator: (pointer_declarator
    declarator: (function_declarator
      declarator: (identifier) @name))) @definition.function

(class_specifier
  name: (type_identifier) @name) @definition.class

(struct_specifier
  name: (type_identifier) @name) @definition.struct

(field_declaration
  declarator: (field_identifier) @name) @definition.property
"""

CPP_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (field_expression
    field: (field_identifier) @call.name)) @call

(call_expression
  function: (qualified_identifier
    name: (identifier) @call.name)) @call
"""

CPP_IMPORTS = """
(preproc_include
  path: [(string_literal) (system_lib_string)] @import.source) @import
"""

CPP_HERITAGE = """
(class_specifier
  name: (type_identifier) @heritage.class
  (base_class_clause
    (type_identifier) @heritage.extends)) @heritage

(struct_specifier
  name: (type_identifier) @heritage.class
  (base_class_clause
    (type_identifier) @heritage.extends)) @heritage
"""

CPP_ASSIGNMENTS = """
(assignment_expression
  left: (field_expression
    argument: (_) @assignment.receiver
    field: (field_identifier) @assignment.name)
  right: (_)) @assignment
"""


CSHARP_DEFINITIONS = """
(class_declaration
  name: (identifier) @name) @definition.class

(interface_declaration
  name: (identifier) @name) @definition.interface

(method_declaration
  name: (identifier) @name) @definition.method

(constructor_declaration
  name: (identifier) @name) @definition.constructor
"""

CSHARP_IMPORTS = """
(using_directive
  (qualified_name) @import.source) @import

(using_directive
  (identifier) @import.source) @import
"""

CSHARP_CALLS = """
(invocation_expression
  function: (identifier) @call.name) @call

(invocation_expression
  function: (member_access_expression
    name: (identifier) @call.name)) @call

(object_creation_expression
  type: (identifier) @call.name) @call
"""

CSHARP_ASSIGNMENTS = """
(assignment_expression
  left: (member_access_expression
    expression: (_) @assignment.receiver
    name: (identifier) @assignment.property)
  right: (_)) @assignment
"""

CSHARP_HERITAGE = """
(class_declaration
  name: (identifier) @heritage.class
  (base_list
    (identifier) @heritage.extends)) @heritage
"""


RUST_DEFINITIONS = """
(function_item
  name: (identifier) @name) @definition.function

(struct_item
  name: (type_identifier) @name) @definition.struct

(enum_item
  name: (type_identifier) @name) @definition.enum

(trait_item
  name: (type_identifier) @name) @definition.trait

(impl_item
  type: (type_identifier) @name) @definition.impl
"""

RUST_IMPORTS = """
(use_declaration
  argument: (scoped_identifier) @import.source) @import

(use_declaration
  argument: (use_as_clause
    path: (scoped_identifier) @import.source)) @import

(use_declaration
  argument: (scoped_use_list
    path: (scoped_identifier) @import.source)) @import

(use_declaration
  argument: (identifier) @import.source) @import
"""

RUST_ASSIGNMENTS = """
(assignment_expression
  left: (field_expression
    value: (_) @assignment.receiver
    field: (field_identifier) @assignment.property)
  right: (_)) @assignment
"""

RUST_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (field_expression
    field: (field_identifier) @call.name)) @call

(call_expression
  function: (scoped_identifier
    name: (identifier) @call.name)) @call
"""

RUST_HERITAGE = """
(impl_item
  trait: (type_identifier) @heritage.extends
  type: (type_identifier) @heritage.class) @heritage
"""


RUBY_DEFINITIONS = """
(class
  name: (constant) @name) @definition.class

(method
  name: (identifier) @name) @definition.method

(singleton_method
  name: (identifier) @name) @definition.method

(module
  name: (constant) @name) @definition.module
"""

RUBY_IMPORTS = """
(call
  method: (identifier) @_method
  arguments: (argument_list
    (string
      (string_content) @import.source))
  (#match? @_method "^(require|require_relative|load)$")) @import
"""

RUBY_ASSIGNMENTS = """
(assignment
  left: (call
    receiver: (_) @assignment.receiver
    method: (identifier) @assignment.property)
  right: (_)) @assignment
"""

RUBY_CALLS = """
(call
  method: (identifier) @call.name) @call
"""

RUBY_HERITAGE = """
(class
  name: (constant) @heritage.class
  superclass: (superclass
    (constant) @heritage.extends)) @heritage
"""


PHP_DEFINITIONS = """
(class_declaration
  name: (name) @name) @definition.class

(method_declaration
  name: (name) @name) @definition.method

(function_definition
  name: (name) @name) @definition.function

(property_declaration
  (property_element
    (variable_name
      (name) @name))) @definition.property
"""

PHP_IMPORTS = """
(namespace_use_declaration
  (namespace_use_clause
    (qualified_name) @import.source)) @import
"""

PHP_CALLS = """
(function_call_expression
  function: (name) @call.name) @call

(member_call_expression
  name: (name) @call.name) @call

(scoped_call_expression
  name: (name) @call.name) @call

(object_creation_expression
  (name) @call.name) @call
"""

PHP_ASSIGNMENTS = """
(assignment_expression
  left: (member_access_expression
    object: (_) @assignment.receiver
    name: (name) @assignment.property)
  right: (_)) @assignment
"""

PHP_HERITAGE = """
(class_declaration
  name: (name) @heritage.class
  (base_clause
    [(name) (qualified_name)] @heritage.extends)) @heritage

(class_declaration
  name: (name) @heritage.class
  (class_interface_clause
    [(name) (qualified_name)] @heritage.implements)) @heritage.impl
"""


KOTLIN_DEFINITIONS = """
(class_declaration
  name: (identifier) @name) @definition.class

(function_declaration
  name: (identifier) @name) @definition.function

(object_declaration
  name: (identifier) @name) @definition.class
"""

KOTLIN_IMPORTS = """
(import
  (qualified_identifier) @import.source) @import
"""

KOTLIN_CALLS = """
(call_expression
  (identifier) @call.name) @call

(call_expression
  (navigation_expression
    (identifier) @call.name)) @call
"""

KOTLIN_ASSIGNMENTS = """
(assignment
  (navigation_expression
    (_) @assignment.receiver
    (identifier) @assignment.property)
  (_)) @assignment
"""

KOTLIN_HERITAGE = """
(class_declaration
  name: (identifier) @heritage.class
  (delegation_specifiers
    (delegation_specifier
      (constructor_invocation
        (user_type
          (identifier) @heritage.extends))))) @heritage
"""


SWIFT_DEFINITIONS = """
(class_declaration
  name: (type_identifier) @name) @definition.class

(function_declaration
  name: (simple_identifier) @name) @definition.function

(protocol_declaration
  name: (type_identifier) @name) @definition.interface
"""

SWIFT_IMPORTS = """
(import_declaration
  (identifier) @import.source) @import
"""

SWIFT_CALLS = """
(call_expression
  (simple_identifier) @call.name) @call
"""

SWIFT_HERITAGE = """
(class_declaration
  name: (type_identifier) @heritage.class
  (inheritance_specifier
    (user_type
      (type_identifier) @heritage.extends))) @heritage
"""


# ═══════════════════════════════════════════════════════════════════════
# FORTRAN
# ═══════════════════════════════════════════════════════════════════════

FORTRAN_DEFINITIONS = """
(program
  (program_statement
    (name) @name)) @definition.class

(module
  (module_statement
    (name) @name)) @definition.class

(function
  name: (name) @name) @definition.function

(subroutine
  name: (name) @name) @definition.function

(derived_type_definition
  (derived_type_statement) @name) @definition.class
"""

FORTRAN_IMPORTS = """
(use_statement
  (module_name) @import.source) @import
"""

FORTRAN_CALLS = """
(call_expression
  (identifier) @call.name) @call

(subroutine_call
  (identifier) @call.name) @call
"""

FORTRAN_HERITAGE = """
"""


# ═══════════════════════════════════════════════════════════════════════
# SCALA
# ═══════════════════════════════════════════════════════════════════════

SCALA_DEFINITIONS = """
(class_definition
  name: (identifier) @name) @definition.class

(object_definition
  name: (identifier) @name) @definition.class

(trait_definition
  name: (identifier) @name) @definition.class

(function_definition
  name: (identifier) @name) @definition.function

(function_declaration
  name: (identifier) @name) @definition.function

(val_definition
  pattern: (identifier) @name) @definition.property

(var_definition
  pattern: (identifier) @name) @definition.property
"""

SCALA_IMPORTS = """
(import_declaration
  (identifier) @import.source) @import
"""

SCALA_CALLS = """
(call_expression
  function: (identifier) @call.name) @call

(call_expression
  function: (field_expression
    field: (identifier) @call.name)) @call
"""

SCALA_HERITAGE = """
(class_definition
  name: (identifier) @heritage.class
  (extends_clause
    (type_identifier) @heritage.extends)) @heritage

(object_definition
  name: (identifier) @heritage.class
  (extends_clause
    (type_identifier) @heritage.extends)) @heritage
"""


# ═══════════════════════════════════════════════════════════════════════
# OBJECTIVE-C
# ═══════════════════════════════════════════════════════════════════════

OBJC_DEFINITIONS = """
(class_interface
  name: (identifier) @name) @definition.class

(class_implementation
  name: (identifier) @name) @definition.class

(protocol_declaration
  name: (identifier) @name) @definition.class

(method_declaration
  (identifier) @name) @definition.function

(method_definition
  (identifier) @name) @definition.function
"""

OBJC_IMPORTS = """
(preproc_include
  path: (string_literal) @import.source) @import

(preproc_include
  path: (system_lib_string) @import.source) @import
"""

OBJC_CALLS = """
(message_expression
  (identifier) @call.name) @call

(call_expression
  function: (identifier) @call.name) @call
"""

OBJC_HERITAGE = """
(class_interface
  name: (identifier) @heritage.class
  (identifier) @heritage.extends) @heritage
"""


# ═══════════════════════════════════════════════════════════════════════
# SOLIDITY
# ═══════════════════════════════════════════════════════════════════════

SOLIDITY_DEFINITIONS = """
(contract_declaration
  name: (identifier) @name) @definition.class

(interface_declaration
  name: (identifier) @name) @definition.class

(library_declaration
  name: (identifier) @name) @definition.class

(function_definition
  name: (identifier) @name) @definition.function

(modifier_definition
  name: (identifier) @name) @definition.function

(event_definition
  name: (identifier) @name) @definition.function

(struct_declaration
  name: (identifier) @name) @definition.class

(enum_declaration
  name: (identifier) @name) @definition.class

(state_variable_declaration
  name: (identifier) @name) @definition.property
"""

SOLIDITY_IMPORTS = """
(import_directive
  (string) @import.source) @import
"""

SOLIDITY_CALLS = """
(call_expression
  function: (expression
    (identifier) @call.name)) @call

(call_expression
  function: (expression
    (member_expression
      (identifier) @call.name))) @call
"""

SOLIDITY_HERITAGE = """
(contract_declaration
  name: (identifier) @heritage.class
  (inheritance_specifier
    (user_defined_type
      (identifier) @heritage.extends))) @heritage
"""


# ═══════════════════════════════════════════════════════════════════════
# PERL (Tier 2 — WASM bridge, queries for mock AST nodes)
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# ADA
# ═══════════════════════════════════════════════════════════════════════

ADA_DEFINITIONS = """
(package_body
  name: (identifier) @name) @definition.class

(package_declaration
  name: (identifier) @name) @definition.class

(subprogram_body
  (procedure_specification
    name: (identifier) @name)) @definition.function

(subprogram_body
  (function_specification
    name: (identifier) @name)) @definition.function
"""

ADA_IMPORTS = """
(with_clause
  (selected_component) @import.source) @import

(with_clause
  (identifier) @import.source) @import
"""

ADA_CALLS = """
(function_call
  name: (identifier) @call.name) @call

(function_call
  name: (selected_component) @call.name) @call

(procedure_call_statement
  name: (identifier) @call.name) @call
"""


# ═══════════════════════════════════════════════════════════════════════
# MATLAB
# ═══════════════════════════════════════════════════════════════════════

MATLAB_DEFINITIONS = """
(function_definition
  name: (identifier) @name) @definition.function

(class_definition
  name: (identifier) @name) @definition.class
"""

MATLAB_CALLS = """
(function_call
  name: (identifier) @name) @call
"""


# ═══════════════════════════════════════════════════════════════════════
# COMMON LISP
# ═══════════════════════════════════════════════════════════════════════

COMMON_LISP_DEFINITIONS = """
(defun
  (defun_header
    (sym_lit) @name)) @definition.function
"""

COMMON_LISP_CALLS = """
(list_lit
  (sym_lit) @call.name) @call
"""


PERL_DEFINITIONS = """
(subroutine_declaration
  name: (identifier) @name) @definition.function

(package_statement
  (identifier) @name) @definition.class
"""

PERL_IMPORTS = """
(use_statement
  (identifier) @import.source) @import
"""

PERL_CALLS = """
(call_expression
  function: (identifier) @call.name) @call
"""

# ═══════════════════════════════════════════════════════════════════════
# COBOL (Tier 2 — WASM bridge, queries for mock AST nodes)
# ═══════════════════════════════════════════════════════════════════════

COBOL_DEFINITIONS = """
"""

COBOL_IMPORTS = """
"""

COBOL_CALLS = """
"""


_QUERIES: dict[SupportedLanguages, dict[str, str]] = {
    SupportedLanguages.PYTHON: {
        "definitions": PYTHON_DEFINITIONS,
        "imports": PYTHON_IMPORTS,
        "calls": PYTHON_CALLS,
        "heritage": PYTHON_HERITAGE,
        "assignments": PYTHON_ASSIGNMENTS,
    },
    SupportedLanguages.JAVASCRIPT: {
        "definitions": JAVASCRIPT_DEFINITIONS,
        "imports": TYPESCRIPT_IMPORTS,
        "calls": TYPESCRIPT_CALLS,
        "heritage": JAVASCRIPT_HERITAGE,
        "assignments": TYPESCRIPT_ASSIGNMENTS,
    },
    SupportedLanguages.TYPESCRIPT: {
        "definitions": TYPESCRIPT_DEFINITIONS,
        "imports": TYPESCRIPT_IMPORTS,
        "calls": TYPESCRIPT_CALLS,
        "heritage": TYPESCRIPT_HERITAGE,
        "assignments": TYPESCRIPT_ASSIGNMENTS,
    },
    SupportedLanguages.JAVA: {
        "definitions": JAVA_DEFINITIONS,
        "imports": JAVA_IMPORTS,
        "calls": JAVA_CALLS,
        "heritage": JAVA_HERITAGE,
        "assignments": JAVA_ASSIGNMENTS,
    },
    SupportedLanguages.GO: {
        "definitions": GO_DEFINITIONS,
        "imports": GO_IMPORTS,
        "calls": GO_CALLS,
        "heritage": GO_HERITAGE,
        "assignments": GO_ASSIGNMENTS,
    },
    SupportedLanguages.C: {
        "definitions": C_DEFINITIONS,
        "imports": C_IMPORTS,
        "calls": C_CALLS,
        "assignments": C_ASSIGNMENTS,
    },
    SupportedLanguages.C_PLUS_PLUS: {
        "definitions": CPP_DEFINITIONS,
        "imports": CPP_IMPORTS,
        "calls": CPP_CALLS,
        "heritage": CPP_HERITAGE,
        "assignments": CPP_ASSIGNMENTS,
    },
    SupportedLanguages.C_SHARP: {
        "definitions": CSHARP_DEFINITIONS,
        "imports": CSHARP_IMPORTS,
        "calls": CSHARP_CALLS,
        "heritage": CSHARP_HERITAGE,
        "assignments": CSHARP_ASSIGNMENTS,
    },
    SupportedLanguages.RUST: {
        "definitions": RUST_DEFINITIONS,
        "imports": RUST_IMPORTS,
        "calls": RUST_CALLS,
        "heritage": RUST_HERITAGE,
        "assignments": RUST_ASSIGNMENTS,
    },
    SupportedLanguages.RUBY: {
        "definitions": RUBY_DEFINITIONS,
        "imports": RUBY_IMPORTS,
        "calls": RUBY_CALLS,
        "heritage": RUBY_HERITAGE,
        "assignments": RUBY_ASSIGNMENTS,
    },
    SupportedLanguages.PHP: {
        "definitions": PHP_DEFINITIONS,
        "imports": PHP_IMPORTS,
        "calls": PHP_CALLS,
        "heritage": PHP_HERITAGE,
        "assignments": PHP_ASSIGNMENTS,
    },
    SupportedLanguages.KOTLIN: {
        "definitions": KOTLIN_DEFINITIONS,
        "imports": KOTLIN_IMPORTS,
        "calls": KOTLIN_CALLS,
        "heritage": KOTLIN_HERITAGE,
        "assignments": KOTLIN_ASSIGNMENTS,
    },
    SupportedLanguages.SWIFT: {
        "definitions": SWIFT_DEFINITIONS,
        "imports": SWIFT_IMPORTS,
        "calls": SWIFT_CALLS,
        "heritage": SWIFT_HERITAGE,
    },
    # VB6: queries not used by tree-sitter (JS bridge handles parsing).
    # Placeholder entries so get_queries() returns a valid dict.
    SupportedLanguages.VB6: {
        "definitions": "",
        "calls": "",
    },
    # ── Fortran ──────────────────────────────────────────────────────
    SupportedLanguages.FORTRAN: {
        "definitions": FORTRAN_DEFINITIONS,
        "imports": FORTRAN_IMPORTS,
        "calls": FORTRAN_CALLS,
        "heritage": FORTRAN_HERITAGE,
    },
    # ── Scala ────────────────────────────────────────────────────────
    SupportedLanguages.SCALA: {
        "definitions": SCALA_DEFINITIONS,
        "imports": SCALA_IMPORTS,
        "calls": SCALA_CALLS,
        "heritage": SCALA_HERITAGE,
    },
    # ── Objective-C ──────────────────────────────────────────────────
    SupportedLanguages.OBJECTIVE_C: {
        "definitions": OBJC_DEFINITIONS,
        "imports": OBJC_IMPORTS,
        "calls": OBJC_CALLS,
        "heritage": OBJC_HERITAGE,
    },
    # ── Solidity ─────────────────────────────────────────────────────
    SupportedLanguages.SOLIDITY: {
        "definitions": SOLIDITY_DEFINITIONS,
        "imports": SOLIDITY_IMPORTS,
        "calls": SOLIDITY_CALLS,
        "heritage": SOLIDITY_HERITAGE,
    },
    # ── Ada ──────────────────────────────────────────────────────────
    SupportedLanguages.ADA: {
        "definitions": ADA_DEFINITIONS,
        "imports": ADA_IMPORTS,
        "calls": ADA_CALLS,
    },
    # ── MATLAB ───────────────────────────────────────────────────────
    SupportedLanguages.MATLAB: {
        "definitions": MATLAB_DEFINITIONS,
        "calls": MATLAB_CALLS,
    },
    # ── Common Lisp ──────────────────────────────────────────────────
    SupportedLanguages.COMMON_LISP: {
        "definitions": COMMON_LISP_DEFINITIONS,
        "calls": COMMON_LISP_CALLS,
    },
    # ── Delphi (Tier 2 — placeholder, WASM bridge pending) ──────────
    SupportedLanguages.DELPHI: {
        "definitions": "",
        "calls": "",
    },
    # ── Perl (Tier 2 — placeholder, WASM bridge pending) ────────────
    SupportedLanguages.PERL: {
        "definitions": "",
        "calls": "",
    },
    # ── COBOL (Tier 2 — placeholder, WASM bridge pending) ───────────
    SupportedLanguages.COBOL: {
        "definitions": "",
        "calls": "",
    },
    # ── Erlang (Tier 2 — WASM bridge, queries not used) ──────────────
    SupportedLanguages.ERLANG: {
        "definitions": "",
        "calls": "",
    },
    # ── Apex (Tier 2 — WASM bridge, queries not used) ────────────────
    SupportedLanguages.APEX: {
        "definitions": "",
        "calls": "",
    },
    # ── Pascal (Tier 2 — WASM bridge, queries not used) ──────────────
    SupportedLanguages.PASCAL: {
        "definitions": "",
        "calls": "",
    },
    # ── Prolog (Tier 2 — WASM bridge, queries not used) ──────────────
    SupportedLanguages.PROLOG: {
        "definitions": "",
        "calls": "",
    },
    # ── Tier 3: Regex-parsed languages (queries not used) ────────────
    SupportedLanguages.RPG: {"definitions": "", "calls": ""},
    SupportedLanguages.ABAP: {"definitions": "", "calls": ""},
    SupportedLanguages.MUMPS: {"definitions": "", "calls": ""},
    SupportedLanguages.ASSEMBLY: {"definitions": "", "calls": ""},
    SupportedLanguages.TCL: {"definitions": "", "calls": ""},
    SupportedLanguages.ALGOL: {"definitions": "", "calls": ""},
    SupportedLanguages.FORTH: {"definitions": "", "calls": ""},
    SupportedLanguages.POSTSCRIPT: {"definitions": "", "calls": ""},
}


def get_queries(lang: SupportedLanguages) -> dict[str, str]:
    """Get all query strings for a language.

    Returns:
        Dict with keys like 'definitions', 'imports', 'calls', 'heritage', 'assignments'.
    """
    return _QUERIES.get(lang, {})


def get_query(lang: SupportedLanguages, query_type: str) -> str | None:
    """Get a specific query string for a language and query type."""
    return _QUERIES.get(lang, {}).get(query_type)
