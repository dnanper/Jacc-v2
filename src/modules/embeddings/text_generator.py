"""Text generator — node → embeddable text.

Port of GitNexus embeddings/text-generator.ts.

Pure functions to generate embedding text from code nodes.
Combines node metadata with code snippets for semantic matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class EmbeddableNode:
    id: str
    name: str
    label: str
    file_path: str
    content: str
    start_line: int | None = None
    end_line: int | None = None


EMBEDDABLE_LABELS = frozenset({
    "Function", "Class", "Method", "Interface", "File", "Section",
    "Struct", "Enum", "Trait",
})

DEFAULT_MAX_SNIPPET_LENGTH = 500


def _get_filename(file_path: str) -> str:
    parts = file_path.split("/")
    return parts[-1] if parts else file_path


def _get_directory(file_path: str) -> str:
    parts = file_path.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def _truncate_content(content: str, max_length: int) -> str:
    if len(content) <= max_length:
        return content

    truncated = content[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > max_length * 0.8:
        return truncated[:last_space] + "..."
    return truncated + "..."


def _clean_content(content: str) -> str:
    content = content.replace("\r\n", "\n")
    content = re.sub(r"\n{3,}", "\n\n", content)
    lines = [line.rstrip() for line in content.split("\n")]
    return "\n".join(lines).strip()


def generate_embedding_text(
    node: EmbeddableNode,
    max_snippet_length: int = DEFAULT_MAX_SNIPPET_LENGTH,
) -> str:
    """Generate embedding text for any embeddable node.

    Dispatches based on node label. Text includes the node type, name,
    file location, and a truncated code snippet.
    """
    label = node.label

    if label == "File":
        parts = [f"File: {node.name}", f"Path: {node.file_path}"]
        if node.content:
            cleaned = _clean_content(node.content)
            snippet = _truncate_content(cleaned, min(max_snippet_length, 300))
            parts.extend(["", snippet])
        return "\n".join(parts)

    if label == "Section":
        parts = [f"Documentation: {node.name}", f"File: {_get_filename(node.file_path)}"]
        directory = _get_directory(node.file_path)
        if directory:
            parts.append(f"Directory: {directory}")
        if node.content:
            cleaned = _clean_content(node.content)
            snippet = _truncate_content(cleaned, max_snippet_length)
            parts.extend(["", snippet])
        return "\n".join(parts)

    parts = [f"{label}: {node.name}", f"File: {_get_filename(node.file_path)}"]

    directory = _get_directory(node.file_path)
    if directory:
        parts.append(f"Directory: {directory}")

    if node.content:
        cleaned = _clean_content(node.content)
        snippet = _truncate_content(cleaned, max_snippet_length)
        parts.extend(["", snippet])

    return "\n".join(parts)


def generate_batch_embedding_texts(
    nodes: list[EmbeddableNode],
    max_snippet_length: int = DEFAULT_MAX_SNIPPET_LENGTH,
) -> list[str]:
    """Generate embedding texts for a batch of nodes."""
    return [generate_embedding_text(n, max_snippet_length) for n in nodes]
