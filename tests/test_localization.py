from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'src/modules'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.localization import evaluate_localizations, evaluate_repeated_localizations, parse_localize_result
from src.modules.export import localize_nodes


class LocalizationContractTest(unittest.TestCase):
    def test_parses_and_deduplicates_graphlocator_result(self) -> None:
        result = parse_localize_result(
            '{"found_files":["/testbed/pkg/a.py","pkg/a.py"],'
            '"found_modules":["pkg/a.py::Parser"],'
            '"found_functions":["pkg/a.py::Parser.parse","pkg/a.py::Parser.parse"]}'
        )

        self.assertEqual(result.found_files, ["pkg/a.py"])
        self.assertEqual(result.found_modules, ["pkg/a.py::Parser"])
        self.assertEqual(result.found_functions, ["pkg/a.py::Parser.parse"])

    def test_rejects_non_json_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "must_be_json"):
            parse_localize_result("The bug is in pkg/a.py")

    def test_file_only_site_is_counted_without_inventing_a_function(self) -> None:
        prediction = localize_nodes(["File:pkg/config.py", "File:pkg/config.py"]).to_dict()
        self.assertEqual(prediction["found_files"], ["pkg/config.py"])
        self.assertEqual(prediction["found_functions"], [])
        scores = evaluate_localizations({"x": prediction}, {"x": {"found_files": ["pkg/config.py"], "found_functions": []}})
        self.assertEqual(scores["found_files"]["success_location"], 1)

    def test_repeats_do_not_change_instance_weight_and_missing_is_zero(self) -> None:
        gold = {"a": {"found_functions": ["a.py::run"]}, "b": {"found_functions": ["b.py::run"]}}
        good = {"found_functions": ["a.py::run"]}
        scores = evaluate_repeated_localizations({"a": [good] * 3, "b": [{}]}, gold)
        self.assertEqual(scores["found_functions"]["recall"], .5)
        self.assertEqual(scores, evaluate_repeated_localizations({"a": [good] * 3}, gold))
        single = evaluate_localizations({"a": good, "b": {}}, gold)
        self.assertEqual(scores, single)

    def test_sl_requires_all_gold_and_empty_gold_is_not_a_success(self) -> None:
        gold = {"a": {"found_functions": ["a.py::one", "a.py::two"]}, "empty": {"found_functions": []}}
        pred = {"found_functions": ["a.py::one"]}
        scores = evaluate_repeated_localizations({"a": [pred, pred]}, gold)["found_functions"]
        self.assertEqual(scores["success_location"], 0)
        self.assertEqual(scores["recall"], .5)
        self.assertEqual(scores["precision"], 1)
        self.assertAlmostEqual(scores["f1"], 2 / 3)

    def test_scores_file_and_function_levels_independently(self) -> None:
        scores = evaluate_localizations(
            {
                "task-1": {
                    "found_files": ["pkg/a.py"],
                    "found_modules": [],
                    "found_functions": ["pkg/a.py::Parser.parse"],
                }
            },
            {
                "task-1": {
                    "found_files": ["pkg/a.py"],
                    "found_modules": ["pkg/a.py::Parser"],
                    "found_functions": ["pkg/a.py::Parser.render"],
                }
            },
        )

        self.assertEqual(scores["found_files"]["f1"], 1.0)
        self.assertEqual(scores["found_modules"]["f1"], 0.0)
        self.assertEqual(scores["found_functions"]["success_location"], 0.0)
