"""Schema / DDL extraction — post-parse analysis pass.

Scans symbol source content for database table definitions:
- Language-agnostic SQL patterns (CREATE TABLE, INSERT INTO)
- Language-specific ORM patterns (Django Model, JPA @Entity, etc.)

Stores discovered table names as ``schema_entities`` on the containing
symbol's NodeProperties so the SRS retrieval layer can surface them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..config import SupportedLanguages
from ..graph.core.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern
    label: str  # human-readable source (e.g., "SQL DDL", "Django ORM")


# ── Language-agnostic SQL patterns (work in any language) ────────────────

_SQL_PATTERNS: list[_Pattern] = [
    _Pattern(re.compile(r"""CREATE\s+TABLE\s+["'`]?(\w+)["'`]?""", re.I), "SQL DDL"),
    _Pattern(re.compile(r"""SQL_CREATE\s+["'](\w+)["']""", re.I), "SQL DDL"),
    _Pattern(re.compile(r"""INSERT\s+INTO\s+["'`]?(\w+)["'`]?""", re.I), "SQL DML"),
    _Pattern(re.compile(r"""ALTER\s+TABLE\s+["'`]?(\w+)["'`]?""", re.I), "SQL DDL"),
]

# ── Language-specific ORM / framework patterns ───────────────────────────

_LANG_PATTERNS: dict[str, list[_Pattern]] = {
    SupportedLanguages.PYTHON: [
        _Pattern(
            re.compile(r"class\s+(\w+)\(.*(?:db\.Model|models\.Model|Base)\)"),
            "ORM model",
        ),
        _Pattern(
            re.compile(r"__tablename__\s*=\s*['\"](\w+)['\"]"), "SQLAlchemy table"
        ),
        _Pattern(
            re.compile(r"class\s+Meta:.*\n\s*db_table\s*=\s*['\"](\w+)['\"]", re.M),
            "Django Meta",
        ),
    ],
    SupportedLanguages.JAVA: [
        _Pattern(re.compile(r"@Entity[\s\S]{0,50}class\s+(\w+)"), "JPA Entity"),
        _Pattern(re.compile(r'@Table\s*\(\s*name\s*=\s*"(\w+)"'), "JPA Table"),
    ],
    SupportedLanguages.KOTLIN: [
        _Pattern(re.compile(r"@Entity[\s\S]{0,50}class\s+(\w+)"), "JPA Entity"),
        _Pattern(re.compile(r'@Table\s*\(\s*name\s*=\s*"(\w+)"'), "JPA Table"),
    ],
    SupportedLanguages.C_SHARP: [
        _Pattern(re.compile(r'\[Table\s*\(\s*"(\w+)"\s*\)\]'), "EF Table attr"),
        _Pattern(re.compile(r"DbSet<(\w+)>"), "EF DbSet"),
        _Pattern(re.compile(r"class\s+(\w+)\s*:\s*DbContext"), "EF DbContext"),
    ],
    SupportedLanguages.GO: [
        _Pattern(
            re.compile(r"type\s+(\w+)\s+struct\s*\{[^}]*`gorm:", re.S), "GORM model"
        ),
        _Pattern(
            re.compile(
                r'func\s*\(\s*\w+\s+\w+\)\s*TableName\s*\(\)\s*string\s*\{[^}]*return\s*"(\w+)"',
                re.S,
            ),
            "GORM TableName",
        ),
    ],
    SupportedLanguages.RUBY: [
        _Pattern(re.compile(r"create_table\s+[:\"'](\w+)"), "ActiveRecord migration"),
        _Pattern(
            re.compile(r"class\s+(\w+)\s*<\s*(?:ApplicationRecord|ActiveRecord::Base)"),
            "ActiveRecord model",
        ),
    ],
    SupportedLanguages.PHP: [
        _Pattern(
            re.compile(r"protected\s+\$table\s*=\s*['\"](\w+)['\"]"), "Eloquent table"
        ),
        _Pattern(re.compile(r"class\s+(\w+)\s+extends\s+Model"), "Eloquent model"),
        _Pattern(
            re.compile(r'@ORM\\Table\s*\(\s*name\s*=\s*"(\w+)"'), "Doctrine table"
        ),
    ],
    SupportedLanguages.TYPESCRIPT: [
        _Pattern(
            re.compile(r"@Entity\s*\(\s*\)[\s\S]{0,30}class\s+(\w+)"), "TypeORM Entity"
        ),
        _Pattern(re.compile(r"model\s+(\w+)\s*\{"), "Prisma model"),
    ],
    SupportedLanguages.JAVASCRIPT: [
        _Pattern(re.compile(r"model\s+(\w+)\s*\{"), "Prisma model"),
        _Pattern(
            re.compile(r"sequelize\.define\s*\(\s*['\"](\w+)['\"]"), "Sequelize model"
        ),
    ],
    SupportedLanguages.RUST: [
        _Pattern(
            re.compile(r'#\[diesel\s*\(\s*table_name\s*=\s*"(\w+)"\s*\)'),
            "Diesel table",
        ),
        _Pattern(
            re.compile(r'#\[sea_orm\s*\(\s*table_name\s*=\s*"(\w+)"\s*\)'),
            "SeaORM table",
        ),
    ],
}


def extract_schema_entities(graph: KnowledgeGraph) -> int:
    """Scan all nodes with source content for schema/DDL patterns.

    Stores discovered table names on ``node.properties.schema_entities``.

    Returns the total number of unique tables discovered.
    """
    all_tables: set[str] = set()
    nodes_annotated = 0

    for node in graph.iter_nodes():
        content = node.properties.content
        if not content or len(content) < 20:
            continue

        lang = node.properties.language
        tables: set[str] = set()

        # SQL patterns (language-agnostic)
        for pat in _SQL_PATTERNS:
            for m in pat.regex.finditer(content):
                tables.add(m.group(1))

        # Language-specific ORM patterns
        if lang:
            for pat in _LANG_PATTERNS.get(lang, []):
                for m in pat.regex.finditer(content):
                    tables.add(m.group(1))

        if tables:
            node.properties.schema_entities = sorted(tables)
            all_tables.update(tables)
            nodes_annotated += 1

    logger.info(
        "Schema extraction: %d unique tables found across %d nodes",
        len(all_tables),
        nodes_annotated,
    )
    return len(all_tables)
