# Jacc localization

Jacc uses one read-only graph-assisted localization pipeline for the three benchmark variants reported by GraphLocator:

- SWE-bench Lite: 300 Python instances
- Loc-Bench V1: 559 valid Python instances (one invalid instance excluded)
- Multi-SWE-bench Java: 128 Java instances

Source repositories are cloned from GitHub once, materialized at each `base_commit` with `git archive`, then indexed locally. Jacc does not use Docker for benchmark execution, run project code, install dependencies, edit files, or generate patches.

## Run one instance

```bash
uv run python src/run_localize.py \
  --benchmark swe_bench_lite \
  --task-id sympy__sympy-18189 \
  --model gpt-5-mini \
  --max-steps 20
```

Use the same runner for the other benchmarks:

```bash
uv run python src/run_localize.py --benchmark locbench --task-id UXARRAY__uxarray-1117
uv run python src/run_localize.py --benchmark multi_swe_bench_java --task-id fasterxml__jackson-databind-4641
```

## Run a benchmark

```bash
uv run python src/run_localize.py \
  --benchmark swe_bench_lite \
  --workers 1 \
  --model gpt-5-mini \
  --max-steps 20
```

Change only `--benchmark` to `locbench` or `multi_swe_bench_java`. Results are written under `.agent_runs/localization/` as `<benchmark>_loc_results.json` and `<benchmark>_summary.json`.

## Track progress

Each task writes timestamped milestones to a plain log file. Terminal logging is disabled by default:

```text
.agent_runs/localization/<instance_id>/logs/*.log
```

Useful commands:

```bash
ps -ef | grep '[r]un_localize.py'
tail -f .agent_runs/localization/<instance_id>/logs/*.log
find .agent_runs/localization/<instance_id> -maxdepth 2 -type f
```

The task writes `result.json` and `trajectory.json` after completion. No log file means the process did not reach the runner logging setup.

## Langfuse tracing

Start the optional local Langfuse server:

```bash
cd docker/langfuse
cp .env.langfuse.example .env.langfuse
# Replace change-me values first.
docker compose pull
docker compose up -d
```

Open `http://localhost:3000`, create a project, then add its keys to `Jacc-v2/.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

Run Jacc again after changing `.env`; an already-running process does not reload environment variables. Langfuse tracing is optional and disabled when either key is blank. The Langfuse setup details are in `docker/langfuse/README.md`.

## Evaluate

```bash
uv run python src/evaluate_localize.py \
  --benchmark swe_bench_lite \
  --predictions .agent_runs/localization/swe_bench_lite_loc_results.json
```

The output uses GraphLocator's three levels and metric names: `found_files`, `found_modules`, `found_functions`; `success_location`, `recall`, `precision`, and `f1`.

Copied benchmark inputs and gold files live in `evaluation/localization/`. The dataset loader validates the expected valid counts and excludes the documented invalid Loc-Bench instance.
