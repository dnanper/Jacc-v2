"""Run the coding agent on one SWE-Bench Verified task."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.environments.docker import DockerEnvironment  # noqa: E402
from src.modules.agents import AgentConfig, BaseCodingAgent, build_bash_tool  # noqa: E402
from src.utils.env import load_env_file  # noqa: E402
from src.utils.llm import build_llm  # noqa: E402
from src.utils.log import add_file_handler, logger  # noqa: E402
from src.utils.dataset import load_dataset  # noqa: E402

VERIFIED_DATASET = "princeton-nlp/SWE-Bench_Verified"
DEFAULT_SPLIT = "test"
DEFAULT_WORKSPACE = Path(".agent_runs") / "swebench"
TESTBED_CWD = "/testbed"
DEFAULT_CONTAINER_ENV = {
    "PAGER": "cat",
    "MANPAGER": "cat",
    "LESS": "-R",
    "PIP_PROGRESS_BAR": "off",
    "TQDM_DISABLE": "1",
}


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
    max_steps: int = 80,
    docker_executable: str | None = None,
    workers: int = 1,
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
    completed = sum(1 for result in complete_results if result.get("status") == "complete")
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
    max_steps: int = 80,
    docker_executable: str | None = None,
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
        agent = BaseCodingAgent(
            llm=build_llm(model),
            tools=build_bash_tool(environment),
            config=AgentConfig(max_steps=max_steps),
        )
        result = agent.solve(
            {
                "task_id": task_id,
                "issue": render_swebench_issue(instance["problem_statement"]),
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
            "trajectory_summary": trajectory_summary,
            "metrics": trajectory_summary,
        }
        log_agent_trajectory(trajectory)
    finally:
        environment.cleanup()
        logger.info("Docker environment cleaned up for %s", task_id)

    write_run_outputs(run_dir, output)
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


def render_swebench_issue(problem_statement: str) -> str:
    problem_statement = clean_swebench_problem_statement(problem_statement)
    return (
        problem_statement
        + "\n\nYou have exactly one tool: bash(command, timeout). "
        + "Use bash to inspect and edit files in /testbed, run verification, and inspect git diff. "
        + "Do not prefix commands with `bash -lc`; commands are already executed by bash in /testbed. "
        + "Prefer short, non-interactive commands with bounded output. "
        + "Do not commit changes. When done, summarize the fix and verification."
    )


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


def write_run_outputs(run_dir: Path, output: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("--max-steps", type=int, default=80)
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
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
