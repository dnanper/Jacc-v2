from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
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
PROFILE = {"repo": "org/repo", "commit": "abc123"}
SEEDS = {"artifact": "A2", "version": run_localize.SEEDS_VERSION}
HYPS = {"artifact": "A3", "version": run_localize.HYPOTHESES_VERSION}
A3S = {"artifact": "A3S", "version": run_localize.EDIT_SITES_VERSION, "picks": []}
A3R = {"artifact": "A3R", "version": run_localize.EDIT_REGIONS_VERSION, "picks": []}
A4 = {"artifact": "A4", "version": run_localize.EXPLORATION_VERSION, "budget": {"calls": 12, "reads": 6}}
A5 = {"artifact": "A5", "version": run_localize.REVISE_VERSION}
EXPORT = {"artifact": "A6", "source": "A4", "top_k": None, "candidates": [], "found_files": ["src/parser.py"], "found_modules": [], "found_functions": ["src/parser.py::parse"]}
SNAPSHOT = MagicMock(path=Path("/snapshot"), reused_repo=True, reused_snapshot=True)
INSTANCE = LocalizationInstance("task-1", "org/repo", "abc123", "parser loses markers", "python")


def _agent(final_answer: str) -> MagicMock:
    agent = MagicMock()
    agent.solve.return_value = MagicMock(status="complete", final_answer=final_answer, errors=[], state={"messages": [AIMessage(content="done")]})
    return agent


class RunLocalizeTest(unittest.TestCase):
    """Stage functions are stubbed; the tests check wiring, caching, and what each mode sees."""

    def _run(self, workspace: Path, mode: str = "pipeline", agent: MagicMock | None = None, explore_budget=None, **patches: MagicMock) -> dict:
        profile_path = workspace / "artifacts" / "A0.5_repo_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps(PROFILE))
        stubs = {
            "find_seeds": MagicMock(return_value=SEEDS), "generate_hypotheses": MagicMock(return_value=HYPS),
            "find_edit_sites": MagicMock(return_value=A3S), "find_region_sites": MagicMock(return_value=A3R),
            "explore": MagicMock(return_value=A4), "revise": MagicMock(return_value=A5),
            "export": MagicMock(return_value=EXPORT), "parse_issue": MagicMock(return_value=PARSED),
            "build_ckg_tools": MagicMock(return_value=[FakeTool("ckg_search")]),
            **patches,
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict("os.environ", {"JACC_CHECKPOINT_DB": ""}))
            stack.enter_context(patch.object(run_localize, "prepare_ckg", return_value={**CKG, "artifact_dir": profile_path.parent}))
            stack.enter_context(patch.object(run_localize, "load_or_build_repo_profile", MagicMock(return_value=profile_path)))
            stack.enter_context(patch.object(run_localize, "build_llm", return_value=MagicMock()))
            stack.enter_context(patch.object(run_localize, "write_run_output"))
            base_agent = stack.enter_context(patch.object(run_localize, "BaseCodingAgent", return_value=agent or _agent("{}")))
            for name, stub in stubs.items():
                stack.enter_context(patch.object(run_localize, name, stub))
            result = run_localize.run_instance(INSTANCE, provider=MagicMock(get=MagicMock(return_value=SNAPSHOT)), model="gpt-5-mini", workspace=workspace, mode=mode, max_steps=5, explore_budget=explore_budget)
        result["_base_agent"], result["_stubs"] = base_agent, stubs
        return result

    def test_pipeline_answer_is_a6_export_and_no_agent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace))
        result["_base_agent"].assert_not_called()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["localization"]["found_functions"], ["src/parser.py::parse"])
        self.assertEqual(set(result["artifacts"]), {"A0", "A0.5", "A1", "A2", "A3", "A4", "A5", "A6"})
        a4, a5 = result["_stubs"]["export"].call_args.args[:2]
        self.assertEqual((a4["artifact"], a5["artifact"]), ("A4", "A5"))

    def test_mode_a3_stops_after_hypotheses_and_exports_a3_targets(self) -> None:
        export_a3 = MagicMock(return_value=EXPORT)
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="a3", export_a3=export_a3)
        result["_stubs"]["explore"].assert_not_called()
        result["_stubs"]["revise"].assert_not_called()
        result["_stubs"]["export"].assert_not_called()
        result["_stubs"]["find_edit_sites"].assert_not_called()
        self.assertEqual(export_a3.call_args.args[0]["artifact"], "A3")
        self.assertIsNone(export_a3.call_args.args[2])
        self.assertEqual(set(result["artifacts"]), {"A0", "A0.5", "A1", "A2", "A3", "A6"})

    def test_mode_a3s_adds_one_edit_sites_step_and_exports_with_it(self) -> None:
        export_a3 = MagicMock(return_value=EXPORT)
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="a3s", export_a3=export_a3)
        result["_stubs"]["explore"].assert_not_called()
        self.assertEqual(result["_stubs"]["find_edit_sites"].call_args.args[1]["artifact"], "A3")
        self.assertEqual([a["artifact"] for a in export_a3.call_args.args[::2]], ["A3", "A3S"])
        self.assertEqual(set(result["artifacts"]), {"A0", "A0.5", "A1", "A2", "A3", "A3S", "A6"})

    def test_mode_a3r_reads_a2_and_a3_then_exports_only_selected_sites(self) -> None:
        export_a3 = MagicMock(return_value=EXPORT)
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="a3r", export_a3=export_a3)
        result["_stubs"]["explore"].assert_not_called()
        region = result["_stubs"]["find_region_sites"].call_args
        self.assertEqual((region.args[1]["artifact"], region.args[2]["artifact"]), ("A2", "A3"))
        self.assertEqual(export_a3.call_args.args[3]["artifact"], "A3R")
        self.assertEqual(set(result["artifacts"]), {"A0", "A0.5", "A1", "A2", "A3", "A3R", "A6"})

    def test_mode_v6_verifies_once_ranks_with_the_frozen_calibrator_and_exports_its_answer(self) -> None:
        ranked = [("Method:src/parser.py:Parser.parse", 0.9), ("Function:src/util.py:helper", 0.1)]
        patches = {"discover": MagicMock(return_value=([], [], [], set())), "candidates": MagicMock(return_value=[]),
                   "verify": MagicMock(return_value={"labels": {}}), "decide": MagicMock(return_value=(ranked, 1)),
                   "export_ranked": MagicMock(return_value=EXPORT)}
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="v6", **patches)
            self._run(Path(workspace), mode="v6", **patches)
        result["_stubs"]["explore"].assert_not_called()
        self.assertEqual(patches["verify"].call_count, 1)  # cached on the second run
        a3v = patches["export_ranked"].call_args.args[0]
        self.assertEqual((a3v["artifact"], a3v["answer"], a3v["calibrator"]), ("A3V", ["Method:src/parser.py:Parser.parse"], run_localize.load_calibrator()["version"]))
        self.assertEqual(set(result["artifacts"]), {"A0", "A0.5", "A1", "A2", "A3", "A3V", "A6"})

    def test_region_cache_tracks_input_content_not_only_mtime(self) -> None:
        region = MagicMock(return_value=A3R)
        answer = MagicMock(return_value=EXPORT)
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            first = self._run(root, mode="a3r", find_region_sites=region, export_a3=answer)
            self._run(root, mode="a3r", find_region_sites=region, export_a3=answer)
            self.assertEqual(region.call_count, 1)
            from os import utime
            a2 = Path(first["artifacts"]["A2"])
            stamp = a2.stat()
            a2.write_text(json.dumps({**SEEDS, "provenance": "changed"}))
            utime(a2, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self._run(root, mode="a3r", find_region_sites=region, export_a3=answer)
            self.assertEqual(region.call_count, 2)
            a3 = Path(first["artifacts"]["A3"])
            stamp = a3.stat()
            a3.write_text(json.dumps({**HYPS, "provenance": "changed"}))
            utime(a3, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self._run(root, mode="a3r", find_region_sites=region, export_a3=answer)
            self.assertEqual(region.call_count, 3)

    def test_pipeline_stages_read_the_previous_artifact_and_are_cached(self) -> None:
        stubs = {k: MagicMock(return_value=v) for k, v in (("find_seeds", SEEDS), ("generate_hypotheses", HYPS), ("explore", A4), ("revise", A5))}
        parse = MagicMock(return_value=PARSED)
        with tempfile.TemporaryDirectory() as workspace:
            for _ in range(2):
                self._run(Path(workspace), parse_issue=parse, **stubs)
        parse.assert_called_once()
        for stub in stubs.values():
            stub.assert_called_once()  # second run reads every cached artifact
        self.assertEqual(stubs["find_seeds"].call_args.args[1], PROFILE)  # seeds see A0.5
        self.assertEqual(stubs["generate_hypotheses"].call_args.args[1]["artifact"], "A2")
        self.assertEqual(stubs["explore"].call_args.args[1]["artifact"], "A3")
        self.assertEqual([a["artifact"] for a in stubs["revise"].call_args.args[1:3]], ["A3", "A4"])

    def test_explore_budget_is_passed_and_part_of_the_cache_key(self) -> None:
        run = MagicMock(return_value=A4)
        with tempfile.TemporaryDirectory() as workspace:
            self._run(Path(workspace), explore=run)
            self._run(Path(workspace), explore=run, explore_budget=(20, 8))
        self.assertEqual(run.call_count, 2)  # a different budget is not served from the cache
        self.assertEqual((run.call_args.kwargs["max_calls"], run.call_args.kwargs["max_reads"]), (20, 8))

    def test_baseline_is_the_free_agent_on_the_raw_issue_only(self) -> None:
        agent = _agent(json.dumps({"found_files": ["src/parser.py"], "found_modules": [], "found_functions": ["src/parser.py::parse"]}))
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="baseline", agent=agent)
        issue = agent.solve.call_args.args[0]["issue"]
        self.assertTrue(issue.startswith("parser loses markers"))
        for tag in ("<issue_model", "<repo_profile", "<issue_repo_map", "<hypotheses", "<exploration", "<revision"):
            self.assertNotIn(tag, issue)
        self.assertEqual([t.name for t in result["_base_agent"].call_args.kwargs["tools"]], ["ckg_search"])
        for name in ("parse_issue", "find_seeds", "generate_hypotheses", "explore", "revise", "export"):
            result["_stubs"][name].assert_not_called()
        self.assertEqual(set(result["artifacts"]), {"A0"})
        self.assertEqual(result["localization"]["found_functions"], ["src/parser.py::parse"])

    def test_invalid_baseline_answer_marks_localization_failed(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run(Path(workspace), mode="baseline", agent=_agent("not json"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("localization_result_must_be_json", result["errors"])


class SnapshotProviderTest(unittest.TestCase):
    def test_cache_key_contains_repo_and_commit(self) -> None:
        provider = GitSnapshotProvider(Path(".tmp-source"))
        first = provider.root / "snapshots" / "org-repo-a"  # shape is implementation-private; key must differ
        second = provider.root / "snapshots" / "org-repo-b"
        self.assertNotEqual(first, second)

    def test_hypotheses_cache_is_kept_per_sample_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            seeds = run_dir / "A2.json"
            seeds.write_text(json.dumps(SEEDS))
            state = {"artifacts": {"A2": str(seeds)}, "issue_model": PARSED.model_dump()}
            with patch.object(run_localize, "instrument_llm", return_value=(MagicMock(), None)), \
                    patch.object(run_localize, "generate_hypotheses", side_effect=lambda *a, samples, lean: {**HYPS, "samples": samples, "lean": lean}) as gen:
                for k, lean in ((2, False), (2, False), (5, False), (5, True), (5, True)):
                    run_localize.load_or_generate_hypotheses(run_dir, INSTANCE, MagicMock(), "m", state, None, samples=k, lean=lean)
        # same count and flag reuse; a new count or the lean flag regenerates
        self.assertEqual([(c.kwargs["samples"], c.kwargs["lean"]) for c in gen.call_args_list], [(2, False), (5, False), (5, True)])
