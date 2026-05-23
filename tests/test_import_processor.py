from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.ingestion.extraction.import_resolvers.utils import SuffixIndex
from repo_explorer.ingestion.import_processor import process_imports
from repo_explorer.ingestion.infile_processor import ExtractedImport
from repo_explorer.ingestion.support.resolution_context import ResolutionContext
from repo_explorer.ingestion.structure_processor import process_structure
from repo_explorer.ingestion.support.symbol_table import SymbolTable


class ImportProcessorTest(unittest.TestCase):
    def test_process_imports_populates_import_edge_and_named_import_map(self) -> None:
        graph = KnowledgeGraph()
        file_paths = ["app/main.py", "models/user.py"]
        process_structure(graph, file_paths)

        symbol_table = SymbolTable()
        symbol_table.add(
            file_path="models/user.py",
            name="Repository",
            node_id="Class:models/user.py:Repository",
            symbol_type="Class",
        )

        ctx = ResolutionContext()
        ctx.symbols = symbol_table

        process_imports(
            graph=graph,
            imports=[
                ExtractedImport(
                    file_path="app/main.py",
                    raw_import_path="models.user",
                    language="python",
                    named_bindings=[
                        {"local": "Repo", "exported": "Repository"},
                    ],
                )
            ],
            ctx=ctx,
            suffix_index=SuffixIndex(file_paths),
        )

        self.assertEqual(ctx.import_map, {"app/main.py": {"models/user.py"}})
        self.assertIn("Repo", ctx.named_import_map["app/main.py"])
        resolved = ctx.resolve("Repo", "app/main.py")
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.tier, "import-scoped")
        self.assertEqual(resolved.candidates[0].name, "Repository")
        self.assertIsNotNone(
            graph.get_relationship("File:app/main.py_imports_File:models/user.py")
        )


if __name__ == "__main__":
    unittest.main()
