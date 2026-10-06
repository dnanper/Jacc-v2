"""Per-stage gold tracking for the A2 -> A3 -> A4 pipeline; reads saved artifacts, no LLM calls.

For each instance: does a gold function (or its file) reach the seeds (A2), a hypothesis target
(A3), a node read in exploration (A4), the defect candidates, or the anomaly lines? This says
where gold is lost, which the end-to-end SL/recall numbers cannot.

    uv run python src/evaluate_stages.py --benchmark swe_bench_lite [--model gpt-5.6-luna]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.benchmarks import get_benchmark, load_ground_truth, load_instances
from src.modules.repo_profile import _loc

STAGES = ("seeds", "hyp_target", "read", "candidate", "anomaly", "cand|anom", "revised")


def gold_sets(gold: dict, repo: str) -> tuple[set[str], set[str]]:
    """Gold functions as 'path::Qualified.name' and gold files, without the '<name>/' checkout prefix."""
    prefix = repo.split("/")[-1] + "/"
    # A few gold entries write 'path.py:Name' instead of 'path.py::Name'; read both.
    funcs = {re.sub(r"(\.\w+):(?!:)", r"\1::", f.removeprefix(prefix), count=1) for f in gold.get("found_functions", [])}
    files = {f.removeprefix(prefix) for f in gold.get("found_files", [])}
    return funcs, files


def hits(nodes: list[str], funcs: set[str], files: set[str]) -> tuple[bool, bool]:
    """(function-level hit, file-level hit). A method gold also matches its class node's methods by name."""
    locs = {_loc(n) for n in nodes if n}
    paths = {loc.split("::")[0] for loc in locs} | {n.split(":", 1)[1] for n in nodes if n and n.startswith("File:")}
    return bool(locs & funcs), bool(paths & files)


def stage_nodes(run_dir: Path, model: str) -> dict[str, list[str]] | None:
    def load(name: str) -> dict | None:
        path = run_dir / f"{name}.{model}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    a2, a3, a4, a5 = load("A2_seeds"), load("A3_hypotheses"), load("A4_exploration"), load("A5_revise")
    if a2 is None:
        return None
    out = {"seeds": [s["id"] for s in a2["seeds"]]}
    if a3:
        out["hyp_target"] = [a["node"] for h in a3["hypotheses"] for a in h["anchors"] if a["role"] == "target"]
    if a4:
        out["read"] = [r["node"] for h in a4["hypotheses"] for r in h["reads"]]
        out["candidate"] = [c["node"] for c in a4["candidates"]]
        out["anomaly"] = [o["node"] for o in a4["anomalies"]]
        out["cand|anom"] = out["candidate"] + out["anomaly"]
    if a5:
        out["revised"] = [c["node"] for c in a5["candidates"]]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--benchmark", choices=("swe_bench_lite", "locbench", "multi_swe_bench_java"), required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workspace", type=Path, default=ROOT / ".agent_runs" / "localization")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "evaluation" / "localization")
    args = parser.parse_args(argv)

    spec = get_benchmark(args.benchmark, args.data_dir)
    gold = load_ground_truth(spec, args.data_dir)
    repos = {i.instance_id: i.repo for i in load_instances(spec, args.data_dir)}
    rows = []
    for task, repo in repos.items():
        run_dir = args.workspace / "".join(c if c.isalnum() or c in "._-" else "_" for c in task)
        nodes = stage_nodes(run_dir, args.model) if run_dir.exists() else None
        if nodes is None or task not in gold:
            continue
        funcs, files = gold_sets(gold[task], repo)
        row = {"task": task, "gold": sorted(funcs) or sorted(files)}
        for stage in STAGES:
            if stage in nodes:
                fn, fl = hits(nodes[stage], funcs, files)
                row[stage] = "F" if fn else ("f" if fl else "-")
                row[f"n_{stage}"] = len(set(nodes[stage]))
        a4_path = run_dir / f"A4_exploration.{args.model}.json"
        if a4_path.exists():
            a4 = json.loads(a4_path.read_text(encoding="utf-8"))
            row["status"] = "".join(h["status"][0].upper() for h in a4["hypotheses"])
            row["calls"], row["cite_fail"] = a4["calls"], a4["citation_failures"]
            ranked = [_loc(c["node"]) for c in a4["candidates"]]
            row["rank"] = next((i + 1 for i, loc in enumerate(ranked) if loc in funcs), "")
            row["final"], row["spent"] = ranked, a4["calls"]
        a5_path = run_dir / f"A5_revise.{args.model}.json"
        if a5_path.exists():
            a5 = json.loads(a5_path.read_text(encoding="utf-8"))
            origin = {h["id"]: h["origin"] for h in a5["hypotheses"]}
            gold_from = {origin[h] for c in a5["candidates"] if _loc(c["node"]) in funcs for h in c["hypotheses"]}
            row["origin"] = ",".join(sorted({o.split("(")[0] for o in gold_from})) or "-"
            row["calls"] = f"{row.get('calls', '')}+{a5['calls']}"
            row["final"], row["spent"] = [_loc(c["node"]) for c in a5["candidates"]], row.get("spent", 0) + a5["calls"]
        rows.append(row)

    print(f"{'task':34} " + " ".join(f"{s:>10}" for s in STAGES) + "  statuses  rank  calls  cite_fail  gold_origin")
    for r in rows:
        cells = " ".join(f"{r.get(s, '.') + '/' + str(r.get('n_' + s, '')):>10}" for s in STAGES)
        print(f"{r['task']:34} {cells}  {r.get('status', ''):8}  {r.get('rank', ''):>4}  {r.get('calls', ''):>5}  {r.get('cite_fail', ''):>9}  {r.get('origin', '')}")
    print("\nF = gold function hit, f = only gold file hit, - = miss, /N = distinct nodes at that stage.")
    print("statuses: S supported, C contested, P partial, I inconclusive, R refuted (one letter per hypothesis).")
    print("rank: position of the first gold function among ranked candidates (blank if absent).")
    print("revised: A5 candidates; gold_origin: which hypotheses (A3 or an A5 op) put gold there; calls: A4+A5.")
    for stage in STAGES:
        have = [r for r in rows if stage in r]
        if have:
            print(f"{stage:>10}: function {sum(r[stage] == 'F' for r in have)}/{len(have)}, file {sum(r[stage] in 'Ff' for r in have)}/{len(have)}")
    final = [r for r in rows if "final" in r]
    if final:  # the pipeline's answer: A5 candidates when A5 ran, else A4's
        top1 = sum(bool(r["final"]) and r["final"][0] in {f for f in r["gold"]} for r in final)
        anyk = sum(bool(set(r["final"]) & set(r["gold"])) for r in final)
        print(f"\nfinal answer: top-1 {top1}/{len(final)}, any-rank {anyk}/{len(final)}, "
              f"candidates/instance {sum(len(r['final']) for r in final) / len(final):.1f}, "
              f"A4+A5 calls {sum(r['spent'] for r in final)} ({sum(r['spent'] for r in final) / len(final):.1f}/instance)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
