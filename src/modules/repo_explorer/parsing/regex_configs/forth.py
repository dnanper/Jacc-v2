"""Forth regex patterns — stack-based, embedded systems."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="forth",
    definitions=[
        # : word-name ... ;  (colon definitions)
        RegexPattern(
            node_type="word_definition",
            pattern=re.compile(r":\s+(?P<name>\S+)", re.MULTILINE),
        ),
        # VARIABLE name, CONSTANT name, CREATE name
        RegexPattern(
            node_type="variable_definition",
            pattern=re.compile(
                r"\b(?:VARIABLE|CONSTANT|CREATE|VALUE|2VARIABLE|2CONSTANT)\s+(?P<name>\S+)",
                re.IGNORECASE,
            ),
        ),
    ],
    calls=[],
    imports=[
        # INCLUDE filename or REQUIRE filename
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(
                r"^\s*(?:INCLUDE|REQUIRE)\s+(?P<name>\S+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
)

register_regex_config("forth", _CONFIG)
