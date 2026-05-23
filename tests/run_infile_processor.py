from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.graph.model.types import RelationshipType
from repo_explorer.ingestion.call_processor import process_calls
from repo_explorer.ingestion.cross_file_propagation import (
    run_cross_file_propagation_phase,
)
from repo_explorer.ingestion.extraction.import_resolvers.utils import SuffixIndex
from repo_explorer.ingestion.import_processor import process_imports
from repo_explorer.ingestion.infile_processor import process_infile_information
from repo_explorer.ingestion.resolution_context import ResolutionContext
from repo_explorer.ingestion.structure_processor import process_structure
from repo_explorer.ingestion.symbol_table import SymbolTable
from repo_explorer.parsing.ast_cache import ASTCache


FILES = {
    "app/main.py": '''\
from models.user import Repository as repo, User


class Service:
    """Coordinates user loading for the application service layer."""

    def build(self):
        user: User = repo.load()
        return repo.save(user)
''',
    "models/user.py": '''\
class User:
    pass


class AuditLog:
    def save(self):
        return None


class Repository:
    def load(self) -> User:
        return User()

    def save(self, user: User) -> User:
        return user
''',
    "README.md": "# Sample repo\n",
}


def write_sample_repo(repo_path: Path) -> None:
    for relative_path, content in FILES.items():
        target = repo_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def graph_counts(graph: KnowledgeGraph) -> str:
    node_labels = Counter(str(node.label) for node in graph.iter_nodes())
    rel_types = Counter(str(rel.type) for rel in graph.iter_relationships())
    return (
        f"nodes={graph.node_count} {dict(sorted(node_labels.items()))} | "
        f"relationships={graph.relationship_count} {dict(sorted(rel_types.items()))}"
    )


def node_name(graph: KnowledgeGraph, node_id: str) -> str:
    node = graph.get_node(node_id)
    if node is None:
        return node_id
    props = node.properties
    if props.file_path:
        return f"{node.label}({props.file_path}:{props.name})"
    return f"{node.label}({props.name})"


def owner_name(graph: KnowledgeGraph, owner_id: str | None) -> str:
    if not owner_id:
        return "<none>"
    return node_name(graph, owner_id)


def symbol_line(symbol) -> str:
    return (
        f"name={symbol.name} type={symbol.type} file={symbol.file_path} "
        f"node={symbol.node_id} owner={symbol.owner_id} "
        f"params={symbol.parameter_count} return={symbol.return_type}"
    )


def print_graph_snapshot(title: str, graph: KnowledgeGraph) -> None:
    print(f"\n{title}")
    print(f"  {graph_counts(graph)}")

    print("  nodes:")
    for node in sorted(graph.iter_nodes(), key=lambda n: (str(n.label), n.id)):
        props = node.properties
        details = [
            f"{node.label}",
            f"id={node.id}",
            f"name={props.name}",
            f"file={props.file_path}",
        ]
        if props.start_line is not None:
            details.append(f"lines={props.start_line}-{props.end_line}")
        if props.signature:
            details.append(f"signature={props.signature}")
        if props.description:
            details.append(f"description={props.description}")
        print("    - " + " | ".join(details))

    print("  relationships:")
    for rel in sorted(graph.iter_relationships(), key=lambda r: (str(r.type), r.id)):
        source = node_name(graph, rel.source_id)
        target = node_name(graph, rel.target_id)
        print(
            f"    - id={rel.id} | {source} -[{rel.type}]-> {target} "
            f"| confidence={rel.confidence} | reason={rel.reason or 'no-reason'}"
        )


def print_parse_result(parse_result) -> None:
    print("\n3. parse result records from infile_processor")

    print(f"  imports ({len(parse_result.imports)}):")
    for imp in parse_result.imports:
        print(
            "    - "
            f"file={imp.file_path} raw={imp.raw_import_path} "
            f"language={imp.language} named_bindings={imp.named_bindings}"
        )

    print(f"  calls ({len(parse_result.calls)}):")
    for call in parse_result.calls:
        print(
            "    - "
            f"file={call.file_path} source={call.source_id} "
            f"name={call.called_name} form={call.call_form} "
            f"receiver={call.receiver_name} args={call.arg_count}"
        )

    print(f"  heritage ({len(parse_result.heritage)}): {parse_result.heritage}")
    print(f"  assignments ({len(parse_result.assignments)}): {parse_result.assignments}")
    print(f"  type_envs: {sorted(parse_result.type_envs.keys())}")
    for file_path, type_env in sorted(parse_result.type_envs.items()):
        print(f"    - {file_path} explicit={type_env.bindings}")
        print(f"      constructors={type_env.constructor_types}")
        print(f"      seeded={type_env.seeded}")
        print(f"      return_types={type_env.return_types}")


def print_symbol_table(symbol_table: SymbolTable, graph: KnowledgeGraph) -> None:
    print("\n3b. symbol table after infile_processor")
    print(f"  stats: {symbol_table.get_stats()}")
    for file_path in ("app/main.py", "models/user.py"):
        print(f"  file={file_path}")
        for name in (
            "Service",
            "build",
            "User",
            "AuditLog",
            "Repository",
            "load",
            "save",
        ):
            defs = symbol_table.lookup_exact_all(file_path, name)
            for symbol in defs:
                print(f"    - {symbol_line(symbol)}")
                if symbol.owner_id:
                    print(f"      owner_node={owner_name(graph, symbol.owner_id)}")


def print_resolution_context(ctx) -> None:
    print("\n5. resolution context after import_processor")

    print("  import_map:")
    for file_path, imported_files in sorted(ctx.import_map.items()):
        print(f"    - {file_path} -> {sorted(imported_files)}")

    print("  package_map:")
    for file_path, package_dirs in sorted(ctx.package_map.items()):
        print(f"    - {file_path} -> {sorted(package_dirs)}")

    print("  named_import_map:")
    for file_path, bindings in sorted(ctx.named_import_map.items()):
        print(f"    - {file_path}")
        for local, binding in sorted(bindings.items()):
            print(
                f"      {local} -> "
                f"{binding.source_path}:{binding.exported_name}"
            )

    for name in (
        "User",
        "repo",
        "AuditLog",
        "Repository",
        "Service",
        "load",
        "save",
    ):
        resolved = ctx.resolve(name, "app/main.py")
        if resolved is None:
            print(f"  resolve {name!r} from app/main.py -> <none>")
            continue
        print(
            f"  resolve {name!r} from app/main.py -> "
            f"tier={resolved.tier} confidence={resolved.confidence} "
            f"candidates={resolved.candidates}"
        )


def print_call_records(
    title: str,
    parse_result,
    graph: KnowledgeGraph,
    ctx: ResolutionContext,
) -> None:
    print(f"\n{title}")
    for call in parse_result.calls:
        resolved = ctx.resolve(call.called_name, call.file_path)
        resolved_summary = "<none>"
        if resolved is not None:
            resolved_summary = (
                f"tier={resolved.tier} candidates="
                f"{[symbol_line(candidate) for candidate in resolved.candidates]}"
            )
        print(
            "  - "
            f"file={call.file_path} source={call.source_id} "
            f"source_node={node_name(graph, call.source_id)} "
            f"name={call.called_name} form={call.call_form} "
            f"receiver={call.receiver_name} "
            f"receiver_type={call.receiver_type_name} args={call.arg_count} "
            f"raw_resolve={resolved_summary}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ckg-import-pipeline-") as tmp:
        repo_path = Path(tmp)
        write_sample_repo(repo_path)

        file_paths = sorted(FILES)
        source_files = [
            {
                "path": path,
                "content": (repo_path / path).read_text(encoding="utf-8"),
            }
            for path in file_paths
            if path.endswith(".py")
        ]

        print("0. import_processor import status")
        print("  - imported repo_explorer.ingestion.import_processor directly")

        graph = KnowledgeGraph()
        symbol_table = SymbolTable()
        ast_cache = ASTCache()

        print("\n1. build structure")
        process_structure(graph, file_paths, repo_path=str(repo_path))
        print_graph_snapshot("graph after structure_processor", graph)

        print("\n2. infile processor")
        parse_progress: list[tuple[int, int, str]] = []
        parse_result = process_infile_information(
            graph,
            source_files,
            symbol_table,
            ast_cache,
            on_progress=lambda current, total, detail: parse_progress.append(
                (current, total, detail)
            ),
        )
        for current, total, detail in parse_progress:
            print(f"  progress: {current}/{total} {detail}")
        print_graph_snapshot("graph after infile_processor", graph)
        print_parse_result(parse_result)
        print_symbol_table(symbol_table, graph)

        print("\n4. import processor")
        ctx = ResolutionContext()
        ctx.symbols = symbol_table
        suffix_index = SuffixIndex(file_paths)
        import_progress: list[tuple[int, int]] = []
        before_import_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.IMPORTS
        )
        process_imports(
            graph=graph,
            imports=parse_result.imports,
            ctx=ctx,
            suffix_index=suffix_index,
            on_progress=lambda current, total: import_progress.append(
                (current, total)
            ),
        )
        for current, total in import_progress:
            print(f"  progress: {current}/{total}")
        after_import_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.IMPORTS
        )
        print(
            "  IMPORTS edges added: "
            f"{after_import_edges - before_import_edges}"
        )
        print_graph_snapshot("graph after import_processor", graph)
        print_resolution_context(ctx)

        print("\n6. call processor")
        call_progress: list[tuple[int, int]] = []
        before_call_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        )
        process_calls(
            graph=graph,
            calls=parse_result.calls,
            ctx=ctx,
            type_envs=parse_result.type_envs,
            on_progress=lambda current, total: call_progress.append(
                (current, total)
            ),
        )
        for current, total in call_progress:
            print(f"  progress: {current}/{total}")
        after_call_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        )
        print("  CALLS edges added: " f"{after_call_edges - before_call_edges}")
        print_graph_snapshot("graph after call_processor", graph)
        print_call_records(
            "7. call records after call_processor type enrichment",
            parse_result,
            graph,
            ctx,
        )

        print("\n8. cross-file propagation")
        before_cross_call_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        )
        cross_result = run_cross_file_propagation_phase(
            graph=graph,
            calls=parse_result.calls,
            ctx=ctx,
            type_envs=parse_result.type_envs,
            file_contents=None,
            repo_path=str(repo_path),
        )
        after_cross_call_edges = sum(
            1
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        )
        print(f"  result: {cross_result}")
        print(
            "  CALLS edges added by cross-file propagation: "
            f"{after_cross_call_edges - before_cross_call_edges}"
        )
        print_graph_snapshot("graph after cross_file_propagation", graph)
        print_call_records(
            "9. call records after cross-file propagation",
            parse_result,
            graph,
            ctx,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
