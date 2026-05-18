from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.config import SupportedLanguages
from repo_explorer.parsing.parser_loader import parse_file

DEFAULT_CODE = """\
def hello(name):
    print(name)
"""


def _node_text(node, max_chars: int) -> str:
    text = node.text
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def _field_name(parent, child) -> str | None:
    for index in range(parent.child_count):
        if parent.child(index) is child:
            return parent.field_name_for_child(index)
    return None


def _print_node(node, depth: int, max_depth: int, max_text: int) -> None:
    indent = "  " * depth
    named = "named" if node.is_named else "anon"
    error = " ERROR" if getattr(node, "has_error", False) else ""
    print(
        f"{indent}- {node.type} ({named}{error}) "
        f"lines={node.start_point}->{node.end_point} "
        f"bytes={node.start_byte}:{node.end_byte} "
        f'text="{_node_text(node, max_text)}"'
    )

    if depth >= max_depth:
        if node.child_count:
            print(f"{indent}  ... {node.child_count} child nodes hidden")
        return

    for child in node.children:
        field_name = _field_name(node, child)
        if field_name:
            print(f"{indent}  field[{field_name}]")
        _print_node(child, depth + 1, max_depth, max_text)


def _language(value: str) -> SupportedLanguages:
    try:
        return SupportedLanguages(value)
    except ValueError as exc:
        valid = ", ".join(lang.value for lang in SupportedLanguages)
        raise argparse.ArgumentTypeError(
            f"Unsupported language '{value}'. Valid values: {valid}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse code with parser_loader and print a readable AST tree."
    )
    parser.add_argument(
        "--language",
        "-l",
        type=_language,
        default=SupportedLanguages.PYTHON,
        help="Language value from SupportedLanguages. Default: python.",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Read source code from a file.",
    )
    parser.add_argument(
        "--code",
        "-c",
        help="Source code string to parse. Defaults to a small Python function.",
    )
    parser.add_argument(
        "--name",
        default="demo.py",
        help="Virtual file name passed to parser_loader. Default: demo.py.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Maximum AST depth to print. Default: 6.",
    )
    parser.add_argument(
        "--max-text",
        type=int,
        default=80,
        help="Maximum text chars per node. Default: 80.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.file:
        file_path = args.file
        code = file_path.read_text(encoding="utf-8", errors="replace")
        display_name = str(file_path)
    else:
        code = args.code if args.code is not None else DEFAULT_CODE
        display_name = args.name

    tree = parse_file(code, args.language, display_name)
    root = tree.root_node
    # print(root)
    print(f"language: {args.language.value}")
    print(f"file: {display_name}")
    print(f"root: {root.type}")
    print(f"has_error: {root.has_error}")
    print(f"children: {root.child_count}")
    print("ast:")
    _print_node(root, depth=0, max_depth=args.max_depth, max_text=args.max_text)
    return 0 if not root.has_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
