"""CSV generator for KuzuDB bulk loading.

Generates per-table CSV files from the in-memory ``KnowledgeGraph``
so that KuzuDB can ingest them via ``COPY ... FROM``.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field, is_dataclass

from graph.core.knowledge_graph import KnowledgeGraph
from graph.model.types import GraphNode

MAX_FILE_CONTENT = 10_000
MAX_SNIPPET = 50_000


_SNAKE_TO_CAMEL: dict[str, str] = {
    "file_path": "filePath",
    "start_line": "startLine",
    "end_line": "endLine",
    "is_exported": "isExported",
    "return_type": "returnType",
    "heuristic_label": "heuristicLabel",
    "symbol_count": "symbolCount",
    "process_type": "processType",
    "step_count": "stepCount",
    "entry_point_id": "entryPointId",
    "terminal_id": "terminalId",
    "parameter_count": "parameterCount",
    "signature": "signature",
    "fan_in": "fanIn",
    "in_cycle": "inCycle",
}


_FILE_COLS = (
    "id",
    "name",
    "searchText",
    "filePath",
    "content",
    "fanIn",
    "lineCount",
    "binary",
)
_FOLDER_COLS = ("id", "name", "filePath")

_CODE_SYMBOL_COLS = (
    "id",
    "name",
    "searchText",
    "filePath",
    "startLine",
    "endLine",
    "isExported",
    "content",
    "description",
    "parameterCount",
    "returnType",
    "signature",
    "fanIn",
)

_METHOD_COLS = (
    "id",
    "name",
    "searchText",
    "filePath",
    "startLine",
    "endLine",
    "isExported",
    "content",
    "description",
    "parameterCount",
    "returnType",
    "signature",
    "fanIn",
)

_COMMUNITY_COLS = ("id", "name", "heuristicLabel", "cohesion", "symbolCount")

_PROCESS_COLS = (
    "id",
    "name",
    "heuristicLabel",
    "processType",
    "stepCount",
    "entryPointId",
    "terminalId",
)

_SECTION_COLS = (
    "id",
    "name",
    "searchText",
    "filePath",
    "startLine",
    "endLine",
    "level",
    "content",
    "description",
)

_REL_COLS = ("from", "to", "id", "type", "confidence", "reason", "step", "inCycle")

_CODE_SYMBOL_LABELS = frozenset(
    {
        "Function",
        "Class",
        "Interface",
        "CodeElement",
        "Struct",
        "Enum",
        "Variable",
        "Decorator",
        "Import",
        "Type",
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
        "Project",
        "Package",
        "Module",
    }
)


def _columns_for_label(label: str) -> tuple[str, ...]:
    """Return the CSV column tuple for a given node label."""
    if label == "File":
        return _FILE_COLS
    if label == "Folder":
        return _FOLDER_COLS
    if label == "Method":
        return _METHOD_COLS
    if label == "Community":
        return _COMMUNITY_COLS
    if label == "Process":
        return _PROCESS_COLS
    if label == "Section":
        return _SECTION_COLS
    return _CODE_SYMBOL_COLS


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Matches word boundaries in identifiers:
#   - lowercase run followed by uppercase: useAuth → [use, Auth]
#   - uppercase run followed by uppercase+lowercase: HTMLParser → [HTML, Parser]
#   - digits as separate tokens: get2ndItem → [get, 2nd, Item]
_IDENT_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]|\d+")


def split_identifier(name: str) -> str:
    """Split an identifier into searchable text.

    Returns the original name followed by its lowercase constituent parts.
    This preserves exact-match capability while enabling partial matching.

    >>> split_identifier("useAuth")
    'useAuth use auth'
    >>> split_identifier("AuthGuard")
    'AuthGuard auth guard'
    >>> split_identifier("get_user_by_id")
    'get_user_by_id get user by id'
    >>> split_identifier("HTMLParser")
    'HTMLParser html parser'
    >>> split_identifier("my-component")
    'my-component my component'
    >>> split_identifier("")
    ''
    """
    if not name:
        return ""

    # First split on underscores and hyphens
    segments = re.split(r"[_\-./]", name)

    parts: list[str] = []
    for segment in segments:
        if not segment:
            continue
        matches = _IDENT_RE.findall(segment)
        if matches:
            parts.extend(matches)
        else:
            parts.append(segment)

    if not parts:
        return name

    lowercase_parts = " ".join(p.lower() for p in parts)
    return f"{name} {lowercase_parts}"


@dataclass
class GeneratedCSVs:
    """Result of :func:`generate_csvs`."""

    files: dict[str, str] = field(default_factory=dict)
    """Mapping of table name -> absolute CSV path."""

    row_counts: dict[str, int] = field(default_factory=dict)
    """Mapping of table name -> number of data rows written."""


def escape_csv_field(value: object) -> str:
    """RFC 4180 field escaping.

    * ``None`` / empty → ``""``
    * Booleans → ``"true"`` / ``"false"``
    * Strips control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)
    * Wraps in double-quotes if the value contains comma, double-quote,
      newline, or carriage return; internal quotes are doubled.
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    text = str(value)
    if text == "" or text == "None":
        return ""

    text = _CONTROL_CHARS_RE.sub("", text)

    if any(ch in text for ch in (",", '"', "\n", "\r")):
        text = '"' + text.replace('"', '""') + '"'

    return text


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate *text* to *max_len* characters; ``None`` → ``""``."""
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _get_node_props(node: GraphNode) -> dict[str, object]:
    """Extract node properties as a flat dict with **camelCase** keys.

    Handles both ``NodeProperties`` dataclass and plain ``dict`` cases.
    """
    props: dict[str, object]

    if is_dataclass(node.properties) and not isinstance(node.properties, type):
        raw = asdict(node.properties)
        extra = raw.pop("_extra", None) or {}
        props = {}
        for key, val in raw.items():
            if key.startswith("_"):
                continue
            camel = _SNAKE_TO_CAMEL.get(key, key)
            props[camel] = val
        # Flatten _extra keys (lineCount, binary, etc.) into the output
        for key, val in extra.items():
            props[key] = val
    elif isinstance(node.properties, dict):
        props = dict(node.properties)
    else:
        props = {}

    return props


def generate_csvs(
    graph: KnowledgeGraph,
    output_dir: str,
) -> GeneratedCSVs:
    """Generate per-table CSV files for KuzuDB bulk loading.

    Parameters
    ----------
    graph:
        The in-memory knowledge graph to export.
    output_dir:
        Directory where CSV files will be written. Created if absent.

    Returns
    -------
    GeneratedCSVs
        Paths and row counts for every generated CSV.
    """
    os.makedirs(output_dir, exist_ok=True)

    result = GeneratedCSVs()

    groups: dict[str, list[GraphNode]] = {}
    for node in graph.iter_nodes():
        label = str(node.label)
        groups.setdefault(label, []).append(node)

    for label, nodes in groups.items():
        columns = _columns_for_label(label)
        csv_path = os.path.join(output_dir, f"{label}.csv")

        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(columns) + "\n")

            row_count = 0
            for node in nodes:
                props = _get_node_props(node)
                row_values: list[str] = []
                for col in columns:
                    if col == "id":
                        raw_val: object = node.id
                    elif col == "searchText":
                        raw_val = split_identifier(str(props.get("name") or ""))
                    elif col == "content":
                        max_len = MAX_FILE_CONTENT if label == "File" else MAX_SNIPPET
                        raw_val = _truncate(
                            props.get("content"),  # type: ignore[arg-type]
                            max_len,
                        )
                    else:
                        raw_val = props.get(col)
                    row_values.append(escape_csv_field(raw_val))
                fh.write(",".join(row_values) + "\n")
                row_count += 1

        result.files[label] = os.path.abspath(csv_path)
        result.row_counts[label] = row_count

    rel_path = os.path.join(output_dir, "CodeRelation.csv")
    with open(rel_path, "w", newline="", encoding="utf-8") as fh:
        fh.write(",".join(_REL_COLS) + "\n")

        rel_count = 0
        for rel in graph.iter_relationships():
            row_values = [
                escape_csv_field(rel.source_id),
                escape_csv_field(rel.target_id),
                escape_csv_field(rel.id),
                escape_csv_field(str(rel.type)),
                escape_csv_field(rel.confidence),
                escape_csv_field(rel.reason),
                escape_csv_field(rel.step),
                escape_csv_field(rel.in_cycle),
            ]
            fh.write(",".join(row_values) + "\n")
            rel_count += 1

    result.files["CodeRelation"] = os.path.abspath(rel_path)
    result.row_counts["CodeRelation"] = rel_count

    return result
