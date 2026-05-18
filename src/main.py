from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path
from typing import Iterable

from modules.repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from modules.repo_explorer.ingestion.structure_processor import process_structure

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".omx",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "data",
    }
)


def scan_repository_paths(
    repo_path: str | Path,
    exclude_dirs: Iterable[str] = DEFAULT_EXCLUDED_DIRS,
) -> list[str]:
    """Return relative file paths for a repository, sorted for stable output."""
    repo = Path(repo_path).resolve()
    excluded = set(exclude_dirs)
    paths: list[str] = []

    for dirpath, dirnames, filenames in os.walk(repo, topdown=True):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in excluded and not dirname.startswith(".")
        ]

        current_dir = Path(dirpath)
        for filename in filenames:
            full_path = current_dir / filename
            try:
                rel_path = full_path.relative_to(repo).as_posix()
            except ValueError:
                continue
            paths.append(rel_path)

    return sorted(paths)


def run_structure_pipeline(repo_path: str | Path) -> tuple[KnowledgeGraph, list[str]]:
    """Scan a repository and build File/Folder structure nodes in memory."""
    repo = Path(repo_path).resolve()
    print(f"Scanning repository at: {repo}")
    if not repo.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo}")
    if not repo.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo}")

    paths = scan_repository_paths(repo)
    print(f"Scanned  {len(paths)} file paths in repository '{repo.name}'")
    graph = KnowledgeGraph()
    process_structure(graph, paths, str(repo))
    return graph, paths


def format_edge(
    graph: KnowledgeGraph, source_id: str, rel_type: str, target_id: str
) -> str:
    """Format one relationship as source node -[type]-> target node."""
    source = graph.get_node(source_id)
    target = graph.get_node(target_id)
    source_name = source.properties.file_path if source else source_id
    target_name = target.properties.file_path if target else target_id
    return f"{source_name} -[{rel_type}]-> {target_name}"


def _print_summary(
    graph: KnowledgeGraph,
    paths: list[str],
    sample_size: int,
    edge_sample_size: int,
) -> None:
    labels = Counter(str(node.label) for node in graph.iter_nodes())
    relationships = Counter(str(rel.type) for rel in graph.iter_relationships())

    print("Structure pipeline summary")
    print(f"Files scanned: {len(paths)}")
    print(f"Nodes: {graph.node_count}")
    for label, count in sorted(labels.items()):
        print(f"  {label}: {count}")
    print(f"Relationships: {graph.relationship_count}")
    for rel_type, count in sorted(relationships.items()):
        print(f"  {rel_type}: {count}")

    if sample_size > 0:
        print("\nSample files:")
        for path in paths[:sample_size]:
            print(f"  {path}")

    if edge_sample_size > 0:
        print("\nSample edges:")
        for rel in graph.relationships[:edge_sample_size]:
            print(
                f"  {format_edge(graph, rel.source_id, str(rel.type), rel.target_id)}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the repo_explorer structure ingestion pipeline in memory."
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository directory to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=10,
        help="Number of scanned file paths to print. Use 0 to hide samples.",
    )
    parser.add_argument(
        "--edges",
        type=int,
        default=10,
        help="Number of graph edges to print as node -[REL]-> node. Use 0 to hide.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    graph, paths = run_structure_pipeline(args.repo_path)
    _print_summary(graph, paths, args.sample, args.edges)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
