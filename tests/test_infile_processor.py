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

DUPLICATE_METHOD_CODE = '''\
class AuditLog:
    def save(self):
        return None

class Repository:
    def save(self, user):
        return user
'''

IMPORT_CODE = '''\
from models.user import User, Repository as Repo

def build():
    return Repo()
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
        self.assertEqual(build.node_id, "Method:sample.py:Service.build")
        self.assertEqual(build.owner_id, "Class:sample.py:Service")
        self.assertEqual(helper.type, "Function")
        self.assertIsNone(helper.owner_id)

        self.assertIsNotNone(
            graph.get_relationship(
                "Class:sample.py:Service_has_method_Method:sample.py:Service.build"
            )
        )
        self.assertTrue(
            any(
                call.called_name == "build"
                and call.source_id == "Function:sample.py:helper"
                for call in result.calls
            )
        )

    def test_methods_with_same_name_in_different_classes_get_distinct_node_ids(self):
        graph = KnowledgeGraph()
        symbol_table = SymbolTable()

        process_infile_information(
            graph,
            [{"path": "models/user.py", "content": DUPLICATE_METHOD_CODE}],
            symbol_table,
            ASTCache(),
        )

        save_defs = symbol_table.lookup_exact_all("models/user.py", "save")
        self.assertEqual(
            sorted(defn.node_id for defn in save_defs),
            [
                "Method:models/user.py:AuditLog.save",
                "Method:models/user.py:Repository.save",
            ],
        )
        self.assertIsNotNone(
            graph.get_node("Method:models/user.py:AuditLog.save")
        )
        self.assertIsNotNone(
            graph.get_node("Method:models/user.py:Repository.save")
        )
        self.assertIsNotNone(
            graph.get_relationship(
                "Class:models/user.py:AuditLog_has_method_Method:models/user.py:AuditLog.save"
            )
        )
        self.assertIsNotNone(
            graph.get_relationship(
                "Class:models/user.py:Repository_has_method_Method:models/user.py:Repository.save"
            )
        )

    def test_python_imports_keep_named_bindings_from_import_statement(self):
        graph = KnowledgeGraph()
        symbol_table = SymbolTable()

        result = process_infile_information(
            graph,
            [{"path": "app/main.py", "content": IMPORT_CODE}],
            symbol_table,
            ASTCache(),
        )

        self.assertEqual(len(result.imports), 1)
        self.assertEqual(result.imports[0].raw_import_path, "models.user")
        self.assertEqual(
            result.imports[0].named_bindings,
            [
                {"local": "User", "exported": "User"},
                {"local": "Repo", "exported": "Repository"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
