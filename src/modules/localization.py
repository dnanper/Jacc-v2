"""Localization result parsing and three-level evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

_LEVELS = ("found_files", "found_modules", "found_functions")


@dataclass(frozen=True)
class LocalizeResult:
    found_files: list[str]
    found_modules: list[str]
    found_functions: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return asdict(self)


def parse_localize_result(value: str) -> LocalizeResult:
    """Parse the final JSON-only answer emitted by the localization agent."""
    text = value.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("localization_result_must_be_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("localization_result_must_be_object")

    values: dict[str, list[str]] = {}
    for level in _LEVELS:
        raw = payload.get(level)
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ValueError(f"{level}_must_be_string_list")
        values[level] = _unique(_normalize(item) for item in raw)

    return LocalizeResult(**values)


def evaluate_localizations(
    predictions: dict[str, dict[str, Any]],
    ground_truth: dict[str, dict[str, Any]],
    repos: dict[str, str] | None = None,
) -> dict[str, dict[str, float]]:
    """Compute GraphLocator-style success, recall, precision, and F1 by level.

    Like GraphLocator's eval_metric.py, a level is skipped for instances whose
    gold list is empty. `repos` maps instance_id to "owner/name" so the gold
    "name/" checkout prefix can be dropped before matching.
    """
    results: dict[str, dict[str, float]] = {}
    task_ids = sorted(ground_truth)
    for level in _LEVELS:
        scores = [
            score
            for task_id in task_ids
            if (
                score := _score(
                    predictions.get(task_id, {}),
                    ground_truth[task_id],
                    level,
                    repo=(repos or {}).get(task_id),
                )
            )
            is not None
        ]
        results[level] = {
            metric: mean(score[metric] for score in scores) if scores else 0.0
            for metric in ("success_location", "recall", "precision", "f1")
        }
    return results


def _score(
    prediction: dict[str, Any], gold: dict[str, Any], level: str, *, repo: str | None = None
) -> dict[str, float] | None:
    prefix = f"{repo.split('/')[-1]}/" if repo else ""
    predicted = set(_unique(_normalize(str(item)) for item in prediction.get(level, [])))
    expected = set(
        _unique(
            _normalize(str(item)).removeprefix(prefix) for item in gold.get(level, [])
        )
    )
    if not expected:
        return None
    matched = len(predicted & expected)
    recall = matched / len(expected) if expected else 0.0
    precision = matched / len(predicted) if predicted else 0.0
    return {
        "success_location": float(matched == len(expected)),
        "recall": recall,
        "precision": precision,
        "f1": (2 * recall * precision / (recall + precision)) if recall + precision else 0.0,
    }


def _normalize(value: str) -> str:
    value = value.strip().replace("\\", "/")
    return value.removeprefix("/testbed/")


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    return [value for value in values if value and not (value in seen or seen.add(value))]
