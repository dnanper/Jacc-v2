from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.localization import evaluate_localizations, parse_localize_result


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
