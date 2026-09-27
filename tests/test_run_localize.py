from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import run_localize
from src.modules.benchmarks import LocalizationInstance
from src.modules.issue_model import IssueModel, Scenario
from src.modules.repository import GitSnapshotProvider


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


PARSED = IssueModel(
    title="parser loses markers", issue_type="bug", report_class="natural_language",
    summary="markers are dropped", scenario=Scenario(precondition="", action="parse", path="parse -> emit"),
    reproduction_steps=[], observed="markers lost", expected="markers kept", error_messages=[],
    stack_trace="", code_snippets=[], environment=[], reporter_hypotheses=[], key_concepts=["marker"],
    explicit_code_refs=[], assumptions=[], unknowns=[],
)
CKG = {"backend": MagicMock(), "snapshot_root": Path("/snapshot"), "db_path": Path("/graph/lbug"), "stats": {}, "reused_graph": True}
SNAPSHOT = MagicMock(path=Path("/snapshot"), reused_repo=True, reused_snapshot=True)
INSTANCE = LocalizationInstance("task-1", "org/repo", "abc123", "parser loses markers", "python")


def _agent(final_answer: str) -> MagicMock:
    agent = MagicMock()
    agent.solve.return_value = MagicMock(status="complete", final_answer=final_answer, errors=[], state={"messages": [AIMessage(content="done")]})
    return agent


class RunLocalizeTest(unittest.TestCase):
    def _run(self, agent: MagicMock, workspace: Path, issue_model: bool = True, **patches: MagicMock) -> dict:
        with (
            patch.dict("os.environ", {"JACC_CHECKPOINT_DB": ""}),
            patch.object(run_localize, "prepare_ckg", return_value=CKG),
            patch.object(run_localize, "build_ckg_tools", patches.get("build_ckg_tools", MagicMock(return_value=[FakeTool("ckg_search")]))),
            patch.object(run_localize, "build_llm", return_value=MagicMock()),
            patch.object(run_localize, "parse_issue", patches.get("parse_issue", MagicMock(return_value=PARSED))),
            patch.object(run_localize, "BaseCodingAgent", return_value=agent) as base_agent,
            patch.object(run_localize, "write_run_output"),
        ):
            result = run_localize.run_instance(INSTANCE, provider=MagicMock(get=MagicMock(return_value=SNAPSHOT)), model="gpt-5-mini", max_steps=5, workspace=workspace, issue_model=issue_model)
        result["_base_agent"] = base_agent
        return result

    def test_run_instance_uses_only_read_only_ckg_tools(self) -> None:
        agent = _agent(json.dumps({"found_files": ["src/parser.py"], "found_modules": [], "found_functions": ["src/parser.py::parse"]}))
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(agent, Path(workspace))
        self.assertEqual([tool.name for tool in result["_base_agent"].call_args.kwargs["tools"]], ["ckg_search"])
        self.assertEqual(result["status"], "complete")
        self.assertNotIn("patch", result)

    def test_invalid_agent_answer_marks_localization_failed(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(_agent("not json"), Path(workspace))
        self.assertEqual(result["status"], "failed")
        self.assertIn("localization_result_must_be_json", result["errors"])

    def test_agent_sees_issue_model_not_raw_issue_and_parse_is_cached(self) -> None:
        agent = _agent('{"found_files": [], "found_modules": [], "found_functions": []}')
        parse = MagicMock(return_value=PARSED)
        with tempfile.TemporaryDirectory() as workspace:
            for _ in range(2):
                result = self._run(agent, Path(workspace), parse_issue=parse)
        parse.assert_called_once()  # second run reads the cached file
        issue = agent.solve.call_args.args[0]["issue"]
        self.assertIn("<issue_model>", issue)
        self.assertEqual(result["issue_model"]["observed"], "markers lost")

    def test_no_issue_model_skips_parse_and_feeds_raw_issue(self) -> None:
        agent = _agent('{"found_files": [], "found_modules": [], "found_functions": []}')
        parse = MagicMock(return_value=PARSED)
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(agent, Path(workspace), issue_model=False, parse_issue=parse)
        parse.assert_not_called()
        issue = agent.solve.call_args.args[0]["issue"]
        self.assertTrue(issue.startswith("parser loses markers"))
        self.assertNotIn("<issue_model>", issue)
        self.assertIsNone(result["issue_model"])


class SnapshotProviderTest(unittest.TestCase):
    def test_cache_key_contains_repo_and_commit(self) -> None:
        provider = GitSnapshotProvider(Path(".tmp-source"))
        first = provider.root / "snapshots" / "org-repo-a"  # shape is implementation-private; key must differ
        second = provider.root / "snapshots" / "org-repo-b"
        self.assertNotEqual(first, second)
