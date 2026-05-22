---
name: csg-refactoring
description: Use for rename, extract, split, move, or cross-file refactors.
---

# CSG Refactoring

- Rename: run `csg_rename(..., dry_run=true)` first, review
  definitions/usages/candidates, then apply only when unambiguous.
- Extract or split: run `csg_context` and upstream `csg_impact`
  before moving code.
- After refactor: run `csg_detect_changes(scope="all")` and verify
  direct callers from the impact report.

Avoid blind text replacement for symbols represented in the graph.
