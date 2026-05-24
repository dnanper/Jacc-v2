uv run python tests/run_mutations_mixin.py --real --db-path src/modules/data/repos/ckg-linear-pipeline-z3gksmty-14e6b4b661c9/lbug --symbol build

uv run python tests/run_impact_mixin.py --db-path src/modules/data/repos/ckg-linear-pipeline-z3gksmty-14e6b4b661c9/lbug --target load

uv run python tests/run_explore_mixin.py --db-path src/modules/data/repos/ckg-linear-pipeline-z3gksmty-14e6b4b661c9/lbug --query Repository --scope file:models/user.py --symbols build,Repository,load,save,hydrate_user

uv run python tests/run_context_mixin.py --real --repo-path <repo_path_da_ingest> --symbol build

uv run python tests/run_ingestion_pipeline.py --persist
