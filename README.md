# Jacc localization

Jacc (called HyLokG in the thesis) localizes the code that must change to resolve a GitHub issue. It builds a code
knowledge graph (CKG) of the repository at the issue's base commit, then runs a read-only, graph-assisted LLM
pipeline that returns the files, modules (classes) and functions to edit.

**Main branch: `main`.** It holds the code behind the results reported in the thesis. Other branches are
development and experiment branches.

Jacc uses one read-only graph-assisted localization pipeline for the three benchmark variants reported by GraphLocator:

- SWE-bench Lite: 300 Python instances
- Loc-Bench V1: 559 valid Python instances (one invalid instance excluded)
- Multi-SWE-bench Java: 128 Java instances

Source repositories are cloned from GitHub once, materialized at each `base_commit` with `git archive`, then indexed locally. Jacc does not use Docker for benchmark execution, run project code, install dependencies, edit files, or generate patches.

## Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [LLM cost control](#llm-cost-control)
5. [Build the code knowledge graph](#build-the-code-knowledge-graph)
6. [Run one instance (demo)](#run-one-instance-demo)
7. [Run a benchmark](#run-a-benchmark)
8. [Track progress](#track-progress)
9. [Optional services](#optional-services)
10. [Evaluate](#evaluate)
11. [Tests](#tests)
12. [Repository layout](#repository-layout)

## Requirements

| Requirement | Notes |
|---|---|
| Linux or WSL2 | Development and all reported runs used Linux (WSL2). |
| Python 3.13 | `pyproject.toml` requires `>=3.13`; `.python-version` pins 3.13. |
| [uv](https://docs.astral.sh/uv/) | Installs the locked dependencies from `uv.lock` and runs every command below. |
| Git | Clones benchmark repositories and extracts snapshots with `git archive`. |
| Network access to GitHub | Needed the first time an instance's repository is cloned. |
| OpenAI API key | Needed for localization runs (paid). Not needed for graph building, evaluation or tests. |
| Graph database | None to install. The CKG is stored in LadybugDB, an embedded graph database shipped as the `real-ladybug` Python package. |
| Docker with Compose (optional) | Only for the optional services: Postgres checkpoints, Langfuse tracing, Ladybug Explorer. |
| Node.js (optional) | Only for parsing a few languages through WASM grammars (Erlang, Pascal, Perl, Prolog, Apex, VB). Python and Java do not need it. |

## Installation

```bash
git clone https://github.com/dnanper/Jacc-v2.git
cd Jacc-v2
uv sync                      # creates .venv with Python 3.13 and the locked dependencies
cp .env.example .env         # then fill in the values (see Configuration)
```

Check the install without spending anything:

```bash
uv run python src/run_localize.py --help
uv run python tests/run_ingestion_pipeline.py     # builds a CKG for a small built-in sample repo
```

All commands are run from the repository root.

## Configuration

`src/run_localize.py` reads `.env` from the repository root at start-up. Variables already set in the shell take
precedence over `.env`. A running process does not reload `.env`.

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | for localization runs | OpenAI key used for the model calls. |
| `OPENAI_MODEL` | no | Default for `--model` (fallback `gpt-5-mini`). |
| approval variable | for paid runs | Must be `1` for any real LLM call; see [LLM cost control](#llm-cost-control). Set it on the command line, not in `.env`. |
| `JACC_CALIBRATOR` | no | Calibrator file for `--mode v6`. Default `src/modules/data/calibrator_v6.json`; the thesis uses `src/modules/data/calibrator_swetrain.json`. |
| `JACC_CONSOLE_LOGS` | no | `true` also prints logs to the terminal. Default: file logs only. |
| `JACC_CHECKPOINT_DB` | no | Postgres URL for LangGraph checkpoints. Default `postgresql://jacc:jacc@localhost:5433/jacc` (`docker/postgres`). Set it to an empty value to disable checkpointing; otherwise the Postgres service must be running. |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | no | Optional Langfuse tracing. Disabled when either key is blank. |
| `CSG_DATA_DIR` | no | Where indexed repositories are stored. Default `src/modules/data`. |

Never commit `.env`; it is in `.gitignore`.

## LLM cost control

Real provider calls cost money. Every paid call path (chat models in `src/utils/llm.py`, embeddings in
`src/modules/embeddings/embedding_pipeline.py`) first calls `src/utils/llm_guard.py::guard()`, which aborts unless
the process was started with the approval variable set to `1`. The variable's name is the `ENV_VAR` constant in
`src/utils/llm_guard.py`. Without it, a run stops with a `RuntimeError` that names the variable.

A paid run must therefore be started by a person, with that variable set to `1` in front of the command. Once
approved, each successful outbound request is appended to `.tmp/llm_calls.log`. Graph building, evaluation, the
analysis scripts and the test suite make no paid calls and need no approval.

## Build the code knowledge graph

`src/run_localize.py` builds the graph automatically: for each instance it clones the repository into the source
cache, extracts the `base_commit` snapshot, and indexes it unless a graph for that snapshot already exists
(`--force` rebuilds it). No LLM is involved in this step.

To build a graph for any local repository on its own (offline, free):

```bash
# Parse, resolve imports/calls/inheritance, detect communities and processes; keep the result in memory
uv run python tests/run_ingestion_pipeline.py /path/to/repo

# Same, and also load it into LadybugDB with full-text indexes and metadata
uv run python tests/run_ingestion_pipeline.py /path/to/repo --persist

# No path: run on a small built-in sample repository
uv run python tests/run_ingestion_pipeline.py --persist
```

With `--persist`, the output goes to `src/modules/data/repos/<name>-<hash>/`:

- `lbug`: the LadybugDB database
- `meta.json`: index metadata and statistics
- `graph.json`: the graph as JSON
- `artifacts/`: derived files such as the A0.5 repository profile (written during localization)

For a quick file/folder-only view of a repository (structure nodes only, no parsing):

```bash
uv run python src/main.py /path/to/repo --sample 10 --edges 10
```

To browse a persisted graph in a web UI, see [Ladybug Explorer](#ladybug-explorer). The graph schema is described in
`docs/design/graph-schema.md`.

## Run one instance (demo)

This is a paid run (see [LLM cost control](#llm-cost-control)). It needs `OPENAI_API_KEY` in `.env` and, unless
`JACC_CHECKPOINT_DB` is empty, the Postgres service from `docker/postgres`. The command runs the thesis
configuration on one SWE-bench Lite issue (start it with the approval variable set to `1`):

```bash
JACC_CALIBRATOR=src/modules/data/calibrator_swetrain.json \
uv run python src/run_localize.py \
  --benchmark swe_bench_lite \
  --task-id sympy__sympy-18189 \
  --mode v6 \
  --model gpt-5.6-luna
```

Use the same runner for the other benchmarks, for example `--benchmark locbench --task-id UXARRAY__uxarray-1117`.

Without the approval variable the run stops at the first model call and the printed summary reports `"failed": 1`
with the guard message. This is a free way to check the wiring.

`--task-id` also accepts several ids separated by commas. `python main.py` at the repository root is the same
command as `python src/run_localize.py`.

Runner options (`uv run python src/run_localize.py --help`):

| Option | Meaning |
|---|---|
| `--benchmark` | `swe_bench_lite`, `locbench` or `multi_swe_bench_java` (required). |
| `--task-id` | One instance id or a comma-separated list. Omitted: the whole benchmark. |
| `--mode` | `v6`: the method of the thesis (A0-A3, graph discovery, one listwise verifier call, frozen calibrator, thresholded answer). The other modes are earlier pipelines kept in the code: `pipeline` (default; A0-A6 with exploration A4 and revision A5), `a3`, `a3s`, `a3r` (A3 answers), `baseline` (a free ReAct agent with read-only CKG tools). |
| `--model` | Chat model (default `OPENAI_MODEL`, else `gpt-5-mini`). |
| `--a3-samples` | A3 samples pooled per instance (default 2). |
| `--explore-budget CALLS READS` | A4 budget (`pipeline` mode only). |
| `--a4-variant` | A4 ablation (`pipeline` mode only): `full` (default), `anchors`, `no_expand`, `veto`. |
| `--max-steps` | Step limit of the `baseline` agent; unused by the other modes. |
| `--workers` | Instances run in parallel (default 1). |
| `--workspace` | Output directory (default `.agent_runs/localization`). |
| `--source-cache` | Where clones and snapshots are kept (default `<workspace>/source-cache`). |
| `--data-dir` | Benchmark inputs (default `evaluation/localization`). |
| `--force` | Rebuild the graph and recompute every cached step. |

Each step caches its artifact in `<workspace>/<instance_id>/` and is reused on the next run with the same inputs:
`issue_model.<model>.json` (A1), `A2_seeds.<model>.json`, `A3_hypotheses.<model>.json`, `A3V_verify.<model>.json`
(verifier and calibrated probabilities), and the exported answer `A6_export.json`.

## Run a benchmark

```bash
JACC_CALIBRATOR=src/modules/data/calibrator_swetrain.json \
uv run python src/run_localize.py --benchmark swe_bench_lite --mode v6 --model gpt-5.6-luna --workers 3
```

Change only `--benchmark` to `locbench` for LocBench. Results are written under `.agent_runs/localization/`: one
directory per instance, plus `<benchmark>_loc_results.json` and `<benchmark>_summary.json`.

A full benchmark makes about eight model calls per instance; run a few ids first and check their logs and outputs
before starting the whole set. The process exits with status 1 if any instance failed.

## Track progress

Each task writes timestamped milestones to a plain log file. Terminal logging is disabled by default (set `JACC_CONSOLE_LOGS=true` to enable it):

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

## Optional services

### Postgres checkpoints

LangGraph checkpoints every step of a localization run to Postgres, as an audit trail.

```bash
cd docker/postgres
docker compose up -d        # listens on 127.0.0.1:5433, URL postgresql://jacc:jacc@localhost:5433/jacc
```

To run without it, start the runner with an empty `JACC_CHECKPOINT_DB`, for example
`JACC_CHECKPOINT_DB= uv run python src/run_localize.py ...`.

### Langfuse tracing

Start the optional local Langfuse server:

```bash
cd docker/langfuse
cp .env.langfuse.example .env.langfuse
# Replace change-me values first.
docker compose --env-file .env.langfuse pull
docker compose --env-file .env.langfuse up -d
```

Open `http://localhost:3000`, create a project, then add its keys to `Jacc-v2/.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

Run Jacc again after changing `.env`; an already-running process does not reload environment variables. Langfuse tracing is optional and disabled when either key is blank. The Langfuse setup details are in `docker/langfuse/README.md`.

### Ladybug Explorer

A read-only web UI for one persisted graph:

```bash
cd docker/explorer
REPO_DIR=../../src/modules/data/repos/<repo-dir> docker compose up
```

Then open `http://localhost:8000`. The image tag must match the `real-ladybug` version in `uv.lock` (0.15.3).

## Evaluate

Evaluation is offline and free. The repository has its own evaluator for a predictions file such as
`<benchmark>_loc_results.json`:

```bash
uv run python src/evaluate_localize.py \
  --benchmark swe_bench_lite \
  --predictions .agent_runs/localization/swe_bench_lite_loc_results.json
```

It reports GraphLocator's three levels and metric names (`found_files`, `found_modules`, `found_functions`;
`success_location`, `recall`, `precision`, `f1`) with paths written without the repository prefix.

Copied benchmark inputs and gold files live in `evaluation/localization/`. The dataset loader validates the expected valid counts and excludes the documented invalid Loc-Bench instance.

The predictions file maps each instance id to its three lists. Paths are relative to the repository root:

```json
{
  "astropy__astropy-12907": {
    "found_files": ["astropy/modeling/separable.py"],
    "found_modules": [],
    "found_functions": ["astropy/modeling/separable.py::_cstack"]
  }
}
```

Further offline analysis of saved runs (no LLM calls):

```bash
# Where gold is lost along A2 -> A3 -> A4, per instance
uv run python src/evaluate_stages.py --benchmark swe_bench_lite --model gpt-5.6-luna --workspace .agent_runs/localization

# Paired comparison of variants run on the same instances (first arm is the reference)
uv run python src/compare_variants.py --benchmark swe_bench_lite --tasks <ids.json> full=<workspace> veto=<workspace>

# Ranking metrics and cross-validated calibrator fit on saved runs
uv run python -m src.evaluate_ranked --benchmark swe_bench_lite --runs <workspace> --cv --features v6
```

`<ids.json>` is a JSON file with an `instances` list.

`evaluation/baseline-*` holds results of earlier baseline agents and `evaluation/benchmark/` notes on SWE-bench
Verified.

## Tests

The tests stub every model and never call a provider, so they are free and need no API key. `pytest` is not a
project dependency; run it through uv:

```bash
uv run --with pytest pytest tests -q \
  --ignore=tests/test_a0_migration_lifecycle.py --ignore=tests/test_development_staging.py
```

The two ignored modules need local development fixtures that are not in the repository. New tests must keep
stubbing the model (`patch.object(..., "guard")` plus a fake client). The `tests/run_*.py` files are manual scripts,
not tests; `tests/run_ingestion_pipeline.py` is the graph builder described above.

## Repository layout

```text
Jacc-v2/
├── main.py                 same entry point as src/run_localize.py
├── pyproject.toml, uv.lock Python project and locked dependencies
├── .env.example            template for .env
├── src/                    program source code
│   ├── run_localize.py     localization runner (CLI)
│   ├── evaluate_localize.py, evaluate_stages.py, evaluate_ranked.py, compare_variants.py   offline evaluation
│   ├── main.py             file/folder structure scan of a repository
│   ├── modules/
│   │   ├── repo_explorer/  CKG construction: discovery, tree-sitter parsing, ingestion, LadybugDB storage, graph queries
│   │   ├── issue_model.py, seeds.py, hypotheses.py, verifier.py, ranking.py, export.py, ...   pipeline steps A1-A6
│   │   ├── agents/         ReAct baseline agent and read-only CKG tools
│   │   ├── embeddings/     embedding pipeline
│   │   └── data/           calibrators; indexed repositories are written to data/repos/ (not tracked)
│   └── utils/              LLM client, cost guard, env loading, logging, tracing
├── tests/                  unit tests (pytest) and manual run_*.py scripts
├── evaluation/
│   ├── localization/       benchmark inputs (*.jsonl) and gold locations (*_gt_entities_3levels.json)
│   └── baseline-*/, benchmark/   earlier baseline results
├── docker/                 optional services: postgres, langfuse, explorer
├── docs/                   design notes, research notes, experiment reports
└── references/             PDFs of the works cited in the thesis, with an index (references/README.md)
```
