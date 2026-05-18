"""ABAP regex patterns — SAP proprietary language."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="abap",
    definitions=[
        # FORM subroutine_name
        RegexPattern(
            node_type="form_definition",
            pattern=re.compile(
                r"^\s*FORM\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
        # METHOD method_name
        RegexPattern(
            node_type="method_definition",
            pattern=re.compile(
                r"^\s*METHOD\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
        # CLASS class_name DEFINITION/IMPLEMENTATION
        RegexPattern(
            node_type="class_definition",
            pattern=re.compile(
                r"^\s*CLASS\s+(?P<name>\w+)\s+(?:DEFINITION|IMPLEMENTATION)",
                re.IGNORECASE | re.MULTILINE,
            ),
        ),
        # FUNCTION function_name
        RegexPattern(
            node_type="function_definition",
            pattern=re.compile(
                r"^\s*FUNCTION\s+(?P<name>\S+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
        # REPORT report_name
        RegexPattern(
            node_type="report",
            pattern=re.compile(
                r"^\s*REPORT\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
    calls=[
        # CALL FUNCTION 'function_name'
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(r"\bCALL\s+FUNCTION\s+'(?P<name>[^']+)'", re.IGNORECASE),
        ),
        # CALL METHOD object->method_name
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(
                r"\bCALL\s+METHOD\s+(?:\w+->)?(?P<name>\w+)", re.IGNORECASE
            ),
        ),
        # PERFORM form_name
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(r"\bPERFORM\s+(?P<name>\w+)", re.IGNORECASE),
        ),
    ],
    imports=[
        # INCLUDE type
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(
                r"^\s*INCLUDE\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
)

register_regex_config("abap", _CONFIG)
