from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.ingestion.infile_processor import process_infile_information
from repo_explorer.ingestion.symbol_table import SymbolTable
from repo_explorer.parsing.ast_cache import ASTCache


CODE = '''\
from models.user import User, Repository as Repo

class Service:
    """Coordinates user loading for the application service layer."""

    def build(self):
        """Build a repository-backed user workflow for callers."""
        repo = Repo()
        user: User = repo.load()
        return repo.save(user)

def helper():
    return Service().build()
'''


def node_line(node) -> str:
    props = node.properties
    details = [
        f"id={node.id}",
        f"label={node.label}",
        f"name={props.name}",
        f"file={props.file_path}",
    ]
    if props.start_line is not None:
        details.append(f"lines={props.start_line}-{props.end_line}")
    if props.is_exported is not None:
        details.append(f"exported={props.is_exported}")
    if props.signature:
        details.append(f"signature={props.signature}")
    if props.description:
        details.append(f"description={props.description}")
    return " | ".join(details)


def main() -> int:
    graph = KnowledgeGraph()
    symbol_table = SymbolTable()
    ast_cache = ASTCache()
    progress_events: list[tuple[int, int, str]] = []

    result = process_infile_information(
        graph,
        [{"path": "sample.py", "content": CODE}],
        symbol_table,
        ast_cache,
        on_progress=lambda current, total, detail: progress_events.append(
            (current, total, detail)
        ),
    )

    print("1. progress")
    for current, total, detail in progress_events:
        print(f"   {current}/{total}: {detail}")

    print("\n2. graph nodes")
    for node in graph.iter_nodes():
        print(f"   - {node_line(node)}")

    print("\n3. graph relationships")
    for rel in graph.iter_relationships():
        print(f"   - {rel.source_id} -[{rel.type}]-> {rel.target_id}")

    print("\n4. parse result")
    print(f"   imports: {result.imports}")
    print(f"   calls: {result.calls}")
    print(f"   heritage: {result.heritage}")
    print(f"   assignments: {result.assignments}")
    print(f"   type_envs: {list(result.type_envs.keys())}")

    print("\n5. ast cache")
    cached_tree = ast_cache.get("sample.py")
    print(f"   sample.py cached: {cached_tree is not None}")
    if cached_tree is not None:
        print(f"   root: {cached_tree.root_node.type}")

    print("\n6. symbol table")
    print(f"   stats: {symbol_table.get_stats()}")
    for name in ("Service", "build", "helper"):
        exact = symbol_table.lookup_exact_full("sample.py", name)
        fuzzy = symbol_table.lookup_fuzzy(name)
        callable_matches = symbol_table.lookup_fuzzy_callable(name)
        print(f"   {name}: exact={exact}")
        print(f"   {name}: fuzzy={fuzzy}")
        print(f"   {name}: callable={callable_matches}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
