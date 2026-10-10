"""Issue preprocessing: turn a raw problem statement into a structured IssueModel."""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

# Field descriptions ship inside the enforced JSON schema, so per-field rules live there,
# not in PROMPT. No defaults: OpenAI strict mode requires every field.


class Scenario(BaseModel):
    precondition: str = Field(description="State that must hold before the action (data, config, flags); empty if not stated.")
    action: str = Field(description="What the user or caller does to trigger the behavior, with the exact API or command used.")
    path: str = Field(description="Execution path the report describes, as short steps joined by ' -> '.")


class IssueModel(BaseModel):
    title: str = Field(description="Issue title, verbatim.")
    issue_type: Literal["bug", "feature", "performance", "refactor", "documentation", "other"]
    report_class: Literal["natural_language", "code_identifiers", "stack_trace"] = Field(
        description=(
            "Richest evidence in the report: stack_trace if it contains a traceback, "
            "else code_identifiers if it names code symbols or paths, else natural_language."
        )
    )
    summary: str = Field(description="One or two sentences stating the technical problem or request.")
    scenario: Scenario
    reproduction_steps: list[str] = Field(description="Ordered steps to reproduce, keeping every concrete value; empty if none.")
    observed: str = Field(description="Actual behavior with exact values, outputs, or wrong results; for features, the current limitation.")
    expected: str = Field(description="Desired behavior with exact values if stated.")
    error_messages: list[str] = Field(description="Every error, exception, or warning line, verbatim.")
    stack_trace: str = Field(description="Full traceback or stack trace, verbatim and complete; empty if none.")
    code_snippets: list[str] = Field(description="Every code, config, or command block from the report, verbatim.")
    environment: list[str] = Field(description="Versions, platform, backend, or configuration details, e.g. 'numpy 1.26'.")
    reporter_hypotheses: list[str] = Field(
        description="Causes, suspect locations, or fixes the reporter proposes, keeping every file, line, and symbol they name."
    )
    key_concepts: list[str] = Field(description="Domain concepts a search should match, short noun phrases.")
    explicit_code_refs: list[str] = Field(
        description="Every code identifier, file path, module, option, or error class named in the report, copied verbatim. Never invent."
    )
    assumptions: list[str] = Field(description="Your own unverified guesses about where or why the behavior happens.")
    unknowns: list[str] = Field(description="Open questions the code must answer before localizing.")


PROMPT = """Convert the GitHub issue into the schema. It replaces the raw issue for a \
code-localization agent, so keep every technical fact, identifier, value, error, trace, \
code block, and reporter hypothesis. Drop only non-technical text (emotion, thanks, \
urgency, template checklists). Verbatim fields stay as written; everything else in English.

<issue>
{issue}
</issue>"""

_BACKTICK = re.compile(r"`([^`\n]{1,120})`")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_FRAME = re.compile(r'File "[^"]*?(\w+)\.\w+", line \d+, in (\w+)')
_IDENT = re.compile(r"\b(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*\b|\b[a-z]+_[a-z_0-9]+\b|\b[A-Z][a-z0-9]+[A-Z]\w*\b")
_NOISE = frozenset({"self", "cls", "None", "True", "False"})


def raw_code_refs(text: str) -> list[str]:
    """Code names written in the raw issue, without the model: traceback frames (module, function) and dotted,
    snake_case or CamelCase identifiers inside fenced code. A small model drops many of these (exp/gpt-4o-mini)."""
    frames = [name for pair in _FRAME.findall(text) for name in pair]
    idents = [i for block in _FENCE.findall(text) for i in _IDENT.findall(block) if i not in _NOISE]
    return list(dict.fromkeys(frames + idents))


def parse_issue(problem_statement: str, llm: Runnable) -> IssueModel:
    """`llm` must be `chat.with_structured_output(IssueModel, strict=True)`."""
    model = llm.invoke(PROMPT.format(issue=problem_statement))
    # Drop invented refs, then add any inline-code span the LLM missed.
    refs = [ref for ref in model.explicit_code_refs if ref and ref in problem_statement]
    refs += [span.strip() for span in _BACKTICK.findall(problem_statement)]
    refs += raw_code_refs(problem_statement)
    # Refs of 1-2 chars (x, y, f) substring-match anything and carry no search signal.
    model.explicit_code_refs = list(dict.fromkeys(ref for ref in refs if len(ref) > 2))
    return model


def render_issue_model(model: IssueModel) -> str:
    return (
        "<issue_model>\n"
        + json.dumps(model.model_dump(), indent=2)
        + "\n</issue_model>\n"
        "This structured model replaces the raw issue report. Treat assumptions "
        "and unknowns as hypotheses to check with CKG tools, not facts."
    )


if __name__ == "__main__":
    class _Fake:
        def invoke(self, _prompt: str) -> IssueModel:
            return IssueModel(
                title="parse loses markers",
                issue_type="bug",
                report_class="code_identifiers",
                summary="parse() drops markers",
                scenario=Scenario(precondition="", action="call parse()", path="parse -> tokenize"),
                reproduction_steps=[],
                observed="markers lost",
                expected="markers kept",
                error_messages=[],
                stack_trace="",
                code_snippets=[],
                environment=[],
                reporter_hypotheses=[],
                key_concepts=["marker"],
                explicit_code_refs=["parse()", "made_up_fn"],
                assumptions=[],
                unknowns=[],
            )

    parsed = parse_issue("calling parse() loses `Marker.tag` markers", _Fake())
    assert parsed.explicit_code_refs == ["parse()", "Marker.tag"], parsed.explicit_code_refs
    assert '"issue_type": "bug"' in render_issue_model(parsed)
    print("ok")
