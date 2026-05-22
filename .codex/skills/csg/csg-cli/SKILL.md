---
name: csg-cli
description: Use when indexing repositories, checking CSG status, starting MCP, or watching for changes.
---

# CSG CLI

Use these commands from the repository root:

- `csg analyze`: build or refresh the graph index.
- `csg analyze --force`: rebuild from scratch.
- `csg analyze --embeddings`: include semantic embeddings.
- `csg status`: show current repo index freshness and stats.
- `csg list`: list indexed repositories.
- `csg mcp`: start the stdio MCP server.
- `csg watch`: watch indexed repos and re-ingest changed files.

After indexing, read `csg://repo/ckg/context` and use
`csg_explore(layer="topology")` to verify the graph is usable.
