"""Evaluate GraphLocator-compatible localization predictions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.benchmarks import get_benchmark, load_ground_truth, load_instances
from src.modules.localization import evaluate_localizations
DEFAULT_DATA_DIR = ROOT / "evaluation" / "localization"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate localization results.")
    parser.add_argument("--benchmark", choices=("swe_bench_lite", "locbench", "multi_swe_bench_java"), required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    spec = get_benchmark(args.benchmark, args.data_dir)
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    gold = load_ground_truth(spec, args.data_dir)
    repos = {instance.instance_id: instance.repo for instance in load_instances(spec, args.data_dir)}
    print(json.dumps(evaluate_localizations(predictions, gold, repos), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
