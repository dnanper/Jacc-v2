"""Language configuration and constants."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

# ---------------------------------------------------------------------------
# Central data directory — all ingestion artifacts live here
# ---------------------------------------------------------------------------

# Resolve CSG project root (directory containing this package)
_PACKAGE_DIR = Path(__file__).resolve().parent  # csg/
PROJECT_ROOT = _PACKAGE_DIR.parent  # CSG/

# Central data directory: CSG/data/
# Override with CSG_DATA_DIR env var for custom locations
DATA_DIR = Path(os.environ.get("CSG_DATA_DIR", PROJECT_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Directory for extracted / uploaded repositories
REPOS_DIR = DATA_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)


class SupportedLanguages(StrEnum):
    """All supported languages."""

    # ── Original 14 ──────────────────────────────────────────────────
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    JAVA = "java"
    C = "c"
    C_PLUS_PLUS = "cpp"
    C_SHARP = "c_sharp"
    GO = "go"
    RUBY = "ruby"
    RUST = "rust"
    PHP = "php"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    VB6 = "vb6"

    # ── Tier 1: Native PyPI tree-sitter packages ─────────────────────
    FORTRAN = "fortran"
    SCALA = "scala"
    OBJECTIVE_C = "objective_c"
    SOLIDITY = "solidity"
    MATLAB = "matlab"
    COMMON_LISP = "common_lisp"
    DELPHI = "delphi"
    ADA = "ada"

    # ── Tier 2: WASM bridge (npm grammars) ───────────────────────────
    PERL = "perl"
    COBOL = "cobol"
    ERLANG = "erlang"
    APEX = "apex"
    PASCAL = "pascal"
    PROLOG = "prolog"

    # ── Tier 3: Regex parser (no grammar) ────────────────────────────
    RPG = "rpg"
    ABAP = "abap"
    MUMPS = "mumps"
    ASSEMBLY = "assembly"
    TCL = "tcl"
    ALGOL = "algol"
    FORTH = "forth"
    POSTSCRIPT = "postscript"


EXTENSION_MAP: dict[str, SupportedLanguages] = {
    # ── Original 14 ──────────────────────────────────────────────────
    ".js": SupportedLanguages.JAVASCRIPT,
    ".jsx": SupportedLanguages.JAVASCRIPT,
    ".mjs": SupportedLanguages.JAVASCRIPT,
    ".cjs": SupportedLanguages.JAVASCRIPT,
    ".ts": SupportedLanguages.TYPESCRIPT,
    ".tsx": SupportedLanguages.TYPESCRIPT,
    ".mts": SupportedLanguages.TYPESCRIPT,
    ".cts": SupportedLanguages.TYPESCRIPT,
    ".py": SupportedLanguages.PYTHON,
    ".pyi": SupportedLanguages.PYTHON,
    ".java": SupportedLanguages.JAVA,
    ".c": SupportedLanguages.C,
    ".h": SupportedLanguages.C,
    ".cpp": SupportedLanguages.C_PLUS_PLUS,
    ".cxx": SupportedLanguages.C_PLUS_PLUS,
    ".cc": SupportedLanguages.C_PLUS_PLUS,
    ".hpp": SupportedLanguages.C_PLUS_PLUS,
    ".hxx": SupportedLanguages.C_PLUS_PLUS,
    ".hh": SupportedLanguages.C_PLUS_PLUS,
    ".cs": SupportedLanguages.C_SHARP,
    ".go": SupportedLanguages.GO,
    ".rb": SupportedLanguages.RUBY,
    ".rs": SupportedLanguages.RUST,
    ".php": SupportedLanguages.PHP,
    ".kt": SupportedLanguages.KOTLIN,
    ".kts": SupportedLanguages.KOTLIN,
    ".swift": SupportedLanguages.SWIFT,
    ".bas": SupportedLanguages.VB6,
    ".frm": SupportedLanguages.VB6,
    # ── Tier 1: Fortran ──────────────────────────────────────────────
    ".f": SupportedLanguages.FORTRAN,
    ".f90": SupportedLanguages.FORTRAN,
    ".f95": SupportedLanguages.FORTRAN,
    ".f03": SupportedLanguages.FORTRAN,
    ".f08": SupportedLanguages.FORTRAN,
    ".for": SupportedLanguages.FORTRAN,
    ".fpp": SupportedLanguages.FORTRAN,
    ".ftn": SupportedLanguages.FORTRAN,
    # ── Tier 1: Scala ────────────────────────────────────────────────
    ".scala": SupportedLanguages.SCALA,
    ".sc": SupportedLanguages.SCALA,
    # ── Tier 1: Objective-C ──────────────────────────────────────────
    ".mm": SupportedLanguages.OBJECTIVE_C,
    # .m is ambiguous (ObjC / MATLAB / MUMPS) — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 1: Solidity ─────────────────────────────────────────────
    ".sol": SupportedLanguages.SOLIDITY,
    # ── Tier 1: MATLAB ───────────────────────────────────────────────
    ".mlx": SupportedLanguages.MATLAB,
    # .m is ambiguous — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 1: Common Lisp ──────────────────────────────────────────
    ".lisp": SupportedLanguages.COMMON_LISP,
    ".lsp": SupportedLanguages.COMMON_LISP,
    ".cl": SupportedLanguages.COMMON_LISP,
    ".fasl": SupportedLanguages.COMMON_LISP,
    # ── Tier 1: Delphi ───────────────────────────────────────────────
    ".dpr": SupportedLanguages.DELPHI,
    ".dpk": SupportedLanguages.DELPHI,
    ".dfm": SupportedLanguages.DELPHI,
    # ── Tier 1: Ada ──────────────────────────────────────────────────
    ".adb": SupportedLanguages.ADA,
    ".ads": SupportedLanguages.ADA,
    ".ada": SupportedLanguages.ADA,
    # ── Tier 2: Perl ─────────────────────────────────────────────────
    ".pm": SupportedLanguages.PERL,
    ".t": SupportedLanguages.PERL,
    # .pl is ambiguous (Perl / Prolog) — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 2: COBOL ────────────────────────────────────────────────
    ".cob": SupportedLanguages.COBOL,
    ".cbl": SupportedLanguages.COBOL,
    ".cpy": SupportedLanguages.COBOL,
    # ── Tier 2: Erlang ───────────────────────────────────────────────
    ".erl": SupportedLanguages.ERLANG,
    ".hrl": SupportedLanguages.ERLANG,
    # ── Tier 2: Apex ─────────────────────────────────────────────────
    ".trigger": SupportedLanguages.APEX,
    # .cls is ambiguous (VB6 / Apex) — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 2: Pascal ───────────────────────────────────────────────
    ".pas": SupportedLanguages.PASCAL,
    ".pp": SupportedLanguages.PASCAL,
    ".inc": SupportedLanguages.PASCAL,
    # ── Tier 2: Prolog ───────────────────────────────────────────────
    ".pro": SupportedLanguages.PROLOG,
    # .pl is ambiguous (Perl / Prolog) — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 3: RPG ──────────────────────────────────────────────────
    ".rpg": SupportedLanguages.RPG,
    ".rpgle": SupportedLanguages.RPG,
    ".sqlrpgle": SupportedLanguages.RPG,
    ".rpgleinc": SupportedLanguages.RPG,
    # ── Tier 3: ABAP ─────────────────────────────────────────────────
    ".abap": SupportedLanguages.ABAP,
    # ── Tier 3: MUMPS ────────────────────────────────────────────────
    ".mps": SupportedLanguages.MUMPS,
    ".zwr": SupportedLanguages.MUMPS,
    # .m is ambiguous — handled by AMBIGUOUS_EXTENSIONS
    # ── Tier 3: Assembly ─────────────────────────────────────────────
    ".asm": SupportedLanguages.ASSEMBLY,
    ".s": SupportedLanguages.ASSEMBLY,
    ".nasm": SupportedLanguages.ASSEMBLY,
    # ── Tier 3: Tcl ──────────────────────────────────────────────────
    ".tcl": SupportedLanguages.TCL,
    ".tk": SupportedLanguages.TCL,
    ".itcl": SupportedLanguages.TCL,
    # ── Tier 3: ALGOL ────────────────────────────────────────────────
    ".alg": SupportedLanguages.ALGOL,
    ".a60": SupportedLanguages.ALGOL,
    ".a68": SupportedLanguages.ALGOL,
    # ── Tier 3: Forth ────────────────────────────────────────────────
    ".fs": SupportedLanguages.FORTH,
    ".fth": SupportedLanguages.FORTH,
    ".4th": SupportedLanguages.FORTH,
    ".forth": SupportedLanguages.FORTH,
    # ── Tier 3: PostScript ───────────────────────────────────────────
    ".ps": SupportedLanguages.POSTSCRIPT,
    ".eps": SupportedLanguages.POSTSCRIPT,
}


# ── Ambiguous extensions — require content-based disambiguation ──────

AMBIGUOUS_EXTENSIONS: dict[str, list[tuple[SupportedLanguages, list[str]]]] = {
    # Each entry: (language, list_of_indicator_patterns_in_first_2KB)
    ".m": [
        (
            SupportedLanguages.OBJECTIVE_C,
            [
                "#import",
                "@interface",
                "@implementation",
                "@protocol",
                "@property",
                "@end",
                "#include",
            ],
        ),
        (
            SupportedLanguages.MATLAB,
            [
                "function ",
                "classdef ",
                "%%",
                "end\n",
                "end;",
            ],
        ),
        (
            SupportedLanguages.MUMPS,
            [
                "\tS ",
                "\tW ",
                "\tD ",
                "\tQ ",
                " SET ",
                " WRITE ",
                " DO ",
            ],
        ),
    ],
    ".cls": [
        (
            SupportedLanguages.VB6,
            [
                "VERSION 1.0",
                "Attribute VB_",
                "BEGIN",
                "MultiUse",
            ],
        ),
        (
            SupportedLanguages.APEX,
            [
                "public class",
                "private class",
                "global class",
                "@isTest",
                "@IsTest",
                "trigger ",
            ],
        ),
    ],
    ".pl": [
        (
            SupportedLanguages.PERL,
            [
                "use strict",
                "use warnings",
                "my $",
                "my @",
                "my %",
                "sub ",
                "#!/usr/bin/perl",
                "#!/usr/bin/env perl",
            ],
        ),
        (
            SupportedLanguages.PROLOG,
            [
                ":-",
                "?-",
                "module(",
                "use_module(",
            ],
        ),
    ],
}

TREE_SITTER_GRAMMAR_MAP: dict[SupportedLanguages, str] = {
    # ── Original 14 ──────────────────────────────────────────────────
    SupportedLanguages.JAVASCRIPT: "javascript",
    SupportedLanguages.TYPESCRIPT: "typescript",
    SupportedLanguages.PYTHON: "python",
    SupportedLanguages.JAVA: "java",
    SupportedLanguages.C: "c",
    SupportedLanguages.C_PLUS_PLUS: "cpp",
    SupportedLanguages.C_SHARP: "c_sharp",
    SupportedLanguages.GO: "go",
    SupportedLanguages.RUBY: "ruby",
    SupportedLanguages.RUST: "rust",
    SupportedLanguages.PHP: "php",
    SupportedLanguages.KOTLIN: "kotlin",
    SupportedLanguages.SWIFT: "swift",
    SupportedLanguages.VB6: "vb6",
    # ── Tier 1: Native PyPI ──────────────────────────────────────────
    SupportedLanguages.FORTRAN: "fortran",
    SupportedLanguages.SCALA: "scala",
    SupportedLanguages.OBJECTIVE_C: "objc",
    SupportedLanguages.SOLIDITY: "solidity",
    SupportedLanguages.MATLAB: "matlab",
    SupportedLanguages.COMMON_LISP: "commonlisp",
    SupportedLanguages.DELPHI: "delphi",
    SupportedLanguages.ADA: "ada",
    # ── Tier 2: WASM bridge ──────────────────────────────────────────
    SupportedLanguages.PERL: "perl",
    SupportedLanguages.COBOL: "cobol",
    SupportedLanguages.ERLANG: "erlang",
    SupportedLanguages.APEX: "sfapex",
    SupportedLanguages.PASCAL: "pascal",
    SupportedLanguages.PROLOG: "prolog",
    # ── Tier 3: Regex parser (no tree-sitter grammar) ────────────────
    SupportedLanguages.RPG: "rpg",
    SupportedLanguages.ABAP: "abap",
    SupportedLanguages.MUMPS: "mumps",
    SupportedLanguages.ASSEMBLY: "assembly",
    SupportedLanguages.TCL: "tcl",
    SupportedLanguages.ALGOL: "algol",
    SupportedLanguages.FORTH: "forth",
    SupportedLanguages.POSTSCRIPT: "postscript",
}

TSX_GRAMMAR = "tsx"

TSX_EXTENSIONS = {".tsx"}

MAX_FILE_SIZE = 512 * 1024

MAX_CONTENT_SIZE = 10 * 1024

# ---------------------------------------------------------------------------
# Document ingestion constants
# ---------------------------------------------------------------------------

DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Office
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
        # PDF
        ".pdf",
        # Web / markup
        ".html",
        ".htm",
        ".rtf",
        ".epub",
        # Data
        ".csv",
        ".tsv",
        # Email
        ".eml",
        ".msg",
        # Text / config (not already code)
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
        ".json",
    }
)

MAX_DOCUMENT_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

MAX_DOCUMENT_PAGES = 200

MAX_DOCUMENT_SECTION_CONTENT = 2000

BUILT_IN_NAMES: frozenset[str] = frozenset(
    {
        # ── JavaScript / TypeScript ──────────────────────────────────────
        "console",
        "log",
        "warn",
        "error",
        "info",
        "debug",
        "stringify",
        "toString",
        "valueOf",
        "hasOwnProperty",
        "Promise",
        "then",
        "catch",
        "finally",
        "resolve",
        "reject",
        "map",
        "filter",
        "reduce",
        "forEach",
        "find",
        "findIndex",
        "some",
        "every",
        "includes",
        "indexOf",
        "slice",
        "splice",
        "push",
        "pop",
        "shift",
        "unshift",
        "concat",
        "join",
        "keys",
        "values",
        "entries",
        "from",
        "of",
        "assign",
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "require",
        # ── Python ───────────────────────────────────────────────────────
        "print",
        "len",
        "range",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "type",
        "isinstance",
        "enumerate",
        "zip",
        "sorted",
        "reversed",
        "max",
        "min",
        "sum",
        "abs",
        "round",
        "open",
        "super",
        "property",
        "staticmethod",
        "classmethod",
        "hasattr",
        "getattr",
        "setattr",
        # ── Go ───────────────────────────────────────────────────────────
        "fmt",
        "make",
        "append",
        "len",
        "cap",
        "close",
        "panic",
        "recover",
        "new",
        "delete",
        "copy",
        # ── Rust ─────────────────────────────────────────────────────────
        "unwrap",
        "expect",
        "unwrap_or",
        "unwrap_or_else",
        "clone",
        "to_string",
        "to_owned",
        "into",
        "from",
        "iter",
        "into_iter",
        "collect",
        "map",
        "filter",
        "fold",
        "ok",
        "err",
        "some",
        "none",
        # ── Ruby ─────────────────────────────────────────────────────────
        "puts",
        "p",
        "pp",
        "raise",
        "each",
        "select",
        "reject",
        "collect",
        "detect",
        # ── PHP ──────────────────────────────────────────────────────────
        "echo",
        "var_dump",
        "print_r",
        "die",
        "exit",
        "array_map",
        "array_filter",
        "array_merge",
        # ── Java / Kotlin ────────────────────────────────────────────────
        "System",
        "out",
        "println",
        # ── VB6 ──────────────────────────────────────────────────────────
        "MsgBox",
        "InputBox",
        "Val",
        "CStr",
        "CInt",
        "CLng",
        "CDbl",
        "Trim",
        "LTrim",
        "RTrim",
        "Left",
        "Right",
        "Mid",
        "Len",
        "UCase",
        "LCase",
        "Replace",
        "Split",
        "Join",
        "InStr",
        "Format",
        "Now",
        "Date",
        "Time",
        "DateAdd",
        "DateDiff",
        "IsNull",
        "IsEmpty",
        "IsNumeric",
        "IsDate",
        "Chr",
        "Asc",
        "Hex",
        "Fix",
        "Abs",
        "Sgn",
        "UBound",
        "LBound",
        "Array",
        "Err",
        "Debug",
        # ── Fortran ──────────────────────────────────────────────────────
        "PRINT",
        "WRITE",
        "READ",
        "OPEN",
        "CLOSE",
        "ALLOCATE",
        "DEALLOCATE",
        "STOP",
        "RETURN",
        "INTEGER",
        "REAL",
        "CHARACTER",
        "LOGICAL",
        "COMPLEX",
        "DIMENSION",
        "PARAMETER",
        # ── Scala ────────────────────────────────────────────────────────
        "Option",
        "Either",
        "Future",
        "Try",
        "Success",
        "Failure",
        "Nil",
        "Vector",
        "Seq",
        # ── Objective-C ──────────────────────────────────────────────────
        "NSLog",
        "NSString",
        "NSArray",
        "NSDictionary",
        "NSNumber",
        "NSObject",
        "NSMutableArray",
        "NSMutableDictionary",
        "alloc",
        "init",
        "dealloc",
        "self",
        "nil",
        "YES",
        "NO",
        # ── Solidity ─────────────────────────────────────────────────────
        "msg",
        "sender",
        "block",
        "timestamp",
        "require",
        "assert",
        "revert",
        "emit",
        "keccak256",
        "abi",
        "transfer",
        "send",
        "delegatecall",
        "selfdestruct",
        # ── MATLAB ───────────────────────────────────────────────────────
        "disp",
        "fprintf",
        "sprintf",
        "plot",
        "figure",
        "hold",
        "xlabel",
        "ylabel",
        "title",
        "legend",
        # ── Common Lisp ──────────────────────────────────────────────────
        "car",
        "cdr",
        "cons",
        "mapcar",
        "format",
        "princ",
        "setf",
        "setq",
        "let",
        "cond",
        "loop",
        "lambda",
        # ── Delphi / Pascal ──────────────────────────────────────────────
        "WriteLn",
        "ReadLn",
        "IntToStr",
        "StrToInt",
        "Length",
        "Copy",
        "Pos",
        "Ord",
        # ── Ada ──────────────────────────────────────────────────────────
        "Put",
        "Put_Line",
        "Get",
        "Get_Line",
        "New_Line",
        "Natural",
        "Positive",
        "Text_IO",
        # ── Perl ─────────────────────────────────────────────────────────
        "say",
        "chomp",
        "chop",
        "splice",
        "sort",
        "defined",
        "exists",
        "ref",
        "bless",
        # ── COBOL ────────────────────────────────────────────────────────
        "DISPLAY",
        "ACCEPT",
        "MOVE",
        "ADD",
        "SUBTRACT",
        "MULTIPLY",
        "DIVIDE",
        "COMPUTE",
        "PERFORM",
        "GO",
        "STRING",
        "UNSTRING",
        "INSPECT",
        # ── Erlang ───────────────────────────────────────────────────────
        "io",
        "lists",
        "erlang",
        "gen_server",
        "ets",
        # ── Prolog ───────────────────────────────────────────────────────
        "write",
        "writeln",
        "read",
        "nl",
        "findall",
        "bagof",
        "setof",
        "member",
        # ── Assembly ─────────────────────────────────────────────────────
        "mov",
        "jmp",
        "cmp",
        "je",
        "jne",
        "ret",
        "nop",
        "syscall",
        # ── Tcl ──────────────────────────────────────────────────────────
        "proc",
        "upvar",
        "uplevel",
        "variable",
        "namespace",
        "package",
        # ── Forth ────────────────────────────────────────────────────────
        "DUP",
        "DROP",
        "SWAP",
        "OVER",
        "ROT",
        "EMIT",
        "TYPE",
        # ── PostScript ───────────────────────────────────────────────────
        "moveto",
        "lineto",
        "stroke",
        "fill",
        "show",
        "setfont",
        "gsave",
        "grestore",
        "translate",
        "scale",
        "rotate",
        "newpath",
        "closepath",
        "showpage",
        # ── ABAP ─────────────────────────────────────────────────────────
        "LOOP",
        "ENDLOOP",
        "REFRESH",
        "CLEAR",
        "CONCATENATE",
        # ── RPG ──────────────────────────────────────────────────────────
        "CALLP",
        "EVAL",
        "EXSR",
        "BEGSR",
        "ENDSR",
        # ── MUMPS ────────────────────────────────────────────────────────
        "SET",
        "KILL",
        "HALT",
    }
)


def _disambiguate_extension(
    ext: str,
    content_head: str,
) -> SupportedLanguages | None:
    """Resolve an ambiguous file extension using content heuristics.

    Checks the first ~2KB of file content for language-specific indicators.
    Returns the best-matching language, or the first candidate as fallback.
    """
    candidates = AMBIGUOUS_EXTENSIONS.get(ext)
    if not candidates:
        return None

    best_lang = None
    best_score = 0

    for lang, indicators in candidates:
        score = sum(1 for ind in indicators if ind in content_head)
        if score > best_score:
            best_score = score
            best_lang = lang

    # If no indicators matched, return the first candidate as default
    if best_lang is None and candidates:
        best_lang = candidates[0][0]

    return best_lang


def get_language_from_filename(
    filename: str,
    content_head: str | None = None,
) -> SupportedLanguages | None:
    """Determine the language from a file's extension.

    Args:
        filename: The filename or path to check.
        content_head: Optional first ~2KB of file content for disambiguating
            extensions shared by multiple languages (.m, .cls, .pl).
    """
    ext = os.path.splitext(filename)[1].lower()

    # Check for ambiguous extensions first
    if ext in AMBIGUOUS_EXTENSIONS:
        if content_head is not None:
            return _disambiguate_extension(ext, content_head)
        # Without content, return the first candidate as default
        return AMBIGUOUS_EXTENSIONS[ext][0][0]

    return EXTENSION_MAP.get(ext)


def is_tsx_file(filename: str) -> bool:
    """Check if a file uses the TSX grammar."""
    return os.path.splitext(filename)[1].lower() in TSX_EXTENSIONS
