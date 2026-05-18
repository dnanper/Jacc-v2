"""MUMPS/M regex patterns — medical systems (Epic, VistA)."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="mumps",
    definitions=[
        # Labels at column 0 (no leading whitespace) define entry points
        # e.g., "MAIN", "INIT(X)", "GETDATA"
        RegexPattern(
            node_type="function_definition",
            pattern=re.compile(
                r"^(?P<name>[A-Za-z%][A-Za-z0-9]*)(?:\([^)]*\))?\s", re.MULTILINE
            ),
        ),
    ],
    calls=[
        # DO label or DO label^routine
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\b(?:DO|D)\s+(?P<name>[A-Za-z%][A-Za-z0-9]*)(?:\^[A-Za-z%][A-Za-z0-9]*)?",
                re.IGNORECASE,
            ),
        ),
        # $$extrinsic^routine or $$extrinsic
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\$\$(?P<name>[A-Za-z%][A-Za-z0-9]*)(?:\^[A-Za-z%][A-Za-z0-9]*)?"
            ),
        ),
    ],
    imports=[],
)

register_regex_config("mumps", _CONFIG)
