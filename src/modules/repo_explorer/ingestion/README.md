# ingestion layout

Top-level files in this package are phase entrypoints used by the ingestion
pipeline, for example `structure_processor.py`, `infile_processor.py`,
`import_processor.py`, `call_processor.py`, `community_processor.py`,
`process_processor.py`, `lbug_loader.py`, and `index_loader.py`.

Internal helpers that do not represent standalone pipeline phases live in
`support/`:

- `import_resolution.py`: resolves raw import paths to target files.
- `resolution_context.py`: stores import maps and name-resolution state.
- `symbol_table.py`: indexes discovered symbols for later processors.
- `entry_point_scoring.py` and `framework_detection.py`: support process detection.
- `fan_in_processor.py` and `schema_extraction.py`: enrich community results.
- `utils.py` and `state.py`: shared ingestion support.

The `extraction/` package remains separate because it contains AST extraction
helpers, import resolvers, and type-env extraction logic used by
`infile_processor.py` and `import_processor.py`.
