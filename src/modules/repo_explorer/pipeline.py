"""LangGraph pipeline — 15-phase ingestion StateGraph.

Port of GitNexus ingestion/pipeline.ts, orchestrated as a LangGraph
StateGraph with 13 sequential phases and 2 conditional phases
(embeddings + semantic linking).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from csg.config import get_language_from_filename
from csg.graph.knowledge_graph import KnowledgeGraph
from csg.graph.lbug_adapter import LadybugAdapter
from csg.storage.repo_manager import get_storage_path
from csg.ingestion.analysis.cross_file_propagation import run_cross_file_propagation
from csg.ingestion.documents.semantic_linker import link_sections_to_symbols
from csg.ingestion.analysis.call_processor import process_calls
from csg.ingestion.analysis.community_processor import process_communities
from csg.ingestion.discovery.filesystem_walker import (
    walk_repository_paths,
    read_file_contents,
    group_by_byte_budget,
    ScannedFile,
)
from csg.ingestion.analysis.heritage_processor import process_heritage
from csg.ingestion.analysis.import_processor import (
    build_import_resolution_context,
    process_imports,
)
from csg.ingestion.documents.markdown_processor import process_markdown
from csg.ingestion.analysis.mro_processor import compute_mro
from csg.ingestion.parsing.parsing_processor import process_parsing
from csg.ingestion.analysis.process_processor import process_processes
from csg.ingestion.analysis.resolution_context import ResolutionContext
from csg.ingestion.state import PipelineConfig, PipelineProgress, PipelineState, PipelineCancelled, check_cancelled
from csg.ingestion.analysis.structure_processor import process_structure
from csg.ingestion.analysis.symbol_table import SymbolTable
from csg.types import RelationshipType
from csg.storage.git import get_git_root, get_current_commit
from csg.storage.repo_manager import RepoMeta, register_repo, save_meta, load_meta

logger = logging.getLogger(__name__)


def discover_files(state: PipelineState) -> dict:
    """Phase 1: Discover repository files."""
    check_cancelled(state)
    cfg = state["config"]
    repo_path = cfg.repo_path

    logger.info("Phase 1: Discovering files in %s", repo_path)
    scanned = walk_repository_paths(repo_path, exclude_dirs=cfg.exclude_dirs)
    file_paths = [f.path for f in scanned]

    repo_name = os.path.basename(os.path.abspath(repo_path))

    return {
        "file_paths": file_paths,
        "scanned_files": scanned,
        "repo_path": repo_path,
        "repo_name": repo_name,
        "progress": PipelineProgress(
            phase="discover_files", phase_index=1,
            message=f"Discovered {len(file_paths)} files",
        ),
    }


def build_structure(state: PipelineState) -> dict:
    """Phase 2: Build file/folder structure nodes."""
    check_cancelled(state)
    logger.info("Phase 2: Building structure (%d files)", len(state["file_paths"]))

    graph = KnowledgeGraph()
    process_structure(graph, state["file_paths"], repo_path=state.get("repo_path", ""))

    return {
        "knowledge_graph": graph,
        "progress": PipelineProgress(
            phase="build_structure", phase_index=2,
            message="Structure built",
        ),
    }


def parse_markdown(state: PipelineState) -> dict:
    """Phase 2.5: Extract Section nodes from markdown files."""
    check_cancelled(state)
    file_paths = state["file_paths"]
    repo_path = state["repo_path"]

    md_paths = [p for p in file_paths if p.endswith(".md") or p.endswith(".mdx")]
    if not md_paths:
        return {
            "progress": PipelineProgress(
                phase="parse_markdown", phase_index=3,
                message="No markdown files found",
            ),
        }

    logger.info("Phase 2.5: Processing %d markdown files", len(md_paths))

    md_contents = read_file_contents(repo_path, md_paths)
    md_files = [{"path": p, "content": c} for p, c in md_contents.items()]
    all_path_set = set(file_paths)

    result = process_markdown(
        graph=state["knowledge_graph"],
        files=md_files,
        all_path_set=all_path_set,
    )

    return {
        "progress": PipelineProgress(
            phase="parse_markdown", phase_index=3,
            message=f"Markdown: {result.sections} sections, {result.links} links",
        ),
    }


def extract_infrastructure(state: PipelineState) -> dict:
    """Phase 2.7: Extract metadata from infrastructure files.

    Scans File nodes for Dockerfile, docker-compose, .env, OpenAPI,
    migrations, CI/CD configs, K8s manifests, and .proto files.
    Stores structured metadata on File nodes for explore/SRS layers.
    """
    check_cancelled(state)
    logger.info("Phase 2.7: Extracting infrastructure metadata")

    from csg.ingestion.analysis.infrastructure_processor import (
        extract_infrastructure as _extract,
    )

    counts = _extract(state["knowledge_graph"])
    total = sum(counts.values())

    return {
        "progress": PipelineProgress(
            phase="extract_infrastructure", phase_index=3,
            message=f"Infrastructure: {total} files extracted ({counts})" if total else "No infrastructure files",
        ),
    }


def parse_ast(state: PipelineState) -> dict:
    """Phase 3: Parse AST and extract definitions, imports, calls, heritage.

    Uses chunked parsing: files are grouped into 20MB byte-budget chunks.
    Each chunk's content is read, parsed, and freed before the next chunk,
    keeping peak memory bounded.
    """
    check_cancelled(state)
    repo_path = state["repo_path"]
    scanned_files = state.get("scanned_files")

    from csg.parsing.ast_cache import ASTCache
    symbol_table = SymbolTable()
    ast_cache = ASTCache()

    from csg.ingestion.parsing.parsing_processor import ParseResult
    aggregate = ParseResult()
    all_type_envs: dict = {}
    total_parsed = 0

    if scanned_files:
        parseable = [f for f in scanned_files if get_language_from_filename(f.path) is not None]
        chunks = group_by_byte_budget(parseable)
        logger.info(
            "Phase 3: Parsing AST for %d files in %d chunks",
            len(parseable), len(chunks),
        )

        for chunk_idx, chunk in enumerate(chunks):
            check_cancelled(state)
            chunk_paths = [f.path for f in chunk]

            chunk_contents = read_file_contents(repo_path, chunk_paths)
            files = [{"path": p, "content": c} for p, c in chunk_contents.items()]

            if not files:
                continue

            chunk_result = process_parsing(
                graph=state["knowledge_graph"],
                files=files,
                symbol_table=symbol_table,
                ast_cache=ast_cache,
            )

            aggregate.imports.extend(chunk_result.imports)
            aggregate.calls.extend(chunk_result.calls)
            aggregate.heritage.extend(chunk_result.heritage)
            aggregate.assignments.extend(chunk_result.assignments)
            all_type_envs.update(chunk_result.type_envs)

            total_parsed += len(files)

            ast_cache.clear()

            logger.debug(
                "  Chunk %d/%d: parsed %d files",
                chunk_idx + 1, len(chunks), len(files),
            )
    else:
        file_paths = state["file_paths"]
        logger.info("Phase 3: Parsing AST for %d files (single batch)", len(file_paths))
        file_contents = read_file_contents(repo_path, file_paths)
        files = [{"path": p, "content": c} for p, c in file_contents.items()]

        aggregate = process_parsing(
            graph=state["knowledge_graph"],
            files=files,
            symbol_table=symbol_table,
            ast_cache=ast_cache,
        )
        all_type_envs = aggregate.type_envs
        total_parsed = len(files)

    return {
        "parse_result": aggregate,
        "imports": aggregate.imports,
        "calls": aggregate.calls,
        "heritage": aggregate.heritage,
        "symbol_table": symbol_table,
        "type_envs": all_type_envs,
        "progress": PipelineProgress(
            phase="parse_ast", phase_index=3,
            message=f"Parsed {total_parsed} files",
        ),
    }


def resolve_imports(state: PipelineState) -> dict:
    """Phase 4: Resolve imports and create IMPORTS edges."""
    check_cancelled(state)
    logger.info("Phase 4: Resolving %d imports", len(state["imports"]))

    suffix_index = build_import_resolution_context(state["file_paths"])

    from csg.ingestion.parsing.language_config import load_import_configs
    try:
        import_configs = load_import_configs(state["repo_path"])
    except Exception as exc:
        logger.debug("Failed to load import configs: %s", exc)
        import_configs = None

    ctx = ResolutionContext()
    ctx.symbols = state["symbol_table"]

    process_imports(
        graph=state["knowledge_graph"],
        imports=state["imports"],
        ctx=ctx,
        suffix_index=suffix_index,
        import_configs=import_configs,
    )

    return {
        "resolution_context": ctx,
        "suffix_index": suffix_index,
        "progress": PipelineProgress(
            phase="resolve_imports", phase_index=4,
            message="Imports resolved",
        ),
    }


def resolve_calls(state: PipelineState) -> dict:
    """Phase 5: Resolve calls and create CALLS edges."""
    check_cancelled(state)
    logger.info("Phase 5: Resolving %d calls", len(state["calls"]))

    process_calls(
        graph=state["knowledge_graph"],
        calls=state["calls"],
        ctx=state["resolution_context"],
        type_envs=state.get("type_envs"),
    )

    return {
        "progress": PipelineProgress(
            phase="resolve_calls", phase_index=5,
            message="Calls resolved",
        ),
    }


def cross_file_propagation(state: PipelineState) -> dict:
    """Phase 5.5: Cross-file binding propagation."""
    check_cancelled(state)
    logger.info("Phase 5.5: Cross-file binding propagation")

    result = run_cross_file_propagation(
        graph=state["knowledge_graph"],
        calls=state["calls"],
        ctx=state["resolution_context"],
        type_envs=state.get("type_envs"),
        file_contents=None,
        repo_path=state.get("repo_path"),
    )

    cycle_edges_set = set(result.get("cycle_edges", []))
    if cycle_edges_set:
        graph = state["knowledge_graph"]
        marked = 0
        for rel in graph.iter_relationships():
            if rel.type == RelationshipType.IMPORTS:
                src_node = graph.get_node(rel.source_id)
                tgt_node = graph.get_node(rel.target_id)
                if src_node and tgt_node:
                    src_path = src_node.properties.file_path
                    tgt_path = tgt_node.properties.file_path
                    if (src_path, tgt_path) in cycle_edges_set:
                        rel.in_cycle = True
                        marked += 1
        logger.info("Marked %d IMPORTS edges as in-cycle", marked)

    return {
        "cycle_edges": result.get("cycle_edges", []),
        "progress": PipelineProgress(
            phase="cross_file_propagation", phase_index=6,
            message=f"Cross-file: {result.get('reprocessed_files', 0)} files re-processed, {result.get('seeded_calls', 0)} calls seeded, {result.get('cycles', 0)} cycle files",
        ),
    }


def resolve_heritage(state: PipelineState) -> dict:
    """Phase 6: Resolve heritage (EXTENDS/IMPLEMENTS)."""
    check_cancelled(state)
    logger.info("Phase 6: Resolving %d heritage records", len(state["heritage"]))

    process_heritage(
        graph=state["knowledge_graph"],
        heritage_records=state["heritage"],
        ctx=state["resolution_context"],
    )

    return {
        "progress": PipelineProgress(
            phase="resolve_heritage", phase_index=6,
            message="Heritage resolved",
        ),
    }


def compute_mro_phase(state: PipelineState) -> dict:
    """Phase 7: Compute Method Resolution Order."""
    check_cancelled(state)
    logger.info("Phase 7: Computing MRO")

    result = compute_mro(state["knowledge_graph"])

    return {
        "progress": PipelineProgress(
            phase="compute_mro", phase_index=7,
            message=f"MRO: {result.override_edges} overrides, {result.ambiguity_count} ambiguities",
        ),
    }


def detect_communities(state: PipelineState) -> dict:
    """Phase 8: Detect communities using Leiden algorithm."""
    check_cancelled(state)
    logger.info("Phase 8: Detecting communities")

    result = process_communities(state["knowledge_graph"])

    graph = state["knowledge_graph"]
    from csg.parsing.ast_helpers import generate_id
    from csg.types import GraphNode, GraphRelationship, NodeProperties, RelationshipType

    for comm in result.communities:
        graph.add_node(GraphNode(
            id=comm.id,
            label="Community",
            properties=NodeProperties(
                name=comm.label,
                heuristic_label=comm.heuristic_label,
                cohesion=comm.cohesion,
                symbol_count=comm.symbol_count,
            ),
        ))

    for m in result.memberships:
        graph.add_relationship(GraphRelationship(
            id=generate_id("MEMBER_OF", f"{m.node_id}->{m.community_id}"),
            source_id=m.node_id,
            target_id=m.community_id,
            type=RelationshipType.MEMBER_OF,
            confidence=1.0,
            reason="leiden",
        ))

    node_to_community: dict[str, str] = {
        m.node_id: m.community_id for m in result.memberships
    }
    from collections import defaultdict as _defaultdict
    interaction_counts: dict[tuple[str, str], dict[str, int]] = _defaultdict(
        lambda: {"calls": 0, "imports": 0}
    )
    for rel in graph.iter_relationships():
        src_comm = node_to_community.get(rel.source_id)
        tgt_comm = node_to_community.get(rel.target_id)
        if src_comm and tgt_comm and src_comm != tgt_comm:
            key = (src_comm, tgt_comm)
            if rel.type == RelationshipType.CALLS:
                interaction_counts[key]["calls"] += 1
            elif rel.type == RelationshipType.IMPORTS:
                interaction_counts[key]["imports"] += 1

    interaction_edge_count = 0
    for (src_comm, tgt_comm), counts in interaction_counts.items():
        total = counts["calls"] + counts["imports"]
        if total < 3:
            continue
        graph.add_relationship(GraphRelationship(
            id=generate_id("COMMUNITY_INTERACTS", f"{src_comm}->{tgt_comm}"),
            source_id=src_comm,
            target_id=tgt_comm,
            type=RelationshipType.COMMUNITY_INTERACTS,
            confidence=float(total),
            reason=f"calls:{counts['calls']},imports:{counts['imports']}",
        ))
        interaction_edge_count += 1

    logger.info("Created %d COMMUNITY_INTERACTS edges", interaction_edge_count)

    from csg.ingestion.analysis.fan_in_processor import compute_fan_in
    compute_fan_in(graph, result.memberships)

    from csg.ingestion.analysis.schema_extraction import extract_schema_entities
    extract_schema_entities(graph)

    return {
        "community_nodes": result.communities,
        "memberships": result.memberships,
        "progress": PipelineProgress(
            phase="detect_communities", phase_index=8,
            message=f"Found {len(result.communities)} communities, {interaction_edge_count} cross-community links",
        ),
    }


def detect_processes(state: PipelineState) -> dict:
    """Phase 9: Detect execution flows (processes)."""
    check_cancelled(state)
    logger.info("Phase 9: Detecting processes")

    result = process_processes(
        knowledge_graph=state["knowledge_graph"],
        memberships=state["memberships"],
    )

    graph = state["knowledge_graph"]
    from csg.parsing.ast_helpers import generate_id
    from csg.types import GraphNode, GraphRelationship, NodeProperties, RelationshipType

    for proc in result.processes:
        graph.add_node(GraphNode(
            id=proc.id,
            label="Process",
            properties=NodeProperties(
                name=proc.label,
                heuristic_label=proc.heuristic_label,
                process_type=proc.process_type,
                step_count=proc.step_count,
            ),
        ))

    for step in result.steps:
        graph.add_relationship(GraphRelationship(
            id=generate_id("STEP_IN_PROCESS", f"{step.node_id}->{step.process_id}:{step.step}"),
            source_id=step.node_id,
            target_id=step.process_id,
            type=RelationshipType.STEP_IN_PROCESS,
            confidence=1.0,
            reason=f"step-{step.step}",
        ))

    return {
        "process_nodes": result.processes,
        "process_steps": result.steps,
        "progress": PipelineProgress(
            phase="detect_processes", phase_index=9,
            message=f"Found {len(result.processes)} processes",
        ),
    }


def load_to_lbug(state: PipelineState) -> dict:
    """Phase 11: Load graph into LadybugDB."""
    cfg = state["config"]
    repo_path = state["repo_path"]
    db_path = str(get_storage_path(repo_path) / "lbug")
    csv_dir = str(get_storage_path(repo_path) / "csv_tmp")

    check_cancelled(state)
    logger.info("Phase 11: Loading to LadybugDB at %s", db_path)

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    cached_embeddings: list[dict] = []
    if not cfg.force:
        cached_embeddings = adapter.load_cached_embeddings()

    try:
        adapter.clear_database()
        adapter.create_schema()
        load_stats = adapter.load_graph(state["knowledge_graph"], csv_dir)
        adapter.create_fts_indexes()
    finally:
        adapter.close()
        import shutil
        shutil.rmtree(csv_dir, ignore_errors=True)

    return {
        "cached_embeddings": cached_embeddings,
        "stats": {
            "nodes": load_stats["node_count"],
            "relationships": load_stats["relationship_count"],
            "files": len(state["file_paths"]),
            "communities": len(state.get("community_nodes", [])),
            "processes": len(state.get("process_nodes", [])),
        },
        "progress": PipelineProgress(
            phase="load_to_lbug", phase_index=11,
            message=f"Loaded {load_stats['node_count']} nodes, {load_stats['relationship_count']} rels",
        ),
    }


def create_indexes(state: PipelineState) -> dict:
    """Phase 12: Create FTS indexes in LadybugDB."""
    cfg = state["config"]
    repo_path = state["repo_path"]
    db_path = str(get_storage_path(repo_path) / "lbug")

    check_cancelled(state)
    logger.info("Phase 12: Creating indexes")

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    try:
        adapter.create_fts_indexes()
    finally:
        adapter.close()

    commit = get_current_commit(repo_path)
    stats = state.get("stats", {})

    from datetime import datetime, timezone
    meta = RepoMeta(
        repo_path=str(repo_path),
        last_commit=commit or "",
        indexed_at=datetime.now(timezone.utc).isoformat(),
        stats={
            "files": stats.get("files", 0),
            "nodes": stats.get("nodes", 0),
            "edges": stats.get("relationships", 0),
            "communities": stats.get("communities", 0),
            "processes": stats.get("processes", 0),
            "embeddings": 0,
        },
    )
    save_meta(repo_path, meta)
    register_repo(repo_path, meta)

    # Save graph.json cache so both MCP and web app can serve it
    try:
        from csg.web.routes.analysis import serialize_results, save_graph_json
        results = serialize_results(dict(state))
        save_graph_json(repo_path, results)
        logger.info("Phase 12: Saved graph.json cache")
    except Exception:
        logger.debug("Could not save graph.json cache", exc_info=True)

    return {
        "progress": PipelineProgress(
            phase="create_indexes", phase_index=12,
            message="FTS indexes created",
        ),
    }


def generate_embeddings(state: PipelineState) -> dict:
    """Phase 13: Generate embeddings and store in LadybugDB."""
    cfg = state["config"]
    repo_path = state["repo_path"]
    db_path = str(get_storage_path(repo_path) / "lbug")

    check_cancelled(state)
    logger.info("Phase 13: Generating embeddings")

    from csg.embeddings.embedding_pipeline import (
        run_embedding_pipeline,
        restore_cached_embeddings,
        EmbeddingConfig,
    )

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    try:
        cached = state.get("cached_embeddings", [])
        skip_node_ids: set[str] = set()
        if cached:
            cached_node_ids = {e["nodeId"] for e in cached if e.get("nodeId")}
            restore_cached_embeddings(adapter, cached)
            skip_node_ids = cached_node_ids

        result = run_embedding_pipeline(
            graph=state["knowledge_graph"],
            repo_name=state["repo_name"],
            adapter=adapter,
            config=EmbeddingConfig(
                model_id=cfg.embedding_model,
                device=cfg.embedding_device,
                batch_size=cfg.embedding_batch_size,
            ),
            skip_node_ids=skip_node_ids or None,
        )

        adapter.create_vector_index()
    finally:
        adapter.close()

    total = result.total_upserted
    existing_meta = load_meta(repo_path)
    if existing_meta:
        existing_meta.stats["embeddings"] = total
        save_meta(repo_path, existing_meta)

    cached_count = len(cached) if cached else 0
    msg = f"Embedded {result.total_embedded} new nodes"
    if cached_count:
        msg += f" (restored {cached_count} cached)"

    return {
        "progress": PipelineProgress(
            phase="generate_embeddings", phase_index=13,
            message=msg,
        ),
    }


def semantic_linking(state: PipelineState) -> dict:
    """Phase 12.5: Link documentation sections to code symbols via embeddings.

    Creates DESCRIBES edges where a Section node's embedding is similar
    to a code symbol's embedding, bridging documentation and code.
    """
    cfg = state["config"]
    repo_path = state["repo_path"]
    db_path = str(get_storage_path(repo_path) / "lbug")

    check_cancelled(state)
    logger.info("Phase 12.5: Semantic linking (Section → Symbol)")

    adapter = LadybugAdapter(db_path=db_path)
    adapter.connect()

    try:
        result = link_sections_to_symbols(
            graph=state["knowledge_graph"],
            adapter=adapter,
        )
    except Exception as e:
        logger.warning("Semantic linking skipped: %s", e)
        return {
            "progress": PipelineProgress(
                phase="semantic_linking", phase_index=14,
                message="Semantic linking skipped",
            ),
        }
    finally:
        adapter.close()

    return {
        "progress": PipelineProgress(
            phase="semantic_linking", phase_index=14,
            message=f"Linked {result.describes_edges_created} section↔symbol pairs (avg sim: {result.avg_similarity})",
        ),
    }


EMBEDDING_NODE_LIMIT = 50_000


def _should_embed(state: PipelineState) -> str:
    """Conditional edge: run embeddings if configured or auto-embed small repos."""
    # Guard: skip if sentence-transformers not installed
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        logger.info("sentence-transformers not installed — skipping embeddings")
        return END

    cfg = state.get("config")
    if cfg and cfg.embeddings:
        return "generate_embeddings"

    node_count = state.get("stats", {}).get("nodes", 0)
    if 0 < node_count <= EMBEDDING_NODE_LIMIT:
        return "generate_embeddings"

    if node_count > EMBEDDING_NODE_LIMIT:
        logger.warning(
            "Auto-embedding skipped: %d nodes > %d limit. "
            "Pass --embeddings to force.",
            node_count,
            EMBEDDING_NODE_LIMIT,
        )
    return END


def build_pipeline() -> StateGraph:
    """Build and compile the full 15-phase LangGraph pipeline (including embeddings)."""
    builder = StateGraph(PipelineState)

    builder.add_node("discover_files", discover_files)
    builder.add_node("build_structure", build_structure)
    builder.add_node("parse_markdown", parse_markdown)
    builder.add_node("extract_infrastructure", extract_infrastructure)
    builder.add_node("parse_ast", parse_ast)
    builder.add_node("resolve_imports", resolve_imports)
    builder.add_node("resolve_calls", resolve_calls)
    builder.add_node("cross_file_propagation", cross_file_propagation)
    builder.add_node("resolve_heritage", resolve_heritage)
    builder.add_node("compute_mro", compute_mro_phase)
    builder.add_node("detect_communities", detect_communities)
    builder.add_node("detect_processes", detect_processes)
    builder.add_node("load_to_lbug", load_to_lbug)
    builder.add_node("create_indexes", create_indexes)
    builder.add_node("generate_embeddings", generate_embeddings)
    builder.add_node("semantic_linking", semantic_linking)

    builder.set_entry_point("discover_files")
    builder.add_edge("discover_files", "build_structure")
    builder.add_edge("build_structure", "parse_markdown")
    builder.add_edge("parse_markdown", "extract_infrastructure")
    builder.add_edge("extract_infrastructure", "parse_ast")
    builder.add_edge("parse_ast", "resolve_imports")
    builder.add_edge("resolve_imports", "resolve_calls")
    builder.add_edge("resolve_calls", "cross_file_propagation")
    builder.add_edge("cross_file_propagation", "resolve_heritage")
    builder.add_edge("resolve_heritage", "compute_mro")
    builder.add_edge("compute_mro", "detect_communities")
    builder.add_edge("detect_communities", "detect_processes")
    builder.add_edge("detect_processes", "load_to_lbug")
    builder.add_edge("load_to_lbug", "create_indexes")

    builder.add_conditional_edges("create_indexes", _should_embed)
    builder.add_edge("generate_embeddings", "semantic_linking")
    builder.add_edge("semantic_linking", END)

    return builder.compile()


def build_core_pipeline() -> StateGraph:
    """Build phases 1-12 pipeline (parsing + LadybugDB, no embeddings).

    Graph is fully queryable after this — embeddings run separately in background.
    """
    builder = StateGraph(PipelineState)

    builder.add_node("discover_files", discover_files)
    builder.add_node("build_structure", build_structure)
    builder.add_node("parse_markdown", parse_markdown)
    builder.add_node("extract_infrastructure", extract_infrastructure)
    builder.add_node("parse_ast", parse_ast)
    builder.add_node("resolve_imports", resolve_imports)
    builder.add_node("resolve_calls", resolve_calls)
    builder.add_node("cross_file_propagation", cross_file_propagation)
    builder.add_node("resolve_heritage", resolve_heritage)
    builder.add_node("compute_mro", compute_mro_phase)
    builder.add_node("detect_communities", detect_communities)
    builder.add_node("detect_processes", detect_processes)
    builder.add_node("load_to_lbug", load_to_lbug)
    builder.add_node("create_indexes", create_indexes)

    builder.set_entry_point("discover_files")
    builder.add_edge("discover_files", "build_structure")
    builder.add_edge("build_structure", "parse_markdown")
    builder.add_edge("parse_markdown", "extract_infrastructure")
    builder.add_edge("extract_infrastructure", "parse_ast")
    builder.add_edge("parse_ast", "resolve_imports")
    builder.add_edge("resolve_imports", "resolve_calls")
    builder.add_edge("resolve_calls", "cross_file_propagation")
    builder.add_edge("cross_file_propagation", "resolve_heritage")
    builder.add_edge("resolve_heritage", "compute_mro")
    builder.add_edge("compute_mro", "detect_communities")
    builder.add_edge("detect_communities", "detect_processes")
    builder.add_edge("detect_processes", "load_to_lbug")
    builder.add_edge("load_to_lbug", "create_indexes")
    builder.add_edge("create_indexes", END)

    return builder.compile()


def _build_embedding_pipeline() -> StateGraph:
    """Build phases 13-15 pipeline (embeddings only)."""
    builder = StateGraph(PipelineState)

    builder.add_node("generate_embeddings", generate_embeddings)
    builder.add_node("semantic_linking", semantic_linking)

    builder.set_entry_point("generate_embeddings")
    builder.add_edge("generate_embeddings", "semantic_linking")
    builder.add_edge("semantic_linking", END)

    return builder.compile()


def build_analysis_pipeline() -> StateGraph:
    """Build a 10-phase analysis-only pipeline (no LadybugDB persistence)."""
    builder = StateGraph(PipelineState)

    builder.add_node("discover_files", discover_files)
    builder.add_node("build_structure", build_structure)
    builder.add_node("parse_markdown", parse_markdown)
    builder.add_node("extract_infrastructure", extract_infrastructure)
    builder.add_node("parse_ast", parse_ast)
    builder.add_node("resolve_imports", resolve_imports)
    builder.add_node("resolve_calls", resolve_calls)
    builder.add_node("cross_file_propagation", cross_file_propagation)
    builder.add_node("resolve_heritage", resolve_heritage)
    builder.add_node("compute_mro", compute_mro_phase)
    builder.add_node("detect_communities", detect_communities)
    builder.add_node("detect_processes", detect_processes)

    builder.set_entry_point("discover_files")
    builder.add_edge("discover_files", "build_structure")
    builder.add_edge("build_structure", "parse_markdown")
    builder.add_edge("parse_markdown", "extract_infrastructure")
    builder.add_edge("extract_infrastructure", "parse_ast")
    builder.add_edge("parse_ast", "resolve_imports")
    builder.add_edge("resolve_imports", "resolve_calls")
    builder.add_edge("resolve_calls", "cross_file_propagation")
    builder.add_edge("cross_file_propagation", "resolve_heritage")
    builder.add_edge("resolve_heritage", "compute_mro")
    builder.add_edge("compute_mro", "detect_communities")
    builder.add_edge("detect_communities", "detect_processes")
    builder.add_edge("detect_processes", END)

    return builder.compile()


def _backup_lbug(repo_path: str) -> str | None:
    """Copy existing lbug/ to lbug_backup/ before destructive Phase 11."""
    storage = get_storage_path(repo_path)
    lbug_dir = storage / "lbug"
    backup_dir = storage / "lbug_backup"
    if lbug_dir.exists() and any(lbug_dir.iterdir()):
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(lbug_dir, backup_dir)
        logger.info("Backed up lbug → lbug_backup for %s", repo_path)
        return str(backup_dir)
    return None


def _restore_lbug(repo_path: str) -> None:
    """Restore lbug/ from lbug_backup/ after a cancelled pipeline."""
    storage = get_storage_path(repo_path)
    lbug_dir = storage / "lbug"
    backup_dir = storage / "lbug_backup"
    if not backup_dir.exists():
        return
    # Release any KuzuPool handles so we can replace the directory
    from csg.graph.kuzu_pool import KuzuPool
    pool = KuzuPool.get()
    pool.close(str(lbug_dir))

    if lbug_dir.exists():
        shutil.rmtree(lbug_dir, ignore_errors=True)
    backup_dir.rename(lbug_dir)
    logger.info("Restored lbug from backup for %s", repo_path)


def _cleanup_partial_artifacts(repo_path: str) -> None:
    """Remove partial artifacts written by Phase 12 on cancellation."""
    storage = get_storage_path(repo_path)
    for name in ("meta.json", "graph.json"):
        path = storage / name
        if path.exists():
            path.unlink()
    # Remove from global registry
    from csg.storage.repo_manager import unregister_repo
    try:
        unregister_repo(repo_path)
    except Exception:
        pass
    # Clean leftover CSV temp dir
    csv_tmp = storage / "csv_tmp"
    if csv_tmp.exists():
        shutil.rmtree(csv_tmp, ignore_errors=True)


def _cleanup_backup(repo_path: str) -> None:
    """Remove lbug_backup/ after successful pipeline completion."""
    backup_dir = get_storage_path(repo_path) / "lbug_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)


def _run_embeddings_background(
    final_state: dict,
    cancel_event: threading.Event | None = None,
) -> None:
    """Run embedding phases (13-15) in background thread.

    The graph is already fully queryable from LadybugDB after phase 12.
    Embeddings only enhance AI agent semantic search.
    """
    try:
        if cancel_event and cancel_event.is_set():
            logger.info("Embeddings skipped (cancelled)")
            return

        cfg = final_state.get("config")
        if not _should_embed(final_state) == "generate_embeddings":
            logger.info("Embeddings skipped (not configured or sentence-transformers missing)")
            return

        logger.info("Background: starting embedding phases (13-15)...")
        pipeline = _build_embedding_pipeline()
        pipeline.invoke(final_state)
        logger.info("Background: embedding phases complete")
    except PipelineCancelled:
        logger.info("Background embedding phases cancelled")
    except Exception:
        logger.exception("Background embedding phases failed (non-blocking)")


def run_analysis_pipeline(
    repo_path: str,
    cancel_event: threading.Event | None = None,
) -> dict:
    """Run core pipeline (phases 1-12) and start embeddings in background.

    Returns immediately after LadybugDB is loaded and indexed.
    Embedding phases (13-15) run asynchronously — they only enhance
    AI agent semantic search and are not needed for graph queries.

    Args:
        repo_path: Path to the repository to analyze.
        cancel_event: If provided, the pipeline checks this event between
            phases and raises PipelineCancelled when set.

    Returns:
        Final pipeline state with all analysis results.

    Raises:
        PipelineCancelled: If cancel_event is set during execution.
    """
    pipeline = build_core_pipeline()

    event = cancel_event or threading.Event()
    config = PipelineConfig(repo_path=repo_path, cancel_event=event)
    initial_state: PipelineState = {
        "config": config,
        "progress": PipelineProgress(),
    }

    # Back up existing DB before Phase 11 can destroy it
    backup_path = _backup_lbug(repo_path)

    try:
        final_state = pipeline.invoke(initial_state)
    except PipelineCancelled:
        logger.warning("Pipeline cancelled for %s — rolling back", repo_path)
        if backup_path:
            _restore_lbug(repo_path)
        _cleanup_partial_artifacts(repo_path)
        raise

    # Success — remove backup, start background embeddings
    _cleanup_backup(repo_path)
    state_dict = dict(final_state)

    threading.Thread(
        target=_run_embeddings_background,
        args=(state_dict, event),
        daemon=True,
        name="csg-embeddings",
    ).start()

    return state_dict


def run_pipeline(config: PipelineConfig) -> dict:
    """Run the full ingestion pipeline.

    Args:
        config: Pipeline configuration.

    Returns:
        Final pipeline state stats.
    """
    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "config": config,
        "progress": PipelineProgress(),
    }

    final_state = pipeline.invoke(initial_state)

    return final_state.get("stats", {})


def run_incremental_pipeline(repo_path: str) -> dict:
    """Run an incremental re-ingestion for a repository.

    Uses the parse cache to skip re-parsing unchanged files.
    Only changed/new files are parsed; resolution and graph rebuild
    run on the full (merged) data. Embeddings run in background.

    This is the entry point called by the background watcher.

    Args:
        repo_path: Absolute path to the repository.

    Returns:
        Final pipeline state stats.
    """
    import threading
    from csg.ingestion.parsing.parse_cache import ParseCache

    storage = get_storage_path(repo_path)
    cache_dir = str(storage / "cache")

    config = PipelineConfig(
        repo_path=repo_path,
        incremental=True,
        cache_dir=cache_dir,
        embeddings=True,
    )

    # Run the same core pipeline — the parse_ast phase checks the cache
    pipeline = build_core_pipeline()

    initial_state: PipelineState = {
        "config": config,
        "progress": PipelineProgress(),
    }

    final_state = pipeline.invoke(initial_state)
    state_dict = dict(final_state)

    # Fire-and-forget: embeddings in background
    threading.Thread(
        target=_run_embeddings_background,
        args=(state_dict,),
        daemon=True,
        name="csg-embeddings-incr",
    ).start()

    return state_dict.get("stats", {})
