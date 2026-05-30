from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.run_swe import render_swebench_issue, safe_name, write_run_outputs


class SwebenchUtilsTest(unittest.TestCase):
    def test_render_swebench_issue_keeps_problem_and_adds_bash_scope(self) -> None:
        rendered = render_swebench_issue("fix pytest collection")

        self.assertIn("fix pytest collection", rendered)
        self.assertIn("exactly one tool: bash(command, timeout)", rendered)
        self.assertIn("/testbed", rendered)
        self.assertIn("Do not use git diff to apply patches", rendered)
        self.assertIn("Use Python file-edit scripts", rendered)

    def test_write_run_outputs_writes_result_and_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / safe_name("pytest-dev__pytest-10356")
            write_run_outputs(
                run_dir,
                {
                    "instance_id": "pytest-dev__pytest-10356",
                    "patch": "diff --git a/x.py b/x.py\n",
                },
            )

            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            patch = (run_dir / "patch.diff").read_text(encoding="utf-8")
            pred = json.loads(
                (run_dir / "preds.jsonl").read_text(encoding="utf-8").strip()
            )

        self.assertEqual(result["instance_id"], "pytest-dev__pytest-10356")
        self.assertEqual(patch, "diff --git a/x.py b/x.py\n")
        self.assertEqual(pred["instance_id"], "pytest-dev__pytest-10356")
        self.assertEqual(pred["model_name_or_path"], "local-agent")
        self.assertEqual(pred["model_patch"], "diff --git a/x.py b/x.py\n")

    def test_write_run_outputs_removes_stale_patch_when_current_patch_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / safe_name("pytest-dev__pytest-10356")
            run_dir.mkdir(parents=True)
            (run_dir / "patch.diff").write_text("old patch", encoding="utf-8")

            write_run_outputs(
                run_dir,
                {
                    "instance_id": "pytest-dev__pytest-10356",
                    "patch": "",
                },
            )

            self.assertFalse((run_dir / "patch.diff").exists())
            pred = json.loads(
                (run_dir / "preds.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(pred["model_patch"], "")


if __name__ == "__main__":
    unittest.main()
