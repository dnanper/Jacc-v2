---
name: csg-impact-analysis
description: Use before modifying a symbol, API, dependency edge, or shared module.
---

# CSG Impact Analysis

1. Identify the target symbol with `csg_context` or `csg_explore`.
2. Run `csg_impact(target="<symbol>", direction="upstream")`.
3. Treat direct dependents as must-check callers.
4. Warn before editing if risk is HIGH or CRITICAL.
5. After edits, run `csg_detect_changes(scope="all")`.

Do not claim a low-risk change if the index is stale or the target
symbol could not be resolved cleanly.
