"""Linear ingestion pipeline for repo_explorer.

This module composes the processor files in ``repo_explorer.ingestion`` without
LangGraph. Each phase is a plain function that accepts and updates a shared
``PipelineState``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import get_language_from_filename
from ..discovery.filesystem_walker import read_file_contents, walk_repository_paths
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..parsing.ast_cache import ASTCache
from .call_processor import process_calls
from .community_processor import run_community_detection_phase
from .cross_file_propagation import run_cross_file_propagation_phase
from .extraction.import_resolvers.utils import SuffixIndex
from .extraction.language_config import load_import_configs
from .heritage_processor import process_heritage
from .import_processor import process_imports
from .index_loader import create_lbug_indexes
from .infile_processor import process_infile_information
from .lbug_loader import load_graph_to_lbug
from .mro_processor import compute_mro
from .process_processor import run_process_detection_phase
from .state import (
    PipelineConfig,
    PipelineProgress,
    PipelineState,
    check_cancelled,
)
from .structure_processor import process_structure
from .support.resolution_context import ResolutionContext
from .support.symbol_table import SymbolTable

logger = logging.getLogger(__name__)


def _progress(
    state: PipelineState,
    phase: str,
    phase_index: int,
    message: str,
    *,
    percent: int | None = None,
) -> PipelineProgress:
    total_phases = 12 if state.get("config", PipelineConfig()).persist else 10
    progress = PipelineProgress(
        phase=phase,
        phase_index=phase_index,
        total_phases=total_phases,
        message=message,
        percent=percent
        if percent is not None
        else int((phase_index / total_phases) * 100),
    )
    state["progress"] = progress

    callback = state.get("config", PipelineConfig()).on_progress
    if callback:
        callback(progress, state)
    return progress


def _merge(state: PipelineState, updates: dict) -> PipelineState:
    state.update(updates)
    return state


def discover_files(state: PipelineState) -> dict:
    """Phase 1: scan repository files without loading all contents."""
    check_cancelled(state)
    cfg = state["config"]
    repo_path = Path(cfg.repo_path).resolve()
    scanned = walk_repository_paths(repo_path, exclude_dirs=cfg.exclude_dirs)
    file_paths = [entry.path for entry in scanned]

    return {
        "repo_path": str(repo_path),
        "repo_name": repo_path.name,
        "scanned_files": scanned,
        "file_paths": file_paths,
        "progress": _progress(
            state,
            "discover_files",
            1,
            f"Discovered {len(file_paths)} files",
        ),
    }


def build_structure(state: PipelineState) -> dict:
    """Phase 2: create File/Folder nodes and CONTAINS edges."""
    check_cancelled(state)
    graph = KnowledgeGraph()
    process_structure(
        graph,
        state.get("file_paths", []),
        repo_path=state.get("repo_path", ""),
    )
    return {
        "knowledge_graph": graph,
        "progress": _progress(state, "build_structure", 2, "Structure built"),
    }


def parse_infile(state: PipelineState) -> dict:
    """Phase 3: parse source files and extract in-file records."""
    check_cancelled(state)
    file_paths = state.get("file_paths", [])
    source_paths = [
        path for path in file_paths if get_language_from_filename(path) is not None
    ]
    contents = read_file_contents(state["repo_path"], source_paths)
    source_files = [
        {"path": path, "content": content} for path, content in contents.items()
    ]

    symbol_table = SymbolTable()
    ast_cache = ASTCache()
    parse_result = process_infile_information(
        state["knowledge_graph"],
        source_files,
        symbol_table,
        ast_cache,
    )

    return {
        "source_files": source_files,
        "symbol_table": symbol_table,
        "ast_cache": ast_cache,
        "parse_result": parse_result,
        "imports": parse_result.imports,
        "calls": parse_result.calls,
        "heritage": parse_result.heritage,
        "type_envs": parse_result.type_envs,
        "progress": _progress(
            state,
            "parse_infile",
            3,
            f"Parsed {len(source_files)} source files",
        ),
    }


def resolve_imports(state: PipelineState) -> dict:
    """Phase 4: resolve import records and add IMPORTS edges."""
    check_cancelled(state)
    ctx = ResolutionContext()
    ctx.symbols = state["symbol_table"]
    suffix_index = SuffixIndex(state.get("file_paths", []))

    try:
        import_configs = load_import_configs(state["repo_path"])
    except Exception as exc:
        logger.debug("Failed to load import configs: %s", exc)
        import_configs = None

    process_imports(
        graph=state["knowledge_graph"],
        imports=state.get("imports", []),
        ctx=ctx,
        suffix_index=suffix_index,
        import_configs=import_configs,
    )

    return {
        "resolution_context": ctx,
        "suffix_index": suffix_index,
        "progress": _progress(
            state,
            "resolve_imports",
            4,
            f"Resolved {len(state.get('imports', []))} imports",
        ),
    }


def resolve_calls(state: PipelineState) -> dict:
    """Phase 5: resolve call records and add CALLS edges."""
    check_cancelled(state)
    process_calls(
        graph=state["knowledge_graph"],
        calls=state.get("calls", []),
        ctx=state["resolution_context"],
        type_envs=state.get("type_envs"),
    )
    return {
        "progress": _progress(
            state,
            "resolve_calls",
            5,
            f"Resolved {len(state.get('calls', []))} calls",
        ),
    }


def propagate_cross_file(state: PipelineState) -> dict:
    """Phase 6: propagate cross-file type bindings and mark import cycles."""
    check_cancelled(state)
    result = run_cross_file_propagation_phase(
        graph=state["knowledge_graph"],
        calls=state.get("calls", []),
        ctx=state["resolution_context"],
        type_envs=state.get("type_envs"),
        file_contents=None,
        repo_path=state.get("repo_path"),
    )
    return {
        "cross_file_result": result,
        "cycle_edges": result.get("cycle_edges", []),
        "progress": _progress(
            state,
            "cross_file_propagation",
            6,
            (
                f"Cross-file: {result.get('reprocessed_files', 0)} files, "
                f"{result.get('seeded_calls', 0)} seeded calls"
            ),
        ),
    }


def resolve_heritage(state: PipelineState) -> dict:
    """Phase 7: resolve EXTENDS/IMPLEMENTS relationships."""
    check_cancelled(state)
    process_heritage(
        graph=state["knowledge_graph"],
        heritage_records=state.get("heritage", []),
        ctx=state["resolution_context"],
    )
    return {
        "progress": _progress(
            state,
            "resolve_heritage",
            7,
            f"Resolved {len(state.get('heritage', []))} heritage records",
        ),
    }


def compute_mro_phase(state: PipelineState) -> dict:
    """Phase 8: compute MRO and add OVERRIDES edges."""
    check_cancelled(state)
    result = compute_mro(state["knowledge_graph"])
    return {
        "mro_result": result,
        "progress": _progress(
            state,
            "compute_mro",
            8,
            f"MRO: {result.override_edges} overrides",
        ),
    }


def detect_communities(state: PipelineState) -> dict:
    """Phase 9: detect code communities and enrich graph metadata."""
    check_cancelled(state)
    result = run_community_detection_phase(state["knowledge_graph"])
    return {
        "community_result": result,
        "community_nodes": result["communities"],
        "memberships": result["memberships"],
        "progress": _progress(
            state,
            "detect_communities",
            9,
            f"Found {len(result['communities'])} communities",
        ),
    }


def detect_processes(state: PipelineState) -> dict:
    """Phase 10: detect execution flows from CALLS edges."""
    check_cancelled(state)
    result = run_process_detection_phase(
        knowledge_graph=state["knowledge_graph"],
        memberships=state.get("memberships", []),
    )
    return {
        "process_result": result,
        "process_nodes": result["processes"],
        "process_steps": result["steps"],
        "progress": _progress(
            state,
            "detect_processes",
            10,
            f"Found {len(result['processes'])} processes",
        ),
    }


def load_to_lbug(state: PipelineState) -> dict:
    """Phase 11: persist graph into LadybugDB."""
    check_cancelled(state)
    load_result = load_graph_to_lbug(
        graph=state["knowledge_graph"],
        repo_path=state["repo_path"],
        file_paths=state.get("file_paths", []),
        community_nodes=state.get("community_nodes", []),
        process_nodes=state.get("process_nodes", []),
        force=state["config"].force,
    )
    return {
        "load_result": load_result,
        "stats": load_result.stats,
        "progress": _progress(
            state,
            "load_to_lbug",
            11,
            (
                f"Loaded {load_result.stats['nodes']} nodes, "
                f"{load_result.stats['relationships']} rels"
            ),
        ),
    }


def create_indexes(state: PipelineState) -> dict:
    """Phase 12: create FTS indexes and repo metadata/cache files."""
    check_cancelled(state)
    index_result = create_lbug_indexes(
        repo_path=state["repo_path"],
        stats=state.get("stats", {}),
        state=dict(state),
        save_graph_cache=True,
    )
    return {
        "index_result": index_result,
        "stats": index_result.stats,
        "progress": _progress(
            state,
            "create_indexes",
            12,
            "FTS indexes and repo metadata created",
            percent=100,
        ),
    }


ANALYSIS_PHASES = (
    discover_files,
    build_structure,
    parse_infile,
    resolve_imports,
    resolve_calls,
    propagate_cross_file,
    resolve_heritage,
    compute_mro_phase,
    detect_communities,
    detect_processes,
)

PERSISTENCE_PHASES = (
    load_to_lbug,
    create_indexes,
)


def run_ingestion_pipeline(config: PipelineConfig | str) -> PipelineState:
    """Run the complete currently-implemented ingestion flow.

    Pass a ``PipelineConfig`` for custom options or a repo path string for the
    default persisted flow.
    """
    cfg = PipelineConfig(repo_path=config) if isinstance(config, str) else config
    if not cfg.repo_path:
        raise ValueError("PipelineConfig.repo_path is required")

    state: PipelineState = {
        "config": cfg,
        "progress": PipelineProgress(),
    }

    phases = ANALYSIS_PHASES + (PERSISTENCE_PHASES if cfg.persist else ())
    for phase in phases:
        check_cancelled(state)
        updates = phase(state)
        _merge(state, updates)

    if not cfg.persist:
        graph = state["knowledge_graph"]
        state["stats"] = {
            "nodes": graph.node_count,
            "relationships": graph.relationship_count,
            "files": len(state.get("file_paths", [])),
            "communities": len(state.get("community_nodes", [])),
            "processes": len(state.get("process_nodes", [])),
        }

    return state


def run_analysis_pipeline(repo_path: str, *, persist: bool = True) -> PipelineState:
    """Convenience wrapper used by callers that only have a repo path."""
    return run_ingestion_pipeline(PipelineConfig(repo_path=repo_path, persist=persist))


def run_pipeline(config: PipelineConfig) -> dict:
    """Compatibility wrapper returning final stats."""
    return run_ingestion_pipeline(config).get("stats", {})


def describe_pipeline() -> list[str]:
    """Return the ordered phase names for diagnostics/UI."""
    return [phase.__name__ for phase in ANALYSIS_PHASES + PERSISTENCE_PHASES]


__all__ = [
    "PipelineConfig",
    "PipelineProgress",
    "PipelineState",
    "ANALYSIS_PHASES",
    "PERSISTENCE_PHASES",
    "build_structure",
    "compute_mro_phase",
    "create_indexes",
    "describe_pipeline",
    "detect_communities",
    "detect_processes",
    "discover_files",
    "load_to_lbug",
    "parse_infile",
    "propagate_cross_file",
    "resolve_calls",
    "resolve_heritage",
    "resolve_imports",
    "run_analysis_pipeline",
    "run_ingestion_pipeline",
    "run_pipeline",
]
