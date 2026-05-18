from dataclasses import dataclass
from typing import ClassVar


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
