"""AST extraction — parse files and extract nodes, calls, imports, heritage.

Port of GitNexus ingestion/parsing-processor.ts + workers/parse-worker.ts.
Uses tree-sitter to parse source files and extract structured records.

In Python, we use sequential processing by default. For large repos,
``ProcessPoolExecutor`` can be used (tree-sitter nodes cannot be pickled,
so workers must return serialized dicts).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from ..parsing.ast_cache import ASTCache
from ..parsing.ast_helpers import (
    FUNCTION_NODE_TYPES,
    count_call_arguments,
    extract_function_name,
    extract_receiver_name,
    find_enclosing_class_id,
    generate_id,
    infer_call_form,
)
from ..parsing.parser_loader import is_language_available, load_language, parse_file
from ..parsing.tree_sitter_queries import get_queries
from .extraction.docstring_extractor import extract_docstring
from .extraction.export_detection import is_exported
from .symbol_table import SymbolTable

from ..config import (
    BUILT_IN_NAMES,
    SupportedLanguages,
    get_language_from_filename,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImport:
    file_path: str
    raw_import_path: str
    language: str
    named_bindings: list[dict] | None = None


@dataclass
class ExtractedCall:
    file_path: str
    called_name: str
    source_id: str
    arg_count: int = 0
    call_form: str = "free"
    receiver_name: str | None = None
    receiver_type_name: str | None = None


@dataclass
class ExtractedHeritage:
    file_path: str
    class_name: str
    parent_name: str
    kind: str = "extends"


@dataclass
class ExtractedAssignment:
    file_path: str
    source_id: str
    receiver_text: str
    property_name: str
    receiver_type_name: str | None = None


@dataclass
class ParseResult:
    """Aggregated results from parsing a batch of files."""

    imports: list[ExtractedImport] = field(default_factory=list)
    calls: list[ExtractedCall] = field(default_factory=list)
    heritage: list[ExtractedHeritage] = field(default_factory=list)
    assignments: list[ExtractedAssignment] = field(default_factory=list)
    type_envs: dict = field(default_factory=dict)


def _parse_single_file(file_info: dict) -> dict | None:
    """Parse one file and extract all records (thread-safe, no shared state).

    Returns a dict with all extracted data, or None on failure.
    """
    file_path = file_info["path"]
    content = file_info["content"]

    lang = get_language_from_filename(file_path, content_head=content[:2048])
    if lang is None or not is_language_available(lang):
        return None

    try:
        tree = parse_file(content, lang, file_path)
    except Exception as exc:
        logger.debug("Failed to parse %s: %s", file_path, exc)
        return None

    root = tree.root_node
    queries = get_queries(lang)
    file_node_id = generate_id("File", file_path)

    # VB6 and WASM-bridged/regex-parsed languages use mock nodes, so
    # ts_lang is None and tree-sitter queries can't be used.
    from ..parsing.regex_parser import get_regex_config
    from ..parsing.wasm_bridge import get_wasm_config

    is_mock = (
        lang == SupportedLanguages.VB6
        or get_wasm_config(lang.value) is not None
        or get_regex_config(lang.value) is not None
    )
    ts_lang = None if is_mock else load_language(lang, file_path)

    imports = []
    calls = []
    heritage = []
    assignments = []

    if is_mock:
        _extract_vb6_calls(calls, root, file_path, file_node_id)
    else:
        _extract_imports(imports, root, ts_lang, queries, file_path, lang)
        _extract_calls(calls, root, ts_lang, queries, file_path, file_node_id)
        _extract_heritage(heritage, root, ts_lang, queries, file_path)
        _extract_assignments(
            assignments, root, ts_lang, queries, file_path, file_node_id
        )

    type_env = None
    if not is_mock:
        try:
            from .extraction.type_env import build_type_env

            type_env = build_type_env(root, lang)
        except Exception as exc:
            logger.debug("Failed to build type env for %s: %s", file_path, exc)

    return {
        "file_path": file_path,
        "content": content,
        "lang": lang,
        "tree": tree,
        "ts_lang": ts_lang,
        "queries": queries,
        "file_node_id": file_node_id,
        "imports": imports,
        "calls": calls,
        "heritage": heritage,
        "assignments": assignments,
        "type_env": type_env,
    }


def process_infile_information(
    graph: KnowledgeGraph,
    files: list[dict],
    symbol_table: SymbolTable,
    ast_cache: ASTCache,
    on_progress: callable = None,
) -> ParseResult:
    """Parse a batch of files and extract nodes + relationships.

    Uses ThreadPoolExecutor for parallel parsing (tree-sitter is a C
    extension that releases the GIL). Graph/symbol_table mutations
    happen single-threaded after all files are parsed.

    Args:
        graph: Knowledge graph to add definition nodes to.
        files: List of ``{path: str, content: str}`` dicts.
        symbol_table: Symbol table for registration.
        ast_cache: AST tree cache.
        on_progress: Optional ``(current, total, file_path)`` callback.

    Returns:
        ParseResult with all extracted records.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = ParseResult()
    total = len(files)

    workers = min(os.cpu_count() or 4, 8, max(1, total))
    parsed_files = []

    if workers <= 1 or total < 10:
        for idx, f in enumerate(files):
            if on_progress and idx % 20 == 0:
                on_progress(idx, total, f["path"])
            parsed = _parse_single_file(f)
            if parsed:
                parsed_files.append(parsed)
    else:
        if on_progress:
            on_progress(0, total, "parallel parsing...")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_parse_single_file, f): f for f in files}
            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                if on_progress and done_count % 50 == 0:
                    on_progress(done_count, total, f"parsed {done_count}/{total}")
                parsed = future.result()
                if parsed:
                    parsed_files.append(parsed)

    if on_progress:
        on_progress(len(parsed_files), total, "merging definitions...")

    for parsed in parsed_files:
        file_path = parsed["file_path"]

        ast_cache.put(file_path, parsed["tree"])

        _extract_definitions(
            graph,
            symbol_table,
            parsed["tree"].root_node,
            parsed["ts_lang"],
            parsed["queries"],
            file_path,
            parsed["file_node_id"],
            parsed["content"],
            parsed["lang"],
        )

        result.imports.extend(parsed["imports"])
        result.calls.extend(parsed["calls"])
        result.heritage.extend(parsed["heritage"])
        result.assignments.extend(parsed["assignments"])

        if parsed["type_env"]:
            result.type_envs[file_path] = parsed["type_env"]

    if on_progress:
        on_progress(total, total, "")

    return result


def _node_text(node) -> str:
    text = node.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


def _run_query(ts_lang, query_str: str, root_node) -> list[tuple]:
    """Run a tree-sitter query, compatible with both old and new APIs.

    Returns list of (node, capture_name) tuples (old-style format).
    """
    try:
        from tree_sitter import Query, QueryCursor

        query = Query(ts_lang, query_str)
        cursor = QueryCursor(query)
        caps_dict = cursor.captures(root_node)
        result = []
        for cap_name, nodes in caps_dict.items():
            for node in nodes:
                result.append((node, cap_name))
        result.sort(key=lambda x: (x[0].start_byte, x[1]))
        return result
    except (ImportError, TypeError):
        query = ts_lang.query(query_str)
        return query.captures(root_node)


_PARAM_FIELD_NAMES = (
    "parameters",
    "formal_parameters",
    "parameter_list",
    "type_parameters",
)
_RETURN_TYPE_FIELDS = ("return_type", "type", "result")


def _extract_signature(
    defn_node, name: str, label: str
) -> tuple[str | None, int | None, str | None]:
    """Extract a human-readable signature, parameter count, and return type from a definition AST node.

    Returns ``(signature, parameter_count, return_type)`` or ``(None, None, None)``
    if the node is not a callable (e.g. class, enum, struct without params).
    """
    if label not in ("Function", "Method", "Constructor"):
        return None, None, None

    params_node = None
    for field_name in _PARAM_FIELD_NAMES:
        params_node = defn_node.child_by_field_name(field_name)
        if params_node is not None:
            break

    if params_node is None:
        for child in defn_node.children:
            if child.type in ("parameters", "formal_parameters", "parameter_list"):
                params_node = child
                break

    if params_node is None:
        return None, None, None

    params_text = _node_text(params_node).strip()
    if params_text.startswith("(") and params_text.endswith(")"):
        params_text = params_text[1:-1].strip()

    if params_text:
        param_count = len([p.strip() for p in params_text.split(",") if p.strip()])
    else:
        param_count = 0

    return_type = None
    for field_name in _RETURN_TYPE_FIELDS:
        rt_node = defn_node.child_by_field_name(field_name)
        if rt_node is not None:
            return_type = _node_text(rt_node).strip()
            if return_type.startswith(("->", ":")):
                return_type = return_type.lstrip("->:").strip()
            break

    sig = f"{name}({params_text})"
    if return_type:
        sig = f"{sig} -> {return_type}"

    if len(sig) > 500:
        sig = sig[:497] + "..."

    return sig, param_count, return_type


def _extract_definitions(
    graph,
    symbol_table,
    root,
    ts_lang,
    queries,
    file_path,
    file_node_id,
    content,
    lang,
):
    """Extract definition nodes (classes, functions, methods) from AST."""
    # VB6: walk mock AST directly instead of running tree-sitter queries
    if lang == SupportedLanguages.VB6:
        captures = _walk_vb6_definitions(root)
    else:
        defn_query_str = queries.get("definitions")
        if not defn_query_str:
            return
        try:
            captures = _run_query(ts_lang, defn_query_str, root)
        except Exception as exc:
            logger.debug("Definition query failed for %s: %s", file_path, exc)
            return

    i = 0
    while i < len(captures):
        node, capture_name = captures[i]

        if capture_name == "name":
            name = _node_text(node)
            defn_node = node.parent
            if defn_node is None:
                i += 1
                continue

            # Walk up to find the actual definition node.
            # For VB6: name is on variable_declarator inside field_declaration,
            # so we may need to go up 1-2 levels.
            label = None
            walk_node = defn_node
            for _ in range(3):
                label = _label_from_defn_capture(walk_node, lang)
                if label is not None:
                    defn_node = walk_node
                    break
                if walk_node.parent is not None:
                    walk_node = walk_node.parent
                else:
                    break
            if label is None:
                i += 1
                continue

            node_id = generate_id(label, f"{file_path}:{name}")
            exported = is_exported(defn_node, name, lang)

            start_line = defn_node.start_point[0]
            end_line = defn_node.end_point[0]
            snippet = _extract_snippet(content, start_line, end_line)

            signature, param_count, return_type = _extract_signature(
                defn_node, name, label
            )

            graph.add_node(
                GraphNode(
                    id=node_id,
                    label=NodeLabel(label),
                    properties=NodeProperties(
                        name=name,
                        file_path=file_path,
                        start_line=start_line + 1,
                        end_line=end_line + 1,
                        is_exported=exported,
                        language=lang.value,
                        content=snippet,
                        signature=signature,
                        parameter_count=param_count,
                        return_type=return_type,
                    ),
                )
            )

            graph.add_relationship(
                GraphRelationship(
                    id=f"{file_node_id}_contains_{node_id}",
                    source_id=file_node_id,
                    target_id=node_id,
                    type=RelationshipType.CONTAINS,
                )
            )

            owner_id = None
            if label in ("Method", "Constructor", "Property"):
                owner_id = find_enclosing_class_id(defn_node, file_path)

            if owner_id:
                rel_type = (
                    RelationshipType.HAS_PROPERTY
                    if label == "Property"
                    else RelationshipType.HAS_METHOD
                )
                graph.add_relationship(
                    GraphRelationship(
                        id=f"{owner_id}_{rel_type.value.lower()}_{node_id}",
                        source_id=owner_id,
                        target_id=node_id,
                        type=rel_type,
                    )
                )

            symbol_table.add(
                file_path=file_path,
                name=name,
                node_id=node_id,
                symbol_type=label,
                owner_id=owner_id,
                parameter_count=param_count,
                return_type=return_type,
            )

            docstring = extract_docstring(defn_node, lang)
            if docstring:
                section_id = generate_id(
                    "Section",
                    f"{file_path}:L{docstring.start_line}:{name}:docstring",
                )
                graph.add_node(
                    GraphNode(
                        id=section_id,
                        label=NodeLabel.SECTION,
                        properties=NodeProperties(
                            name=f"{name} docstring",
                            file_path=file_path,
                            start_line=docstring.start_line + 1,
                            end_line=docstring.end_line + 1,
                            content=docstring.content[:500],
                            description="docstring",
                            language=lang.value,
                        ),
                    )
                )
                graph.add_relationship(
                    GraphRelationship(
                        id=generate_id("DESCRIBES", f"{section_id}->{node_id}"),
                        source_id=section_id,
                        target_id=node_id,
                        type=RelationshipType.DESCRIBES,
                        confidence=1.0,
                        reason="docstring-direct",
                    )
                )

        i += 1


def _extract_imports(imports_list, root, ts_lang, queries, file_path, lang):
    """Extract import statements from AST."""
    import_query_str = queries.get("imports")
    if not import_query_str:
        return

    try:
        captures = _run_query(ts_lang, import_query_str, root)
    except Exception as exc:
        logger.debug("Import query failed for %s: %s", file_path, exc)
        return

    from .extraction.named_binding_extraction import NAMED_BINDING_EXTRACTORS

    extractor = NAMED_BINDING_EXTRACTORS.get(lang)

    import_nodes = {}
    for node, capture_name in captures:
        if capture_name == "import":
            import_nodes[id(node)] = node

    for node, capture_name in captures:
        if capture_name == "import.source":
            raw_path = _node_text(node).strip("'\"")

            bindings = None
            if extractor:
                import_node = node.parent
                while import_node and id(import_node) not in import_nodes:
                    import_node = import_node.parent
                if import_node:
                    try:
                        bindings = extractor(import_node)
                    except Exception as exc:
                        logger.debug("Binding extraction failed: %s", exc)
                        bindings = None

            imports_list.append(
                ExtractedImport(
                    file_path=file_path,
                    raw_import_path=raw_path,
                    language=lang.value,
                    named_bindings=bindings if bindings else None,
                )
            )


def _extract_calls(calls_list, root, ts_lang, queries, file_path, file_node_id):
    """Extract function/method calls from AST."""
    call_query_str = queries.get("calls")
    if not call_query_str:
        return

    try:
        captures = _run_query(ts_lang, call_query_str, root)
    except Exception as exc:
        logger.debug("Call query failed for %s: %s", file_path, exc)
        return

    for node, capture_name in captures:
        if capture_name == "call.name":
            called_name = _node_text(node)

            if called_name in BUILT_IN_NAMES:
                continue

            call_node = node.parent
            if call_node is not None and call_node.parent is not None:
                if call_node.type not in (
                    "call_expression",
                    "call",
                    "method_invocation",
                    "function_call_expression",
                    "member_call_expression",
                    "scoped_call_expression",
                    "new_expression",
                    "object_creation_expression",
                ):
                    call_node = call_node.parent

            call_form = infer_call_form(call_node, node) if call_node else "free"
            receiver_name = (
                extract_receiver_name(node) if call_form == "member" else None
            )
            arg_count = count_call_arguments(call_node) if call_node else 0

            source_id = _find_enclosing_function_id(node, file_path) or file_node_id

            calls_list.append(
                ExtractedCall(
                    file_path=file_path,
                    called_name=called_name,
                    source_id=source_id,
                    arg_count=arg_count,
                    call_form=call_form,
                    receiver_name=receiver_name,
                )
            )


def _extract_heritage(heritage_list, root, ts_lang, queries, file_path):
    """Extract extends/implements relationships from AST."""
    heritage_query_str = queries.get("heritage")
    if not heritage_query_str:
        return

    try:
        captures = _run_query(ts_lang, heritage_query_str, root)
    except Exception as exc:
        logger.debug("Heritage query failed for %s: %s", file_path, exc)
        return

    class_name = None
    for node, capture_name in captures:
        if capture_name == "heritage.class":
            class_name = _node_text(node)
        elif capture_name == "heritage.extends" and class_name:
            heritage_list.append(
                ExtractedHeritage(
                    file_path=file_path,
                    class_name=class_name,
                    parent_name=_node_text(node),
                    kind="extends",
                )
            )
        elif capture_name == "heritage.implements" and class_name:
            heritage_list.append(
                ExtractedHeritage(
                    file_path=file_path,
                    class_name=class_name,
                    parent_name=_node_text(node),
                    kind="implements",
                )
            )


def _extract_assignments(
    assignments_list, root, ts_lang, queries, file_path, file_node_id
):
    """Extract field write assignments from AST."""
    assignment_query_str = queries.get("assignments")
    if not assignment_query_str:
        return

    try:
        captures = _run_query(ts_lang, assignment_query_str, root)
    except Exception as exc:
        logger.debug("Assignment query failed for %s: %s", file_path, exc)
        return

    receiver_text = None
    for node, capture_name in captures:
        if capture_name == "assignment.receiver":
            receiver_text = _node_text(node)
        elif capture_name == "assignment.property" and receiver_text:
            source_id = _find_enclosing_function_id(node, file_path) or file_node_id
            assignments_list.append(
                ExtractedAssignment(
                    file_path=file_path,
                    source_id=source_id,
                    receiver_text=receiver_text,
                    property_name=_node_text(node),
                )
            )
            receiver_text = None


def _label_from_defn_capture(defn_node, lang) -> str | None:
    """Determine NodeLabel string from a definition AST node type."""
    t = defn_node.type

    label_map = {
        # ── Original 14 languages ────────────────────────────────────
        "class_declaration": "Class",
        "class_definition": "Class",
        "class_specifier": "Class",
        "interface_declaration": "Interface",
        "function_declaration": "Function",
        "function_definition": "Function",
        "async_function_declaration": "Function",
        "function_item": "Function",
        "method_definition": "Method",
        "method_declaration": "Method",
        "method": "Method",
        "singleton_method": "Method",
        "constructor_declaration": "Constructor",
        "struct_specifier": "Struct",
        "enum_item": "Enum",
        "trait_item": "Trait",
        "impl_item": "Impl",
        "object_declaration": "Class",
        "protocol_declaration": "Interface",
        "struct_declaration": "Struct",
        "enum_declaration": "Enum",
        "module": "Module",
        "module_block": "Module",
        "property_declaration": "Property",
        "public_field_definition": "Property",
        "field_declaration": "Property",
        "type_alias_declaration": "TypeAlias",
        "structure_block": "Struct",
        "enum_block": "Enum",
        "class_block": "Class",
        "interface_block": "Interface",
        # ── Fortran ──────────────────────────────────────────────────
        "subroutine": "Function",
        "program": "Module",
        "type_declaration": "Struct",
        # "interface_block": "Interface",
        "module_statement": "Module",
        # ── Scala ────────────────────────────────────────────────────
        "object_definition": "Class",
        "trait_definition": "Trait",
        "val_definition": "Property",
        "var_definition": "Property",
        # ── Objective-C ──────────────────────────────────────────────
        "class_interface": "Class",
        "class_implementation": "Class",
        "category_interface": "Module",
        "category_implementation": "Module",
        # ── Solidity ─────────────────────────────────────────────────
        "contract_declaration": "Class",
        "library_declaration": "Module",
        "modifier_definition": "Function",
        "event_definition": "Function",
        "state_variable_declaration": "Property",
        # ── Delphi / Pascal ──────────────────────────────────────────
        "procedure_declaration": "Function",
        "unit_declaration": "Module",
        "program_declaration": "Module",
        "record_declaration": "Struct",
        # ── Ada ──────────────────────────────────────────────────────
        "subprogram_body": "Function",
        "subprogram_declaration": "Function",
        "package_declaration": "Module",
        "package_body": "Module",
        "task_type_declaration": "Class",
        "protected_type_declaration": "Class",
        # ── Common Lisp ──────────────────────────────────────────────
        "defun": "Function",
        "defmacro": "Function",
        "defclass": "Class",
        "defgeneric": "Function",
        "defmethod": "Method",
        "defpackage": "Module",
        "defvar": "Property",
        "defparameter": "Property",
        # ── Perl ─────────────────────────────────────────────────────
        "subroutine_declaration": "Function",
        # ── COBOL ────────────────────────────────────────────────────
        "paragraph": "Function",
        "section_header": "Module",
        "program_id": "Class",
        "data_description_entry": "Property",
        # ── Erlang ───────────────────────────────────────────────────
        "function_clause": "Function",
        "module_attribute": "Module",
        # ── Apex ─────────────────────────────────────────────────────
        "trigger_declaration": "Function",
        # ── Prolog ───────────────────────────────────────────────────
        "clause": "Function",
        "directive": "Module",
        # ── Tcl ──────────────────────────────────────────────────────
        "proc_definition": "Function",
        # ── RPG ──────────────────────────────────────────────────────
        "dcl_proc": "Function",
        "begsr": "Function",
        "dcl_ds": "Struct",
        # ── ABAP ─────────────────────────────────────────────────────
        "form_definition": "Function",
        "report": "Module",
        # ── Forth ────────────────────────────────────────────────────
        "word_definition": "Function",
        # ── PostScript ───────────────────────────────────────────────
        "procedure_def": "Function",
    }
    if t in FUNCTION_NODE_TYPES:
        _name, label = extract_function_name(defn_node)
        return label
    if t in ("lexical_declaration",):
        return "Function"
    # variable_declarator: in JS/TS means arrow function assignment,
    # but in VB6 it's a variable inside field_declaration — skip it
    # so the parent walk-up finds field_declaration → "Property".
    if t == "variable_declarator" and lang != SupportedLanguages.VB6:
        return "Function"
    return label_map.get(t)


def _extract_snippet(
    content: str, start_line: int, end_line: int, max_lines: int = 200
) -> str:
    """Extract a content snippet from source code."""
    lines = content.split("\n")
    snippet_lines = lines[start_line : min(end_line + 1, start_line + max_lines)]
    return "\n".join(snippet_lines)


def _find_enclosing_function_id(node, file_path: str) -> str | None:
    """Walk up AST to find the enclosing function and return its ID."""
    from ..parsing.ast_helpers import FUNCTION_NODE_TYPES

    current = node.parent
    while current is not None:
        if current.type in FUNCTION_NODE_TYPES:
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                # name = _node_text(name_node)
                func_name, label = extract_function_name(current)
                return generate_id(label, f"{file_path}:{func_name}")
        current = current.parent
    return None


# ── VB6 AST walkers (for mock nodes from JS bridge) ─────────────────

# Node types that have a direct "name" field
_VB6_NAMED_DEFINITIONS = frozenset(
    {
        "method_declaration",
        "property_declaration",
        "constructor_declaration",
        "structure_block",
        "enum_block",
        "class_block",
        "interface_block",
        "const_declaration",
    }
)

# Node types where name is on a child (variable_declarator)
_VB6_FIELD_DEFINITIONS = frozenset(
    {
        "field_declaration",
    }
)


def _walk_vb6_definitions(root) -> list[tuple]:
    """Walk VB6 mock AST and return (node, capture_name) pairs like tree-sitter queries."""
    captures = []
    _walk_vb6_defns_recursive(root, captures)
    return captures


def _walk_vb6_defns_recursive(node, captures):
    if node.type in _VB6_NAMED_DEFINITIONS:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            captures.append((name_node, "name"))

    elif node.type in _VB6_FIELD_DEFINITIONS:
        # field_declaration: name is on variable_declarator child, not on the node itself.
        # e.g., "Public gstrSQL As String" → field_declaration > variable_declarator(name=gstrSQL)
        # Only capture module-level fields (Public/Private), skip local Dim vars and Option statements.
        text = node.text
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        first_line = text.strip().split("\n")[0].lower()
        if first_line.startswith(("option ", "dim ")):
            pass  # skip Option Explicit, local Dim vars
        else:
            for child in getattr(node, "children", []):
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        captures.append((name_node, "name"))
                    break

    for child in getattr(node, "children", []):
        _walk_vb6_defns_recursive(child, captures)


def _extract_vb6_calls(calls_list, root, file_path, file_node_id):
    """Extract function/method calls from VB6 mock AST."""
    _walk_vb6_calls_recursive(root, calls_list, file_path, file_node_id)


def _walk_vb6_calls_recursive(node, calls_list, file_path, file_node_id):
    if node.type in ("invocation", "call_statement"):
        target = node.child_by_field_name("target")
        if target is not None:
            name = _node_text(target)
            # Handle member access: obj.Method -> name is full text
            if "." in name:
                parts = name.rsplit(".", 1)
                receiver_name = parts[0]
                called_name = parts[1]
                call_form = "member"
            else:
                receiver_name = None
                called_name = name
                call_form = "free"

            source_id = _find_enclosing_function_id(node, file_path) or file_node_id
            calls_list.append(
                ExtractedCall(
                    file_path=file_path,
                    called_name=called_name,
                    source_id=source_id,
                    call_form=call_form,
                    receiver_name=receiver_name,
                )
            )
    for child in getattr(node, "children", []):
        _walk_vb6_calls_recursive(child, calls_list, file_path, file_node_id)
