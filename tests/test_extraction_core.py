from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.config import SupportedLanguages
from repo_explorer.ingestion.extraction.docstring_extractor import extract_docstring
from repo_explorer.ingestion.extraction.export_detection import is_exported
from repo_explorer.ingestion.extraction.extract_cache import (
    FileParseResult,
    ParseCache,
    hash_file,
)
from repo_explorer.ingestion.extraction.import_resolvers.utils import SuffixIndex
from repo_explorer.ingestion.extraction.named_binding_extraction import (
    extract_python_named_bindings,
)
from repo_explorer.ingestion.extraction.type_env import TypeEnv, build_type_env
from repo_explorer.parsing.parser_loader import parse_file


def parse_python(code: str):
    return parse_file(code, SupportedLanguages.PYTHON, "sample.py")


def first_node(root, node_type: str):
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == node_type:
            return node
        stack.extend(reversed(node.children))
    raise AssertionError(f"node type not found: {node_type}")


class ExtractionCoreTest(unittest.TestCase):
    def test_extract_python_docstring_from_function_body(self) -> None:
        tree = parse_python(
            'def hello(name):\n'
            '    """Return a friendly greeting for the supplied name."""\n'
            '    return f"Hello {name}"\n'
        )

        function_node = first_node(tree.root_node, "function_definition")
        docstring = extract_docstring(function_node, SupportedLanguages.PYTHON)

        self.assertIsNotNone(docstring)
        assert docstring is not None
        self.assertEqual(
            docstring.content,
            "Return a friendly greeting for the supplied name.",
        )
        self.assertEqual(docstring.start_line, 1)

    def test_python_export_detection_uses_leading_underscore(self) -> None:
        tree = parse_python("def public_name():\n    pass\n\ndef _private_name():\n    pass\n")
        functions = [
            node
            for node in tree.root_node.children
            if node.type == "function_definition"
        ]

        self.assertTrue(
            is_exported(functions[0], "public_name", SupportedLanguages.PYTHON)
        )
        self.assertFalse(
            is_exported(functions[1], "_private_name", SupportedLanguages.PYTHON)
        )

    def test_extract_python_named_bindings_from_import_aliases(self) -> None:
        tree = parse_python("from models.user import User, Repository as Repo\n")
        import_node = first_node(tree.root_node, "import_from_statement")

        bindings = extract_python_named_bindings(import_node)

        self.assertEqual(
            bindings,
            [
                {"local": "User", "exported": "User"},
                {"local": "Repo", "exported": "Repository"},
            ],
        )

    def test_build_type_env_collects_python_annotations_and_constructors(self) -> None:
        tree = parse_python(
            "from models import User\n"
            "user: User = User()\n"
            "repo = Repository()\n"
        )

        env = build_type_env(tree.root_node, SupportedLanguages.PYTHON)

        self.assertEqual(env.lookup("user"), "User")
        self.assertEqual(env.lookup("repo"), "Repository")

    def test_type_env_priority_prefers_explicit_over_constructor_and_seeded(self) -> None:
        env = TypeEnv()
        env.seed({"value": "SeededType"})
        env.add_constructor("value", "ConstructorType")
        env.add_explicit("value", "ExplicitType")

        self.assertEqual(env.lookup("value"), "ExplicitType")

    def test_suffix_index_resolves_unique_file_suffixes(self) -> None:
        index = SuffixIndex(
            [
                "src/models/user.py",
                "src/models/repository.py",
            ]
        )

        self.assertEqual(index.lookup("models/user"), "src/models/user.py")
        self.assertEqual(index.get("repository.py"), "src/models/repository.py")

    def test_parse_cache_classifies_delta_and_round_trips_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            source = repo / "sample.py"
            source.write_text("def hello():\n    pass\n", encoding="utf-8")

            cache = ParseCache(root / "cache")
            cache.load_manifest()
            delta = cache.compute_delta(repo, ["sample.py"])
            self.assertEqual(delta.new_files, ["sample.py"])

            content_hash = hash_file(source)
            result = FileParseResult(
                content_hash=content_hash,
                rel_path="sample.py",
                language="python",
                symbols=[{"name": "hello"}],
            )
            cache.put("sample.py", result)
            cache.save_manifest()

            reloaded = ParseCache(root / "cache")
            reloaded.load_manifest()
            self.assertEqual(reloaded.size, 1)
            cached = reloaded.get("sample.py")
            self.assertIsNotNone(cached)
            assert cached is not None
            self.assertEqual(cached.symbols, [{"name": "hello"}])
            self.assertEqual(
                reloaded.compute_delta(repo, ["sample.py"]).unchanged_files,
                ["sample.py"],
            )


if __name__ == "__main__":
    unittest.main()
