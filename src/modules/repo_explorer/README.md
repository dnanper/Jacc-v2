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

9. Process Processor:

process_processor.py: tìm luồng thực thi từ call graph. Nó chọn entry point tốt, BFS theo cạnh CALLS, bỏ trace trùng/lồng nhau, rồi tạo Process và các step.

entry_point_scoring.py: chấm điểm function/method nào giống “điểm bắt đầu” hơn. Điểm dựa vào số callee/caller, exported hay không, tên như main, run, handleX, Controller, và framework path.

framework_detection.py: nhận diện framework qua path hoặc text. Ví dụ views.py được boost kiểu Django, pages/api kiểu Next.js API, controllers/\*.java kiểu Spring.

10. lbug_loader: Lưu graph vào ladybug database (modules/data/repos)

11. index_loader:

Mở LadybugDB tại get_storage_path(repo_path) / "lbug".
Gọi adapter.create_fts_indexes(): Tạo index từ 2 cột searchText (tên symbol) và Content (code snippet) cho các bảng (File/Function/...)
Lưu meta.json.
Cập nhật registry.json.
Lưu thêm graph.json cache nếu có state truyền vào.

==> Sau khi graph đã được load vào LadybugDB, phase này làm database “queryable” hơn bằng FTS index, rồi ghi metadata để các phần khác biết repo này đã được index ở đâu, commit nào, số node/edge bao nhiêu. graph.json là cache JSON để UI/MCP/API có thể đọc nhanh mà không nhất thiết phải query Kuzu ngay.
