"""Design v3 offline evaluation (no LLM): H1-set, Ranked-prior and, with --cv, Calibrated arms on saved runs.

Each instance directory under --runs holds one A2 seeds file (or --a2-dir/<id>/ does) and one or more A3 files;
every A3 file is one run. Metrics are averaged over runs within an instance, then over instances. --cv fits the
calibrator with 5 folds grouped by instance and reports, on the held-out fold, Calibrated vs Ranked-prior (paired
bootstrap), calibration, the expected-F1 answer and a CRC recall set, each set also against H1-set.
--features v1 (§4.5), v2 (amendment A2), v3 (A3: graph discovery, needs G_candidates.json), v4 (A4: + verifier), v5 (A5) or v6 (A5b: + co-edit completion, needs C2_complete*.json);
--verifier v1|v2 picks V_verify / V2_verify artifacts; --keep-samples 2 rebuilds A3 as K=2 (A5); --ranker pointwise (the calibrator's own order) or conditional (a
within-instance softmax ranker orders, the pointwise calibrator still gives the probabilities the set rules use).

Usage: python -m src.evaluate_ranked --benchmark swe_bench_lite --runs .agent_runs/X [--benchmark B --runs DIR ...] [--a2-dir DIR] [--cv]
       [--alpha 0.3] [--features v1|v2|v3|v4] [--ranker pointwise|conditional]
(pairs of --benchmark/--runs are pooled, so one calibrator is fitted over all of them)
"""

from __future__ import annotations

import argparse
import json
import random
import zlib
from pathlib import Path
from statistics import mean

import numpy as np

from src.evaluate_stages import gold_sets
from src.modules.benchmarks import get_benchmark, load_ground_truth, load_instances
from src.modules.ranking import (FEATURES, FEATURES_V2, FEATURES_V3, FEATURES_V4, FEATURES_V5, FEATURES_V6, FUNCTION_KINDS, restrict_samples, acc_at, average_precision, brier, candidates, crc_threshold,
                                 ece, expected_f1_prefix, fit_conditional_logit, fit_logistic, matrix, ndcg, predict,
                                 reciprocal_rank, set_metrics)
from src.modules.repo_profile import _loc

RANKED = (("MAP@10", average_precision), ("Acc@1", lambda r, g: acc_at(r, g, 1)), ("Acc@5", lambda r, g: acc_at(r, g, 5)),
          ("Acc@10", lambda r, g: acc_at(r, g, 10)), ("MRR", reciprocal_rank), ("NDCG@10", ndcg))
SETS = ("SL", "REC", "PRE", "F1")


def load_runs(runs: Path, a2_dir: Path | None, benchmark: str, data_dir: Path, verifier: str = "V_verify", keep: int | None = None,
              with_completion: bool = True) -> list[dict]:
    """`verifier`: artifact name prefix (V_verify = v1, V2_verify = v2, which also reads the A5b completion unless
    `with_completion` is False); `keep`: rebuild A3 as if only that many samples ran."""
    spec = get_benchmark(benchmark, data_dir)
    gold, meta = load_ground_truth(spec, data_dir), {i.instance_id: i for i in load_instances(spec, data_dir)}
    out = []
    for d in sorted(p for p in runs.iterdir() if p.is_dir() and p.name in gold):
        a2s = sorted(d.glob("A2_seeds*.json")) or (sorted((a2_dir / d.name).glob("A2_seeds*.json")) if a2_dir else [])
        a3s = sorted(d.glob("A3_*.json"))
        funcs = gold_sets(gold[d.name], meta[d.name].repo)[0]
        a1 = next(iter(sorted(d.glob("issue_model*.json"))), None)
        a1 = json.loads(a1.read_text(encoding="utf-8")) if a1 else {}
        trace = "\n".join([a1.get("stack_trace") or "", *(a1.get("error_messages") or [])])
        g = d / "G_candidates.json"
        graph = json.loads(g.read_text(encoding="utf-8"))["candidates"] if g.exists() else None
        v = next(iter(sorted(d.glob(f"{verifier}*.json"))), None)
        checked = json.loads(v.read_text(encoding="utf-8")) if v else None
        c = next(iter(sorted(d.glob("C2_complete*.json"))), None) if verifier == "V2_verify" and with_completion else None
        completion = json.loads(c.read_text(encoding="utf-8")) if c else None
        if not (a2s and a3s and funcs):
            continue
        a2 = json.loads(a2s[0].read_text(encoding="utf-8"))
        for f in a3s:
            a3 = json.loads(f.read_text(encoding="utf-8"))
            a3 = restrict_samples(a3, keep) if keep else a3
            rows = candidates(a3, a2, issue=meta[d.name].problem_statement, trace=trace, graph=graph, verifier=checked, completion=completion)
            h1 = [_loc(a["node"]) for a in (a3["hypotheses"][0]["anchors"] if a3["hypotheses"] else [])
                  if a["role"] == "target" and a["node"].startswith(FUNCTION_KINDS)]
            out.append({"id": d.name, "run": f.name, "gold": funcs, "rows": rows, "h1": list(dict.fromkeys(h1)),
                        "y": np.array([r["loc"] in funcs for r in rows], dtype=float)})
    return out


def per_instance(runs: list[dict], score) -> dict[str, float]:
    """score(run) -> float, averaged over the runs of each instance."""
    by: dict[str, list[float]] = {}
    for r in runs:
        by.setdefault(r["id"], []).append(score(r))
    return {t: mean(v) for t, v in by.items()}


def boot(diffs: list[float], b: int = 10000, seed: int = 0) -> tuple[float, float, float]:
    rng, n = random.Random(seed), len(diffs)
    ms = sorted(mean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(b))
    return mean(diffs), ms[int(0.025 * b)], ms[int(0.975 * b)]


def report(name: str, runs: list[dict], ranked_of) -> dict[str, float]:
    """Ranked metrics of the list ranked_of(run) gives, plus GraphLocator set metrics of that whole list."""
    row = {m: mean(per_instance(runs, lambda r: f(ranked_of(r), r["gold"])).values()) for m, f in RANKED}
    for i, m in enumerate(SETS):
        row[m] = mean(per_instance(runs, lambda r: set_metrics(ranked_of(r), r["gold"])[i]).values())
    row["size"] = mean(per_instance(runs, lambda r: len(ranked_of(r))).values())
    print(f"  {name:34}" + "".join(f" {100 * row[m]:7.1f}" for m, _ in RANKED) + "".join(f" {100 * row[m]:6.1f}" for m in SETS) + f" {row['size']:6.1f}")
    return row


def cross_validate(runs: list[dict], alpha: float, features: tuple[str, ...] = FEATURES, ranker: str = "pointwise", folds: int = 5) -> None:
    ids = sorted({r["id"] for r in runs})
    fold = {t: zlib.crc32(t.encode()) % folds for t in ids}
    for k in range(folds):
        train = [r for r in runs if fold[r["id"]] != k]
        test = [r for r in runs if fold[r["id"]] == k]
        if not test:
            continue
        w = fit_logistic(np.vstack([matrix(r["rows"], features) for r in train]), np.concatenate([r["y"] for r in train]))
        rank_w = fit_conditional_logit([(matrix(r["rows"], features), r["y"]) for r in train]) if ranker == "conditional" else None
        cal = []
        for r in train:
            s = predict(w, matrix(r["rows"], features)).tolist()
            cal.append((s, [bool(v) for v in r["y"]], len(r["gold"])))
        lam = crc_threshold(cal, alpha)
        for r in test:
            x = matrix(r["rows"], features)
            r["p"] = predict(w, x)
            order = np.argsort(-(x @ rank_w if rank_w is not None else r["p"]), kind="stable")
            r["cal"] = [r["rows"][i]["loc"] for i in order]
            r["ef1"] = r["cal"][:expected_f1_prefix(r["p"][order].tolist())]
            r["crc"] = [r["rows"][i]["loc"] for i in order if r["p"][i] >= lam]
    print(f"\n  cross-validated ({folds} folds by instance; {len(features)} features; ranker {ranker}; CRC target recall >= {1 - alpha:.2f}):")
    hdr()
    report("Calibrated (ranked list)", runs, lambda r: r["cal"])
    report("Calibrated, expected-F1 answer", runs, lambda r: r["ef1"])
    report(f"Calibrated, CRC set (alpha {alpha})", runs, lambda r: r["crc"])
    p, y = np.concatenate([r["p"] for r in runs]), np.concatenate([r["y"] for r in runs])
    print(f"  calibration over all candidate rows: Brier {brier(p, y):.3f}, ECE {ece(p, y):.3f}, base rate {y.mean():.3f}")
    a = per_instance(runs, lambda r: average_precision(r["cal"], r["gold"]))
    b = per_instance(runs, lambda r: average_precision([x["loc"] for x in r["rows"]], r["gold"]))
    d, lo, hi = boot([100 * (a[t] - b[t]) for t in a])
    print(f"  MAP@10 Calibrated - Ranked-prior: {d:+.1f} [{lo:+.1f}, {hi:+.1f}] points (paired bootstrap over {len(a)} instances)")
    for arm, name in (("ef1", "expected-F1 answer"), ("crc", "CRC set")):
        line = f"  {name} - H1-set:"
        for i, m in enumerate(SETS):
            a = per_instance(runs, lambda r: set_metrics(r[arm], r["gold"])[i])
            b = per_instance(runs, lambda r: set_metrics(r["h1"], r["gold"])[i])
            d, lo, hi = boot([100 * (a[t] - b[t]) for t in a])
            line += f"  {m} {d:+.1f} [{lo:+.1f}, {hi:+.1f}]"
        print(line)


def hdr() -> None:
    print(f"  {'arm':34}" + "".join(f" {m:>7}" for m, _ in RANKED) + "".join(f" {m:>6}" for m in SETS) + f" {'size':>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", action="append", required=True)
    ap.add_argument("--runs", type=Path, action="append", required=True)
    ap.add_argument("--a2-dir", type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path("evaluation/localization"))
    ap.add_argument("--cv", action="store_true")
    ap.add_argument("--alpha", type=float, default=0.3)
    ap.add_argument("--features", choices=("v1", "v2", "v3", "v4", "v5", "v6"), default="v1")
    ap.add_argument("--verifier", choices=("v1", "v2"), default="v1")
    ap.add_argument("--keep-samples", type=int, help="rebuild A3 as if only the first N samples ran (needs sample_ids)")
    ap.add_argument("--ranker", choices=("pointwise", "conditional"), default="pointwise")
    args = ap.parse_args()
    assert len(args.benchmark) == len(args.runs), "give one --benchmark per --runs"
    prefix = {"v1": "V_verify", "v2": "V2_verify"}[args.verifier]
    runs = [r for b, d in zip(args.benchmark, args.runs) for r in load_runs(d, args.a2_dir, b, args.data_dir, prefix, args.keep_samples)]
    n_ids = len({r["id"] for r in runs})
    ceiling = mean(per_instance(runs, lambda r: len(r["gold"] & {x["loc"] for x in r["rows"]}) / len(r["gold"])).values())
    print(f"{', '.join(f'{d} [{b}]' for b, d in zip(args.benchmark, args.runs))}: {n_ids} instances, {len(runs)} runs, {mean(len(r['rows']) for r in runs):.1f} candidates/run, "
          f"gold among candidates {100 * ceiling:.1f}%")
    hdr()
    report("H1-set (frozen answer)", runs, lambda r: r["h1"])
    report("Ranked-prior (list)", runs, lambda r: [x["loc"] for x in r["rows"]])
    if args.cv:
        cross_validate(runs, args.alpha, {"v1": FEATURES, "v2": FEATURES_V2, "v3": FEATURES_V3, "v4": FEATURES_V4, "v5": FEATURES_V5, "v6": FEATURES_V6}[args.features], args.ranker)


if __name__ == "__main__":
    main()
