from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from repo_explorer.ingestion.pipeline import (  # noqa: E402
    PipelineConfig,
    PipelineProgress,
    describe_pipeline,
    run_ingestion_pipeline,
)


FILES = {
    "app/main.py": '''\
from models.user import Repository as repo, User


class Service:
    """Coordinates user loading for the application service layer."""

    def build(self):
        user: User = repo.load()
        return repo.save(user)
''',
    "models/base.py": '''\
class BaseRepository:
    def ping(self):
        return True


class CacheMixin:
    def ping(self):
        return "cached"
''',
    "models/user.py": '''\
from models.base import BaseRepository, CacheMixin


class User:
    __tablename__ = "users"

    pass


def hydrate_user() -> User:
    return User()


class AuditLog:
    def save(self):
        return None


class Repository(BaseRepository, CacheMixin):
    def load(self) -> User:
        return hydrate_user()

    def save(self, user: User) -> User:
        return user
''',
    "README.md": "# Sample repo\n",
}


def write_sample_repo(repo_path: Path) -> None:
    for relative_path, content in FILES.items():
        target = repo_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def print_progress(progress: PipelineProgress, _state: dict) -> None:
    print(
        f"  [{progress.phase_index}/{progress.total_phases}] "
        f"{progress.phase}: {progress.message}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the linear repo_explorer ingestion pipeline."
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        help="Repository path to ingest. If omitted, a temporary sample repo is used.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Load graph into LadybugDB and create FTS indexes/metadata.",
    )
    args = parser.parse_args()

    print("pipeline phases:")
    for index, phase in enumerate(describe_pipeline(), start=1):
        print(f"  {index}. {phase}")

    if args.repo_path:
        repo_path = Path(args.repo_path).resolve()
        print(f"\nrepo: {repo_path}")
        state = run_ingestion_pipeline(
            PipelineConfig(
                repo_path=str(repo_path),
                persist=args.persist,
                force=True,
                on_progress=print_progress,
            )
        )
    else:
        with tempfile.TemporaryDirectory(prefix="ckg-linear-pipeline-") as tmp:
            repo_path = Path(tmp)
            write_sample_repo(repo_path)
            print(f"\nrepo: {repo_path}")
            state = run_ingestion_pipeline(
                PipelineConfig(
                    repo_path=str(repo_path),
                    persist=args.persist,
                    force=True,
                    on_progress=print_progress,
                )
            )

    print("\nresult:")
    print(f"  stats: {state.get('stats')}")
    print(f"  files: {len(state.get('file_paths', []))}")
    print(f"  imports: {len(state.get('imports', []))}")
    print(f"  calls: {len(state.get('calls', []))}")
    print(f"  heritage: {len(state.get('heritage', []))}")
    print(f"  communities: {len(state.get('community_nodes', []))}")
    print(f"  processes: {len(state.get('process_nodes', []))}")

    load_result = state.get("load_result")
    if load_result:
        print(f"  lbug: {load_result.db_path}")
        print(f"  failed_tables: {load_result.stats.get('failed_tables', [])}")

    index_result = state.get("index_result")
    if index_result:
        print(f"  meta: {index_result.meta_path}")
        print(f"  graph_json: {index_result.graph_json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
