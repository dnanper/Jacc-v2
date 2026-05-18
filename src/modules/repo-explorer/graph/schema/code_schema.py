"""
KuzuDB (LadybugDB) schema definitions for CSG.

Ported from the GitNexus schema.ts. Defines all node tables, the
CodeRelation relationship table, the CodeEmbedding vector-storage table,
full-text-search index definitions, and helper utilities.
"""

from __future__ import annotations


EMBEDDING_DIMS: int = 768


NODE_TABLES: list[str] = [
    "File",
    "Folder",
    "Function",
    "Class",
    "Interface",
    "Method",
    "CodeElement",
    "Community",
    "Process",
    "Section",
    "Struct",
    "Enum",
    "Macro",
    "Typedef",
    "Union",
    "Namespace",
    "Trait",
    "Impl",
    "TypeAlias",
    "Const",
    "Static",
    "Property",
    "Record",
    "Delegate",
    "Annotation",
    "Constructor",
    "Template",
    "Module",
]

BACKTICK_TABLES: set[str] = {
    "Struct",
    "Enum",
    "Macro",
    "Typedef",
    "Union",
    "Namespace",
    "Trait",
    "Impl",
    "TypeAlias",
    "Const",
    "Static",
    "Property",
    "Record",
    "Delegate",
    "Annotation",
    "Constructor",
    "Template",
    "Module",
}


_CODE_SYMBOL_COLS = (
    "id STRING, name STRING, searchText STRING, filePath STRING, startLine INT64, endLine INT64, "
    "isExported BOOLEAN, content STRING, description STRING, "
    "parameterCount INT32, returnType STRING, signature STRING, fanIn INT32"
)

_NODE_COLUMN_MAP: dict[str, str] = {
    "File": "id STRING, name STRING, searchText STRING, filePath STRING, content STRING, fanIn INT32, lineCount INT32, binary BOOLEAN, infrastructure STRING",
    "Folder": "id STRING, name STRING, filePath STRING",
    "Method": (
        "id STRING, name STRING, searchText STRING, filePath STRING, startLine INT64, endLine INT64, "
        "isExported BOOLEAN, content STRING, description STRING, "
        "parameterCount INT32, returnType STRING, signature STRING, fanIn INT32"
    ),
    "Community": (
        "id STRING, name STRING, heuristicLabel STRING, cohesion DOUBLE, "
        "symbolCount INT32"
    ),
    "Process": (
        "id STRING, name STRING, heuristicLabel STRING, processType STRING, "
        "stepCount INT32, entryPointId STRING, terminalId STRING"
    ),
    "Section": (
        "id STRING, name STRING, searchText STRING, filePath STRING, startLine INT64, endLine INT64, "
        "level INT64, content STRING, description STRING"
    ),
}

_CODE_SYMBOL_TABLES: set[str] = {
    "Function",
    "Class",
    "Interface",
    "CodeElement",
    "Struct",
    "Enum",
    "Macro",
    "Typedef",
    "Union",
    "Namespace",
    "Trait",
    "Impl",
    "TypeAlias",
    "Const",
    "Static",
    "Property",
    "Record",
    "Delegate",
    "Annotation",
    "Constructor",
    "Template",
    "Module",
}


def _columns_for(label: str) -> str:
    """Return the raw column-definition string for *label*."""
    if label in _NODE_COLUMN_MAP:
        return _NODE_COLUMN_MAP[label]
    if label in _CODE_SYMBOL_TABLES:
        return _CODE_SYMBOL_COLS
    raise ValueError(f"Unknown node label: {label!r}")


def _esc_node(name: str) -> str:
    return f"`{name}`" if name in BACKTICK_TABLES else name


NODE_SCHEMA_QUERIES: list[str] = [
    f"CREATE NODE TABLE {_esc_node(t)} ({_columns_for(t)}, PRIMARY KEY (id))"
    for t in NODE_TABLES
]


_REL_FROM_TO_PAIRS: list[tuple[str, str]] = [
    ("Folder", "Folder"),
    ("Folder", "File"),
    ("File", "Section"),
    ("Section", "Section"),
    ("File", "Function"),
    ("File", "Class"),
    ("File", "Interface"),
    ("File", "Method"),
    ("File", "Struct"),
    ("File", "Enum"),
    ("File", "Macro"),
    ("File", "Typedef"),
    ("File", "Union"),
    ("File", "Namespace"),
    ("File", "Trait"),
    ("File", "Impl"),
    ("File", "TypeAlias"),
    ("File", "Const"),
    ("File", "Static"),
    ("File", "Property"),
    ("File", "Record"),
    ("File", "Delegate"),
    ("File", "Annotation"),
    ("File", "Constructor"),
    ("File", "Template"),
    ("File", "Module"),
    ("File", "CodeElement"),
    ("File", "File"),
    ("Section", "File"),
    ("Function", "Function"),
    ("Function", "Method"),
    ("Function", "Class"),
    ("Function", "Constructor"),
    ("Method", "Function"),
    ("Method", "Method"),
    ("Method", "Class"),
    ("Method", "Constructor"),
    ("Constructor", "Function"),
    ("Constructor", "Method"),
    ("File", "Function"),
    ("File", "Method"),
    ("File", "Class"),
    ("Class", "Class"),
    ("Class", "Interface"),
    ("Struct", "Struct"),
    ("Struct", "Class"),
    ("Interface", "Interface"),
    ("Class", "Interface"),
    ("Class", "Trait"),
    ("Struct", "Trait"),
    ("Struct", "Interface"),
    ("Impl", "Trait"),
    ("Class", "Method"),
    ("Struct", "Method"),
    ("Interface", "Method"),
    ("Trait", "Method"),
    ("Impl", "Method"),
    ("Record", "Method"),
    ("Enum", "Method"),
    ("Class", "Property"),
    ("Struct", "Property"),
    ("Interface", "Property"),
    ("Record", "Property"),
    ("Function", "Community"),
    ("Class", "Community"),
    ("Method", "Community"),
    ("Interface", "Community"),
    ("Struct", "Community"),
    ("Enum", "Community"),
    ("Function", "Process"),
    ("Method", "Process"),
    ("Class", "Process"),
    ("Function", "Property"),
    ("Method", "Property"),
    ("Function", "Method"),
    ("Section", "Function"),
    ("Section", "Class"),
    ("Section", "Method"),
    ("Section", "Interface"),
    ("Section", "Struct"),
    ("Section", "Enum"),
    ("Section", "Trait"),
    ("Section", "Module"),
    ("Function", "Section"),
    ("Class", "Section"),
    ("Method", "Section"),
    ("Interface", "Section"),
    ("Struct", "Section"),
    ("Enum", "Section"),
    ("Trait", "Section"),
    ("Module", "Section"),
    ("Community", "Community"),
    # Section/Property/File can be community members and process participants
    ("Section", "Community"),
    ("Section", "Process"),
    ("Property", "Community"),
    ("Property", "Process"),
    ("File", "Community"),
    ("File", "Process"),
]


def _build_rel_schema_query() -> str:
    """Build the CREATE REL TABLE statement for CodeRelation.

    KuzuDB requires every valid (FROM label, TO label) combination to be
    declared explicitly.
    """
    seen: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[str, str]] = []
    for pair in _REL_FROM_TO_PAIRS:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)

    def _esc(name: str) -> str:
        return f"`{name}`" if name in BACKTICK_TABLES else name

    from_to_clause = ", ".join(
        f"FROM {_esc(src)} TO {_esc(dst)}" for src, dst in unique_pairs
    )

    return (
        f"CREATE REL TABLE CodeRelation ("
        f"{from_to_clause}, "
        f"id STRING, type STRING, confidence DOUBLE, reason STRING, step STRING, "
        f"inCycle BOOLEAN"
        f")"
    )


REL_SCHEMA_QUERY: str = _build_rel_schema_query()


EMBEDDING_SCHEMA_QUERY: str = (
    "CREATE NODE TABLE CodeEmbedding ("
    "id STRING, nodeId STRING, name STRING, label STRING, filePath STRING, "
    f"startLine INT64, endLine INT64, embedding DOUBLE[{EMBEDDING_DIMS}], "
    "PRIMARY KEY (id))"
)


FTS_INDEXES: list[tuple[str, str, list[str]]] = [
    ("file_fts", "File", ["searchText", "content"]),
    ("function_fts", "Function", ["searchText", "content"]),
    ("class_fts", "Class", ["searchText", "content"]),
    ("method_fts", "Method", ["searchText", "content"]),
    ("interface_fts", "Interface", ["searchText", "content"]),
    ("section_fts", "Section", ["searchText", "content"]),
    ("struct_fts", "`Struct`", ["searchText", "content"]),
    ("enum_fts", "`Enum`", ["searchText", "content"]),
    ("trait_fts", "`Trait`", ["searchText", "content"]),
    ("const_fts", "`Const`", ["searchText", "content"]),
    ("record_fts", "`Record`", ["searchText", "content"]),
]


def escape_table_name(name: str) -> str:
    """Wrap *name* in backticks if it is a reserved/ambiguous identifier.

    >>> escape_table_name("File")
    'File'
    >>> escape_table_name("Struct")
    '`Struct`'
    """
    if name in BACKTICK_TABLES:
        return f"`{name}`"
    return name


def get_node_csv_columns(label: str) -> list[str]:
    """Return the ordered column names for *label*'s CSV export.

    >>> get_node_csv_columns("File")
    ['id', 'name', 'filePath', 'content']
    >>> get_node_csv_columns("Method")
    ['id', 'name', 'filePath', 'startLine', 'endLine', 'isExported', 'content', 'description', 'parameterCount', 'returnType']
    """
    raw = _columns_for(label)
    columns: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        col_name = part.split()[0]
        columns.append(col_name)
    return columns
