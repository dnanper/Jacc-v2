"""Import resolution dispatcher — routes to per-language resolvers.

Each language gets its own resolver function that understands its import
semantics. All resolvers fall back to standard suffix-index resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .extraction.import_resolvers.utils import (
    SuffixIndex,
    resolve_relative_path,
)

from ..config import SupportedLanguages


@dataclass
class ImportResult:
    """Result of import resolution."""

    kind: str
    files: list[str]
    dir_suffix: str | None = None


@dataclass
class ImportConfigs:
    """Bundled language config data for import resolution."""

    tsconfig_paths: dict[str, str] | None = None
    tsconfig_base_url: str | None = None
    go_module: object | None = None
    composer_config: object | None = None
    swift_package_config: object | None = None
    csharp_configs: list | None = field(default_factory=list)


@dataclass
class ResolveCtx:
    """Context passed to per-language resolvers."""

    all_files: set[str]
    all_file_list: list[str]
    suffix_index: SuffixIndex
    configs: ImportConfigs | None = None


def _resolve_standard(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Standard resolution: relative paths + suffix index."""
    result = resolve_relative_path(raw_path, current_file, ctx.all_files)
    if result:
        return ImportResult(kind="files", files=[result])

    result = ctx.suffix_index.lookup(raw_path)
    if result:
        return ImportResult(kind="files", files=[result])

    return None


def _resolve_ts_js(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """TypeScript/JavaScript: tsconfig path aliases + standard."""
    rewritten = raw_path
    if ctx.configs and ctx.configs.tsconfig_paths:
        for alias, replacement in ctx.configs.tsconfig_paths.items():
            if rewritten.startswith(alias):
                base_url = ctx.configs.tsconfig_base_url or ""
                remainder = rewritten[len(alias) :]
                if base_url:
                    rewritten = base_url.rstrip("/") + "/" + replacement + remainder
                else:
                    rewritten = replacement + remainder
                break

    return _resolve_standard(rewritten, current_file, ctx)


def _resolve_python_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Python: PEP 328 relative + proximity, then standard."""
    from .extraction.import_resolvers.python import resolve_python_import

    result = resolve_python_import(current_file, raw_path, ctx.all_files)
    if result:
        return ImportResult(kind="files", files=[result])

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_go_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Go: package-based resolution."""
    from .extraction.import_resolvers.go import resolve_go_import

    go_module = ctx.configs.go_module if ctx.configs else None
    files = resolve_go_import(raw_path, go_module, ctx.all_file_list)
    if files:
        return ImportResult(
            kind="package",
            files=files,
            dir_suffix="/" + raw_path.rsplit("/", 1)[-1] + "/",
        )

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_java_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Java: wildcard/member imports."""
    from .extraction.import_resolvers.jvm import resolve_java_import

    result = resolve_java_import(raw_path, ctx.all_file_list, ctx.suffix_index)
    if result:
        files = result if isinstance(result, list) else [result]
        return ImportResult(kind="files", files=files)

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_kotlin_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Kotlin: JVM wildcard/member with .kt/.kts + .java interop."""
    from .extraction.import_resolvers.jvm import resolve_kotlin_import

    result = resolve_kotlin_import(raw_path, ctx.all_file_list, ctx.suffix_index)
    if result:
        files = result if isinstance(result, list) else [result]
        return ImportResult(kind="files", files=files)

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_rust_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Rust: crate::, super::, self:: + module paths."""
    from .extraction.import_resolvers.rust import resolve_rust_import

    result = resolve_rust_import(current_file, raw_path, ctx.all_files)
    if result:
        return ImportResult(kind="files", files=[result])

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_csharp_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """C#: namespace-based resolution."""
    from .extraction.import_resolvers.csharp import resolve_csharp_import

    csharp_configs = ctx.configs.csharp_configs if ctx.configs else []
    files = resolve_csharp_import(
        raw_path, csharp_configs or [], ctx.all_file_list, ctx.suffix_index
    )
    if files:
        return ImportResult(kind="files", files=files)

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_php_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """PHP: PSR-4 namespace resolution."""
    from .extraction.import_resolvers.php import resolve_php_import

    composer = ctx.configs.composer_config if ctx.configs else None
    result = resolve_php_import(raw_path, composer, ctx.all_files)
    if result:
        return ImportResult(kind="files", files=[result])

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_ruby_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Ruby: require/require_relative."""
    from .extraction.import_resolvers.ruby import resolve_ruby_import

    result = resolve_ruby_import(raw_path, ctx.all_file_list, ctx.suffix_index)
    if result:
        return ImportResult(kind="files", files=[result])

    return _resolve_standard(raw_path, current_file, ctx)


def _resolve_swift_dispatch(
    raw_path: str,
    current_file: str,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Swift: target map lookup."""
    from .extraction.import_resolvers.swift import resolve_swift_import

    swift_config = ctx.configs.swift_package_config if ctx.configs else None
    files = resolve_swift_import(raw_path, swift_config, ctx.all_file_list)
    if files:
        return ImportResult(kind="package", files=files)

    return None


IMPORT_RESOLVERS: dict[
    SupportedLanguages,
    Callable[[str, str, ResolveCtx], ImportResult | None],
] = {
    SupportedLanguages.JAVASCRIPT: _resolve_ts_js,
    SupportedLanguages.TYPESCRIPT: _resolve_ts_js,
    SupportedLanguages.PYTHON: _resolve_python_dispatch,
    SupportedLanguages.JAVA: _resolve_java_dispatch,
    SupportedLanguages.C: _resolve_standard,
    SupportedLanguages.C_PLUS_PLUS: _resolve_standard,
    SupportedLanguages.C_SHARP: _resolve_csharp_dispatch,
    SupportedLanguages.GO: _resolve_go_dispatch,
    SupportedLanguages.RUBY: _resolve_ruby_dispatch,
    SupportedLanguages.RUST: _resolve_rust_dispatch,
    SupportedLanguages.PHP: _resolve_php_dispatch,
    SupportedLanguages.KOTLIN: _resolve_kotlin_dispatch,
    SupportedLanguages.SWIFT: _resolve_swift_dispatch,
    # ── Wave 1 ───────────────────────────────────────────────────────
    # Fortran: USE module_name → suffix lookup for module file
    SupportedLanguages.FORTRAN: _resolve_standard,
    # Scala: JVM-style imports — reuse Java resolver
    SupportedLanguages.SCALA: _resolve_java_dispatch,
    # Objective-C: #import "Header.h" — same as C includes
    SupportedLanguages.OBJECTIVE_C: _resolve_standard,
    # Solidity: import "./Foo.sol" — path-based, similar to JS
    SupportedLanguages.SOLIDITY: _resolve_standard,
    # Perl: use Module::Name → Module/Name.pm — suffix lookup
    SupportedLanguages.PERL: _resolve_standard,
    # COBOL: COPY copybook → .cpy file lookup
    SupportedLanguages.COBOL: _resolve_standard,
    # ── Wave 2 ───────────────────────────────────────────────────────
    # Ada: with Ada.Text_IO → convention-based file mapping
    SupportedLanguages.ADA: _resolve_standard,
    # MATLAB: function name = file name convention
    SupportedLanguages.MATLAB: _resolve_standard,
    # Common Lisp: (require ...) → ASDF system files
    SupportedLanguages.COMMON_LISP: _resolve_standard,
    # Delphi: uses UnitName → file mapping
    SupportedLanguages.DELPHI: _resolve_standard,
    # ── Wave 3 ───────────────────────────────────────────────────────
    # Erlang: module_name → module_name.erl
    SupportedLanguages.ERLANG: _resolve_standard,
    # Pascal: uses UnitName → UnitName.pas
    SupportedLanguages.PASCAL: _resolve_standard,
    # Prolog: use_module(library(X)) → library path
    SupportedLanguages.PROLOG: _resolve_standard,
    # Apex: no imports (all classes in same namespace)
    # ── Wave 4-5: Tier 3 ─────────────────────────────────────────────
    SupportedLanguages.RPG: _resolve_standard,  # /COPY, /INCLUDE
    SupportedLanguages.ABAP: _resolve_standard,  # INCLUDE
    SupportedLanguages.ASSEMBLY: _resolve_standard,  # .include
    SupportedLanguages.TCL: _resolve_standard,  # package require, source
    SupportedLanguages.FORTH: _resolve_standard,  # INCLUDE, REQUIRE
    SupportedLanguages.POSTSCRIPT: _resolve_standard,  # (file) run
    # MUMPS and ALGOL have no formal import system
}


def resolve_import(
    raw_path: str,
    from_file: str,
    language: SupportedLanguages,
    ctx: ResolveCtx,
) -> ImportResult | None:
    """Resolve an import path using the appropriate language strategy.

    Args:
        raw_path: Raw import path from the source code.
        from_file: File containing the import statement.
        language: Source language.
        ctx: Resolution context with file lists and configs.

    Returns:
        ImportResult with resolved files, or None if unresolvable.
    """
    resolver = IMPORT_RESOLVERS.get(language, _resolve_standard)
    return resolver(raw_path, from_file, ctx)
