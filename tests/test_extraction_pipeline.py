from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.config import SupportedLanguages
from repo_explorer.ingestion.extraction.docstring_extractor import extract_docstring
from repo_explorer.ingestion.extraction.export_detection import is_exported
from repo_explorer.ingestion.extraction.import_resolvers.python import (
    resolve_python_import,
)
from repo_explorer.ingestion.extraction.import_resolvers.standard import (
    resolve_import_path,
)
from repo_explorer.ingestion.extraction.import_resolvers.utils import SuffixIndex
from repo_explorer.ingestion.extraction.named_binding_extraction import (
    extract_python_named_bindings,
)
from repo_explorer.ingestion.extraction.type_env import build_type_env
from repo_explorer.parsing.parser_loader import parse_file


PYTHON_SAMPLE = '''\
from models.user import User, Repository as Repo

class Service:
    """Coordinates user loading for the application service layer."""

    def build(self, raw: User):
        """Build a repository-backed user workflow for callers."""
        repo = Repo()
        user: User = raw
        return repo.save(user)

def _private_helper():
    return None
'''


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def nodes_of_type(root, node_type: str):
    return [node for node in walk(root) if node.type == node_type]


def node_name(node) -> str | None:
    name = node.child_by_field_name("name")
    if name is None:
        return None
    text = name.text
    return text.decode("utf-8") if isinstance(text, bytes) else text


class ExtractionPipelineTest(unittest.TestCase):
    def test_python_ast_flows_through_extraction_helpers(self) -> None:
        tree = parse_file(PYTHON_SAMPLE, SupportedLanguages.PYTHON, "sample.py")
        root = tree.root_node

        self.assertEqual(root.type, "module")
        self.assertFalse(root.has_error)

        imports = nodes_of_type(root, "import_from_statement")
        self.assertEqual(len(imports), 1)
        self.assertEqual(
            extract_python_named_bindings(imports[0]),
            [
                {"local": "User", "exported": "User"},
                {"local": "Repo", "exported": "Repository"},
            ],
        )
        all_files = {
            "sample.py",
            "models/user.py",
            "models/repository.py",
        }
        self.assertEqual(
            resolve_python_import("sample.py", "models.user", all_files),
            "models/user.py",
        )
        self.assertEqual(
            resolve_import_path(
                "models/repository",
                "sample.py",
                SuffixIndex(sorted(all_files)),
            ),
            "models/repository.py",
        )

        classes = nodes_of_type(root, "class_definition")
        self.assertEqual([node_name(node) for node in classes], ["Service"])
        class_doc = extract_docstring(classes[0], SupportedLanguages.PYTHON)
        self.assertIsNotNone(class_doc)
        assert class_doc is not None
        self.assertIn("service layer", class_doc.content)
        self.assertTrue(is_exported(classes[0], "Service", SupportedLanguages.PYTHON))

        functions = nodes_of_type(root, "function_definition")
        function_names = [node_name(node) for node in functions]
        self.assertEqual(function_names, ["build", "_private_helper"])

        build_node = functions[0]
        build_doc = extract_docstring(build_node, SupportedLanguages.PYTHON)
        self.assertIsNotNone(build_doc)
        assert build_doc is not None
        self.assertIn("repository-backed", build_doc.content)

        private_node = functions[1]
        self.assertFalse(
            is_exported(private_node, "_private_helper", SupportedLanguages.PYTHON)
        )

        type_env = build_type_env(root, SupportedLanguages.PYTHON)
        self.assertEqual(type_env.lookup("user"), "User")
        self.assertEqual(type_env.lookup("repo"), "Repo")


if __name__ == "__main__":
    unittest.main()
