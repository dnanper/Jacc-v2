Run all

```bash
uv run python src\run_swe.py `
  --task-file evaluation\benchmark\swe_bench_verified.md `
  --workers 1 `
  --model gpt-5-nano `
  --max-steps 80 `
  --predictions-path .agent_runs\swebench\preds.jsonl
```

Run one

```bash
uv run python src\run_swe.py sympy__sympy-18189 --use-ckg --ckg-force
```

eval

```bash
wsl
```

```bash
cd /mnt/f/UNI/2_OUTSIDE/ckg

uv run --no-project --with swebench python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-Bench_Verified \
  --predictions_path .agent_runs/swebench/preds.jsonl \
  --max_workers 1 \
  --run_id local-agent-pytest-10356
```
