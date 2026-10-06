from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph  # noqa: E402
from repo_explorer.ingestion.exception_processor import process_exceptions  # noqa: E402
from repo_explorer.ingestion.infile_processor import _parse_single_file, process_infile_information  # noqa: E402
from repo_explorer.ingestion.support.resolution_context import ResolutionContext  # noqa: E402
from repo_explorer.ingestion.support.symbol_table import SymbolTable  # noqa: E402
from repo_explorer.parsing.ast_cache import ASTCache  # noqa: E402

PY = '''class PolyError(ValueError):
    pass


def parse(s):
    try:
        return int(s)
    except (ValueError, pkg.DataError) as e:
        raise PolyError("cannot parse %s" % s) from e
    except OSError:
        raise
    raise err
'''
JAVA = 'class A { void m() throws java.io.IOException { try { f(); } catch (IllegalStateException | FooException e) { throw new BarException("msg " + e); } } }'


class ExceptionEdgesTest(unittest.TestCase):
    def test_extraction_covers_raise_catch_throws(self) -> None:
        py = [(e.kind, e.type_name, e.line, e.message) for e in _parse_single_file({"path": "a.py", "content": PY})["exceptions"]]
        self.assertEqual(py, [
            ("catch", "ValueError", 8, ""), ("catch", "DataError", 8, ""),
            ("raise", "PolyError", 9, "cannot parse %s"), ("catch", "OSError", 10, ""), ("raise", "err", 12, ""),
        ])
        java = [(e.kind, e.type_name) for e in _parse_single_file({"path": "A.java", "content": JAVA})["exceptions"]]
        self.assertEqual(java, [("throws", "IOException"), ("catch", "IllegalStateException"), ("catch", "FooException"), ("raise", "BarException")])

    def test_edges_resolve_repo_classes_and_stub_only_exception_names(self) -> None:
        graph, symbols = KnowledgeGraph(), SymbolTable()
        result = process_infile_information(graph, [{"path": "a.py", "content": PY}], symbols, ASTCache())
        ctx = ResolutionContext()
        ctx.symbols = symbols
        stats = process_exceptions(graph, result.exceptions, ctx)
        edges = sorted((r.type.value, r.target_id, r.line, r.reason) for r in graph.iter_relationships() if r.type.value in ("RAISES", "CATCHES"))
        self.assertEqual(edges, [
            ("CATCHES", "Class:DataError", 8, "external"),
            ("CATCHES", "Class:OSError", 10, "external"),
            ("CATCHES", "Class:ValueError", 8, "external"),
            ("RAISES", "Class:a.py:PolyError", 9, "same-file"),
        ])
        self.assertEqual(stats["unresolved"], 1)  # `raise err` names a variable, not a class
        self.assertEqual(graph.get_node("Class:OSError").properties.description, "external exception class")


if __name__ == "__main__":
    unittest.main()
