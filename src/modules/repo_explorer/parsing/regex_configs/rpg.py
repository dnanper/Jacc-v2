"""RPG (Report Program Generator) regex patterns — IBM AS/400 legacy.

Covers both free-form (RPG IV) and fixed-form patterns.
"""

import re

from ..regex_parser import (
    RegexLanguageConfig,
    RegexPattern,
    register_regex_config,
)

_CONFIG = RegexLanguageConfig(
    language_key="rpg",
    definitions=[
        # Free-form: DCL-PROC procedure_name
        RegexPattern(
            node_type="dcl_proc",
            pattern=re.compile(
                r"^\s*DCL-PROC\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
        # Free-form: DCL-DS data_structure_name
        RegexPattern(
            node_type="dcl_ds",
            pattern=re.compile(
                r"^\s*DCL-DS\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
        # Fixed-form: BEGSR subroutine_name
        RegexPattern(
            node_type="begsr",
            pattern=re.compile(
                r"^\s*BEGSR\s+(?P<name>\w+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
    calls=[
        # CALLP procedure(args)
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(r"\bCALLP\s+(?P<name>\w+)\s*\(", re.IGNORECASE),
        ),
        # EXSR subroutine_name
        RegexPattern(
            node_type="call_expression",
            pattern=re.compile(r"\bEXSR\s+(?P<name>\w+)", re.IGNORECASE),
        ),
    ],
    imports=[
        # /COPY or /INCLUDE
        RegexPattern(
            node_type="include_statement",
            pattern=re.compile(
                r"^\s*/(?:COPY|INCLUDE)\s+(?P<name>\S+)", re.IGNORECASE | re.MULTILINE
            ),
        ),
    ],
)

register_regex_config("rpg", _CONFIG)
