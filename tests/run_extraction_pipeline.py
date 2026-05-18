from __future__ import annotations

import sys
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


CODE = '''\
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


def text(node) -> str:
    value = node.text
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def nodes_of_type(root, node_type: str):
    return [node for node in walk(root) if node.type == node_type]


def node_name(node) -> str:
    name = node.child_by_field_name("name")
    return text(name) if name is not None else "<anonymous>"


def print_doc(node, language: SupportedLanguages) -> None:
    doc = extract_docstring(node, language)
    if doc is None:
        print("    docstring: <none>")
        return
    print(f"    docstring lines: {doc.start_line + 1}-{doc.end_line + 1}")
    print(f"    docstring: {doc.content}")


def main() -> int:
    language = SupportedLanguages.PYTHON
    tree = parse_file(CODE, language, "sample.py")
    root = tree.root_node

    print("1. parser_loader -> AST")
    print(f"   root: {root.type}")
    print(f"   has_error: {root.has_error}")
    print(f"   top-level children: {root.child_count}")

    print("\n2. named_binding_extraction")
    all_files = {
        "sample.py",
        "models/user.py",
        "models/repository.py",
    }
    suffix_index = SuffixIndex(sorted(all_files))
    for import_node in nodes_of_type(root, "import_from_statement"):
        print(f"   import node: {text(import_node).strip()}")
        for binding in extract_python_named_bindings(import_node):
            print(f"    - local={binding['local']} exported={binding['exported']}")

    print("\n3. import_resolver")
    print(
        "   python resolver: models.user -> "
        f"{resolve_python_import('sample.py', 'models.user', all_files)}"
    )
    print(
        "   suffix fallback: models/repository -> "
        f"{resolve_import_path('models/repository', 'sample.py', suffix_index)}"
    )

    print("\n4. docstring_extractor + export_detection")
    for class_node in nodes_of_type(root, "class_definition"):
        name = node_name(class_node)
        print(f"   class {name}")
        print(f"    exported: {is_exported(class_node, name, language)}")
        print_doc(class_node, language)

    for function_node in nodes_of_type(root, "function_definition"):
        name = node_name(function_node)
        print(f"   function {name}")
        print(f"    exported: {is_exported(function_node, name, language)}")
        print_doc(function_node, language)

    print("\n5. type_env")
    env = build_type_env(root, language)
    for name in ("raw", "repo", "user"):
        print(f"   {name} -> {env.lookup(name)}")

    return 0 if not root.has_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
