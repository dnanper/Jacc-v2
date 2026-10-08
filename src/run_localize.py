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
from typing import Annotated, Any, Callable, Iterator, TypedDict
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
from src.modules.exploration import EXPLORATION_VERSION, _issue_terms, MAX_CALLS as EXPLORE_CALLS, MAX_READS as EXPLORE_READS, VARIANTS, ExplainCheck, NodeReview, explore
from src.modules.edit_sites import EDIT_SITES_VERSION, EditSites, find_edit_sites
from src.modules.region_sites import EDIT_REGIONS_VERSION, RegionSites, discover, find_region_sites, input_digest
from src.modules.hypotheses import HYPOTHESES_VERSION, SAMPLES, HypothesisSet, _words, generate_hypotheses
from src.modules.issue_model import IssueModel, parse_issue
from src.modules.benchmarks import (
    BenchmarkSpec,
    LocalizationInstance,
    get_benchmark,
    iter_selected,
    load_instances,
)
from src.modules.localization import LocalizeResult, parse_localize_result
from src.modules.export import export, export_a3, export_ranked
from src.modules.ranking import candidates, decide, load_calibrator
from src.modules.verifier import VERIFIER_VERSION, Verification, verify
from src.modules.revise import REVISE_VERSION, Revision, revise
from src.modules.repo_profile import load_or_build_repo_profile, write_json
from src.modules.seeds import SEEDS_VERSION, Review, SeedQueries, find_seeds
from src.modules.repo_explorer.explore import Backend
from src.modules.repo_explorer.graph.storage.code_adapter import LadybugAdapter
from src.modules.repo_explorer.ingestion.pipeline import run_ingestion_pipeline
from src.modules.repo_explorer.ingestion.state import PipelineConfig
from src.modules.repo_explorer.repository.repo_manager import get_storage_path, load_meta
from src.modules.repository import GitSnapshotProvider
from src.utils.env import load_env_file
from src.utils.log import add_file_handler, logger
from langchain_core.callbacks import UsageMetadataCallbackHandler
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
    snapshot: dict[str, Any]
    ckg: dict[str, Any]
    # artifact name -> file path; steps load content from disk, never from state. Merged, since parallel branches both add entries.
    artifacts: Annotated[dict[str, str], lambda old, new: {**old, **new}]
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
        "artifact_dir": (storage / "artifacts").resolve(),
        "stats": stats,
        "reused_graph": reused,
    }


def run_instance(
    instance: LocalizationInstance,
    *,
    provider: GitSnapshotProvider,
    model: str,
    workspace: Path,
    mode: str = "pipeline",
    max_steps: int = DEFAULT_MAX_STEPS,
    force: bool = False,
    explore_budget: tuple[int, int] | None = None,
    a4_variant: str = "full",
    a3_samples: int = SAMPLES,
) -> dict[str, Any]:
    """`pipeline`: A0-A6, the answer is A6. `baseline`: the free ReAct agent on the raw issue with CKG tools only."""
    run_dir = workspace / safe_name(instance.instance_id)
    log_path = make_log_path(run_dir, instance.instance_id)
    add_file_handler(log_path)
    observer = start_observer(instance.instance_id)
    observer.step(f"start mode={mode} benchmark={instance.language} repo={instance.repo}", style="bold cyan")
    thread_id = f"{instance.instance_id}/{mode}/{uuid4().hex[:8]}"
    try:
        usage = UsageMetadataCallbackHandler()  # real token usage per instance (incl. reasoning), summed over every call
        chat = build_llm(model, callbacks=[usage])
        llm, flush = instrument_llm(chat, task_id=instance.instance_id, benchmark=instance.language, model=model)
        observer.flush = flush
        live: dict[str, Any] = {}  # non-serializable handles (DB backend) kept out of checkpoints

        def build_ckg_node(state: PipelineState) -> PipelineState:
            observer.step("[ckg] acquiring Git snapshot", style="cyan")
            snapshot = provider.get(instance, force=force)
            observer.step(f"[ckg] snapshot ready reused_repo={snapshot.reused_repo} reused_snapshot={snapshot.reused_snapshot}", style="green")
            ckg = prepare_ckg(snapshot.path, force=force, observer=observer)
            live["backend"], live["snapshot_root"], live["artifact_dir"] = ckg["backend"], ckg["snapshot_root"], ckg["artifact_dir"]
            return {
                "snapshot": {"repo": instance.repo, "commit": instance.base_commit, "path": str(snapshot.path), "reused_repo": snapshot.reused_repo, "reused_snapshot": snapshot.reused_snapshot},
                "ckg": {"db_path": str(ckg["db_path"]), "stats": ckg["stats"], "reused_graph": ckg["reused_graph"]},
                "artifacts": {"A0": str(ckg["db_path"])},
            }

        def repo_profile_node(state: PipelineState) -> PipelineState:
            observer.step("[ckg] building A0.5 repo profile", style="cyan")
            # Forced graph rebuilds must not reuse a profile computed from the old graph.
            path = load_or_build_repo_profile(live["artifact_dir"], live["backend"]._query, repo=instance.repo, commit=instance.base_commit, force=force)
            observer.step(f"[ckg] A0.5 ready: {path}", style="green")
            return {"artifacts": {"A0.5": str(path)}}

        def parse_issue_node(state: PipelineState) -> PipelineState:
            observer.step("[issue] parsing issue into IssueModel", style="cyan")
            parsed, path = load_or_parse_issue(run_dir, instance, chat, model)
            observer.step(f"[issue] A1 IssueModel ready: {path}", style="green")
            return {"issue_model": parsed.model_dump(), "artifacts": {"A1": str(path)}}

        def stage(name: str, tag: str, loader: Callable[..., Path], **kw: Any) -> Callable[[PipelineState], PipelineState]:
            def node(state: PipelineState) -> PipelineState:
                observer.step(f"[{name}] building {tag}", style="cyan")
                path = loader(run_dir, instance, chat, model, state, live["backend"]._query, force=force, **kw)
                observer.step(f"[{name}] {tag} ready: {path}", style="green")
                return {"artifacts": {tag: str(path)}}
            return node

        def export_node(state: PipelineState) -> PipelineState:
            path = load_or_export(run_dir, state, live["backend"]._query)
            answer = json.loads(path.read_text(encoding="utf-8"))
            observer.step(f"[export] A6 from {answer['source']}: {len(answer['found_functions'])} functions", style="green")
            return {"artifacts": {"A6": str(path)}, "final_answer": json.dumps({k: answer[k] for k in _ANSWER_KEYS}), "status": "complete", "errors": []}

        def baseline_node(state: PipelineState) -> PipelineState:
            repo_path = state["snapshot"]["path"]
            tools = build_ckg_tools(live["backend"], snapshot_root=live["snapshot_root"], container_root=repo_path)
            observer.step(f"[baseline] free agent max_steps={max_steps}", style="bold magenta")
            agent = BaseCodingAgent(llm=llm, tools=tools, config=AgentConfig(max_steps=max_steps, enable_ckg_phase_policy=True))
            issue = "\n\n".join([clean_issue_text(instance.problem_statement), TOOL_INSTRUCTIONS])
            solved = agent.solve({"task_id": state["task_id"], "issue": issue, "repo_path": repo_path})
            return {"messages": solved.state.get("messages", []), "final_answer": solved.final_answer, "status": solved.status, "errors": list(solved.errors)}

        graph = StateGraph(PipelineState)
        graph.add_node("build_ckg", build_ckg_node)
        graph.add_edge(START, "build_ckg")
        if mode == "baseline":
            graph.add_node("baseline", baseline_node)
            graph.add_edge("build_ckg", "baseline")
            graph.add_edge("baseline", END)
        else:
            steps = [
                ("seeds", stage("seeds", "A2", load_or_find_seeds)),
                ("hypotheses", stage("hypotheses", "A3", load_or_generate_hypotheses, samples=a3_samples)),
                *([("edit_sites", stage("edit_sites", "A3S", load_or_find_edit_sites))] if mode == "a3s" else []),
                *([("region_sites", stage("region_sites", "A3R", load_or_find_region_sites))] if mode == "a3r" else []),
                *([("verify", stage("verify", "A3V", load_or_verify))] if mode == "v6" else []),
                *([] if mode in ("a3", "a3s", "a3r", "v6") else [
                    ("exploration", stage("exploration", "A4", load_or_explore, budget=explore_budget, variant=a4_variant)),
                    ("revise", stage("revise", "A5", load_or_revise)),
                ]),
                ("export", export_node),
            ]
            graph.add_node("repo_profile", repo_profile_node)
            graph.add_node("parse_issue", parse_issue_node)
            for name, fn in steps:
                graph.add_node(name, fn)
            graph.add_edge("build_ckg", "repo_profile")
            graph.add_edge(START, "parse_issue")
            graph.add_edge(["parse_issue", "repo_profile"], "seeds")  # seeds join both branches
            for (a, _), (b, _) in zip(steps, steps[1:]):
                graph.add_edge(a, b)
            graph.add_edge("export", END)
        initial: PipelineState = {"task_id": instance.instance_id, "problem_statement": instance.problem_statement, "issue_model": None}
        with open_checkpointer() as checkpointer:
            final = graph.compile(checkpointer=checkpointer).invoke(initial, {"configurable": {"thread_id": thread_id}})
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
        "mode": mode,
        "status": final.get("status", "failed") if not errors else "failed",
        "localization": localization.to_dict() if localization else None,
        "final_answer": final.get("final_answer", ""),
        "issue_model": final.get("issue_model"),
        "thread_id": thread_id,
        "errors": errors,
        "snapshot": final["snapshot"],
        "ckg": final["ckg"],
        "artifacts": final.get("artifacts", {}),
        "trajectory": trajectory,
        "metrics": summarize_trajectory(trajectory),
        "usage": usage.usage_metadata,
        "log_path": str(log_path),
    }
    write_run_output(run_dir, output)
    observer.step(f"output written: {run_dir / 'result.json'}", style="bold green")
    observer.close()
    return output


_ANSWER_KEYS = ("found_files", "found_modules", "found_functions")


def load_or_export(run_dir: Path, state: PipelineState, query: Any) -> Path:
    """A6 is recomputed every run: it is cheap, deterministic, and must follow the latest A3 (mode a3) or A4/A5."""
    path = run_dir / "A6_export.json"
    if "A3V" in state["artifacts"]:
        write_json(path, export_ranked(json.loads(Path(state["artifacts"]["A3V"]).read_text(encoding="utf-8")), query))
        return path
    if "A4" not in state["artifacts"]:
        a3s = json.loads(Path(state["artifacts"]["A3S"]).read_text(encoding="utf-8")) if "A3S" in state["artifacts"] else None
        a3r = json.loads(Path(state["artifacts"]["A3R"]).read_text(encoding="utf-8")) if "A3R" in state["artifacts"] else None
        write_json(path, export_a3(json.loads(Path(state["artifacts"]["A3"]).read_text(encoding="utf-8")), query, a3s, a3r))
        return path
    a4, a5 = (json.loads(Path(state["artifacts"][k]).read_text(encoding="utf-8")) for k in ("A4", "A5"))
    write_json(path, export(a4, a5, query))
    return path


def load_or_find_seeds(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False) -> Path:
    """Find seeds once per instance and model; a forced graph rebuild finds them again."""
    path = run_dir / f"A2_seeds.{safe_name(model)}.json"
    if not force and path.exists() and json.loads(path.read_text(encoding="utf-8")).get("version") == SEEDS_VERSION:
        return path
    profile_path = state.get("artifacts", {}).get("A0.5")
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8")) if profile_path else None
    structured = [
        instrument_llm(chat.with_structured_output(schema, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)[0]
        for schema in (SeedQueries, Review)
    ]
    found = find_seeds(IssueModel.model_validate(state["issue_model"]), profile, query, *structured)
    write_json(path, {**found, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_generate_hypotheses(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False, samples: int = SAMPLES) -> Path:
    """Generate hypotheses once per instance and model; stale when the seeds were redone after them or the sample count differs."""
    path = run_dir / f"A3_hypotheses.{safe_name(model)}.json"
    seeds_path = Path(state["artifacts"]["A2"])
    fresh = path.exists() and path.stat().st_mtime >= seeds_path.stat().st_mtime
    cached = json.loads(path.read_text(encoding="utf-8")) if fresh else {}
    if not force and cached.get("version") == HYPOTHESES_VERSION and cached.get("samples", SAMPLES) == samples:
        return path
    structured, _ = instrument_llm(chat.with_structured_output(HypothesisSet, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
    found = generate_hypotheses(IssueModel.model_validate(state["issue_model"]), seeds, query, structured, samples=samples)
    write_json(path, {**found, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_find_edit_sites(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False) -> Path:
    """Find the other edit sites once per instance and model; stale when the hypotheses were redone after it."""
    path = run_dir / f"A3S_edit_sites.{safe_name(model)}.json"
    hyps_path = Path(state["artifacts"]["A3"])
    fresh = path.exists() and path.stat().st_mtime >= hyps_path.stat().st_mtime
    if not force and fresh and json.loads(path.read_text(encoding="utf-8")).get("version") == EDIT_SITES_VERSION:
        return path
    structured, _ = instrument_llm(chat.with_structured_output(EditSites, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    found = find_edit_sites(IssueModel.model_validate(state["issue_model"]), json.loads(hyps_path.read_text(encoding="utf-8")), query, structured)
    write_json(path, {**found, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_find_region_sites(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False) -> Path:
    """One bounded multi-region edit-set selection; stale when either A2 or A3 changes."""
    path = run_dir / f"A3R_region_sites.{safe_name(model)}.json"
    inputs = [Path(state["artifacts"][tag]) for tag in ("A2", "A3")]
    seeds, hyps = (json.loads(p.read_text(encoding="utf-8")) for p in inputs)
    issue = IssueModel.model_validate(state["issue_model"])
    digest = input_digest(issue, seeds, hyps)
    cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not force and (cached.get("version"), cached.get("input_hash"), cached.get("commit")) == (EDIT_REGIONS_VERSION, digest, instance.base_commit):
        return path
    structured, _ = instrument_llm(chat.with_structured_output(RegionSites, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    found = find_region_sites(issue, seeds, hyps, query, structured, Path(state["snapshot"]["path"]))
    write_json(path, {**found, "input_hash": digest, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_verify(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False) -> Path:
    """V6 (design v3): graph discovery, one listwise verifier call, the frozen calibrator and its expected-F1 answer.
    Stale when A2, A3, the verifier version or the calibrator version changes."""
    path = run_dir / f"A3V_verify.{safe_name(model)}.json"
    seeds, hyps = (json.loads(Path(state["artifacts"][tag]).read_text(encoding="utf-8")) for tag in ("A2", "A3"))
    issue = IssueModel.model_validate(state["issue_model"])
    calibrator = load_calibrator()
    key = (VERIFIER_VERSION, calibrator["version"], input_digest(issue, seeds, hyps), instance.base_commit)
    cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not force and (cached.get("version"), cached.get("calibrator"), cached.get("input_hash"), cached.get("commit")) == key:
        return path
    _, graph, _, _ = discover(issue, seeds, hyps, query)
    trace = "\n".join([issue.stack_trace or "", *issue.error_messages])
    rows = candidates(hyps, seeds, issue=instance.problem_statement, trace=trace, graph=graph)
    structured, _ = instrument_llm(chat.with_structured_output(Verification, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    checked = verify(clean_issue_text(instance.problem_statement), [r["node"] for r in rows], query, _issue_terms(issue) | _words(issue.summary),
                     Path(state["snapshot"]["path"]), structured, seed=instance.instance_id)
    ranked, k = decide(candidates(hyps, seeds, issue=instance.problem_statement, trace=trace, graph=graph, verifier=checked), calibrator)
    write_json(path, {"artifact": "A3V", "version": key[0], "calibrator": key[1], "input_hash": key[2], "verifier": checked, "graph": graph,
                      "ranked": [{"node": n, "p": round(q, 6)} for n, q in ranked], "answer": [n for n, _ in ranked[:k]],
                      "repo": instance.repo, "commit": key[3]})
    return path


def load_or_explore(
    run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any,
    *, force: bool = False, budget: tuple[int, int] | None = None, variant: str = "full",
) -> Path:
    """Explore once per instance, model, budget and ablation variant; stale when the hypotheses were redone after it."""
    calls, reads = budget or (EXPLORE_CALLS, EXPLORE_READS)
    path = run_dir / f"A4_exploration.{safe_name(model)}.json"
    hyps_path = Path(state["artifacts"]["A3"])
    fresh = path.exists() and path.stat().st_mtime >= hyps_path.stat().st_mtime
    cached = json.loads(path.read_text(encoding="utf-8")) if fresh else {}
    if not force and cached.get("version") == EXPLORATION_VERSION and cached.get("budget") == {"calls": calls, "reads": reads} and cached.get("variant", "full") == variant:
        return path
    structured = [
        instrument_llm(chat.with_structured_output(schema, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)[0]
        for schema in (NodeReview, ExplainCheck)
    ]
    hyps = json.loads(hyps_path.read_text(encoding="utf-8"))
    found = explore(IssueModel.model_validate(state["issue_model"]), hyps, query, *structured, max_calls=calls, max_reads=reads, **VARIANTS[variant])
    found["variant"] = variant
    write_json(path, {**found, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_revise(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str, state: PipelineState, query: Any, *, force: bool = False) -> Path:
    """Revise once per instance and model; stale when the exploration was redone after it."""
    path = run_dir / f"A5_revise.{safe_name(model)}.json"
    a4_path = Path(state["artifacts"]["A4"])
    fresh = path.exists() and path.stat().st_mtime >= a4_path.stat().st_mtime
    if not force and fresh and json.loads(path.read_text(encoding="utf-8")).get("version") == REVISE_VERSION:
        return path
    structured = [
        instrument_llm(chat.with_structured_output(schema, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)[0]
        for schema in (Revision, NodeReview, ExplainCheck)
    ]
    a3, a4 = (json.loads(Path(state["artifacts"][k]).read_text(encoding="utf-8")) for k in ("A3", "A4"))
    found = revise(IssueModel.model_validate(state["issue_model"]), a3, a4, query, *structured)
    write_json(path, {**found, "repo": instance.repo, "commit": instance.base_commit})
    return path


def load_or_parse_issue(run_dir: Path, instance: LocalizationInstance, chat: Any, model: str) -> tuple[IssueModel, Path]:
    """Artifact A1. Parse once per instance and model; reruns reuse the cached file instead of paying again."""
    path = run_dir / f"issue_model.{safe_name(model)}.json"
    if path.exists():
        return IssueModel.model_validate_json(path.read_text(encoding="utf-8")), path
    structured, _ = instrument_llm(chat.with_structured_output(IssueModel, method="json_schema", strict=True), task_id=instance.instance_id, benchmark=instance.language, model=model)
    parsed = parse_issue(clean_issue_text(instance.problem_statement), structured)
    run_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
    return parsed, path


def run_benchmark(
    benchmark: str,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    workspace: Path = DEFAULT_WORKSPACE,
    source_cache: Path | None = None,
    task_id: str | None = None,
    model: str = "gpt-5-mini",
    mode: str = "pipeline",
    max_steps: int = DEFAULT_MAX_STEPS,
    workers: int = 1,
    force: bool = False,
    explore_budget: tuple[int, int] | None = None,
    a4_variant: str = "full",
    a3_samples: int = SAMPLES,
) -> dict[str, Any]:
    spec = get_benchmark(benchmark, data_dir)
    all_instances = load_instances(spec, data_dir)
    # --task-id accepts a comma-separated list.
    instances = [i for t in (task_id.split(",") if task_id else [None]) for i in iter_selected(all_instances, t)]
    provider = GitSnapshotProvider(source_cache or workspace / "source-cache")
    results: list[dict[str, Any] | None] = [None] * len(instances)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(run_instance, instance, provider=provider, model=model, workspace=workspace, mode=mode, max_steps=max_steps, force=force, explore_budget=explore_budget, a4_variant=a4_variant, a3_samples=a3_samples): index
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
    parser.add_argument("--task-id", help="One instance id, or several separated by commas.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--mode", choices=("a3", "a3s", "a3r", "v6", "pipeline", "baseline"), default="pipeline",
                        help="a3: frozen A0-A3 answer. v6: A0-A3 (K=2), graph discovery, one listwise verifier call, frozen calibrator, expected-F1 answer (design v3). a3s: H1 plus cited neighbouring sites. a3r: one cited complete edit-set selection over bounded A2/A3 regions. pipeline: A0-A6 (A4/A5 ablation). baseline: the free ReAct agent on the raw issue with CKG tools.")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS, help="Baseline agent steps; unused by the pipeline.")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--explore-budget", type=int, nargs=2, metavar=("CALLS", "READS"), help="A4 budget: max LLM calls per instance and max reads per hypothesis (default 12 6).")
    parser.add_argument("--a3-samples", type=int, default=SAMPLES, help=f"A3 samples pooled per instance (default {SAMPLES}); design v3 Phase 1 uses 5.")
    parser.add_argument("--a4-variant", choices=sorted(VARIANTS), default="full", help="A4 ablation (same prompt and budget); see exploration.VARIANTS.")
    args = parser.parse_args(argv)
    summary = run_benchmark(args.benchmark, data_dir=args.data_dir, workspace=args.workspace, source_cache=args.source_cache, task_id=args.task_id, model=args.model, mode=args.mode, max_steps=args.max_steps, workers=args.workers, force=args.force, explore_budget=tuple(args.explore_budget) if args.explore_budget else None, a4_variant=args.a4_variant, a3_samples=args.a3_samples)
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
