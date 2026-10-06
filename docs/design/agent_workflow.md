# Jacc-v2 — Agent Workflow (current design)

Entrypoint `src/run_localize.py`; evaluation `src/evaluate_localize.py`.

## 1. End-to-end flow

```mermaid
flowchart TB
    IN["<b>INPUT</b><br/>Benchmark instance<br/>repo + base_commit + problem_statement"]

    SNAP["<b>Step 0a — Snapshot</b><br/>GitSnapshotProvider<br/>clone once, git archive at base_commit"]
    ING["<b>Step 0b — CKG build</b> (no LLM)<br/>run_ingestion_pipeline<br/>10 analysis + 2 persistence phases"]
    DB[("<b>Ladybug CKG</b><br/>reused unless --force")]

    TOOLS["<b>7 read-only CKG tools</b><br/>search · file_context · symbol_context<br/>contract · crosscut · impact · overview"]

    AGENT["<b>Step 1 — Localization agent</b><br/>LangGraph ReAct loop<br/>call_model ⇄ ToolNode, max_steps=20"]

    OUT["<b>OUTPUT</b><br/>JSON only<br/>found_files / found_modules / found_functions"]
    ART["<b>Artifacts</b><br/>result.json · trajectory.json · logs<br/>llm_calls, tool_calls, tokens"]
    EVAL["<b>Evaluation</b> vs gold<br/>3 levels × success / recall / precision / F1"]

    IN --> SNAP --> ING --> DB --> TOOLS --> AGENT --> OUT --> ART --> EVAL
    IN -- "render_localization_issue<br/>+ JSON-only system prompt" --> AGENT
```

## 2. Step 1 in detail — the agent loop

```mermaid
flowchart LR
    S(["start"]) --> CM["call_model<br/>LLM bound to CKG tools"]
    CM -- "tool_calls" --> TN["ToolNode<br/>run CKG tools"]
    TN -- "steps left" --> CM
    CM -- "no tool_calls" --> F["finalize"]
    TN -- "max_steps hit" --> F
    F --> E(["JSON answer<br/>status complete | failed"])
```

Each `call_model` turn re-detects a phase and injects it as a `SystemMessage`
(`_detect_phase`, active only when `AgentConfig.enable_ckg_phase_policy=True`,
which `run_localize.py` sets):

```mermaid
stateDiagram-v2
    [*] --> explore
    explore: explore — no CKG signal yet, start with ckg_search
    targeted: targeted — signal strong, use context / contract, then crosscut / impact
    recover: recover — 2+ recent tool errors, one focused retry else return JSON
    explore --> targeted: container_path or signal=strong
    targeted --> recover: tool errors pile up
    recover --> targeted: evidence recovered
    targeted --> [*]: evidence sufficient
```

## 3. Notes

- Single-agent ReAct loop; no separate search/causal agents. The differentiator
  is the offline CKG build plus the phase policy steering tool choice.
- The agent is strictly read-only: no shell, no edits, no patch generation.
- All CKG results are path-normalized to repo-relative plus a `/testbed`
  container path before reaching the model.
