"""3-tier name resolution engine.

Port of GitNexus ingestion/resolution-context.ts.

Resolution tiers (highest confidence first):
1. same-file   — exact match in the same file (confidence 0.95)
2. import-scoped — found via import chain (confidence 0.9)
3. global      — found anywhere in the repo (confidence 0.5)
"""

from __future__ import annotations

from dataclasses import dataclass

from .symbol_table import SymbolDefinition, SymbolTable

TIER_CONFIDENCE = {
    "same-file": 0.95,
    "import-scoped": 0.9,
    "global": 0.5,
}


@dataclass
class TieredCandidates:
    candidates: list[SymbolDefinition]
    tier: str

    @property
    def confidence(self) -> float:
        return TIER_CONFIDENCE.get(self.tier, 0.5)


@dataclass
class NamedImportBinding:
    source_path: str
    exported_name: str


class ResolutionContext:
    """Cross-file name resolution with import awareness."""

    def __init__(self) -> None:
        self.symbols = SymbolTable()
        self.import_map: dict[str, set[str]] = {}
        self.package_map: dict[str, set[str]] = {}
        self.named_import_map: dict[str, dict[str, NamedImportBinding]] = {}
        self._cache: dict[str, dict[str, TieredCandidates | None]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def resolve(self, name: str, from_file: str) -> TieredCandidates | None:
        """Resolve a symbol name from a file context.

        Returns the highest-confidence match, or None if not found.
        """
        file_cache = self._cache.get(from_file)
        if file_cache is not None and name in file_cache:
            self._cache_hits += 1
            return file_cache[name]

        self._cache_misses += 1
        result = self._resolve_uncached(name, from_file)

        if from_file not in self._cache:
            self._cache[from_file] = {}
        self._cache[from_file][name] = result
        return result

    def _resolve_uncached(self, name: str, from_file: str) -> TieredCandidates | None:
        """Internal resolution without caching."""
        defs = self.symbols.lookup_exact_all(from_file, name)
        if defs:
            return TieredCandidates(candidates=defs, tier="same-file")

        bindings = self.named_import_map.get(from_file)
        if bindings and name in bindings:
            binding = bindings[name]
            defs = self.symbols.lookup_exact_all(
                binding.source_path, binding.exported_name
            )
            if defs:
                return TieredCandidates(candidates=defs, tier="import-scoped")

        imported_files = self.import_map.get(from_file, set())
        for imp_file in imported_files:
            defs = self.symbols.lookup_exact_all(imp_file, name)
            if defs:
                return TieredCandidates(candidates=defs, tier="import-scoped")

        defs = self.symbols.lookup_fuzzy(name)
        if defs:
            return TieredCandidates(candidates=defs, tier="global")

        return None

    def enable_cache(self, file_path: str) -> None:
        """Pre-initialize the cache for a file."""
        if file_path not in self._cache:
            self._cache[file_path] = {}

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()

    def get_stats(self) -> dict:
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
        }

    def clear(self) -> None:
        """Release all memory."""
        self.symbols.clear()
        self.import_map.clear()
        self.package_map.clear()
        self.named_import_map.clear()
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
