---
name: csg-exploring
description: Use when understanding architecture, finding implementations, or answering how code works.
---

# CSG Exploring

1. Start with `csg_list_repos()` if repo selection is unclear.
2. Read `csg://repo/<name>/context` for staleness and stats.
3. Use `csg_explore(layer="topology")` for communities.
4. Use `csg_explore(layer="relevance", query="<concept>")` for search.
5. Drill into a community with
   `csg_explore(layer="context", scope="community:<name>")`.
6. Pull contracts or source with `layer="contract"` or
   `layer="implementation"` when symbol names are known.

Prefer graph search first, then raw file reads for final verification.
