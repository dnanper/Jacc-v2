from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.benchmarks import get_benchmark, load_ground_truth, load_instances


class BenchmarkAdapterTest(unittest.TestCase):
    data_dir = ROOT / "evaluation" / "localization"

    def test_registered_benchmarks_match_reported_subsets(self) -> None:
        expected = {
            "swe_bench_lite": ("python", 300),
            "locbench": ("python", 559),
            "multi_swe_bench_java": ("java", 128),
        }
        for name, (language, count) in expected.items():
            spec = get_benchmark(name, self.data_dir)
            instances = load_instances(spec, self.data_dir)
            self.assertEqual(spec.language, language)
            self.assertEqual(len(instances), count)
            self.assertEqual(len({item.instance_id for item in instances}), count)

    def test_ground_truth_uses_same_valid_instance_set(self) -> None:
        for name in ("swe_bench_lite", "locbench", "multi_swe_bench_java"):
            spec = get_benchmark(name, self.data_dir)
            instances = {item.instance_id for item in load_instances(spec, self.data_dir)}
            gold = load_ground_truth(spec, self.data_dir)
            self.assertEqual(instances, set(gold))
