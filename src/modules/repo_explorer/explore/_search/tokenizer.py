"""Identifier tokenizer for FTS indexing.

Splits camelCase, PascalCase, snake_case, and kebab-case identifiers
into constituent words so BM25 search can match partial terms.

Example: ``useAuth`` → ``"useAuth use auth"``
"""

from __future__ import annotations

import re

# Matches word boundaries in identifiers:
#   - lowercase run followed by uppercase: useAuth → [use, Auth]
#   - uppercase run followed by uppercase+lowercase: HTMLParser → [HTML, Parser]
#   - digits as separate tokens: get2ndItem → [get, 2nd, Item]
_IDENT_RE = re.compile(
    r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]|\d+"
)


def split_identifier(name: str) -> str:
    """Split an identifier into searchable text.

    Returns the original name followed by its lowercase constituent parts.
    This preserves exact-match capability while enabling partial matching.

    >>> split_identifier("useAuth")
    'useAuth use auth'
    >>> split_identifier("AuthGuard")
    'AuthGuard auth guard'
    >>> split_identifier("get_user_by_id")
    'get_user_by_id get user by id'
    >>> split_identifier("HTMLParser")
    'HTMLParser html parser'
    >>> split_identifier("my-component")
    'my-component my component'
    >>> split_identifier("")
    ''
    """
    if not name:
        return ""

    # First split on underscores and hyphens
    segments = re.split(r"[_\-./]", name)

    parts: list[str] = []
    for segment in segments:
        if not segment:
            continue
        matches = _IDENT_RE.findall(segment)
        if matches:
            parts.extend(matches)
        else:
            parts.append(segment)

    if not parts:
        return name

    lowercase_parts = " ".join(p.lower() for p in parts)
    return f"{name} {lowercase_parts}"
