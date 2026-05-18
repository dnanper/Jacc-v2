"""PostScript regex patterns — page description language."""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="postscript",
    definitions=[
        # /name { ... } def  or  /name { ... } bind def
        RegexPattern(
            node_type="procedure_def",
            pattern=re.compile(
                r"/(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{[^}]*\}\s*(?:bind\s+)?def\b"
            ),
        ),
        # /name value def  (simple variable definitions)
        RegexPattern(
            node_type="variable_definition",
            pattern=re.compile(
                r"/(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+(?!\{)\S+\s+def\b"
            ),
        ),
    ],
    calls=[],
    imports=[
        # (filename) run
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(r"\((?P<name>[^)]+)\)\s+run\b"),
        ),
    ],
)

register_regex_config("postscript", _CONFIG)
