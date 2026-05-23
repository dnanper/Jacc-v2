"""Symbol table — 4-index registry for name resolution.

Port of GitNexus ingestion/symbol-table.ts.

Four indexes:
1. file_index    — per-file exact lookup: file_path → name → [SymbolDefinition]
2. global_index  — name-based fuzzy lookup: name → [SymbolDefinition]
3. callable_index — lazy-built callable-only: name → [SymbolDefinition]
4. field_by_owner — O(1) property lookup: owner_id\\0field_name → SymbolDefinition
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SymbolDefinition:
    """Metadata about a resolved symbol."""

    node_id: str
    file_path: str
    name: str
    type: str
    parameter_count: int | None = None
    required_parameter_count: int | None = None
    parameter_types: list[str] | None = None
    return_type: str | None = None
    declared_type: str | None = None
    owner_id: str | None = None


class SymbolTable:
    """Multi-index symbol registry for resolution context."""

    def __init__(self) -> None:
        self._file_index: dict[str, dict[str, list[SymbolDefinition]]] = {}
        self._global_index: dict[str, list[SymbolDefinition]] = {}
        self._callable_index: dict[str, list[SymbolDefinition]] | None = None
        self._field_by_owner: dict[str, SymbolDefinition] = {}

    def add(
        self,
        file_path: str,
        name: str,
        node_id: str,
        symbol_type: str,
        *,
        parameter_count: int | None = None,
        required_parameter_count: int | None = None,
        parameter_types: list[str] | None = None,
        return_type: str | None = None,
        declared_type: str | None = None,
        owner_id: str | None = None,
    ) -> None:
        """Register a new symbol in all applicable indexes."""
        defn = SymbolDefinition(
            node_id=node_id,
            file_path=file_path,
            name=name,
            type=symbol_type,
            parameter_count=parameter_count,
            required_parameter_count=required_parameter_count,
            parameter_types=parameter_types,
            return_type=return_type,
            declared_type=declared_type,
            owner_id=owner_id,
        )

        file_map = self._file_index.setdefault(file_path, {})
        file_map.setdefault(name, []).append(defn)

        if symbol_type != "Property":
            self._global_index.setdefault(name, []).append(defn)

        if owner_id and symbol_type in ("Property", "Method", "Constructor"):
            key = f"{owner_id}\0{name}"
            if key not in self._field_by_owner:
                self._field_by_owner[key] = defn

        self._callable_index = None

    def lookup_exact(self, file_path: str, name: str) -> str | None:
        """File-local exact lookup — returns node_id or None."""
        file_map = self._file_index.get(file_path)
        if file_map is None:
            return None
        defs = file_map.get(name)
        if not defs:
            return None
        return defs[0].node_id

    def lookup_exact_full(self, file_path: str, name: str) -> SymbolDefinition | None:
        """File-local exact lookup — returns full SymbolDefinition."""
        file_map = self._file_index.get(file_path)
        if file_map is None:
            return None
        defs = file_map.get(name)
        return defs[0] if defs else None

    def lookup_exact_all(self, file_path: str, name: str) -> list[SymbolDefinition]:
        """All overloads of a name in a specific file."""
        file_map = self._file_index.get(file_path)
        if file_map is None:
            return []
        return file_map.get(name, [])

    def lookup_fuzzy(self, name: str) -> list[SymbolDefinition]:
        """Global search by symbol name (low confidence)."""
        return self._global_index.get(name, [])

    def lookup_fuzzy_callable(self, name: str) -> list[SymbolDefinition]:
        """Cached callable-only global search (Function/Method/Constructor)."""
        if self._callable_index is None:
            self._callable_index = {}
            callable_types = {"Function", "Method", "Constructor"}
            for sym_name, defs in self._global_index.items():
                callables = [d for d in defs if d.type in callable_types]
                if callables:
                    self._callable_index[sym_name] = callables
        return self._callable_index.get(name, [])

    def lookup_field_by_owner(
        self, owner_id: str, field_name: str
    ) -> SymbolDefinition | None:
        """O(1) property lookup via owner class ID."""
        return self._field_by_owner.get(f"{owner_id}\0{field_name}")

    def get_stats(self) -> dict:
        """Return file/symbol counts."""
        total_symbols = sum(
            len(defs)
            for file_map in self._file_index.values()
            for defs in file_map.values()
        )
        return {
            "files": len(self._file_index),
            "symbols": total_symbols,
            "global_names": len(self._global_index),
        }

    def clear(self) -> None:
        """Release all memory."""
        self._file_index.clear()
        self._global_index.clear()
        self._callable_index = None
        self._field_by_owner.clear()
