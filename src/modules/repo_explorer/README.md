1. Discover Repo
2. repo structure explore -> File/Folder node
3. Build AST (markdown, docs, ...) for each files:
   - In each file: Extract in-file infomation from AST node (datatype, alias, public/private, docstring)

   - Create: Symbol Node (Defn) and CONTAIN, HAS_METHOD, HAS_PROPERTY, DESCRIBES edges

4. Import resolver: Multi-files information
   - infile_processor:
     source code -> ExtractedImport(raw_import_path, named_bindings)

   - import_processor:
     ExtractedImport -> resolved file path -> IMPORTS edge + import_map + named_import_map
     ==> Create: IMPORT Edges Between File Nodes
     ==> Create: Information (Resoltion_context): import_map, ... for later processor

5. Call processor: Dùng thông tin từ resolution context và infile_processor to create CALL EDGE

5.5. Cross_file_propagation: enrich thông tin xuyên file, seed thêm receiver type / return type, detect import cycle, rồi re-run call resolution có chọn lọc.

6. Heritage Processor: Tạo cạnh EXTEND/IMPLEMENT

7. MRO Processor: Khi 1 method từ 1 Class kế thừa Override -> Tạo cạnh OVERRIDE
