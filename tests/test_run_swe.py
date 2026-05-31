from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import run_swe


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class RunSweTest(unittest.TestCase):
    def test_verified_task_loader_selects_instance_by_id(self) -> None:
        rows = [
            {"instance_id": "django__django-1", "problem_statement": "wrong"},
            {"instance_id": "pytest-dev__pytest-10356", "problem_statement": "fix pytest"},
        ]

        with patch.object(run_swe, "load_dataset", return_value=rows) as load_dataset:
            instance = run_swe.load_swebench_instance("pytest-dev__pytest-10356")

        load_dataset.assert_called_once_with("princeton-nlp/SWE-Bench_Verified", split="test")
        self.assertEqual(instance["problem_statement"], "fix pytest")

    def test_image_name_falls_back_to_swebench_eval_image(self) -> None:
        image = run_swe.get_swebench_docker_image_name(
            {"instance_id": "pytest-dev__pytest-10356"}
        )

        self.assertEqual(
            image,
            "docker.io/swebench/sweb.eval.x86_64.pytest-dev_1776_pytest-10356:latest",
        )

    def test_run_task_sets_up_agent_for_benchmark(self) -> None:
        instance = {
            "instance_id": "pytest-dev__pytest-10356",
            "problem_statement": "fix pytest",
        }
        fake_environment = MagicMock()
        fake_agent = MagicMock()
        fake_agent.solve.return_value = MagicMock(
            status="complete",
            final_answer="done",
            errors=[],
            state={
                "messages": [
                    HumanMessage(content="fix pytest"),
                    AIMessage(
                        content="I will inspect files",
                        tool_calls=[
                            {
                                "name": "bash",
                                "args": {"command": "ls -la"},
                                "id": "call_1",
                                "type": "tool_call",
                            }
                        ],
                        usage_metadata={
                            "input_tokens": 11,
                            "output_tokens": 7,
                            "total_tokens": 18,
                        },
                    ),
                    ToolMessage(content="total 4", name="bash", tool_call_id="call_1"),
                ]
            },
        )

        with (
            patch.object(run_swe, "load_swebench_instance", return_value=instance),
            patch.object(run_swe, "create_swebench_environment", return_value=fake_environment) as create_environment,
            patch.object(run_swe, "build_llm", return_value=MagicMock()) as build_llm,
            patch.object(run_swe, "build_bash_tool", return_value=[FakeTool("bash")]) as build_tools,
            patch.object(run_swe, "BaseCodingAgent", return_value=fake_agent) as base_agent,
            patch.object(run_swe, "collect_patch", return_value="diff --git a/x.py b/x.py\n") as collect_patch,
            patch.object(run_swe, "write_run_outputs") as write_outputs,
        ):
            result = run_swe.run_task("pytest-dev__pytest-10356", model="gpt-5-mini", max_steps=12)

        create_environment.assert_called_once()
        build_llm.assert_called_once_with("gpt-5-mini")
        build_tools.assert_called_once_with(
            fake_environment,
            max_output_chars=run_swe.SWEBENCH_BASH_MAX_OUTPUT_CHARS,
        )
        base_agent.assert_called_once()
        agent_config = base_agent.call_args.kwargs["config"]
        self.assertEqual(agent_config.max_steps, 12)
        self.assertEqual(
            agent_config.recent_message_limit,
            run_swe.SWEBENCH_RECENT_MESSAGE_LIMIT,
        )
        fake_agent.solve.assert_called_once()
        collect_patch.assert_called_once_with(fake_environment)
        fake_environment.cleanup.assert_called_once()
        write_outputs.assert_called_once()
        self.assertEqual(write_outputs.call_args.kwargs["model_name"], "gpt-5-mini")
        self.assertEqual(result["patch"], "diff --git a/x.py b/x.py\n")
        self.assertIn("pytest-dev__pytest-10356-", result["log_path"])
        self.assertTrue(result["log_path"].endswith(".log"))
        self.assertTrue(result["predictions_path"].endswith("preds.jsonl"))
        self.assertEqual(result["trajectory"][1]["tool_calls"][0]["args"]["command"], "ls -la")
        self.assertEqual(result["trajectory"][2]["tool_name"], "bash")
        self.assertTrue(result["trajectory_path"].endswith("trajectory.json"))
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertEqual(result["metrics"]["total_tokens"], 18)

    def test_run_task_can_enable_ckg_tools_for_benchmark(self) -> None:
        instance = {
            "instance_id": "pytest-dev__pytest-10356",
            "problem_statement": "fix pytest",
        }
        fake_environment = MagicMock()
        fake_agent = MagicMock()
        fake_agent.solve.return_value = MagicMock(
            status="complete",
            final_answer="done",
            errors=[],
            state={"messages": [AIMessage(content="done")]},
        )

        with (
            patch.object(run_swe, "load_swebench_instance", return_value=instance),
            patch.object(run_swe, "create_swebench_environment", return_value=fake_environment),
            patch.object(run_swe, "prepare_swebench_ckg_backend", return_value=MagicMock()) as prepare_ckg,
            patch.object(run_swe, "build_llm", return_value=MagicMock()),
            patch.object(run_swe, "build_bash_tool", return_value=[FakeTool("bash")]),
            patch.object(run_swe, "build_ckg_tools", return_value=[FakeTool("ckg_search")]) as build_ckg,
            patch.object(run_swe, "BaseCodingAgent", return_value=fake_agent) as base_agent,
            patch.object(run_swe, "collect_patch", return_value="diff --git a/x.py b/x.py\n"),
            patch.object(run_swe, "write_run_outputs"),
        ):
            result = run_swe.run_task("pytest-dev__pytest-10356", use_ckg=True)

        prepare_ckg.assert_called_once()
        build_ckg.assert_called_once()
        tools = base_agent.call_args.kwargs["tools"]
        self.assertEqual([tool.name for tool in tools], ["bash", "ckg_search"])
        self.assertTrue(base_agent.call_args.kwargs["config"].enable_ckg_phase_policy)
        self.assertTrue(result["ckg"]["enabled"])

    def test_run_task_marks_empty_patch_or_answer_as_failed(self) -> None:
        instance = {
            "instance_id": "pytest-dev__pytest-10356",
            "problem_statement": "fix pytest",
        }
        fake_environment = MagicMock()
        fake_agent = MagicMock()
        fake_agent.solve.return_value = MagicMock(
            status="complete",
            final_answer="",
            errors=[],
            state={"messages": [AIMessage(content="")]},
        )

        with (
            patch.object(run_swe, "load_swebench_instance", return_value=instance),
            patch.object(run_swe, "create_swebench_environment", return_value=fake_environment),
            patch.object(run_swe, "build_llm", return_value=MagicMock()),
            patch.object(run_swe, "build_bash_tool", return_value=[FakeTool("bash")]),
            patch.object(run_swe, "BaseCodingAgent", return_value=fake_agent),
            patch.object(run_swe, "collect_patch", return_value=""),
            patch.object(run_swe, "write_run_outputs"),
        ):
            result = run_swe.run_task("pytest-dev__pytest-10356")

        self.assertEqual(result["status"], "failed")
        self.assertIn("empty_patch", result["errors"])
        self.assertIn("empty_final_answer", result["errors"])

    def test_render_swebench_issue_deduplicates_and_strips_pr_template(self) -> None:
        problem_statement = (
            "Bug title\nDetails\n"
            "Bug title\nDetails\n"
            "Fix missing marks\n"
            "<!--\nChecklist text that should not be sent to the agent.\n-->\n"
        )

        rendered = run_swe.render_swebench_issue(problem_statement)

        self.assertEqual(rendered.count("Bug title\nDetails"), 1)
        self.assertNotIn("Checklist text", rendered)
        self.assertIn("Do not prefix commands with `bash -lc`", rendered)

    def test_render_swebench_issue_includes_ckg_guidance_when_enabled(self) -> None:
        rendered = run_swe.render_swebench_issue("fix pytest", use_ckg=True)

        self.assertIn("You have bash plus read-only CKG tools", rendered)
        self.assertIn("CKG was built from the initial /testbed snapshot", rendered)
        self.assertIn("Use bash as the source of truth", rendered)
        self.assertIn("Start with ckg_repair_context", rendered)
        self.assertIn("or ckg_search", rendered)
        self.assertIn("smallest patch", rendered)
        self.assertIn("Use ckg_contract", rendered)
        self.assertIn("Use ckg_impact", rendered)
        self.assertIn("Use ckg_crosscut", rendered)
        self.assertIn("Use Python file-edit scripts", rendered)
        self.assertIn("Do not use git diff to apply patches", rendered)

    def test_copy_testbed_snapshot_prefers_git_archive_of_tracked_source(self) -> None:
        fake_environment = MagicMock()
        fake_environment.container_id = "container-1"
        fake_environment.config.executable = "docker"
        snapshot_root = Path(".agent_runs") / "copy-test" / "testbed"

        def fake_run(command, **kwargs):
            if command[:3] == ["docker", "exec", "-w"]:
                if command[-2:] == ["rev-parse", "--show-toplevel"]:
                    return MagicMock(stdout="/testbed\n", returncode=0)
                if command[-3:] == ["archive", "--format=tar", "HEAD"]:
                    kwargs["stdout"].write(b"tar-bytes")
                    return MagicMock(returncode=0)
            raise AssertionError(f"unexpected command: {command}")

        try:
            with (
                patch.object(run_swe.subprocess, "run", side_effect=fake_run) as run,
                patch.object(run_swe.tarfile, "open") as tar_open,
            ):
                copied = run_swe.copy_testbed_snapshot(fake_environment, snapshot_root)

            self.assertTrue(copied)
            self.assertTrue(snapshot_root.exists())
            self.assertEqual(run.call_args_list[1].args[0][-3:], ["archive", "--format=tar", "HEAD"])
            tar_open.return_value.__enter__.return_value.extractall.assert_called_once()
        finally:
            if snapshot_root.parent.exists():
                run_swe.shutil.rmtree(snapshot_root.parent, ignore_errors=True)

    def test_serialize_agent_trajectory_captures_tool_calls_and_outputs(self) -> None:
        trajectory = run_swe.serialize_agent_trajectory(
            [
                HumanMessage(content="task"),
                AIMessage(
                    content="run test",
                    tool_calls=[
                        {
                            "name": "bash",
                            "args": {"command": "pytest -q"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="1 failed", name="bash", tool_call_id="call_1"),
            ]
        )

        self.assertEqual(trajectory[0]["type"], "human")
        self.assertEqual(trajectory[1]["tool_calls"][0]["name"], "bash")
        self.assertEqual(trajectory[1]["tool_calls"][0]["args"]["command"], "pytest -q")
        self.assertEqual(trajectory[2]["tool_name"], "bash")
        self.assertEqual(trajectory[2]["content"], "1 failed")

    def test_make_log_path_is_unique_and_task_named(self) -> None:
        run_dir = Path(".agent_runs") / "swebench" / "pytest-dev__pytest-10356"

        first = run_swe.make_log_path(run_dir, "pytest-dev__pytest-10356")
        second = run_swe.make_log_path(run_dir, "pytest-dev__pytest-10356")

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, run_dir / "logs")
        self.assertTrue(first.name.startswith("pytest-dev__pytest-10356-"))
        self.assertEqual(first.suffix, ".log")

    def test_load_task_ids_from_markdown_unescapes_and_preserves_order(self) -> None:
        markdown = (
            "pytest-dev\\_\\_pytest-10356\n\n"
            "django\\_\\_django-11532\n\n"
            "pytest-dev\\_\\_pytest-10356\n\n"
            "sympy__sympy-18189\n"
        )
        path = Path(".agent_runs") / "test_tasks.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")

        try:
            task_ids = run_swe.load_task_ids_from_markdown(path)
        finally:
            path.unlink()

        self.assertEqual(
            task_ids,
            [
                "pytest-dev__pytest-10356",
                "django__django-11532",
                "sympy__sympy-18189",
            ],
        )

    def test_run_tasks_collects_results_and_counts_statuses(self) -> None:
        def fake_run_task(task_id, **kwargs):
            return {
                "instance_id": task_id,
                "status": "complete" if task_id.endswith("1") else "failed",
                "patch": f"diff --git a/{task_id}.py b/{task_id}.py\n",
            }

        with patch.object(run_swe, "run_task", side_effect=fake_run_task) as run_task:
            batch = run_swe.run_tasks(
                ["repo__task-1", "repo__task-2"],
                model="gpt-5-nano",
                split="test",
                workspace_root=Path(".agent_runs") / "swebench-test",
                max_steps=7,
                docker_executable="docker",
                workers=2,
                use_ckg=True,
            )

        self.assertEqual(run_task.call_count, 2)
        self.assertEqual(batch["total"], 2)
        self.assertEqual(batch["completed"], 1)
        self.assertEqual(batch["failed"], 1)
        self.assertEqual(batch["metrics"]["llm_calls"], 0)
        self.assertTrue(all(call.kwargs["use_ckg"] for call in run_task.call_args_list))
        self.assertEqual([item["instance_id"] for item in batch["results"]], ["repo__task-1", "repo__task-2"])

    def test_make_predictions_jsonl_writes_model_patches(self) -> None:
        predictions = run_swe.make_predictions_jsonl(
            [
                {
                    "instance_id": "repo__task-1",
                    "patch": "diff --git a/a.py b/a.py\n",
                },
                {"instance_id": "repo__task-2", "patch": ""},
            ],
            model_name="local-agent",
        )

        lines = predictions.splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        self.assertEqual(first["instance_id"], "repo__task-1")
        self.assertEqual(first["model_name_or_path"], "local-agent")
        self.assertEqual(first["model_patch"], "diff --git a/a.py b/a.py\n")
        self.assertEqual(second["model_patch"], "")

    def test_summarize_agent_trajectory_counts_llm_calls_and_tokens(self) -> None:
        summary = run_swe.summarize_agent_trajectory(
            [
                {
                    "type": "ai",
                    "tool_calls": [{"name": "bash"}],
                    "usage_metadata": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                },
                {"type": "tool", "content": '{"returncode": 0}'},
                {
                    "type": "ai",
                    "tool_calls": [],
                    "usage_metadata": {
                        "input_tokens": 20,
                        "output_tokens": 6,
                        "total_tokens": 26,
                    },
                },
            ]
        )

        self.assertEqual(summary["llm_calls"], 2)
        self.assertEqual(summary["input_tokens"], 30)
        self.assertEqual(summary["output_tokens"], 11)
        self.assertEqual(summary["total_tokens"], 41)


if __name__ == "__main__":
    unittest.main()
