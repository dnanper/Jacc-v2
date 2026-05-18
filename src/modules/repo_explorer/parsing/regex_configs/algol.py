"""ALGOL regex patterns — historical language."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="algol",
    definitions=[
        # procedure name or PROCEDURE name
        RegexPattern(
            node_type="procedure_declaration",
            pattern=re.compile(
                r"\b(?:procedure|PROCEDURE)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
                re.MULTILINE,
            ),
        ),
    ],
    calls=[
        # Procedure calls: name(args) pattern
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("),
        ),
    ],
    imports=[],
)

register_regex_config("algol", _CONFIG)
