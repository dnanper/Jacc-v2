1. repo structure explore -> File/Folder node
2. Build AST (markdown, docs, ...) for each files:
   - In each file: Extract in-file infomation from AST node (datatype, alias, public/private, docstring)

   - Create: Symbol Node (Defn) and CONTAIN, HAS_METHOD, HAS_PROPERTY, DESCRIBES edges

3. Import resolver: Multi-files information
   - infile_processor:
     source code -> ExtractedImport(raw_import_path, named_bindings)

   - import_processor:
     ExtractedImport -> resolved file path -> IMPORTS edge + import_map + named_import_map
     ==> Create: IMPORT Edges Between File Nodes
     ==> Create: Information (Resoltion_context): import_map, ... for later processor

4. Call processor: resolve recode from infile_processor to create CALL EDGE
