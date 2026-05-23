from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.graph.model.types import (
    GraphNode,
    GraphRelationship,
    NodeLabel,
    NodeProperties,
    RelationshipType,
)
from repo_explorer.ingestion.cross_file_propagation import (
    build_exported_type_map,
    mark_import_cycle_edges,
)
from repo_explorer.ingestion.structure_processor import process_structure
from repo_explorer.ingestion.support.symbol_table import SymbolTable


class CrossFilePropagationTest(unittest.TestCase):
    def test_exported_type_map_uses_exported_class_name_as_receiver_type(self):
        graph = KnowledgeGraph()
        graph.add_node(
            GraphNode(
                id="Class:models/user.py:Repository",
                label=NodeLabel.CLASS,
                properties=NodeProperties(
                    name="Repository",
                    file_path="models/user.py",
                    is_exported=True,
                ),
            )
        )
        symbols = SymbolTable()
        symbols.add(
            file_path="models/user.py",
            name="Repository",
            node_id="Class:models/user.py:Repository",
            symbol_type="Class",
        )

        exported = build_exported_type_map(graph, symbols)

        self.assertEqual(exported["models/user.py"]["Repository"], "Repository")

    def test_mark_import_cycle_edges_sets_in_cycle_on_matching_import_edges(self):
        graph = KnowledgeGraph()
        process_structure(graph, ["a.py", "b.py", "c.py"])
        graph.add_relationship(
            GraphRelationship(
                id="a_imports_b",
                source_id="File:a.py",
                target_id="File:b.py",
                type=RelationshipType.IMPORTS,
            )
        )
        graph.add_relationship(
            GraphRelationship(
                id="b_imports_a",
                source_id="File:b.py",
                target_id="File:a.py",
                type=RelationshipType.IMPORTS,
            )
        )
        graph.add_relationship(
            GraphRelationship(
                id="a_imports_c",
                source_id="File:a.py",
                target_id="File:c.py",
                type=RelationshipType.IMPORTS,
            )
        )

        marked = mark_import_cycle_edges(
            graph,
            [("a.py", "b.py"), ("b.py", "a.py")],
        )

        self.assertEqual(marked, 2)
        self.assertTrue(graph.get_relationship("a_imports_b").in_cycle)
        self.assertTrue(graph.get_relationship("b_imports_a").in_cycle)
        self.assertIsNone(graph.get_relationship("a_imports_c").in_cycle)


if __name__ == "__main__":
    unittest.main()
