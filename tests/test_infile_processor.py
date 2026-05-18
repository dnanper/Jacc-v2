from __future__ import annotations

import sys
import unittest
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
class Service:
    def build(self):
        return "ok"

def helper():
    return Service().build()
'''


class InfileProcessorTest(unittest.TestCase):
    def test_python_class_function_is_registered_as_method_with_owner_relation(self):
        graph = KnowledgeGraph()
        symbol_table = SymbolTable()

        result = process_infile_information(
            graph,
            [{"path": "sample.py", "content": CODE}],
            symbol_table,
            ASTCache(),
        )

        build = symbol_table.lookup_exact_full("sample.py", "build")
        helper = symbol_table.lookup_exact_full("sample.py", "helper")

        self.assertIsNotNone(build)
        self.assertIsNotNone(helper)
        assert build is not None
        assert helper is not None

        self.assertEqual(build.type, "Method")
        self.assertEqual(build.owner_id, "Class:sample.py:Service")
        self.assertEqual(helper.type, "Function")
        self.assertIsNone(helper.owner_id)

        self.assertIsNotNone(
            graph.get_relationship(
                "Class:sample.py:Service_has_method_Method:sample.py:build"
            )
        )
        self.assertTrue(
            any(
                call.called_name == "build"
                and call.source_id == "Function:sample.py:helper"
                for call in result.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
