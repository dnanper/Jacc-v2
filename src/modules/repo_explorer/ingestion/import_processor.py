"""Import resolution — resolve raw import paths to file paths, create IMPORTS edges.

Port of GitNexus ingestion/import-processor.ts.
Uses per-language resolvers via the dispatch table in import_resolution.py.
"""

from __future__ import annotations

from ..config import SupportedLanguages
from ..graph.core.knowledge_graph import KnowledgeGraph
from ..graph.model.types import GraphRelationship, RelationshipType
from ..parsing.ast_helpers import generate_id
from .import_resolution import (
    ImportConfigs,
    ImportResult,
    ResolveCtx,
    resolve_import,
)
from .infile_processor import ExtractedImport
from .resolution_context import (
    ResolutionContext,
    NamedImportBinding,
)
from .extraction.import_resolvers.utils import SuffixIndex


def build_import_resolution_context(all_paths: list[str]) -> SuffixIndex:
    """Build the suffix index used for import resolution."""
    return SuffixIndex(all_paths)


def process_imports(
    graph: KnowledgeGraph,
    imports: list[ExtractedImport],
    ctx: ResolutionContext,
    suffix_index: SuffixIndex,
    on_progress: callable = None,
    import_configs=None,
) -> None:
    """Resolve imports and create IMPORTS edges + populate import maps.

    Args:
        graph: Knowledge graph to add IMPORTS edges to.
        imports: Extracted import records from parsing.
        ctx: Resolution context (import_map and named_import_map populated here).
        suffix_index: Suffix index for path resolution.
        on_progress: Optional ``(current, total)`` callback.
        import_configs: Parsed language config files for import resolution.
    """
    total = len(imports)
    resolved_count = 0

    all_file_set = set(suffix_index.get_all("") or [])
    all_file_list: list[str] = []
    seen: set[str] = set()
    for imp in imports:
        fp = imp.file_path
        if fp not in seen:
            seen.add(fp)
            all_file_list.append(fp)
    for node in graph.iter_nodes():
        if node.label == "File":
            props = node.properties
            fp = props.get("file_path", "")
            if fp and fp not in seen:
                seen.add(fp)
                all_file_list.append(fp)
    all_file_set = seen

    configs = _build_import_configs(import_configs) if import_configs else None

    resolve_ctx = ResolveCtx(
        all_files=all_file_set,
        all_file_list=all_file_list,
        suffix_index=suffix_index,
        configs=configs,
    )

    for idx, imp in enumerate(imports):
        if on_progress and idx % 100 == 0:
            on_progress(idx, total)

        raw_path = imp.raw_import_path
        language = _get_language_enum(imp.language)

        import_result = resolve_import(raw_path, imp.file_path, language, resolve_ctx)

        if import_result is None:
            if import_configs:
                raw_path = _rewrite_import_path(raw_path, imp.language, import_configs)
            from .extraction.import_resolvers.standard import resolve_import_path

            resolved_path = resolve_import_path(raw_path, imp.file_path, suffix_index)
            if resolved_path:
                import_result = ImportResult(kind="files", files=[resolved_path])

        if import_result is None:
            continue

        resolved_count += 1

        for resolved_path in import_result.files:
            if imp.file_path not in ctx.import_map:
                ctx.import_map[imp.file_path] = set()
            ctx.import_map[imp.file_path].add(resolved_path)

            source_id = generate_id("File", imp.file_path)
            target_id = generate_id("File", resolved_path)
            edge_id = f"{source_id}_imports_{target_id}"

            graph.add_relationship(
                GraphRelationship(
                    id=edge_id,
                    source_id=source_id,
                    target_id=target_id,
                    type=RelationshipType.IMPORTS,
                    confidence=1.0,
                    reason="import-statement",
                )
            )

        if import_result.kind == "package" and import_result.dir_suffix:
            ctx.package_map.setdefault(imp.file_path, set()).add(
                import_result.dir_suffix
            )

        if imp.named_bindings:
            resolved_path = import_result.files[0] if import_result.files else None
            if resolved_path:
                file_bindings = ctx.named_import_map.setdefault(imp.file_path, {})
                for binding in imp.named_bindings:
                    local = binding.get("local", binding.get("exported", ""))
                    exported = binding.get("exported", local)
                    file_bindings[local] = NamedImportBinding(
                        source_path=resolved_path,
                        exported_name=exported,
                    )


def _get_language_enum(lang_str: str) -> SupportedLanguages:
    """Convert a language string to SupportedLanguages enum."""
    try:
        return SupportedLanguages(lang_str)
    except ValueError:
        return SupportedLanguages.JAVASCRIPT


def _build_import_configs(configs) -> ImportConfigs:
    """Convert the old-style config object to ImportConfigs."""
    result = ImportConfigs()
    if hasattr(configs, "tsconfig_paths") and configs.tsconfig_paths:
        result.tsconfig_paths = configs.tsconfig_paths
    if hasattr(configs, "go_module") and configs.go_module:
        from .extraction.import_resolvers.go import GoModuleConfig

        result.go_module = GoModuleConfig(module_path=configs.go_module)
    if hasattr(configs, "php_psr4") and configs.php_psr4:
        from .extraction.import_resolvers.php import ComposerConfig

        result.composer_config = ComposerConfig(psr4=configs.php_psr4)
    if hasattr(configs, "csharp_root_namespaces") and configs.csharp_root_namespaces:
        from .extraction.import_resolvers.csharp import CSharpProjectConfig

        result.csharp_configs = [
            CSharpProjectConfig(
                root_namespace=cfg["rootNamespace"],
                project_dir=cfg.get("projectDir", "."),
            )
            for cfg in configs.csharp_root_namespaces
        ]
    return result


def _rewrite_import_path(raw_path: str, language: str, configs) -> str:
    """Rewrite an import path using language config data (legacy fallback)."""
    if (
        language in ("javascript", "typescript")
        and hasattr(configs, "tsconfig_paths")
        and configs.tsconfig_paths
    ):
        for alias, replacement in configs.tsconfig_paths.items():
            if raw_path.startswith(alias):
                return replacement + raw_path[len(alias) :]

    if language == "go" and hasattr(configs, "go_module") and configs.go_module:
        if raw_path.startswith(configs.go_module):
            stripped = raw_path[len(configs.go_module) :]
            return stripped.lstrip("/")

    if language == "php" and hasattr(configs, "php_psr4") and configs.php_psr4:
        for ns, directory in sorted(configs.php_psr4.items(), key=lambda x: -len(x[0])):
            if raw_path.startswith(ns):
                remainder = raw_path[len(ns) :].replace("\\", "/")
                return directory.rstrip("/") + "/" + remainder

    if (
        language == "c_sharp"
        and hasattr(configs, "csharp_root_namespaces")
        and configs.csharp_root_namespaces
    ):
        for cfg in configs.csharp_root_namespaces:
            root_ns = cfg["rootNamespace"]
            if raw_path.startswith(root_ns + "."):
                remainder = raw_path[len(root_ns) + 1 :].replace(".", "/")
                proj_dir = cfg["projectDir"]
                return (proj_dir + "/" + remainder) if proj_dir != "." else remainder

    return raw_path
