---
name: csg-debugging
description: Use when tracing a bug through callers, callees, processes, or architecture boundaries.
---

# CSG Debugging

1. Search the failure concept with `csg_explore(layer="relevance")`.
2. Inspect likely symbols with `csg_context`.
3. Read process traces from `csg://repo/<name>/processes` and
   `csg://repo/<name>/process/<process>`.
4. Use `csg_impact` to find upstream callers that can trigger the bug.
5. Confirm with source reads and tests.
