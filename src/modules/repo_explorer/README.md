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
   Repository -[OVERRIDES]-> BaseRepository.ping

8. Gọi process_communities(...).
   Tạo node Community.
   Tạo edge MEMBER_OF.
   Tạo edge COMMUNITY_INTERACTS.
   Gọi compute_fan_in(...) để ghi fan_in, fan_out lên node.
   Gọi extract_schema_entities(...) để ghi schema_entities lên node.

- Dùng Leiden algorithm để gom các symbol thành cụm chức năng.

Nó chỉ đưa vào thuật toán các node symbol loại: Function, Class, Method, Interface
và các relationship: CALLS, EXTENDS, IMPLEMENTS
Không dùng IMPORTS để clustering trực tiếp. IMPORTS chỉ được dùng sau đó khi tạo COMMUNITY_INTERACTS.

- fan_in = số source distinct trỏ vào node này
  fan_out = số target distinct mà node này trỏ tới
  ==> Tính dựa trên cạnh: CALLS và IMPORTS

- schema_extraction: scan node.properties.content của các node có source snippet, tìm dấu hiệu liên quan DB/schema, ví dụ:CREATE TABLE user
  ==> Nếu tìm thấy, thêm vào Node đó: node.properties.schema_entitie = ["user"]
