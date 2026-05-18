"""Assembly regex patterns — x86 AT&T/Intel + ARM basics."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="assembly",
    definitions=[
        # Labels: name followed by colon (e.g., main:, _start:, .Lfoo:)
        RegexPattern(
            node_type="function_definition",
            pattern=re.compile(r"^(?P<name>[A-Za-z_.][A-Za-z0-9_.]*):", re.MULTILINE),
        ),
    ],
    calls=[
        # call/CALL instruction (x86)
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\b(?:call|CALL)\s+(?P<name>[A-Za-z_.][A-Za-z0-9_.]*)", re.IGNORECASE
            ),
        ),
        # bl instruction (ARM branch-and-link)
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\bbl\s+(?P<name>[A-Za-z_.][A-Za-z0-9_.]*)", re.IGNORECASE
            ),
        ),
        # jsr instruction (68k/MIPS)
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\bjsr\s+(?P<name>[A-Za-z_.][A-Za-z0-9_.]*)", re.IGNORECASE
            ),
        ),
    ],
    imports=[
        # .include "file" or %include "file"
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(
                r'^\s*[.%]include\s+"(?P<name>[^"]+)"', re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
)

register_regex_config("assembly", _CONFIG)
