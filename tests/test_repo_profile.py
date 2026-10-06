from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.repo_profile import build_repo_profile, load_or_build_repo_profile, render_repo_profile

# Canned rows keyed by a fragment unique to each Cypher query, shaped like LadybugAdapter output.
ROWS = {
    "f.filePath ENDS WITH '__init__.py'": [
        {"path": "pkg/polys/__init__.py", "doc": "Polynomial manipulation algorithms. Examples ======== >>> ..."},
        {"path": "pkg/tests/__init__.py", "doc": "Test package for everything."},
        {"path": "pkg/empty/__init__.py", "doc": ""},
    ],
    "RETURN p.id AS base, c.id AS sub": [
        {"base": "Class:pkg/printer.py:Printer", "sub": f"Class:pkg/p{i}.py:P{i}", "path": f"pkg/p{i}.py"} for i in range(3)
    ] + [
        {"base": "Class:pkg/printer.py:Printer", "sub": "Class:pkg/tests/t.py:TP", "path": "pkg/tests/t.py"},
    ] + [
        {"base": "Class:pkg/errors.py:BaseError", "sub": f"Class:pkg/errors.py:E{i}", "path": "pkg/errors.py"} for i in range(3)
    ] + [
        {"base": "Class:pkg/nodoc.py:Plain", "sub": f"Class:pkg/n{i}.py:N{i}", "path": f"pkg/n{i}.py"} for i in range(3)
    ],
    "c.id AS child, p.id AS parent": [
        {"child": "Class:pkg/errors.py:BaseError", "parent": "Class:Exception"},
        {"child": "Class:pkg/errors.py:DomainProblem", "parent": "Class:pkg/errors.py:BaseError"},
        {"child": "Class:pkg/ops.py:Curl", "parent": "Class:pkg/expr.py:Expr"},
    ],
    "m.name AS name": [
        {"cls": f"Class:pkg/p{i}.py:P{i}", "name": name}
        for i in range(3) for name in ("_print_Add", "_print_Mul", "__init__", "doprint")
    ],
    "n.id IN $ids RETURN n.id AS id, s.content": [{"id": "Class:pkg/printer.py:Printer", "doc": "Generic printer."}],
    "CONTAINS 'getattr'": [
        {"id": "Method:pkg/printer.py:Printer._print", "path": "pkg/printer.py", "code": "f = getattr(self, '_print_' + cls.__name__)"},
        {"id": "Method:pkg/printer.py:Printer.emit", "path": "pkg/printer.py", "code": "m = '_print_' + n\n    return getattr(self, m)(e)"},
        {"id": "Function:pkg/util.py:memo", "path": "pkg/util.py", "code": "getattr(self, '_' + name)"},
        {"id": "Function:pkg/util.py:get", "path": "pkg/util.py", "code": "getattr(obj, name)"},
    ],
    "['RAISES', 'CATCHES']": [
        {"exc": "Class:pkg/errors.py:DomainProblem", "kind": "RAISES", "site": "Function:pkg/poly.py:degree", "path": "pkg/poly.py", "message": "negative degree %s"},
        {"exc": "Class:pkg/errors.py:DomainProblem", "kind": "RAISES", "site": "Function:pkg/poly.py:lead", "path": "pkg/poly.py", "message": ""},
        {"exc": "Class:pkg/errors.py:DomainProblem", "kind": "RAISES", "site": "Function:pkg/poly.py:tail", "path": "pkg/poly.py", "message": ""},
        {"exc": "Class:pkg/errors.py:DomainProblem", "kind": "CATCHES", "site": "Function:pkg/api.py:safe", "path": "pkg/api.py", "message": ""},
        {"exc": "Class:pkg/ops.py:Curl", "kind": "RAISES", "site": "Function:pkg/ops.py:curl", "path": "pkg/ops.py", "message": ""},
        {"exc": "Class:pkg/utils/pytest.py:Skipped", "kind": "RAISES", "site": "Function:pkg/utils/pytest.py:skip", "path": "pkg/utils/pytest.py", "message": ""},
        {"exc": "Class:pkg/errors.py:LoneError", "kind": "RAISES", "site": "Function:pkg/a.py:f", "path": "pkg/a.py", "message": ""},
    ],
    "RETURN a.filePath AS path, r.reason": [
        {"path": "pkg/handlers/h.py", "reason": "global", "n": 80},
        {"path": "pkg/handlers/h.py", "reason": "same-file", "n": 20},
        {"path": "pkg/parsing/test-examples/x.py", "reason": "global", "n": 90},
        {"path": "bin/run.py", "reason": "global", "n": 90},
        {"path": "pkg/poly.py", "reason": "import-scoped", "n": 100},
    ],
}


def fake_query(cypher: str, _params: dict | None = None) -> list[dict]:
    hits = [rows for key, rows in ROWS.items() if key in cypher]
    assert len(hits) == 1, cypher
    return [dict(row) for row in hits[0]]


class RepoProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = build_repo_profile(fake_query, repo="org/repo", commit="abc")

    def test_packages_use_first_sentence_of_init_docstring(self) -> None:
        self.assertEqual(self.profile["packages"], [{"package": "pkg/polys", "purpose": "Polynomial manipulation algorithms."}])

    def test_families_need_doc_or_hooks_and_exclude_exception_trees(self) -> None:
        self.assertEqual(self.profile["families"], [
            {"base": "Class:pkg/printer.py:Printer", "subclasses": 3, "hooks": ["_print_*"], "doc": "Generic printer."},
        ])

    def test_dispatch_groups_by_prefix_and_drops_bare_underscore(self) -> None:
        self.assertEqual(self.profile["dispatch"], [{
            "calls_methods_named": "_print_<name>",
            "dispatchers": ["Method:pkg/printer.py:Printer._print", "Method:pkg/printer.py:Printer.emit"],
            "more": 0,
        }])

    def test_error_map_keeps_repo_exceptions_only(self) -> None:
        # Curl extends Expr (not an exception); Skipped lives in test infra.
        self.assertEqual(self.profile["errors"], [
            {"exception": "Class:pkg/errors.py:DomainProblem", "raised_in": ["Function:pkg/poly.py:degree", "Function:pkg/poly.py:lead"],
             "raise_sites": 3, "message": "negative degree %s", "caught_in": ["Function:pkg/api.py:safe"]},
            {"exception": "Class:pkg/errors.py:LoneError", "raised_in": ["Function:pkg/a.py:f"], "raise_sites": 1, "message": "", "caught_in": []},
        ])

    def test_blind_spots_skip_scripts_and_test_examples(self) -> None:
        self.assertEqual(self.profile["blind_spots"], [{"path": "pkg/handlers", "guessed_call_share": 0.8}])

    def test_render(self) -> None:
        text = render_repo_profile(self.profile)
        self.assertIn("- pkg/polys: Polynomial manipulation algorithms.", text)
        self.assertIn("- pkg/printer.py::Printer (3 subclasses; hooks _print_*): Generic printer.", text)
        self.assertIn("- _print_<name>: pkg/printer.py::Printer._print, pkg/printer.py::Printer.emit", text)
        self.assertIn("- pkg/errors.py::DomainProblem: pkg/poly.py::degree, pkg/poly.py::lead +1; 'negative degree %s'; caught pkg/api.py::safe", text)
        self.assertIn("- pkg/handlers 80%", text)

    def test_profile_file_is_cached_per_commit(self) -> None:
        calls = []

        def counting(cypher: str, params: dict | None = None) -> list[dict]:
            calls.append(cypher)
            return fake_query(cypher, params)

        with tempfile.TemporaryDirectory() as tmp:
            path = load_or_build_repo_profile(Path(tmp), counting, repo="org/repo", commit="abc")
            first = len(calls)
            load_or_build_repo_profile(Path(tmp), counting, repo="org/repo", commit="abc")
            self.assertEqual(len(calls), first)
            load_or_build_repo_profile(Path(tmp), counting, repo="org/repo", commit="def")
            self.assertGreater(len(calls), first)
            self.assertEqual(json.loads(path.read_text())["commit"], "def")


if __name__ == "__main__":
    unittest.main()
