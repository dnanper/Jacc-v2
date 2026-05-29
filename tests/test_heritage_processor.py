from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.ingestion.heritage_processor import process_heritage
from repo_explorer.ingestion.infile_processor import ExtractedHeritage
from repo_explorer.ingestion.structure_processor import process_structure
from repo_explorer.ingestion.support.resolution_context import ResolutionContext
from repo_explorer.ingestion.support.symbol_table import SymbolTable
from repo_explorer.graph.model.types import GraphNode, NodeLabel, NodeProperties
from repo_explorer.parsing.ast_helpers import generate_id


class HeritageProcessorTest(unittest.TestCase):
    def test_unresolved_external_parent_gets_stub_node(self) -> None:
        graph = KnowledgeGraph()
        file_paths = ["app/dto.py"]
        process_structure(graph, file_paths)

        child_id = generate_id("Class", "app/dto.py:ChatRequest")
        graph.add_node(
            GraphNode(
                id=child_id,
                label=NodeLabel.CLASS,
                properties=NodeProperties(name="ChatRequest", file_path="app/dto.py"),
            )
        )

        symbol_table = SymbolTable()
        symbol_table.add(
            file_path="app/dto.py",
            name="ChatRequest",
            node_id=child_id,
            symbol_type="Class",
        )

        ctx = ResolutionContext()
        ctx.symbols = symbol_table

        process_heritage(
            graph,
            [ExtractedHeritage("app/dto.py", "ChatRequest", "BaseModel")],
            ctx,
        )

        parent_id = generate_id("Class", "BaseModel")
        self.assertIsNotNone(graph.get_node(parent_id))

        orphaned_relationships = [
            rel
            for rel in graph.iter_relationships()
            if graph.get_node(rel.source_id) is None
            or graph.get_node(rel.target_id) is None
        ]
        self.assertEqual(orphaned_relationships, [])


if __name__ == "__main__":
    unittest.main()
