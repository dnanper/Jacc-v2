"""Staging preparation fixtures: no benchmark, model, old DB reset or graph rebuild."""
import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src/modules'), str(ROOT / '.tmp')]
from staging_graph import reconstruct, normalize
from src.modules.repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from src.modules.repo_explorer.graph.model.types import GraphNode, GraphRelationship, NodeLabel, NodeProperties, RelationshipType
from src.modules.repo_explorer.graph.schema import code_schema


def node(label, name):
    return GraphNode(f'{label}:x.py:{name}', NodeLabel(label), NodeProperties(name=name, file_path='x.py'))


class StagingTest(unittest.TestCase):
    def test_cache_identity_correction_without_phantom_nodes(self):
        ns = [node('Module', 'Widget'), node('Class', 'Widget'), node('Class', 'Base')]
        r = GraphRelationship('inherit', ns[0].id, ns[2].id, RelationshipType.EXTENDS)
        payload = {'nodes': [asdict(n) for n in ns], 'relationships': [asdict(r)]}
        graph, relations = reconstruct(payload)
        changes = normalize(graph, relations)
        self.assertEqual(changes['declared_source_correction'], 1)
        self.assertEqual(graph.node_count, 3)
        self.assertEqual(next(graph.iter_relationships()).source_id, ns[1].id)

    def test_unclassified_missing_application_source_blocks_ready(self):
        graph = KnowledgeGraph()
        graph.add_node(node('Function', 'target'))
        rel = GraphRelationship('call', 'Function:app.py:missing', 'Function:x.py:target', RelationshipType.CALLS)
        with self.assertRaisesRegex(ValueError, 'unclassified dangling'):
            normalize(graph, [rel])

    def test_vendor_source_deferred_explicitly_and_duplicate_cache_rejected(self):
        graph = KnowledgeGraph()
        graph.add_node(node('Function', 'target'))
        rel = GraphRelationship('call', 'Function:vendor/min.js:anon', 'Function:x.py:target', RelationshipType.CALLS)
        self.assertEqual(normalize(graph, [rel])['deferred_non_python_dangling.js'], 1)
        self.assertEqual(graph.relationship_count, 0)
        n = asdict(node('Class', 'Repeated'))
        with self.assertRaisesRegex(ValueError, 'duplicate cached node'):
            reconstruct({'nodes': [n, n], 'relationships': []})

    def test_cpp_template_owner_deferred_but_python_owner_still_blocks(self):
        graph = KnowledgeGraph()
        prop = GraphNode('Property:a.cpp:Conv<half>.type', NodeLabel('Property'), NodeProperties(name='type', file_path='a.cpp'))
        graph.add_node(prop)
        rel = GraphRelationship('owner', 'Struct:a.cpp:Conv<half>', prop.id, RelationshipType.HAS_PROPERTY)
        self.assertEqual(normalize(graph, [rel])['deferred_non_python_dangling.cpp'], 1)
        py = GraphNode('Property:app.py:Model.field', NodeLabel('Property'), NodeProperties(name='field', file_path='app.py'))
        graph.add_node(py)
        bad = GraphRelationship('owner2', 'Class:app.py:Model', py.id, RelationshipType.HAS_PROPERTY)
        with self.assertRaisesRegex(ValueError, 'unclassified dangling'):
            normalize(graph, [bad])

    def test_derived_edges_are_checked_before_any_db(self):
        from staging_graph import check_pairs
        graph = KnowledgeGraph()
        ctor = GraphNode('Constructor:A.java:A.A', NodeLabel('Constructor'), NodeProperties(name='A', file_path='A.java'))
        proc = GraphNode('Process:p1', NodeLabel('Process'), NodeProperties(name='p1'))
        fold = GraphNode('Folder:x', NodeLabel('Folder'), NodeProperties(name='x'))
        for n in (ctor, proc, fold):
            graph.add_node(n)
        graph.add_relationship(GraphRelationship('ok', ctor.id, proc.id, RelationshipType.STEP_IN_PROCESS))
        check_pairs(graph)  # constructor process steps are storable
        graph.add_relationship(GraphRelationship('bad', ctor.id, fold.id, RelationshipType.CONTAINS))
        with self.assertRaisesRegex(ValueError, 'after recompute'):
            check_pairs(graph)

    def test_brand_new_load_close_and_readonly_reopen_without_clear(self):
        import real_ladybug as lb
        from src.modules.repo_explorer.graph.storage.code_adapter import LadybugAdapter
        graph = KnowledgeGraph()
        s, p = node('Section', 'doc'), node('Property', 'field')
        graph.add_node(s); graph.add_node(p)
        graph.add_relationship(GraphRelationship('doc', s.id, p.id, RelationshipType.DESCRIBES))
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / 'brand-new-db')
            db = lb.Database(path, buffer_pool_size=256 << 20, max_db_size=1 << 30)
            conn = lb.Connection(db)
            needed = {'Section', 'Property'}
            for label, ddl in zip(code_schema.NODE_TABLES, code_schema.NODE_SCHEMA_QUERIES):
                if label in needed:
                    conn.execute(ddl)
            pairs = [x for x in code_schema._REL_FROM_TO_PAIRS if set(x) <= needed]
            with patch.object(code_schema, '_REL_FROM_TO_PAIRS', pairs):
                conn.execute(code_schema._build_rel_schema_query())
            adapter = LadybugAdapter(path)
            adapter._db, adapter._conn = db, conn
            with patch.object(adapter, 'clear_database', side_effect=AssertionError('must never reset a stage')):
                result = adapter.load_graph(graph, str(Path(root) / 'csv'))
            self.assertEqual((result['node_count'], result['relationship_count']), (2, 1))
            adapter.close()
            del conn, db
            readonly = lb.Database(path, read_only=True, buffer_pool_size=256 << 20, max_db_size=1 << 30)
            conn2 = lb.Connection(readonly)
            query = conn2.execute('MATCH ()-[r:CodeRelation]->() RETURN count(r)')
            self.assertEqual(query.get_next()[0], 1)
            del query, conn2, readonly

    def test_preparation_code_has_no_clear_or_force_reset(self):
        text = (ROOT / '.tmp/prepare_development_cache.py').read_text()
        self.assertNotIn('.clear_database(', text)
        self.assertNotIn('force=True', text)
        self.assertNotIn('build_llm(', text)


if __name__ == '__main__':
    unittest.main()
