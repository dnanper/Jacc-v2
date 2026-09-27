"""Run one read-only localization pipeline across three benchmarks."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))
if str(MODULES) not in os.sys.path:
    os.sys.path.insert(0, str(MODULES))

from src.modules.agents import AgentConfig, BaseCodingAgent, build_ckg_tools
from src.modules.issue_model import IssueModel, parse_issue, render_issue_model
from src.modules.benchmarks import (
    BenchmarkSpec,
    LocalizationInstance,
    get_benchmark,
    iter_selected,
    load_instances,
)
from src.modules.localization import LocalizeResult, parse_localize_result
from src.modules.repo_explorer.explore import Backend
from src.modules.repo_explorer.graph.storage.code_adapter import LadybugAdapter
from src.modules.repo_explorer.ingestion.pipeline import run_ingestion_pipeline
from src.modules.repo_explorer.ingestion.state import PipelineConfig
from src.modules.repo_explorer.repository.repo_manager import get_storage_path, load_meta
from src.modules.repository import GitSnapshotProvider
from src.utils.env import load_env_file
from src.utils.log import add_file_handler, logger
from src.utils.llm import build_llm
from src.utils.observability import instrument_llm, start_observer
DEFAULT_WORKSPACE = Path(".agent_runs") / "localization"
DEFAULT_DATA_DIR = ROOT / "evaluation" / "localization"
DEFAULT_MAX_STEPS = 20
DEFAULT_CHECKPOINT_DB = "postgresql://jacc:jacc@localhost:5433/jacc"  # docker/postgres
DEFAULT_CKG_EXCLUDE = frozenset({".cache", ".mypy_cache", ".pytest_cache", ".tox", "build", "coverage", "dist", "htmlcov", "node_modules", "site-packages"})


TOOL_INSTRUCTIONS = (
    "Use only read-only CKG tools. Start with ckg_search, then retrieve "
    "targeted evidence through CKG context, contract, crosscut, or impact. "
    "Do not edit code, run tests, generate a patch, or use shell commands. "
    "Return only the required JSON localization result."
)


def clean_issue_text(problem_statement: str) -> str:
    """Strip HTML comments and a duplicated title block before issue parsing."""
    text = re.sub(r"<!--.*?-->", "", problem_statement, flags=re.DOTALL).strip()
    lines = text.splitlines()
    for length in range(1, (len(lines) // 2) + 1):
        if lines[:length] == lines[length : 2 * length]:
            lines = lines[:length] + lines[2 * length :]
            break
    return "\n".join(lines).strip()


class PipelineState(TypedDict, total=False):
    """Checkpointed per-instance state; plain JSON-able values only so Postgres rows stay auditable."""

    task_id: str
    problem_statement: str
    issue_model: dict[str, Any] | None
    agent_issue: str  # the only issue text localize sees: rendered IssueModel, or the cleaned raw issue
    snapshot: dict[str, Any]
    ckg: dict[str, Any]
    messages: list[BaseMessage]
    final_answer: str
    status: str
    errors: list[str]


@contextmanager
def open_checkpointer() -> Iterator[Any]:
    """Postgres checkpointer from JACC_CHECKPOINT_DB; set it to an empty string to disable."""
    url = os.getenv("JACC_CHECKPOINT_DB", DEFAULT_CHECKPOINT_DB)
    if not url:
        yield None
        return
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        yield saver


def prepare_ckg(snapshot_path: Path, *, force: bool = False, observer: Any = None) -> dict[str, Any]:
    storage = get_storage_path(snapshot_path)
    db_path = storage / "lbug"
    meta = load_meta(snapshot_path)
    reused = db_path.exists() and meta is not None and not force
    stats = dict(meta.stats) if reused else {}
    if observer:
        observer.step("CKG reuse check: " + ("hit" if reused else "miss"), style="green" if reused else "yellow")
    if not reused:
        state = run_ingestion_pipeline(
            PipelineConfig(
                repo_path=str(snapshot_path),
                force=force,
                persist=True,
                exclude_dirs=DEFAULT_CKG_EXCLUDE,
                on_progress=lambda progress, _: observer.step(
                    f"CKG {progress.phase} ({progress.percent}%)"
                ) if observer else None,
            )
        )
        stats = dict(state.get("stats", {}))
    adapter = LadybugAdapter(db_path=str(db_path), repo_source_path=str(snapshot_path.resolve()))
    adapter.connect(read_only=True)
    return {
        "backend": Backend(adapter),
        "snapshot_root": snapshot_path.resolve(),
        "db_path": db_path.resolve(),
        "stats": stats,
        "reused_graph": reused,
    }


def run_instance(
    instance: LocalizationInstance,
    *,
    provider: GitSnapshotProvider,
    model: str,
    max_steps: int,
    workspace: Path,
    force: bool = False,
    issue_model: bool = True,
) -> dict[str, Any]:
    run_dir = workspace / safe_name(instance.instance_id)
    log_path = make_log_path(run_dir, instance.instance_id)
    add_file_handler(log_path)
    observer = start_observer(instance.instance_id)
    observer.step(f"start benchmark={instance.language} repo={instance.repo}", style="bold cyan")
    thread_id = f"{instance.instance_id}/{uuid4().hex[:8]}"
    try:
        chat = build_llm(model)
        llm, flush = instrument_llm(chat, task_id=instance.instance_id, benchmark=instance.language, model=model)
        observer.flush = flush
        live: dict[str, Any] = {}  # non-serializable handles (DB backend) kept out of checkpoints

        def parse_issue_node(state: PipelineState) -> PipelineState:
            observer.step("[issue] parsing issue into IssueModel", style="cyan")
            parsed = load_or_parse_issue(run_dir, instance, chat, model)
            observer.step("[issue] IssueModel ready", style="green")
            return {"issue_model": parsed.model_dump(), "agent_issue": render_issue_model(parsed)}

        def build_ckg_node(state: PipelineState) -> PipelineState:
            observer.step("[ckg] acquiring Git snapshot", style="cyan")
            snapshot = provider.get(instance, force=force)
            observer.step(f"[ckg] snapshot ready reused_repo={snapshot.reused_repo} reused_snapshot={snapshot.reused_snapshot}", style="green")
            ckg = prepare_ckg(snapshot.path, force=force, observer=observer)
            live["backend"], live["snapshot_root"] = ckg["backend"], ckg["snapshot_root"]
            return {
                "snapshot": {"repo": instance.repo, "commit": instance.base_commit, "path": str(snapshot.path), "reused_repo": snapshot.reused_repo, "reused_snapshot": snapshot.reused_snapshot},
                "ckg": {"db_path": str(ckg["db_path"]), "stats": ckg["stats"], "reused_graph": ckg["reused_graph"]},
            }

        def localize_node(state: PipelineState) -> PipelineState:
            repo_path = state["snapshot"]["path"]
            tools = build_ckg_tools(live["backend"], snapshot_root=live["snapshot_root"], container_root=repo_path)
            observer.step(f"starting localization agent max_steps={max_steps}", style="bold magenta")
            agent = BaseCodingAgent(llm=llm, tools=tools, config=AgentConfig(max_steps=max_steps, enable_ckg_phase_policy=True))
            # Fresh agent: its input is agent_issue only, never earlier node output or messages.
            solved = agent.solve({"task_id": state["task_id"], "issue": state["agent_issue"] + "\n\n" + TOOL_INSTRUCTIONS, "repo_path": repo_path})
            return {"messages": solved.state.get("messages", []), "final_answer": solved.final_answer, "status": solved.status, "errors": list(solved.errors)}

        graph = StateGraph(PipelineState)
        graph.add_node("build_ckg", build_ckg_node)
        graph.add_node("localize", localize_node)
        graph.add_edge(START, "build_ckg")
        if issue_model:
            graph.add_node("parse_issue", parse_issue_node)
            graph.add_edge(START, "parse_issue")
            graph.add_edge(["parse_issue", "build_ckg"], "localize")
        else:
            graph.add_edge("build_ckg", "localize")
        graph.add_edge("localize", END)
        initial: PipelineState = {"task_id": instance.instance_id, "problem_statement": instance.problem_statement, "issue_model": None}
        if not issue_model:
            initial["agent_issue"] = clean_issue_text(instance.problem_statement)
        with open_checkpointer() as checkpointer:
            final = graph.compile(checkpointer=checkpointer).invoke(initial, {"configurable": {"thread_id": thread_id}})
        observer.step("agent finished; parsing localization JSON", style="magenta")
    except Exception:
        observer.step("failed", style="bold red")
        observer.close()
        raise
    trajectory = serialize_agent_trajectory(final.get("messages", []))
    errors = list(final.get("errors", []))
    localization: LocalizeResult | None = None
    try:
        localization = parse_localize_result(final.get("final_answer", ""))
    except ValueError as exc:
        errors.append(str(exc))
    output = {
        "instance_id": instance.instance_id,
        "benchmark": instance.language,
        "status": final.get("status", "failed") if not errors else "failed",
        "localization": localization.to_dict() if localization else None,
        "final_answer": final.get("final_answer", ""),
        "issue_model_enabled": issue_model,
        "issue_model": final.get("issue_model"),
        "thread_id": thread_id,
        "errors": errors,
        "snapshot": final["snapshot"],
        "ckg": final["ckg"],
        "trajectory": trajectory,
        "metrics": summarize_trajectory(trajectory),
        "log_path": str(log_path),
    }
    write_run_output(run_dir, output)
    observer.step(f"output written: {run_dir / 'result.json'}", style="bold green")
    observer.close()
    return output


def load_or_parse_issue(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str) -> IssueModel:
    """Parse once per instance and model; reruns reuse the cached file instead of paying again."""
    path = run_dir / f"issue_model.{safe_name(model)}.json"
    if path.exists():
        return IssueModel.model_validate_json(path.read_text(encoding="utf-8"))
    structured, _ = instrument_llm(chat.with_structured_output(IssueModel, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    parsed = parse_issue(clean_issue_text(instance.problem_statement), structured)
    run_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
    return parsed


def run_benchmark(
    benchmark: str,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    workspace: Path = DEFAULT_WORKSPACE,
    source_cache: Path | None = None,
    task_id: str | None = None,
    model: str = "gpt-5-mini",
    max_steps: int = DEFAULT_MAX_STEPS,
    workers: int = 1,
    force: bool = False,
    issue_model: bool = True,
) -> dict[str, Any]:
    spec = get_benchmark(benchmark, data_dir)
    instances = list(iter_selected(load_instances(spec, data_dir), task_id))
    provider = GitSnapshotProvider(source_cache or workspace / "source-cache")
    results: list[dict[str, Any] | None] = [None] * len(instances)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(run_instance, instance, provider=provider, model=model, max_steps=max_steps, workspace=workspace, force=force, issue_model=issue_model): index
            for index, instance in enumerate(instances)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                logger.exception("Localization failed")
                results[index] = {"instance_id": instances[index].instance_id, "status": "failed", "localization": None, "errors": [str(exc)]}
    complete = [result for result in results if result is not None]
    loc_results = {result["instance_id"]: result["localization"] for result in complete if result.get("localization") is not None}
    workspace.mkdir(parents=True, exist_ok=True)
    result_path = workspace / f"{spec.name}_loc_results.json"
    result_path.write_text(json.dumps(loc_results, indent=2), encoding="utf-8")
    summary = {"benchmark": spec.name, "language": spec.language, "total": len(complete), "completed": sum(result["status"] == "complete" for result in complete), "failed": sum(result["status"] != "complete" for result in complete), "results_path": str(result_path), "results": complete}
    (workspace / f"{spec.name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def write_run_output(run_dir: Path, output: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    (run_dir / "trajectory.json").write_text(json.dumps(output["trajectory"], indent=2), encoding="utf-8")


def serialize_agent_trajectory(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    items = []
    for index, message in enumerate(messages):
        item = {"index": index, "type": message.type, "content": _json_safe(message.content)}
        if isinstance(message, AIMessage):
            item["tool_calls"] = _json_safe(message.tool_calls)
            item["usage_metadata"] = _json_safe(message.usage_metadata)
        if isinstance(message, ToolMessage):
            item["tool_name"] = message.name
            item["tool_call_id"] = message.tool_call_id
        items.append(item)
    return items


def summarize_trajectory(trajectory: list[dict[str, Any]]) -> dict[str, int]:
    result = {"llm_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for item in trajectory:
        if item["type"] != "ai":
            continue
        result["llm_calls"] += 1
        result["tool_calls"] += len(item.get("tool_calls") or [])
        usage = item.get("usage_metadata") or {}
        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                result[key] += int(usage.get(key) or 0)
    return result


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "task"


def make_log_path(run_dir: Path, task_id: str) -> Path:
    return run_dir / "logs" / f"{safe_name(task_id)}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}.log"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def main(argv: list[str] | None = None) -> int:
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run read-only localization on GraphLocator benchmarks.")
    parser.add_argument("--benchmark", choices=("swe_bench_lite", "locbench", "multi_swe_bench_java"), required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--issue-model", action=argparse.BooleanOptionalAction, default=True, help="Parse the issue into an IssueModel before localizing (--no-issue-model feeds the raw issue instead).")
    args = parser.parse_args(argv)
    summary = run_benchmark(args.benchmark, data_dir=args.data_dir, workspace=args.workspace, source_cache=args.source_cache, task_id=args.task_id, model=args.model, max_steps=args.max_steps, workers=args.workers, force=args.force, issue_model=args.issue_model)
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
