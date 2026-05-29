from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from agents.tools import GENERATED_TOOL_ARTIFACT_PREFIX, build_base_tools, build_create_tool


class BaseToolsTest(unittest.TestCase):
    def test_file_tools_are_scoped_to_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "app.py").write_text("alpha\nbeta\n", encoding="utf-8")

            tools = {tool.name: tool for tool in build_base_tools(root)}
            self.assertTrue(all(tool.args_schema is not None for tool in tools.values()))

            listed = tools["list_dir"].invoke({"path": "pkg"})
            self.assertEqual(listed["entries"][0]["name"], "app.py")

            read = tools["read_file"].invoke(
                {"path": "pkg/app.py", "start_line": 2, "end_line": 2}
            )
            self.assertEqual(read["content"], "beta")

            matches = tools["search_text"].invoke({"query": "alpha", "path": "."})
            self.assertEqual(matches["matches"][0]["path"], "pkg/app.py")

            with self.assertRaises(ValueError):
                tools["read_file"].invoke({"path": "../outside.py"})

    def test_write_and_command_tools_use_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = {tool.name: tool for tool in build_base_tools(root)}

            written = tools["write_file"].invoke(
                {"path": "created.txt", "content": "hello"}
            )
            self.assertTrue(written["written"])
            self.assertEqual((root / "created.txt").read_text(encoding="utf-8"), "hello")

            replaced = tools["replace_in_file"].invoke(
                {
                    "path": "created.txt",
                    "old": "hello",
                    "new": "hello world",
                    "expected_replacements": 1,
                }
            )
            self.assertEqual(replaced["replacements"], 1)
            self.assertEqual(
                (root / "created.txt").read_text(encoding="utf-8"),
                "hello world",
            )

            output = tools["run_command"].invoke({"command": "python -c \"print('ok')\""})
            self.assertEqual(output["returncode"], 0)
            self.assertIn("ok", output["stdout"])

            with self.assertRaises(ValueError):
                tools["run_command"].invoke({"command": "rm -rf ."})

    def test_create_tool_has_schema_and_artifact_prefix(self) -> None:
        create_tool = build_create_tool()

        result = create_tool.invoke(
            {
                "name": "generated_echo",
                "description": "Echo.",
                "code": "def run(text: str) -> str:\n    return text\n",
            }
        )

        self.assertIsNotNone(create_tool.args_schema)
        self.assertTrue(result.startswith(GENERATED_TOOL_ARTIFACT_PREFIX))


if __name__ == "__main__":
    unittest.main()
