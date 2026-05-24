"""Mutations mixin — rename, cypher, list_repos, delete_repo, analyze."""

from __future__ import annotations

import logging
import os
from typing import Any

from repo_explorer.repository.repo_manager import list_registered_repos

from ._helpers import CYPHER_WRITE_RE

logger = logging.getLogger(__name__)


class MutationsMixin:
    """Write operations: rename, cypher, repo management, ingestion."""

    def rename(
        self,
        symbol_name: str,
        new_name: str,
        dry_run: bool = True,
    ) -> dict:
        """Graph-aware rename preview or execution."""
        ctx = self.context(symbol_name)
        if "error" in ctx:
            return ctx

        refs = []
        for caller in ctx.get("callers", []):
            refs.append(
                {
                    "filePath": caller.get("filePath", ""),
                    "type": "reference",
                    "relType": caller.get("relType", ""),
                }
            )

        sym = ctx["symbol"]
        refs.append(
            {
                "filePath": sym.get("filePath", ""),
                "type": "definition",
            }
        )

        definitions = sum(1 for r in refs if r.get("type") == "definition")
        usages = sum(1 for r in refs if r.get("type") == "reference")

        result = {
            "symbol": symbol_name,
            "new_name": new_name,
            "dry_run": dry_run,
            "affected_files": list({r["filePath"] for r in refs if r["filePath"]}),
            "references": refs,
            "counts": {"definitions": definitions, "usages": usages},
        }

        all_matches = ctx.get("_all_matches", [])
        if len(all_matches) > 1:
            result["candidates"] = [
                {
                    "name": m.get("name"),
                    "type": m.get("type"),
                    "filePath": m.get("filePath"),
                }
                for m in all_matches
            ]
            result["_disambiguation"] = (
                f"Found {len(all_matches)} symbols named '{symbol_name}'. "
                "Renaming references for the first match only. "
                "Use csg_explore with scope='file:<path>' to target a specific one."
            )

        if not dry_run:
            import re as regex_mod

            pattern = regex_mod.compile(r"\b" + regex_mod.escape(symbol_name) + r"\b")
            files_modified = 0

            from repo_explorer.discovery.content_filter import is_binary_path

            for fp in result["affected_files"]:
                if is_binary_path(fp):
                    logger.debug("Skipping rename in binary file: %s", fp)
                    continue
                try:
                    with open(fp, "r") as f:
                        content = f.read()
                    new_content = pattern.sub(new_name, content)
                    if new_content != content:
                        with open(fp, "w") as f:
                            f.write(new_content)
                        files_modified += 1
                except Exception as e:
                    logger.warning("Failed to rename in %s: %s", fp, e)

            result["files_modified"] = files_modified

            # Publish event so MCP's event-driven re-ingestion picks it up
            if files_modified > 0:
                repo_path = getattr(self._adapter, "repo_source_path", None)
                if repo_path:
                    try:
                        from ..graph.storage.kuzu_pool import KuzuPool

                        KuzuPool.get().event_bus.publish(
                            "source_changed",
                            {
                                "repo_path": repo_path,
                                "reason": "rename",
                                "symbol": symbol_name,
                                "new_name": new_name,
                                "files_modified": files_modified,
                            },
                        )
                    except Exception:
                        logger.debug(
                            "Could not publish source_changed event", exc_info=True
                        )

        return result

    def cypher(self, query: str) -> dict:
        """Execute a raw read-only Cypher query."""
        if CYPHER_WRITE_RE.search(query):
            return {
                "error": "Write operations are not allowed. Only read queries are supported."
            }

        try:
            rows = self._query(query)
            return {"results": rows, "count": len(rows)}
        except Exception as e:
            return {"error": str(e)}

    def list_repos(self) -> dict:
        """List all indexed repositories."""
        repos = list_registered_repos()
        return {
            "repos": [
                {
                    "name": r.name,
                    "path": r.path,
                    "indexed_at": r.indexed_at,
                }
                for r in repos
            ],
            "total": len(repos),
        }

    @staticmethod
    def delete_repo(
        repo: str = "",
        clean_storage: bool = True,
        delete_all: bool = False,
    ) -> dict:
        """Delete indexed repositories from the registry and optionally disk."""
        import shutil

        from repo_explorer.repository.repo_manager import (
            get_storage_path,
            unregister_repo,
        )

        repos = list_registered_repos(validate=False)

        if delete_all:
            targets = repos
        elif repo:
            targets = [r for r in repos if r.name.lower() == repo.lower()]
            if not targets:
                available = [r.name for r in repos]
                return {
                    "status": "not_found",
                    "error": f"Repository '{repo}' not found",
                    "available": available,
                }
        else:
            return {
                "status": "error",
                "error": "Provide a repo name, or set delete_all=true",
            }

        deleted: list[dict] = []
        for target in targets:
            unregister_repo(target.path)

            storage_cleaned = False
            if clean_storage:
                storage = get_storage_path(target.path)
                if storage.exists():
                    # Release KuzuDB lock before deleting files
                    try:
                        from ..graph.storage.kuzu_pool import KuzuPool

                        lbug_path = os.path.join(str(storage), "lbug")
                        KuzuPool.get().close(lbug_path)
                    except Exception:
                        pass
                    shutil.rmtree(storage, ignore_errors=True)
                    storage_cleaned = True

            deleted.append(
                {
                    "name": target.name,
                    "path": target.path,
                    "storage_cleaned": storage_cleaned,
                }
            )
            logger.info("Deleted repo: %s (%s)", target.name, target.path)

        return {
            "status": "ok",
            "deleted": deleted,
            "count": len(deleted),
        }

    # Built-in dirs to always exclude (compiled output, caches)
    _DEFAULT_EXCLUDE = frozenset(
        {
            "dist",
            "build",
            "out",
            ".next",
            "__pycache__",
            ".nuxt",
            "target",
            "bin",
            "obj",
            ".gradle",
            ".cache",
            "coverage",
            ".nyc_output",
            ".tox",
        }
    )

    @staticmethod
    def _analyze_single(
        path: str,
        force: bool = False,
        embeddings: bool = True,
        exclude: list[str] | None = None,
    ) -> dict:
        """Ingest / index a single repository so it becomes queryable."""
        import shutil
        import tempfile
        import zipfile

        from repo_explorer.ingestion.pipeline import run_pipeline
        from repo_explorer.ingestion.state import PipelineConfig
        from repo_explorer.repository.repo_manager import get_storage_path

        repo_path = path

        if zipfile.is_zipfile(path):
            # 1. Extract to temp to discover project name
            tmp_dir = tempfile.mkdtemp(prefix="csg_analyze_")
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmp_dir)
            entries = os.listdir(tmp_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(tmp_dir, entries[0])):
                project_name = entries[0]
            else:
                project_name = os.path.splitext(os.path.basename(path))[0]

            # 2. Compute storage from the zip path, move codebase inside it
            storage = get_storage_path(path)
            storage.mkdir(parents=True, exist_ok=True)
            dest = storage / project_name
            if dest.exists():
                shutil.rmtree(dest)
            src = (
                os.path.join(tmp_dir, entries[0])
                if len(entries) == 1
                and os.path.isdir(os.path.join(tmp_dir, entries[0]))
                else tmp_dir
            )
            shutil.move(src, str(dest))
            shutil.rmtree(tmp_dir, ignore_errors=True)

            repo_path = str(dest)
            logger.info("Extracted zip %s -> %s", path, repo_path)

        repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(repo_path):
            return {"error": f"Not a directory: {repo_path}"}

        embeddings_warning = None
        if embeddings:
            file_count = sum(1 for _, _, files in os.walk(repo_path) for _ in files)
            if file_count > 2000:
                embeddings = False
                embeddings_warning = (
                    f"Embeddings auto-disabled: {file_count} files detected. "
                    f"Embedding large repos can take 10+ minutes on CPU. "
                    f"Re-run with embeddings=true explicitly if needed."
                )
                logger.warning(embeddings_warning)

        all_excludes = MutationsMixin._DEFAULT_EXCLUDE | frozenset(exclude or [])

        config = PipelineConfig(
            repo_path=repo_path,
            force=force,
            embeddings=embeddings,
            exclude_dirs=all_excludes,
        )

        try:
            stats = run_pipeline(config)
        except Exception as exc:
            logger.exception("Analyze failed for %s", repo_path)
            return {"error": str(exc), "path": repo_path}

        result: dict[str, Any] = {
            "status": "ok",
            "path": repo_path,
            "stats": stats,
        }
        if embeddings_warning:
            result["warning"] = embeddings_warning
        return result

    @staticmethod
    def analyze(
        path: str = "",
        force: bool = False,
        embeddings: bool = True,
        exclude: list[str] | None = None,
        paths: list[str] | None = None,
    ) -> dict:
        """Ingest / index one or more repositories.

        When *paths* is provided, each entry is ingested sequentially and
        results are collected.  When only *path* is provided, behaves as
        before (single-repo ingestion).
        """
        all_paths = list(paths or [])
        if path and path not in all_paths:
            all_paths.insert(0, path)

        if not all_paths:
            return {"error": "Provide 'path' (single) or 'paths' (batch) to analyze."}

        if len(all_paths) == 1:
            return MutationsMixin._analyze_single(
                all_paths[0],
                force=force,
                embeddings=embeddings,
                exclude=exclude,
            )

        results: list[dict] = []
        for p in all_paths:
            logger.info(
                "Batch analyze: %s (%d/%d)", p, len(results) + 1, len(all_paths)
            )
            result = MutationsMixin._analyze_single(
                p,
                force=force,
                embeddings=embeddings,
                exclude=exclude,
            )
            results.append(result)

        ok_count = sum(1 for r in results if r.get("status") == "ok")
        return {
            "status": "ok" if ok_count == len(results) else "partial",
            "results": results,
            "total": len(results),
            "succeeded": ok_count,
            "failed": len(results) - ok_count,
        }
