"""A0 load: relationships go in by one COPY per label pair and match the old row-by-row inserts."""
import sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src" / "modules")]

from src.modules.repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from src.modules.repo_explorer.graph.model.types import GraphNode, GraphRelationship, NodeLabel, NodeProperties, RelationshipType
from src.modules.repo_explorer.graph.storage.code_adapter import LadybugAdapter


def graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    for label, name in (("Class", "Doc"), ("Method", "Doc.render"), ("Function", "helper")):
        g.add_node(GraphNode(f"{label}:x.py:{name}", NodeLabel(label), NodeProperties(name=name.split(".")[-1], file_path="x.py")))
    g.add_relationship(GraphRelationship("h", "Class:x.py:Doc", "Method:x.py:Doc.render", RelationshipType.HAS_METHOD))
    g.add_relationship(GraphRelationship("c", "Method:x.py:Doc.render", "Function:x.py:helper", RelationshipType.CALLS,
                                         confidence=0.5, reason='said "hi", twice\nok', line=3))
    return g


def dump(adapter: LadybugAdapter) -> list[tuple]:
    r = adapter._conn.execute("MATCH (a)-[r:CodeRelation]->(b) RETURN a.id, b.id, r.type, r.confidence, r.reason, r.line ORDER BY r.type")
    rows = []
    while r.has_next():
        rows.append(tuple(None if v == "" else v for v in r.get_next()))
    return rows


class LbugLoadTest(unittest.TestCase):
    def test_copy_load_equals_row_inserts(self):
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("rows", "copy"):
                a = LadybugAdapter(db_path=str(Path(tmp) / mode))
                a.connect(); a.create_schema()
                calls = []
                if mode == "rows":
                    a._copy_rels = lambda *x, **k: False  # force the row-insert fallback
                else:
                    real = a._copy_rels
                    a._copy_rels = lambda *x, **k: calls.append(real(*x, **k)) or calls[-1]
                stats = a.load_graph(graph(), str(Path(tmp) / f"{mode}_csv"))
                out[mode] = dump(a)
                a.close()
                self.assertEqual(stats["relationship_count"], 2)
        self.assertEqual(calls, [True, True])  # both label pairs went in by COPY
        self.assertEqual(len(out["copy"]), 2)
        self.assertEqual(out["rows"], out["copy"])
        self.assertIn(("Method:x.py:Doc.render", "Function:x.py:helper", "CALLS", 0.5, 'said "hi", twice\nok', 3), out["copy"])


if __name__ == "__main__":
    unittest.main()
