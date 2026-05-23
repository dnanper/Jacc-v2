"""State objects for the repo_explorer ingestion pipeline."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from ..discovery.filesystem_walker import ScannedFile
from ..graph.core.knowledge_graph import KnowledgeGraph
from .community_processor import CommunityMembership, CommunityNode
from .infile_processor import (
    ExtractedCall,
    ExtractedHeritage,
    ExtractedImport,
    ParseResult,
)
from .index_loader import IndexCreationResult
from .lbug_loader import LbugLoadResult
from .process_processor import ProcessNode, ProcessStep
from .support.resolution_context import ResolutionContext
from .support.symbol_table import SymbolTable
from .extraction.import_resolvers.utils import SuffixIndex


@dataclass
class PipelineProgress:
    """Progress update emitted after each ingestion phase."""

    phase: str = ""
    phase_index: int = 0
    total_phases: int = 12
    message: str = ""
    percent: int = 0


ProgressCallback = Callable[[PipelineProgress, "PipelineState"], None]


@dataclass
class PipelineConfig:
    """Configuration for the linear ingestion pipeline."""

    repo_path: str = ""
    force: bool = False
    persist: bool = True
    exclude_dirs: frozenset[str] = frozenset()
    cancel_event: threading.Event = field(default_factory=threading.Event)
    on_progress: ProgressCallback | None = None


class PipelineState(TypedDict, total=False):
    """Shared state passed through the linear ingestion phases."""

    config: PipelineConfig
    progress: PipelineProgress

    repo_path: str
    repo_name: str
    file_paths: list[str]
    scanned_files: list[ScannedFile]
    source_files: list[dict]

    knowledge_graph: KnowledgeGraph
    symbol_table: SymbolTable
    ast_cache: Any

    parse_result: ParseResult
    imports: list[ExtractedImport]
    calls: list[ExtractedCall]
    heritage: list[ExtractedHeritage]
    type_envs: dict

    resolution_context: ResolutionContext
    suffix_index: SuffixIndex

    cross_file_result: dict
    cycle_edges: list[tuple[str, str]]
    mro_result: Any

    community_result: dict
    community_nodes: list[CommunityNode]
    memberships: list[CommunityMembership]

    process_result: dict
    process_nodes: list[ProcessNode]
    process_steps: list[ProcessStep]

    load_result: LbugLoadResult
    index_result: IndexCreationResult
    stats: dict[str, Any]


class PipelineCancelled(Exception):
    """Raised when a pipeline run is cancelled."""

    def __init__(self, phase: str = ""):
        self.phase = phase
        super().__init__(
            f"Pipeline cancelled during {phase}" if phase else "Pipeline cancelled"
        )


def check_cancelled(state: PipelineState) -> None:
    """Raise when the configured cancellation event is set."""
    cfg = state.get("config")
    if cfg and cfg.cancel_event.is_set():
        phase = state.get("progress", PipelineProgress()).phase
        raise PipelineCancelled(phase)
