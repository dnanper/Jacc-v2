from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.graph.core.knowledge_graph import KnowledgeGraph
from repo_explorer.graph.model.types import RelationshipType
from repo_explorer.ingestion.call_processor import process_calls
from repo_explorer.ingestion.infile_processor import ExtractedCall
from repo_explorer.ingestion.support.resolution_context import ResolutionContext


class CallProcessorTest(unittest.TestCase):
    def test_member_call_with_multiple_owners_waits_for_receiver_type(self):
        graph = KnowledgeGraph()
        ctx = ResolutionContext()
        ctx.import_map["app/main.py"] = {"models/user.py"}
        ctx.symbols.add(
            "models/user.py",
            "save",
            "Method:models/user.py:AuditLog.save",
            "Method",
            parameter_count=1,
            owner_id="Class:models/user.py:AuditLog",
        )
        ctx.symbols.add(
            "models/user.py",
            "save",
            "Method:models/user.py:Repository.save",
            "Method",
            parameter_count=2,
            owner_id="Class:models/user.py:Repository",
        )

        calls = [
            ExtractedCall(
                file_path="app/main.py",
                called_name="save",
                source_id="Method:app/main.py:Service.build",
                arg_count=1,
                call_form="member",
                receiver_name="repo",
            )
        ]

        process_calls(graph, calls, ctx)

        call_edges = [
            rel
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        ]
        self.assertEqual(call_edges, [])

    def test_member_call_with_receiver_type_resolves_matching_owner(self):
        graph = KnowledgeGraph()
        ctx = ResolutionContext()
        ctx.import_map["app/main.py"] = {"models/user.py"}
        ctx.symbols.add(
            "models/user.py",
            "save",
            "Method:models/user.py:AuditLog.save",
            "Method",
            parameter_count=1,
            owner_id="Class:models/user.py:AuditLog",
        )
        ctx.symbols.add(
            "models/user.py",
            "save",
            "Method:models/user.py:Repository.save",
            "Method",
            parameter_count=2,
            owner_id="Class:models/user.py:Repository",
        )

        calls = [
            ExtractedCall(
                file_path="app/main.py",
                called_name="save",
                source_id="Method:app/main.py:Service.build",
                arg_count=1,
                call_form="member",
                receiver_name="repo",
                receiver_type_name="Repository",
            )
        ]

        process_calls(graph, calls, ctx)

        call_edges = [
            rel
            for rel in graph.iter_relationships()
            if rel.type == RelationshipType.CALLS
        ]
        self.assertEqual(len(call_edges), 1)
        self.assertEqual(call_edges[0].target_id, "Method:models/user.py:Repository.save")
        self.assertEqual(call_edges[0].reason, "import-scoped+owner")


if __name__ == "__main__":
    unittest.main()
