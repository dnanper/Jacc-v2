"""Paired comparison of A4 variants run on the same A1-A3; reads saved artifacts, no LLM calls.

Metrics fixed before the held-out runs (EXPLORATION_A4.vn.md §17):
- top-1: the first exported function is a gold function;
- function recall / precision / F1 (GraphLocator style, per instance, then mean), file SL;
- A4+A5 calls per instance; co_change precision (co_change candidates that are gold);
- paired tests against the first arm: exact McNemar on top-1, bootstrap 95% CI of the F1 difference;
- every number also split by whether the issue text names a gold function, and by 1 vs 2+ gold functions.
Arms are `name=workspace`; `a3first` (the first function target of A3) is added from the first arm.

    uv run python src/compare_variants.py --benchmark swe_bench_lite --tasks .tmp/heldout3_lite.json \
        full=.agent_runs/heldout3/full veto=.agent_runs/heldout3/veto ...
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.evaluate_stages import gold_sets
from src.modules.benchmarks import get_benchmark, load_ground_truth, load_instances
from src.modules.localization import _score
from src.modules.repo_profile import _loc

MODEL = "gpt-5.6-luna"
_FUNCTIONS = ("Function:", "Method:", "Constructor:")


def answer(run_dir: Path) -> dict | None:
    """The pipeline's answer (A6) plus A4 diagnostics, or None if the run is missing."""
    load = lambda name: json.loads(p.read_text()) if (p := run_dir / name).exists() else None
    a6, a4, a5 = load("A6_export.json"), load(f"A4_exploration.{MODEL}.json"), load(f"A5_revise.{MODEL}.json")
    if not a6 or not a4:
        return None
    co = [c["node"] for c in (a5 if a6["source"] == "A5" else a4)["candidates"] if c.get("role") == "co_change"]
    return {"functions": a6["found_functions"], "files": a6["found_files"], "co_change": [_loc(n) for n in co],
            "calls": a4["calls"] + (a5["calls"] if a5 else 0)}


def a3_first(run_dir: Path) -> dict | None:
    path = run_dir / f"A3_hypotheses.{MODEL}.json"
    if not path.exists():
        return None
    hyps = json.loads(path.read_text())["hypotheses"]
    first = next((a["node"] for h in hyps for a in h["anchors"] if a["role"] == "target" and a["node"].startswith(_FUNCTIONS)), None)
    return {"functions": [_loc(first)] if first else [], "files": [first.split(":")[1]] if first else [], "co_change": [], "calls": 0}


def row(ans: dict, gold: dict, repo: str) -> dict:
    funcs, _ = gold_sets(gold, repo)
    pred = {"found_functions": ans["functions"], "found_files": ans["files"]}
    fn = _score(pred, gold, "found_functions", repo=repo) or {"recall": 0, "precision": 0, "f1": 0}
    fl = _score(pred, gold, "found_files", repo=repo) or {"success_location": 0}
    return {"top1": bool(ans["functions"]) and ans["functions"][0] in funcs, "R": fn["recall"], "P": fn["precision"], "F1": fn["f1"],
            "file_SL": fl["success_location"], "calls": ans["calls"], "co": len(ans["co_change"]), "co_gold": len(set(ans["co_change"]) & funcs)}


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Discordant pairs (a only, b only) and the exact two-sided p-value."""
    x, y = sum(p and not q for p, q in zip(a, b)), sum(q and not p for p, q in zip(a, b))
    n = x + y
    return x, y, min(1.0, 2 * sum(comb(n, k) for k in range(min(x, y) + 1)) / 2**n) if n else 1.0


def boot(d: list[float], reps: int = 10000) -> tuple[float, float]:
    rng = random.Random(0)
    means = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def names_gold(text: str, gold: dict) -> bool:
    return any(re.search(rf"\b{re.escape(re.split(r'[.:]', f)[-1])}\b", text) for f in gold.get("found_functions", []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--tasks", type=Path, required=True, help="JSON with an 'instances' list (the frozen held-out).")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "evaluation" / "localization")
    ap.add_argument("arms", nargs="+", help="name=workspace; the first is the reference arm.")
    args = ap.parse_args(argv)
    spec = get_benchmark(args.benchmark, args.data_dir)
    gold, meta = load_ground_truth(spec, args.data_dir), {i.instance_id: i for i in load_instances(spec, args.data_dir)}
    tasks = json.loads(args.tasks.read_text())["instances"]
    arms = dict(a.split("=", 1) for a in args.arms)
    safe = lambda t: "".join(c if c.isalnum() or c in "._-" else "_" for c in t)
    first_ws = Path(next(iter(arms.values())))
    runs = {name: {t: answer(Path(ws) / safe(t)) for t in tasks} for name, ws in arms.items()}
    runs["a3first"] = {t: a3_first(first_ws / safe(t)) for t in tasks}
    done = [t for t in tasks if all(runs[n][t] for n in runs)]
    print(f"{len(done)}/{len(tasks)} instances have every arm; missing: {sorted(set(tasks) - set(done)) or '-'}")
    rows = {n: {t: row(runs[n][t], gold[t], meta[t].repo) for t in done} for n in runs}
    groups = {"all": done,
              "names gold": [t for t in done if names_gold(meta[t].problem_statement, gold[t])],
              "does not name gold": [t for t in done if not names_gold(meta[t].problem_statement, gold[t])],
              "1 gold function": [t for t in done if len(gold_sets(gold[t], meta[t].repo)[0]) == 1],
              "2+ gold functions": [t for t in done if len(gold_sets(gold[t], meta[t].repo)[0]) > 1]}
    ref = next(iter(arms))
    for g, ts in groups.items():
        if not ts:
            continue
        print(f"\n== {g} (n={len(ts)})")
        print(f"{'arm':10} {'top1':>7} {'R':>5} {'P':>5} {'F1':>5} {'fileSL':>6} {'calls':>6} {'co_change P':>11}   vs {ref}: top1 McNemar (ref only/arm only, p), F1 diff 95% CI")
        for n in runs:
            r = [rows[n][t] for t in ts]
            m = lambda k: sum(x[k] for x in r) / len(r)
            co = sum(x["co"] for x in r)
            line = f"{n:10} {sum(x['top1'] for x in r):>3}/{len(r):<3} {m('R'):5.2f} {m('P'):5.2f} {m('F1'):5.2f} {m('file_SL'):6.2f} {m('calls'):6.1f} {(f'{sum(x['co_gold'] for x in r)}/{co}' if co else '-'):>11}"
            if n != ref:
                x, y, p = mcnemar([rows[ref][t]["top1"] for t in ts], [rows[n][t]["top1"] for t in ts])
                lo, hi = boot([rows[n][t]["F1"] - rows[ref][t]["F1"] for t in ts])
                line += f"   {x}/{y}, p={p:.2f}; [{lo:+.2f}, {hi:+.2f}]"
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
