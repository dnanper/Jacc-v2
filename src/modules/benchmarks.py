"""Shared dataset adapters for GraphLocator-compatible localization benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

INVALID_LOCBENCH_IDS = frozenset(
    {"NCSU-High-Powered-Rocketry-Club__AirbrakesV2-151"}
)


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    dataset_file: str
    ground_truth_file: str
    language: str
    expected_count: int
    excluded_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LocalizationInstance:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    language: str


BENCHMARKS = {
    "swe_bench_lite": BenchmarkSpec(
        "swe_bench_lite", "swe_bench_lite.jsonl", "swe_bench_lite_gt_entities_3levels.json", "python", 300
    ),
    "locbench": BenchmarkSpec(
        "locbench", "locbench.jsonl", "locbench_gt_entities_3levels.json", "python", 559, INVALID_LOCBENCH_IDS
    ),
    "multi_swe_bench_java": BenchmarkSpec(
        "multi_swe_bench_java", "multi_swe_bench_java.jsonl", "multi_swe_bench_java_gt_entities_3levels.json", "java", 128
    ),
}


def get_benchmark(name: str, data_dir: Path) -> BenchmarkSpec:
    try:
        return BENCHMARKS[name]
    except KeyError as exc:
        raise ValueError(f"unknown benchmark: {name}; choose from {sorted(BENCHMARKS)}") from exc


def load_instances(spec: BenchmarkSpec, data_dir: Path) -> list[LocalizationInstance]:
    path = data_dir / spec.dataset_file
    if not path.exists():
        raise FileNotFoundError(path)
    instances: list[LocalizationInstance] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            required = ("instance_id", "repo", "base_commit", "problem_statement")
            missing = [key for key in required if not row.get(key)]
            if missing:
                raise ValueError(f"{path}:{line_number}: missing {missing}")
            instance_id = str(row["instance_id"])
            if instance_id in spec.excluded_ids:
                continue
            if instance_id in seen:
                raise ValueError(f"duplicate instance_id: {instance_id}")
            seen.add(instance_id)
            instances.append(
                LocalizationInstance(
                    instance_id=instance_id,
                    repo=str(row["repo"]),
                    base_commit=str(row["base_commit"]),
                    problem_statement=str(row["problem_statement"]),
                    language=spec.language,
                )
            )
    if len(instances) != spec.expected_count:
        raise ValueError(
            f"{spec.name}: expected {spec.expected_count} valid instances, got {len(instances)}"
        )
    return instances


def load_ground_truth(spec: BenchmarkSpec, data_dir: Path) -> dict[str, dict[str, Any]]:
    path = data_dir / spec.ground_truth_file
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: ground truth must be an object")
    return {str(key): value for key, value in payload.items() if key not in spec.excluded_ids}


def iter_selected(
    instances: list[LocalizationInstance], task_id: str | None = None
) -> Iterator[LocalizationInstance]:
    if task_id is None:
        yield from instances
        return
    for instance in instances:
        if instance.instance_id == task_id:
            yield instance
            return
    raise KeyError(f"task id not found: {task_id}")
