"""Synthetic storage/identity regression, independent of benchmark issue/gold."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src/modules')]
from src.modules.repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from src.modules.repo_explorer.graph.model.types import GraphNode, NodeLabel, NodeProperties
from src.modules.repo_explorer.graph.schema import code_schema
from src.modules.repo_explorer.graph.schema.code_schema import _REL_FROM_TO_PAIRS, _CODE_SYMBOL_TABLES, NODE_SCHEMA_QUERIES, NODE_TABLES
from src.modules.repo_explorer.ingestion.infile_processor import ExtractedHeritage
from src.modules.repo_explorer.ingestion.heritage_processor import process_heritage, _declared_source_id


class StorageContractTest(unittest.TestCase):
    def test_docstring_edges_supported_for_every_definition_label(self):
        pairs = set(_REL_FROM_TO_PAIRS)
        self.assertTrue({('Section', label) for label in _CODE_SYMBOL_TABLES | {'Method'}} <= pairs)
        self.assertIn(('Interface', 'Class'), pairs)
        self.assertNotIn(('Module', 'Class'), pairs)
        self.assertIn(('Constructor', 'Constructor'), pairs)
        self.assertIn(('Enum', 'Interface'), pairs)

    def test_child_comes_from_declaration_not_same_name_assignment(self):
        graph = KnowledgeGraph()
        for label, name in ((NodeLabel.MODULE, 'Widget'), (NodeLabel.CLASS, 'Widget'), (NodeLabel.CLASS, 'Base')):
            graph.add_node(GraphNode(id=f'{label.value}:pkg/example.py:{name}', label=label,
                                     properties=NodeProperties(name=name, file_path='pkg/example.py')))
        class Context:
            def resolve(self, name, path):
                label = 'Module' if name == 'Widget' else 'Class'
                return SimpleNamespace(tier='same-file', candidates=[SimpleNamespace(type=label, node_id=f'{label}:{path}:{name}')])
        process_heritage(graph, [ExtractedHeritage('pkg/example.py', 'Widget', 'Base', 'extends')], Context())
        edges = list(graph.iter_relationships())
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].source_id, 'Class:pkg/example.py:Widget')
        self.assertEqual(edges[0].target_id, 'Class:pkg/example.py:Base')
        self.assertEqual(_declared_source_id(graph, 'Missing', 'pkg/example.py'), ('', 0.0))
        self.assertIsNone(graph.get_node('Class:pkg/example.py:Missing'))

    def test_parent_must_be_a_type_never_a_function_or_module(self):
        def graph_with(*nodes):
            g = KnowledgeGraph()
            for label, name in nodes:
                g.add_node(GraphNode(id=f'{label.value}:pkg/m.py:{name}', label=label,
                                     properties=NodeProperties(name=name, file_path='pkg/m.py')))
            return g

        class Ctx:
            def __init__(self, labels):
                self.labels = labels
            def resolve(self, name, path):
                if name == 'Child':
                    return SimpleNamespace(tier='same-file', candidates=[SimpleNamespace(type='Class', node_id=f'Class:{path}:Child')])
                return SimpleNamespace(tier='same-file', candidates=[SimpleNamespace(type=l, node_id=f'{l}:{path}:{name}') for l in self.labels])

        record = [ExtractedHeritage('pkg/m.py', 'Child', 'make_base', 'extends')]
        # Base expression is a function (e.g. a metaclass factory): no edge, no invented Class stub.
        g = graph_with((NodeLabel.CLASS, 'Child'), (NodeLabel.FUNCTION, 'make_base'))
        process_heritage(g, record, Ctx(['Function']))
        self.assertEqual(g.relationship_count, 0)
        self.assertIsNone(g.get_node('Class:make_base'))
        # Same name resolves to both a module and a class: the class is the parent.
        g = graph_with((NodeLabel.CLASS, 'Child'), (NodeLabel.MODULE, 'make_base'), (NodeLabel.CLASS, 'make_base'))
        process_heritage(g, record, Ctx(['Module', 'Class']))
        self.assertEqual([r.target_id for r in g.iter_relationships()], ['Class:pkg/m.py:make_base'])

    def test_schema_really_accepts_docstring_property_and_interface_class(self):
        import real_ladybug as lb
        from unittest.mock import patch
        needed = {'Section', 'Property', 'Interface', 'Class'}
        pairs = [pair for pair in _REL_FROM_TO_PAIRS if set(pair) <= needed]
        with tempfile.TemporaryDirectory() as root:
            db = lb.Database(str(Path(root) / 'db'), buffer_pool_size=256 << 20, max_db_size=1 << 30)
            conn = lb.Connection(db)
            for label, ddl in zip(NODE_TABLES, NODE_SCHEMA_QUERIES):
                if label in needed:
                    conn.execute(ddl)
            with patch.object(code_schema, '_REL_FROM_TO_PAIRS', pairs):
                conn.execute(code_schema._build_rel_schema_query())
            conn.execute("CREATE (:Section {id: 's'})")
            conn.execute("CREATE (:`Property` {id: 'p'})")
            conn.execute("CREATE (:Interface {id: 'i'})")
            conn.execute("CREATE (:Class {id: 'c'})")
            conn.execute("MATCH (s:Section), (p:`Property`) WHERE s.id='s' AND p.id='p' CREATE (s)-[:CodeRelation {id:'doc', type:'DESCRIBES'}]->(p)")
            conn.execute("MATCH (i:Interface), (c:Class) WHERE i.id='i' AND c.id='c' CREATE (i)-[:CodeRelation {id:'inherit', type:'EXTENDS'}]->(c)")
            result = conn.execute('MATCH ()-[r:CodeRelation]->() RETURN count(r)')
            self.assertEqual(result.get_next()[0], 2)
            del result, conn, db


if __name__ == '__main__':
    unittest.main()
