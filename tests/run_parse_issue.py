"""Parse at most two benchmark issues into IssueModel with the real LLM (paid).

Needs the human LLM approval env var (see CLAUDE.md). Usage:
    uv run python tests/run_parse_issue.py <instance_id> [<instance_id>]

Writes each IssueModel to .tmp/issue_model/<id>.json and prints token usage.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.benchmarks import BENCHMARKS, load_instances  # noqa: E402
from src.modules.issue_model import IssueModel, parse_issue  # noqa: E402
from src.run_localize import DEFAULT_DATA_DIR, clean_issue_text  # noqa: E402
from src.utils.env import load_env_file  # noqa: E402
from src.utils.llm import build_llm  # noqa: E402

MAX_CALLS = 2


class _Recorder:
    """Structured-output runnable that keeps the raw message for usage stats."""

    def __init__(self, llm) -> None:
        self.llm, self.usage = llm, None

    def invoke(self, prompt: str) -> IssueModel:
        out = self.llm.invoke(prompt)
        if out["parsing_error"]:
            raise out["parsing_error"]
        self.usage = out["raw"].usage_metadata
        return out["parsed"]


def main(ids: list[str]) -> int:
    if not 1 <= len(ids) <= MAX_CALLS:
        raise SystemExit(f"pass 1..{MAX_CALLS} instance ids")
    load_env_file(ROOT / ".env")
    issues = {i.instance_id: i for spec in BENCHMARKS.values() for i in load_instances(spec, DEFAULT_DATA_DIR)}
    chat = build_llm(os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    out_dir = ROOT / ".tmp" / "issue_model"
    out_dir.mkdir(parents=True, exist_ok=True)
    for task_id in ids:
        raw = clean_issue_text(issues[task_id].problem_statement)
        recorder = _Recorder(chat.with_structured_output(IssueModel, method="json_schema", strict=True, include_raw=True))
        model = parse_issue(raw, recorder)
        (out_dir / f"{task_id}.json").write_text(model.model_dump_json(indent=2), encoding="utf-8")
        print(f"== {task_id}  raw_chars={len(raw)}  usage={json.dumps(recorder.usage)}")
        print(model.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
