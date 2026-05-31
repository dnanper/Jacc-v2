"""Run the coding agent on one SWE-Bench Verified task."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from src.environments.docker import DockerEnvironment  # noqa: E402
from src.modules.agents import (  # noqa: E402
    AgentConfig,
    BaseCodingAgent,
    build_bash_tool,
    build_ckg_tools,
)
from src.modules.repo_explorer.explore import Backend  # noqa: E402
from src.modules.repo_explorer.graph.storage.code_adapter import (
    LadybugAdapter,  # noqa: E402
)
from src.modules.repo_explorer.ingestion.pipeline import (
    run_ingestion_pipeline,  # noqa: E402
)
from src.modules.repo_explorer.ingestion.state import PipelineConfig  # noqa: E402
from src.modules.repo_explorer.repository.repo_manager import (  # noqa: E402
    get_storage_path,
    load_meta,
)
from src.utils.dataset import load_dataset  # noqa: E402
from src.utils.env import load_env_file  # noqa: E402
from src.utils.llm import build_llm  # noqa: E402
from src.utils.log import add_file_handler, logger  # noqa: E402

VERIFIED_DATASET = "princeton-nlp/SWE-Bench_Verified"
DEFAULT_SPLIT = "test"
DEFAULT_WORKSPACE = Path(".agent_runs") / "swebench"
DEFAULT_MAX_STEPS = 50
TESTBED_CWD = "/testbed"
SWEBENCH_BASH_MAX_OUTPUT_CHARS = 8000
SWEBENCH_RECENT_MESSAGE_LIMIT = 12
DEFAULT_CONTAINER_ENV = {
    "PAGER": "cat",
    "MANPAGER": "cat",
    "LESS": "-R",
    "PIP_PROGRESS_BAR": "off",
    "TQDM_DISABLE": "1",
}
DEFAULT_CKG_EXCLUDE = frozenset(
    {
        ".cache",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "site-packages",
    }
)


def load_swebench_instance(
    task_id: str,
    *,
    dataset: str = VERIFIED_DATASET,
    split: str = DEFAULT_SPLIT,
) -> dict[str, Any]:
    """Load one SWE-Bench instance by id."""

    instances = {
        row["instance_id"]: dict(row) for row in load_dataset(dataset, split=split)
    }
    if task_id not in instances:
        available = ", ".join(sorted(instances)[:10])
        raise KeyError(
            f"Task id not found: {task_id}. First available ids: {available}"
        )
    return instances[task_id]


def get_swebench_docker_image_name(instance: dict[str, Any]) -> str:
    """Return the Docker image name used by SWE-Bench eval images."""

    image_name = instance.get("image_name") or instance.get("docker_image")
    if image_name:
        return str(image_name)
    compatible_id = instance["instance_id"].replace("__", "_1776_")
    return f"docker.io/swebench/sweb.eval.x86_64.{compatible_id}:latest".lower()


def create_swebench_environment(
    *,
    image: str,
    timeout: int = 60,
    executable: str | None = None,
) -> DockerEnvironment:
    kwargs: dict[str, Any] = {
        "image": image,
        "cwd": TESTBED_CWD,
        "timeout": timeout,
        "interpreter": ["bash", "-c"],
        "env": DEFAULT_CONTAINER_ENV,
    }
    if executable:
        kwargs["executable"] = executable
    return DockerEnvironment(**kwargs)


def load_task_ids_from_markdown(path: Path) -> list[str]:
    """Extract SWE-Bench instance ids from a markdown task list."""

    text = path.read_text(encoding="utf-8").replace(r"\_", "_")
    task_ids: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-\d+\b", text):
        task_id = match.group(0)
        if task_id not in seen:
            seen.add(task_id)
            task_ids.append(task_id)
    return task_ids


def run_tasks(
    task_ids: list[str],
    *,
    model: str = "gpt-5-mini",
    split: str = DEFAULT_SPLIT,
    workspace_root: Path = DEFAULT_WORKSPACE,
    max_steps: int = DEFAULT_MAX_STEPS,
    docker_executable: str | None = None,
    workers: int = 1,
    use_ckg: bool = False,
    ckg_force: bool = False,
) -> dict[str, Any]:
    """Run multiple SWE-Bench tasks concurrently."""

    max_workers = max(1, workers)
    results: list[dict[str, Any] | None] = [None] * len(task_ids)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                run_task,
                task_id,
                model=model,
                split=split,
                workspace_root=workspace_root,
                max_steps=max_steps,
                docker_executable=docker_executable,
                use_ckg=use_ckg,
                ckg_force=ckg_force,
            ): index
            for index, task_id in enumerate(task_ids)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            task_id = task_ids[index]
            try:
                results[index] = future.result()
            except Exception as exc:
                logger.exception("SWE-Bench task %s failed", task_id)
                results[index] = {
                    "instance_id": task_id,
                    "status": "failed",
                    "final_answer": "",
                    "patch": "",
                    "errors": [str(exc)],
                }

    complete_results = [result for result in results if result is not None]
    completed = sum(
        1 for result in complete_results if result.get("status") == "complete"
    )
    failed = len(complete_results) - completed
    metrics = aggregate_batch_metrics(complete_results)
    return {
        "total": len(complete_results),
        "completed": completed,
        "failed": failed,
        "workers": max_workers,
        "metrics": metrics,
        "results": complete_results,
    }


def run_task(
    task_id: str,
    *,
    model: str = "gpt-5-mini",
    split: str = DEFAULT_SPLIT,
    workspace_root: Path = DEFAULT_WORKSPACE,
    max_steps: int = DEFAULT_MAX_STEPS,
    docker_executable: str | None = None,
    use_ckg: bool = False,
    ckg_force: bool = False,
) -> dict:
    instance = load_swebench_instance(task_id, split=split)
    image = get_swebench_docker_image_name(instance)
    run_dir = workspace_root / safe_name(task_id)
    log_path = make_log_path(run_dir, task_id)
    add_file_handler(log_path)
    logger.info("Starting SWE-Bench task %s with image %s", task_id, image)

    environment = create_swebench_environment(
        image=image,
        executable=docker_executable,
    )
    try:
        logger.info("Docker environment started for %s", task_id)
        tools = build_bash_tool(
            environment,
            max_output_chars=SWEBENCH_BASH_MAX_OUTPUT_CHARS,
        )
        ckg_info: dict[str, Any] = {"enabled": False}
        if use_ckg:
            ckg_context = prepare_swebench_ckg_backend(
                environment,
                run_dir,
                force=ckg_force,
            )
            tools.extend(
                build_ckg_tools(
                    ckg_context["backend"],
                    snapshot_root=ckg_context["snapshot_root"],
                    container_root=TESTBED_CWD,
                )
            )
            ckg_info = summarize_ckg_context(ckg_context)
        agent = BaseCodingAgent(
            llm=build_llm(model),
            tools=tools,
            config=AgentConfig(
                max_steps=max_steps,
                recent_message_limit=SWEBENCH_RECENT_MESSAGE_LIMIT,
                enable_ckg_phase_policy=use_ckg,
            ),
        )
        result = agent.solve(
            {
                "task_id": task_id,
                "issue": render_swebench_issue(
                    instance["problem_statement"],
                    use_ckg=use_ckg,
                ),
                "repo_path": TESTBED_CWD,
            }
        )
        logger.info("Agent finished task %s with status %s", task_id, result.status)
        trajectory = serialize_agent_trajectory(result.state.get("messages", []))
        patch = collect_patch(environment)
        errors = list(result.errors)
        status = result.status
        errors.extend(validate_swebench_result(result.final_answer, patch, trajectory))
        if errors and status == "complete":
            status = "failed"
        trajectory_summary = summarize_agent_trajectory(trajectory)
        logger.info("Agent trajectory summary: %s", trajectory_summary)
        output = {
            "instance_id": task_id,
            "image": image,
            "status": status,
            "final_answer": result.final_answer,
            "patch": patch,
            "errors": errors,
            "log_path": str(log_path),
            "trajectory": trajectory,
            "trajectory_path": str(run_dir / "trajectory.json"),
            "predictions_path": str(run_dir / "preds.jsonl"),
            "trajectory_summary": trajectory_summary,
            "metrics": trajectory_summary,
            "ckg": ckg_info,
        }
        log_agent_trajectory(trajectory)
    finally:
        environment.cleanup()
        logger.info("Docker environment cleaned up for %s", task_id)

    write_run_outputs(run_dir, output, model_name=model)
    logger.info("Wrote SWE-Bench outputs to %s", run_dir)
    return output


def make_predictions_jsonl(
    results: list[dict[str, Any]],
    *,
    model_name: str,
) -> str:
    lines = []
    for result in results:
        prediction = {
            "instance_id": result["instance_id"],
            "model_name_or_path": model_name,
            "model_patch": result.get("patch", ""),
        }
        lines.append(json.dumps(prediction, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def write_batch_outputs(
    workspace_root: Path,
    batch: dict[str, Any],
    *,
    model_name: str,
    predictions_path: Path | None = None,
) -> dict[str, Path]:
    workspace_root.mkdir(parents=True, exist_ok=True)
    summary_path = workspace_root / "batch_summary.json"
    preds_path = predictions_path or workspace_root / "preds.jsonl"
    summary_path.write_text(
        json.dumps(batch, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    preds_path.parent.mkdir(parents=True, exist_ok=True)
    preds_path.write_text(
        make_predictions_jsonl(batch["results"], model_name=model_name),
        encoding="utf-8",
    )
    return {"summary": summary_path, "predictions": preds_path}


def render_swebench_issue(problem_statement: str, *, use_ckg: bool = False) -> str:
    problem_statement = clean_swebench_problem_statement(problem_statement)
    if use_ckg:
        return (
            problem_statement
            + "\n\nYou have bash plus read-only CKG tools. "
            + "CKG was built from the initial /testbed snapshot before any edits; "
            + "use it for localization, call/context lookup, and impact checks only. "
            + "Use bash as the source of truth for current file contents, edits, "
            + "tests, git diff, and any verification. "
            + "Start with ckg_repair_context for a compact evidence bundle, "
            + "or ckg_search when you only need likely files/symbols. "
            + "Use ckg_file_context or ckg_symbol_context to inspect local flows. "
            + "After CKG identifies a likely file, read the exact current source "
            + "region with bash and prefer the smallest patch that addresses the "
            + "reported failure. "
            + "Use ckg_contract for signatures/callers/callees only before risky API edits. "
            + "Use ckg_impact only before changing shared, public, inherited, or high-fan-in symbols. "
            + "Use ckg_crosscut only for cross-file shared utilities, cycles, or duplicated logic. "
            + "Paths returned by CKG are repository-relative and map to /testbed/<path>. "
            + "After you edit files, assume CKG may be stale for those changed files. "
            + "Do not prefix bash commands with `bash -lc`; commands are already "
            + "executed by bash in /testbed. "
            + "Use Python file-edit scripts for reliable multi-line edits. "
            + "Do not use git diff to apply patches; git diff is only for inspection after editing. "
            + "Prefer short, non-interactive commands with bounded output. "
            + "Do not commit changes. When done, summarize the fix and verification."
        )
    return (
        problem_statement
        + "\n\nYou have exactly one tool: bash(command, timeout). "
        + "Use bash to inspect and edit files in /testbed, run verification, and inspect git diff. "
        + "Do not prefix commands with `bash -lc`; commands are already executed by bash in /testbed. "
        + "Use Python file-edit scripts for reliable multi-line edits. "
        + "Do not use git diff to apply patches; git diff is only for inspection after editing. "
        + "Prefer short, non-interactive commands with bounded output. "
        + "Do not commit changes. When done, summarize the fix and verification."
    )


def prepare_swebench_ckg_backend(
    environment: DockerEnvironment,
    run_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Copy /testbed locally, ingest it, and return a read-only CKG backend."""

    snapshot_root = run_dir / "ckg_snapshot" / "testbed"
    copied_snapshot = copy_testbed_snapshot(environment, snapshot_root, force=force)
    storage_path = get_storage_path(snapshot_root)
    db_path = storage_path / "lbug"
    meta = load_meta(snapshot_root)
    reused_graph = db_path.exists() and meta is not None and not force
    stats: dict[str, Any] = dict(meta.stats) if meta and reused_graph else {}

    if reused_graph:
        logger.info("Reusing SWE-Bench CKG graph at %s", db_path)
    else:
        logger.info("Analyzing SWE-Bench snapshot for CKG at %s", snapshot_root)
        state = run_ingestion_pipeline(
            PipelineConfig(
                repo_path=str(snapshot_root),
                force=force,
                persist=True,
                exclude_dirs=DEFAULT_CKG_EXCLUDE,
            )
        )
        stats = dict(state.get("stats", {}))

    adapter = LadybugAdapter(
        db_path=str(db_path),
        repo_source_path=str(snapshot_root.resolve()),
    )
    adapter.connect(read_only=True)
    return {
        "backend": Backend(adapter),
        "snapshot_root": snapshot_root.resolve(),
        "db_path": db_path.resolve(),
        "stats": stats,
        "copied_snapshot": copied_snapshot,
        "reused_graph": reused_graph,
    }


def copy_testbed_snapshot(
    environment: DockerEnvironment,
    snapshot_root: Path,
    *,
    force: bool = False,
) -> bool:
    """Copy the task container's /testbed directory to a local snapshot."""

    if force and snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    if snapshot_root.exists():
        return False
    if not environment.container_id:
        raise RuntimeError("Docker container is not running")

    temp_root = snapshot_root.with_name(f"{snapshot_root.name}.tmp-{uuid4().hex[:8]}")
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        if not copy_tracked_source_snapshot(environment, temp_root):
            copy_full_testbed_snapshot(environment, temp_root)
        temp_root.rename(snapshot_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return True


def copy_tracked_source_snapshot(
    environment: DockerEnvironment,
    destination: Path,
) -> bool:
    """Copy only git-tracked source files from /testbed when possible."""

    if not environment.container_id:
        return False

    try:
        git_root_result = subprocess.run(
            [
                environment.config.executable,
                "exec",
                "-w",
                TESTBED_CWD,
                environment.container_id,
                "git",
                "rev-parse",
                "--show-toplevel",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        git_root = git_root_result.stdout.strip() or TESTBED_CWD
        archive_path = destination.with_suffix(".tar")
        with archive_path.open("wb") as archive_file:
            subprocess.run(
                [
                    environment.config.executable,
                    "exec",
                    "-w",
                    git_root,
                    environment.container_id,
                    "git",
                    "archive",
                    "--format=tar",
                    "HEAD",
                ],
                stdout=archive_file,
                stderr=subprocess.PIPE,
                timeout=600,
                check=True,
            )
        with tarfile.open(archive_path, "r") as archive:
            archive.extractall(destination)
        archive_path.unlink(missing_ok=True)
        return True
    except Exception:
        archive_path = destination.with_suffix(".tar")
        archive_path.unlink(missing_ok=True)
        logger.info(
            "Falling back to docker cp for SWE-Bench CKG snapshot", exc_info=True
        )
        return False


def copy_full_testbed_snapshot(
    environment: DockerEnvironment,
    destination: Path,
) -> None:
    if not environment.container_id:
        raise RuntimeError("Docker container is not running")

    command = [
        environment.config.executable,
        "cp",
        f"{environment.container_id}:{TESTBED_CWD}/.",
        str(destination),
    ]
    subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )


def summarize_ckg_context(context: Any) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"enabled": True}
    return {
        "enabled": True,
        "snapshot_root": str(context.get("snapshot_root", "")),
        "db_path": str(context.get("db_path", "")),
        "stats": _json_safe(context.get("stats", {})),
        "copied_snapshot": bool(context.get("copied_snapshot", False)),
        "reused_graph": bool(context.get("reused_graph", False)),
    }


def clean_swebench_problem_statement(problem_statement: str) -> str:
    """Remove benchmark noise before handing the task to the agent."""

    text = re.sub(r"<!--.*?-->", "", problem_statement, flags=re.DOTALL).strip()
    lines = text.splitlines()
    for length in range(1, (len(lines) // 2) + 1):
        if lines[:length] == lines[length : 2 * length]:
            lines = lines[:length] + lines[2 * length :]
            break
    return "\n".join(lines).strip()


def validate_swebench_result(
    final_answer: str,
    patch: str,
    trajectory: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not patch.strip():
        errors.append("empty_patch")
    if not final_answer.strip():
        errors.append("empty_final_answer")
    if (
        trajectory
        and trajectory[-1]["type"] == "ai"
        and trajectory[-1].get("tool_calls")
    ):
        errors.append("pending_tool_call_at_stop")
    return errors


def collect_patch(environment: DockerEnvironment) -> str:
    """Collect the final patch from the task container."""

    output = environment.execute(
        {"command": "git diff"},
        cwd=environment.config.cwd,
        timeout=60,
    )
    if output["returncode"] != 0:
        raise RuntimeError(output.get("output") or output.get("exception_info"))
    return output["output"]


def write_run_outputs(
    run_dir: Path,
    output: dict[str, Any],
    *,
    model_name: str = "local-agent",
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    output.setdefault("predictions_path", str(run_dir / "preds.jsonl"))
    (run_dir / "result.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    if output.get("trajectory"):
        (run_dir / "trajectory.json").write_text(
            json.dumps(output["trajectory"], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    if output.get("patch"):
        (run_dir / "patch.diff").write_text(output["patch"], encoding="utf-8")
    else:
        (run_dir / "patch.diff").unlink(missing_ok=True)
    (run_dir / "preds.jsonl").write_text(
        make_predictions_jsonl([output], model_name=model_name),
        encoding="utf-8",
    )


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "task"


def make_log_path(run_dir: Path, task_id: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid4().hex[:8]
    return run_dir / "logs" / f"{safe_name(task_id)}-{timestamp}-{suffix}.log"


def serialize_agent_trajectory(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    trajectory: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        item: dict[str, Any] = {
            "index": index,
            "type": getattr(message, "type", type(message).__name__),
            "content": _json_safe(getattr(message, "content", "")),
        }
        if isinstance(message, AIMessage):
            item["tool_calls"] = _json_safe(message.tool_calls)
            item["usage_metadata"] = _json_safe(
                getattr(message, "usage_metadata", None)
            )
            item["response_metadata"] = _json_safe(
                getattr(message, "response_metadata", None)
            )
        if isinstance(message, ToolMessage):
            item["tool_name"] = message.name
            item["tool_call_id"] = message.tool_call_id
        trajectory.append(item)
    return trajectory


def summarize_agent_trajectory(trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "messages": len(trajectory),
        "ai_messages": 0,
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_outputs": 0,
        "tool_errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    for item in trajectory:
        if item["type"] == "ai":
            summary["ai_messages"] += 1
            summary["llm_calls"] += 1
            summary["tool_calls"] += len(item.get("tool_calls") or [])
            usage = item.get("usage_metadata") or {}
            if isinstance(usage, dict):
                summary["input_tokens"] += int(usage.get("input_tokens") or 0)
                summary["output_tokens"] += int(usage.get("output_tokens") or 0)
                summary["total_tokens"] += int(usage.get("total_tokens") or 0)
        if item["type"] == "tool":
            summary["tool_outputs"] += 1
            try:
                payload = json.loads(str(item.get("content", "")))
            except json.JSONDecodeError:
                continue
            if payload.get("returncode") not in (None, 0):
                summary["tool_errors"] += 1
    return summary


def aggregate_batch_metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    metrics = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_outputs": 0,
        "tool_errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    for result in results:
        task_metrics = result.get("metrics") or result.get("trajectory_summary") or {}
        for key in metrics:
            metrics[key] += int(task_metrics.get(key) or 0)
    return metrics


def log_agent_trajectory(trajectory: list[dict[str, Any]]) -> None:
    logger.info("Agent trajectory start (%d messages)", len(trajectory))
    for item in trajectory:
        logger.info(
            "message[%s] type=%s content=%s",
            item["index"],
            item["type"],
            _truncate_for_log(str(item.get("content", ""))),
        )
        for call in item.get("tool_calls") or []:
            logger.info(
                "message[%s] tool_call name=%s args=%s",
                item["index"],
                call.get("name"),
                _truncate_for_log(json.dumps(call.get("args", {}), ensure_ascii=True)),
            )
        if item["type"] == "tool":
            logger.info(
                "message[%s] tool_output name=%s output=%s",
                item["index"],
                item.get("tool_name"),
                _truncate_for_log(str(item.get("content", ""))),
            )
    logger.info("Agent trajectory end")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _truncate_for_log(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    head = max_chars // 2
    tail = max_chars - head
    return value[:head] + "\n...[truncated]...\n" + value[-tail:]


def main(argv: list[str] | None = None) -> int:
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Run local agent on one SWE-Bench Verified task."
    )
    parser.add_argument(
        "task_id",
        nargs="?",
        help="SWE-Bench instance id, e.g. pytest-dev__pytest-10356",
    )
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--task-file", type=Path, help="Markdown file with task ids.")
    parser.add_argument(
        "--skip-first",
        action="store_true",
        help="Skip the first task id loaded from --task-file.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("SWEBENCH_WORKERS", "1")),
        help="Number of tasks to run concurrently in --task-file mode.",
    )
    parser.add_argument(
        "--predictions-path",
        type=Path,
        help="Where to write SWE-Bench predictions jsonl in --task-file mode.",
    )
    parser.add_argument(
        "--docker-executable", default=os.getenv("SWEBENCH_DOCKER_EXECUTABLE")
    )
    parser.add_argument(
        "--use-ckg",
        action="store_true",
        default=os.getenv("SWEBENCH_USE_CKG", "").lower() in {"1", "true", "yes"},
        help="Build a read-only CKG snapshot for each task and expose CKG tools.",
    )
    parser.add_argument(
        "--ckg-force",
        action="store_true",
        default=os.getenv("SWEBENCH_CKG_FORCE", "").lower() in {"1", "true", "yes"},
        help="Re-copy /testbed and re-analyze the CKG snapshot.",
    )
    args = parser.parse_args(argv)

    if args.task_file:
        task_ids = load_task_ids_from_markdown(args.task_file)
        if args.skip_first:
            task_ids = task_ids[1:]
        if not task_ids:
            parser.error("No task ids found after applying filters.")
        batch = run_tasks(
            task_ids,
            model=args.model,
            split=args.split,
            workspace_root=args.workspace,
            max_steps=args.max_steps,
            docker_executable=args.docker_executable,
            workers=args.workers,
            use_ckg=args.use_ckg,
            ckg_force=args.ckg_force,
        )
        paths = write_batch_outputs(
            args.workspace,
            batch,
            model_name=args.model,
            predictions_path=args.predictions_path,
        )
        batch["batch_summary_path"] = str(paths["summary"])
        batch["predictions_path"] = str(paths["predictions"])
        print(json.dumps(batch, indent=2, ensure_ascii=True))
        return 0 if batch["failed"] == 0 else 1

    if not args.task_id:
        parser.error("Provide task_id or --task-file.")

    result = run_task(
        args.task_id,
        model=args.model,
        split=args.split,
        workspace_root=args.workspace,
        max_steps=args.max_steps,
        docker_executable=args.docker_executable,
        use_ckg=args.use_ckg,
        ckg_force=args.ckg_force,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
