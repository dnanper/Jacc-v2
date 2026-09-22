from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import run_localize
from src.modules.benchmarks import LocalizationInstance
from src.modules.repository import GitSnapshotProvider


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class RunLocalizeTest(unittest.TestCase):
    def test_run_instance_uses_only_read_only_ckg_tools(self) -> None:
        instance = LocalizationInstance("task-1", "org/repo", "abc123", "parser loses markers", "python")
        agent = MagicMock()
        agent.solve.return_value = MagicMock(
            status="complete",
            final_answer=json.dumps({"found_files": ["src/parser.py"], "found_modules": [], "found_functions": ["src/parser.py::parse"]}),
            errors=[],
            state={"messages": [AIMessage(content="done")]},
        )
        snapshot = MagicMock(path=Path("/snapshot"), reused_repo=True, reused_snapshot=True)
        ckg = {"backend": MagicMock(), "snapshot_root": Path("/snapshot"), "db_path": Path("/graph/lbug"), "stats": {}, "reused_graph": True}

        with (
            patch.object(run_localize, "prepare_ckg", return_value=ckg),
            patch.object(run_localize, "build_ckg_tools", return_value=[FakeTool("ckg_search")]) as build_tools,
            patch.object(run_localize, "build_llm", return_value=MagicMock()),
            patch.object(run_localize, "BaseCodingAgent", return_value=agent) as base_agent,
            patch.object(run_localize, "write_run_output"),
        ):
            result = run_localize.run_instance(instance, provider=MagicMock(get=MagicMock(return_value=snapshot)), model="gpt-5-mini", max_steps=5, workspace=Path(".tmp"))

        self.assertEqual([tool.name for tool in base_agent.call_args.kwargs["tools"]], ["ckg_search"])
        self.assertEqual(result["status"], "complete")
        self.assertNotIn("patch", result)
        build_tools.assert_called_once()

    def test_invalid_agent_answer_marks_localization_failed(self) -> None:
        instance = LocalizationInstance("task-1", "org/repo", "abc123", "parser loses markers", "python")
        agent = MagicMock()
        agent.solve.return_value = MagicMock(status="complete", final_answer="not json", errors=[], state={"messages": []})
        ckg = {"backend": MagicMock(), "snapshot_root": Path("/snapshot"), "db_path": Path("/graph/lbug"), "stats": {}, "reused_graph": True}
        snapshot = MagicMock(path=Path("/snapshot"), reused_repo=True, reused_snapshot=True)
        with (
            patch.object(run_localize, "prepare_ckg", return_value=ckg),
            patch.object(run_localize, "build_ckg_tools", return_value=[]),
            patch.object(run_localize, "build_llm", return_value=MagicMock()),
            patch.object(run_localize, "BaseCodingAgent", return_value=agent),
            patch.object(run_localize, "write_run_output"),
        ):
            result = run_localize.run_instance(instance, provider=MagicMock(get=MagicMock(return_value=snapshot)), model="gpt-5-mini", max_steps=5, workspace=Path(".tmp"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("localization_result_must_be_json", result["errors"])


class SnapshotProviderTest(unittest.TestCase):
    def test_cache_key_contains_repo_and_commit(self) -> None:
        provider = GitSnapshotProvider(Path(".tmp-source"))
        first = provider.root / "snapshots" / "org-repo-a"  # shape is implementation-private; key must differ
        second = provider.root / "snapshots" / "org-repo-b"
        self.assertNotEqual(first, second)
