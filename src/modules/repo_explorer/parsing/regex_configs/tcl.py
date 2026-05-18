"""Tcl regex patterns — EDA, testing frameworks, Tk GUI apps."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="tcl",
    definitions=[
        # proc name {args} {body}
        RegexPattern(
            node_type="proc_definition",
            pattern=re.compile(
                r"^\s*proc\s+(?P<name>[A-Za-z_:][A-Za-z0-9_:]*)\s+\{", re.MULTILINE
            ),
        ),
        # oo::class create ClassName
        RegexPattern(
            node_type="class_definition",
            pattern=re.compile(
                r"\boo::class\s+create\s+(?P<name>[A-Za-z_:][A-Za-z0-9_:]*)",
                re.MULTILINE,
            ),
        ),
        # namespace eval name
        RegexPattern(
            node_type="module",
            pattern=re.compile(
                r"^\s*namespace\s+eval\s+(?P<name>[A-Za-z_:][A-Za-z0-9_:]*)",
                re.MULTILINE,
            ),
        ),
    ],
    calls=[],
    imports=[
        # package require name
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(
                r"^\s*package\s+require\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)",
                re.MULTILINE,
            ),
        ),
        # source file
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(r"^\s*source\s+(?P<name>\S+)", re.MULTILINE),
        ),
    ],
)

register_regex_config("tcl", _CONFIG)
