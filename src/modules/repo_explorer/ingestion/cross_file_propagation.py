"""Cross-file binding propagation — Phase 14.

Port of GitNexus ingestion/cross-file-propagation.ts.

After initial call resolution, many cross-file member calls remain unresolved
because receiver types were unknown. This phase:
1. Topologically sorts files by import order.
2. Expands wildcard imports for Go/Ruby/C/C++/Swift.
3. Seeds receiver_type_name on member calls using import bindings.
4. Re-runs call resolution level-by-level so downstream files benefit from
   upstream type information.

This module MUTATES the graph (adds new CALLS edges) and mutates calls
(sets receiver_type_name). It does NOT remove existing edges.
"""

from __future__ import annotations

from collections import defaultdict, deque
from math import ceil

from ..config import get_language_from_filename
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import RelationshipType
from .call_processor import process_calls
from .infile_processor import ExtractedCall
from .resolution_context import (
    NamedImportBinding,
    ResolutionContext,
)
from .symbol_table import SymbolTable

CROSS_FILE_SKIP_THRESHOLD = 0.03
MAX_CROSS_FILE_REPROCESS = 2000
MAX_SYNTHETIC_BINDINGS_PER_FILE = 1000
MAX_EXPORTS_PER_FILE = 500
MAX_TYPE_NAME_LENGTH = 256

WILDCARD_IMPORT_LANGUAGES = frozenset({"go", "ruby", "c", "cpp", "swift"})

IMPORTABLE_SYMBOL_LABELS = frozenset(
    {
        "Function",
        "Class",
        "Interface",
        "Struct",
        "Enum",
        "Trait",
        "TypeAlias",
        "Const",
        "Static",
        "Record",
        "Union",
        "Typedef",
        "Macro",
    }
)

TYPE_NAMED_SYMBOL_LABELS = frozenset(
    {
        "Class",
        "Interface",
        "Struct",
        "Enum",
        "Trait",
        "TypeAlias",
        "Record",
        "Union",
        "Typedef",
    }
)


def topological_level_sort(
    import_map: dict[str, set[str]],
) -> tuple[list[list[str]], int, list[tuple[str, str]]]:
    """Kahn's BFS algorithm on the import graph.

    Returns ``(levels, cycle_count, cycle_edges)`` where *levels* is a list of
    lists — each inner list contains files that can be processed in parallel —
    *cycle_count* is the number of files trapped in import cycles, and
    *cycle_edges* is the list of ``(source, target)`` IMPORTS edges that
    participate in the cycles.
    """
    all_files: set[str] = set(import_map.keys())
    for deps in import_map.values():
        all_files.update(deps)

    in_degree: dict[str, int] = {f: 0 for f in all_files}
    reverse_deps: dict[str, set[str]] = defaultdict(set)

    for file, deps in import_map.items():
        for dep in deps:
            in_degree[file] = in_degree.get(file, 0) + 1
            reverse_deps[dep].add(file)

    queue = deque(f for f, deg in in_degree.items() if deg == 0)

    levels: list[list[str]] = []
    while queue:
        level = list(queue)
        levels.append(level)
        next_queue: deque[str] = deque()
        for file in level:
            for dependent in reverse_deps.get(file, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)
        queue = next_queue

    cycle_files_set = {f for f, deg in in_degree.items() if deg > 0}
    cycle_count = len(cycle_files_set)

    cycle_edges: list[tuple[str, str]] = []
    if cycle_files_set:
        for file in cycle_files_set:
            for dep in import_map.get(file, set()):
                if dep in cycle_files_set:
                    cycle_edges.append((file, dep))
        levels.append(list(cycle_files_set))

    return levels, cycle_count, cycle_edges


def build_exported_type_map(
    graph: KnowledgeGraph,
    symbols: SymbolTable,
) -> dict[str, dict[str, str]]:
    """Build file -> {symbol_name -> type_name} for exported definition nodes.

    ``type_name`` is resolved as: return_type > declared_type > node.label.
    """
    result: dict[str, dict[str, str]] = {}

    for node in graph.iter_nodes():
        label = node.label
        if label not in IMPORTABLE_SYMBOL_LABELS:
            continue

        props = node.properties

        is_exported = props.get("is_exported")
        name = props.get("name", "")
        file_path = props.get("file_path", "")

        if not is_exported:
            continue
        if not name or len(name) > MAX_TYPE_NAME_LENGTH:
            continue

        file_map = result.get(file_path)
        if file_map is not None and len(file_map) >= MAX_EXPORTS_PER_FILE:
            continue

        sym = symbols.lookup_exact_full(file_path, name)
        if sym is not None:
            type_name = (
                sym.return_type
                or sym.declared_type
                or (name if str(label) in TYPE_NAMED_SYMBOL_LABELS else str(label))
            )
        else:
            type_name = name if str(label) in TYPE_NAMED_SYMBOL_LABELS else str(label)

        if file_path not in result:
            result[file_path] = {}
        result[file_path][name] = type_name

    return result


def synthesize_wildcard_import_bindings(
    graph: KnowledgeGraph,
    ctx: ResolutionContext,
) -> int:
    """Expand whole-module imports for Go/Ruby/C/C++/Swift.

    For languages that import an entire module (no named imports), we
    synthesize a ``NamedImportBinding`` for each exported symbol in the
    imported file so that the resolution context can find them.

    Returns the total number of synthetic bindings created.
    """
    exported_symbols_by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in graph.iter_nodes():
        label = node.label
        if label not in IMPORTABLE_SYMBOL_LABELS:
            continue
        props = node.properties
        is_exported = props.get("is_exported")
        name = props.get("name", "")
        file_path = props.get("file_path", "")

        if is_exported and name:
            exported_symbols_by_file[file_path].append(
                {
                    "name": name,
                    "node_id": node.id,
                }
            )

    total_synthesized = 0

    for file_path, imported_files in ctx.import_map.items():
        lang = get_language_from_filename(file_path)
        if lang is None or lang.value not in WILDCARD_IMPORT_LANGUAGES:
            continue

        existing_bindings = ctx.named_import_map.get(file_path, {})
        count = len(existing_bindings)

        for imported_file in imported_files:
            for sym in exported_symbols_by_file.get(imported_file, []):
                sym_name = sym["name"]
                if sym_name in existing_bindings:
                    continue
                if count >= MAX_SYNTHETIC_BINDINGS_PER_FILE:
                    break

                if file_path not in ctx.named_import_map:
                    ctx.named_import_map[file_path] = {}
                ctx.named_import_map[file_path][sym_name] = NamedImportBinding(
                    source_path=imported_file,
                    exported_name=sym_name,
                )
                existing_bindings = ctx.named_import_map[file_path]
                count += 1
                total_synthesized += 1

    return total_synthesized


def seed_cross_file_receiver_types(
    calls: list[ExtractedCall],
    named_import_map: dict[str, dict[str, NamedImportBinding]],
    exported_type_map: dict[str, dict[str, str]],
) -> int:
    """Fill missing ``receiver_type_name`` on member calls using import bindings.

    Returns the number of calls enriched.
    """
    enriched = 0

    for call in calls:
        if call.receiver_type_name:
            continue
        if call.receiver_name is None:
            continue
        if call.call_form != "member":
            continue

        file_imports = named_import_map.get(call.file_path, {})
        binding = file_imports.get(call.receiver_name)
        if binding is None:
            continue

        upstream = exported_type_map.get(binding.source_path, {})
        type_name = upstream.get(binding.exported_name)
        if type_name:
            call.receiver_type_name = type_name
            enriched += 1

    return enriched


def build_imported_return_types(
    file_path: str,
    named_import_map: dict[str, dict[str, NamedImportBinding]],
    symbols: SymbolTable,
) -> dict[str, str]:
    """Map local import names to their return types (from the exporting file).

    Returns ``{local_name: return_type}`` for each binding whose upstream
    symbol has a non-None ``return_type``.
    """
    result: dict[str, str] = {}

    bindings = named_import_map.get(file_path, {})
    for local_name, binding in bindings.items():
        sym = symbols.lookup_exact_full(binding.source_path, binding.exported_name)
        if sym is None:
            continue
        if hasattr(sym, "return_type") and sym.return_type is not None:
            result[local_name] = sym.return_type

    return result


def build_imported_raw_return_types(
    file_path: str,
    named_import_map: dict[str, dict[str, NamedImportBinding]],
    symbols: SymbolTable,
) -> dict[str, str]:
    """Map local import names to their raw (unwrapped) return types.

    Similar to ``build_imported_return_types`` but returns the raw return
    type string (e.g. ``Promise<User>`` becomes ``User``).
    """
    result: dict[str, str] = {}

    bindings = named_import_map.get(file_path, {})
    for local_name, binding in bindings.items():
        sym = symbols.lookup_exact_full(binding.source_path, binding.exported_name)
        if sym is None:
            continue
        raw = getattr(sym, "raw_return_type", None) or getattr(sym, "return_type", None)
        if raw is not None:
            result[local_name] = raw

    return result


def mark_import_cycle_edges(
    graph: KnowledgeGraph,
    cycle_edges: list[tuple[str, str]],
) -> int:
    """Mark IMPORTS relationships that participate in import cycles.

    ``cycle_edges`` contains ``(source_file_path, target_file_path)`` pairs
    returned by ``topological_level_sort``.
    """
    cycle_edges_set = set(cycle_edges)
    if not cycle_edges_set:
        return 0

    marked = 0
    for rel in graph.iter_relationships():
        if rel.type != RelationshipType.IMPORTS:
            continue
        src_node = graph.get_node(rel.source_id)
        tgt_node = graph.get_node(rel.target_id)
        if src_node is None or tgt_node is None:
            continue

        src_path = src_node.properties.file_path
        tgt_path = tgt_node.properties.file_path
        if (src_path, tgt_path) in cycle_edges_set:
            rel.in_cycle = True
            marked += 1

    return marked


def run_cross_file_propagation_phase(
    graph: KnowledgeGraph,
    calls: list[ExtractedCall],
    ctx: ResolutionContext,
    type_envs: dict | None,
    file_contents: dict[str, str] | None = None,
    repo_path: str | None = None,
) -> dict:
    """Run cross-file propagation and mark cycle IMPORTS edges.

    This is the phase-level entry point for pipeline code: callers get the
    propagation stats and the graph mutation in one function call.
    """
    result = run_cross_file_propagation(
        graph=graph,
        calls=calls,
        ctx=ctx,
        type_envs=type_envs,
        file_contents=file_contents,
        repo_path=repo_path,
    )
    marked = mark_import_cycle_edges(graph, result.get("cycle_edges", []))
    return {**result, "marked_cycle_edges": marked}


def run_cross_file_propagation(
    graph: KnowledgeGraph,
    calls: list[ExtractedCall],
    ctx: ResolutionContext,
    type_envs: dict | None,
    file_contents: dict[str, str] | None,
    repo_path: str | None = None,
) -> dict:
    """Run the full cross-file binding propagation phase.

    Parameters
    ----------
    graph:
        Knowledge graph to mutate (adds new CALLS edges).
    calls:
        Extracted call records from parsing.
    ctx:
        Resolution context (symbols, import_map, named_import_map populated).
    type_envs:
        Per-file TypeEnv for receiver type resolution (may be None).
    file_contents:
        ``file_path -> content`` mapping (may be None).
    repo_path:
        Repository root path, used to read files if *file_contents* is None.

    Returns
    -------
    dict with keys: reprocessed_files, seeded_calls, synthetic_bindings, cycles.
    """
    empty_stats: dict = {
        "reprocessed_files": 0,
        "seeded_calls": 0,
        "synthetic_bindings": 0,
        "cycles": 0,
        "cycle_edges": [],
    }

    exported_type_map = build_exported_type_map(graph, ctx.symbols)
    if not exported_type_map:
        return empty_stats

    levels, cycle_count, cycle_edges = topological_level_sort(ctx.import_map)
    total_files = sum(len(level) for level in levels)
    if total_files == 0:
        return {**empty_stats, "cycles": cycle_count, "cycle_edges": cycle_edges}

    gap_count = 0
    for level in levels:
        for file_path in level:
            bindings = ctx.named_import_map.get(file_path, {})
            has_gap = False
            for _local_name, binding in bindings.items():
                upstream = exported_type_map.get(binding.source_path, {})
                if binding.exported_name in upstream:
                    has_gap = True
                    break
                sym = ctx.symbols.lookup_exact_full(
                    binding.source_path,
                    binding.exported_name,
                )
                if sym is not None and sym.return_type is not None:
                    has_gap = True
                    break
            if has_gap:
                gap_count += 1

    threshold_count = max(1, ceil(total_files * CROSS_FILE_SKIP_THRESHOLD))
    if (
        gap_count / total_files < CROSS_FILE_SKIP_THRESHOLD
        and gap_count < threshold_count
    ):
        return {**empty_stats, "cycles": cycle_count, "cycle_edges": cycle_edges}

    synthesized = synthesize_wildcard_import_bindings(graph, ctx)

    seeded = seed_cross_file_receiver_types(
        calls,
        ctx.named_import_map,
        exported_type_map,
    )

    reprocessed = 0
    enriched_type_envs = dict(type_envs) if type_envs else {}

    for level in levels:
        for file_path in level:
            if reprocessed >= MAX_CROSS_FILE_REPROCESS:
                break

            bindings = ctx.named_import_map.get(file_path, {})
            seeded_bindings: dict[str, str] = {}
            for local_name, binding in bindings.items():
                upstream = exported_type_map.get(binding.source_path, {})
                type_name = upstream.get(binding.exported_name)
                if type_name:
                    seeded_bindings[local_name] = type_name

            imported_returns = build_imported_return_types(
                file_path,
                ctx.named_import_map,
                ctx.symbols,
            )

            if not seeded_bindings and not imported_returns:
                continue

            file_calls = [c for c in calls if c.file_path == file_path]
            if not file_calls:
                continue

            original_env = enriched_type_envs.get(file_path)
            if original_env is not None:
                from .extraction.type_env import TypeEnv

                enriched = (
                    original_env.clone()
                    if hasattr(original_env, "clone")
                    else TypeEnv()
                )
            else:
                from .extraction.type_env import TypeEnv

                enriched = TypeEnv()

            if seeded_bindings:
                enriched.seed(seeded_bindings)

            if imported_returns:
                enriched.seed_return_types(imported_returns)

            enriched_type_envs[file_path] = enriched

            if hasattr(ctx, "_cache"):
                ctx._cache.pop(file_path, None)

            process_calls(graph, file_calls, ctx, type_envs=enriched_type_envs)
            reprocessed += 1

        if reprocessed >= MAX_CROSS_FILE_REPROCESS:
            break

    return {
        "reprocessed_files": reprocessed,
        "seeded_calls": seeded,
        "synthetic_bindings": synthesized,
        "cycles": cycle_count,
        "cycle_edges": cycle_edges,
    }
