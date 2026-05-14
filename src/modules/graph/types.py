"""Core type definitions for CSG knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class NodeLabel(StrEnum):
    """All node labels in the knowledge graph."""

    PROJECT = "Project"
    PACKAGE = "Package"
    MODULE = "Module"
    FOLDER = "Folder"
    FILE = "File"

    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"
    VARIABLE = "Variable"
    INTERFACE = "Interface"
    ENUM = "Enum"
    DECORATOR = "Decorator"
    IMPORT = "Import"
    TYPE = "Type"
    CODE_ELEMENT = "CodeElement"

    COMMUNITY = "Community"
    PROCESS = "Process"

    STRUCT = "Struct"
    MACRO = "Macro"
    TYPEDEF = "Typedef"
    UNION = "Union"
    NAMESPACE = "Namespace"
    TRAIT = "Trait"
    IMPL = "Impl"
    TYPE_ALIAS = "TypeAlias"
    CONST = "Const"
    STATIC = "Static"
    PROPERTY = "Property"
    RECORD = "Record"
    DELEGATE = "Delegate"
    ANNOTATION = "Annotation"
    CONSTRUCTOR = "Constructor"
    TEMPLATE = "Template"

    SECTION = "Section"


class RelationshipType(StrEnum):
    """All relationship types in the knowledge graph."""

    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    OVERRIDES = "OVERRIDES"
    IMPORTS = "IMPORTS"
    USES = "USES"
    DEFINES = "DEFINES"
    DECORATES = "DECORATES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    HAS_METHOD = "HAS_METHOD"
    HAS_PROPERTY = "HAS_PROPERTY"
    ACCESSES = "ACCESSES"
    MEMBER_OF = "MEMBER_OF"
    STEP_IN_PROCESS = "STEP_IN_PROCESS"
    DESCRIBES = "DESCRIBES"
    DOCUMENTED_BY = "DOCUMENTED_BY"
    COMMUNITY_INTERACTS = "COMMUNITY_INTERACTS"


@dataclass
class NodeProperties:
    """Properties attached to every graph node."""

    name: str = ""
    file_path: str = ""
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None
    is_exported: bool | None = None
    content: str | None = None
    description: str | None = None
    return_type: str | None = None

    ast_framework_multiplier: float | None = None
    ast_framework_reason: str | None = None

    heuristic_label: str | None = None
    cohesion: float | None = None
    symbol_count: int | None = None
    keywords: list[str] | None = None
    enriched_by: str | None = None

    process_type: str | None = None
    step_count: int | None = None
    communities: list[str] | None = None
    entry_point_id: str | None = None
    terminal_id: str | None = None

    entry_point_score: float | None = None
    entry_point_reason: str | None = None

    parameter_count: int | None = None
    signature: str | None = None

    fan_in: int | None = None
    fan_out: int | None = None
    schema_entities: list[str] | None = None

    level: int | None = None

    _extra: dict | None = None

    _CAMEL_MAP: ClassVar[dict[str, str]] = {
        "isExported": "is_exported",
        "filePath": "file_path",
        "startLine": "start_line",
        "endLine": "end_line",
        "returnType": "return_type",
        "heuristicLabel": "heuristic_label",
        "symbolCount": "symbol_count",
        "processType": "process_type",
        "stepCount": "step_count",
        "entryPointId": "entry_point_id",
        "terminalId": "terminal_id",
        "entryPointScore": "entry_point_score",
        "entryPointReason": "entry_point_reason",
        "parameterCount": "parameter_count",
        "signature": "signature",
        "fanIn": "fan_in",
        "fanOut": "fan_out",
        "schemaEntities": "schema_entities",
        "enrichedBy": "enriched_by",
        "astFrameworkMultiplier": "ast_framework_multiplier",
        "astFrameworkReason": "ast_framework_reason",
    }

    def get(self, key: str, default=None):
        """Dict-compatible access for properties, supporting camelCase aliases."""
        resolved = self._CAMEL_MAP.get(key, key)
        if hasattr(self, resolved) and resolved != "_extra":
            val = getattr(self, resolved)
            return val if val is not None else default
        if self._extra and key in self._extra:
            return self._extra[key]
        return default


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    id: str
    label: NodeLabel
    properties: NodeProperties


@dataclass
class GraphRelationship:
    """A relationship (edge) in the knowledge graph."""

    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    confidence: float = 1.0
    reason: str = ""
    step: int | None = None
    in_cycle: bool | None = None


@dataclass
class PipelineProgress:
    """Progress update from the analysis pipeline."""

    phase: str
    percent: int
    message: str
    detail: str | None = None
    stats: dict | None = None


@dataclass
class PipelineResult:
    """Result of a completed analysis pipeline run."""

    node_count: int
    relationship_count: int
    file_count: int
    community_count: int
    process_count: int
    duration_ms: int
    embedding_count: int = 0
