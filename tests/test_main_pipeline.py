from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from main import format_edge, run_structure_pipeline


class StructurePipelineTest(unittest.TestCase):
    def test_run_structure_pipeline_builds_file_folder_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            src_dir = repo / "src"
            src_dir.mkdir()
            (src_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

            graph, scanned_paths = run_structure_pipeline(repo)

        self.assertEqual(scanned_paths, ["README.md", "src/app.py"])
        self.assertEqual(graph.node_count, 3)
        self.assertEqual(graph.relationship_count, 1)

        rel = graph.relationships[0]
        self.assertEqual(
            format_edge(graph, rel.source_id, str(rel.type), rel.target_id),
            "src -[CONTAINS]-> src/app.py",
        )


if __name__ == "__main__":
    unittest.main()
