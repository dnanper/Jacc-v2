# Roadmap — khoảng cách giữa mã hiện tại và schema mục tiêu

Schema mục tiêu: [graph-schema.md](graph-schema.md). Thiết kế non-graph workflow và task **W0–W3**: [agent-workflow.md](agent-workflow.md). **P0–P2 dưới đây thuộc tầng đồ thị**, không bao gồm việc triển khai bộ nhớ bằng chứng, lịch truy vấn và kiểm tra vị trí sửa. Các task đều là đề xuất, không đánh dấu là đã hoàn thành.

## Trạng thái hiện tại

Tầng đồ thị là bản port Python của GitNexus/CKG (`src/modules/repo_explorer/graph/schema/code_schema.py:4`), kế thừa cả phần tốt lẫn phần chết. Toàn bộ bề mặt sinh đồ thị gói trong 9 vị trí emit.

| | Khai báo | Có bảng DB | Thực sự phát ra |
|---|---|---|---|
| Node label | 34 | 28 | **17** |
| Edge type | 18 | — | **12** |

Ba mức này khác nhau: *khai báo* là tên có trong enum; *có bảng DB* là có `CREATE NODE TABLE`; *phát ra* là có dòng code thật sự gọi `add_node` / `add_relationship`. Một nhãn khai báo mà không phát ra thì bảng luôn rỗng.

Label phát ra: `File`, `Folder`, `Class`, `Interface`, `Function`, `Method`, `Constructor`, `Struct`, `Enum`, `Trait`, `Impl`, `Module`, `Property`, `TypeAlias`, `Section`, `Community`, `Process`.

Edge phát ra: `CONTAINS`, `HAS_METHOD`, `HAS_PROPERTY`, `DESCRIBES`, `IMPORTS`, `CALLS`, `EXTENDS`, `IMPLEMENTS`, `OVERRIDES`, `MEMBER_OF`, `COMMUNITY_INTERACTS`, `STEP_IN_PROCESS`.

Chỉ có 5 loại truy vấn tree-sitter cho mọi ngôn ngữ: `definitions`, `imports`, `calls`, `heritage`, `assignments` (`src/modules/repo_explorer/parsing/tree_sitter_queries.py:1160-1167`).

Ghi chú tên gọi: `EXTENDS` trong mã chính là `INHERITS` trong schema mục tiêu. Nhãn `INHERITS` có khai báo nhưng không phát ra.

---

## P0 — rẻ, và đang chặn đường

### P0.1 Nối `READS` / `WRITES` — phần lớn công việc đã xong

Truy xuất đã chạy thật: `_extract_assignments` (`ingestion/infile_processor.py:658-686`) bắt `@assignment.receiver` + `@assignment.property` cho 10 ngôn ngữ, dồn vào `ParseResult.assignments` (`:246`).

Nhưng `ingestion/pipeline.py:131-146` chỉ trả `imports`, `calls`, `heritage`, `type_envs` — **không trả `assignments`**, và không processor nào đọc trường đó. Toàn bộ kết quả trích xuất đang bị vứt.

Việc cần làm:
- Thêm `"assignments": parse_result.assignments` vào dict trả về của `parse_infile`.
- Viết processor phân giải receiver thành node `Field`, phát cạnh `WRITES`.
- Thêm truy vấn tree-sitter cho phía đọc — truy vấn hiện tại chỉ bắt vế trái phép gán.

Đây là cạnh dataflow duy nhất trong schema mục tiêu, và là hạng mục có tỷ lệ giá trị trên công sức cao nhất.

### P0.2 Ghi nhận coverage parse

Hiện **không tồn tại**: tìm `coverage|parse_success|parse_fail|partial|skipped_files|parse_error` trong `ingestion/` và `parsing/` không ra kết quả nào.

Khi hỏng thì im lặng:
- File không parse được → `logger.debug` rồi biến mất khỏi `parsed_files` (`ingestion/infile_processor.py:106,111-112`).
- Mỗi truy vấn hỏng (`definitions:369`, `imports:513`, `calls:578`, `heritage:631`, `assignments:670`) → `logger.debug` rồi `return`, trích xuất một phần không ghi lại.
- Thống kê `files` là **số file phát hiện**, không phải số file parse thành công (`ingestion/pipeline.py:387-393`).
- `resolved_count` tính ở `call_processor.py:190` và `import_processor.py:51` là biến cục bộ chết.

Việc cần làm: bảng `index_coverage(file_path, status, detail)` với `status ∈ {ok, parse_partial, unsupported_language, skipped, oversized}`, ghi tại các điểm `logger.debug` nói trên; trả `resolved_count` ra thống kê.

Coverage parse là điều kiện cần nhưng chưa đủ để phủ định một quan hệ từ kết quả rỗng. Cần thêm coverage phân giải theo predicate/phạm vi, snapshot đúng và query không bị cắt; phần chưa bảo đảm phải trả `unknown`. Phản chứng trực tiếp từ source vẫn có thể bác một tiền đề cụ thể mà không cần graph phủ toàn repo.

### P0.3 Sửa lỗi ghi sai commit

`meta.json` của bản index sympy ghi `"last_commit": "145917baa51c83506b8247576864a03ed0ea4c8f"` — đó là HEAD của chính repo Jacc-v2, không phải `base_commit` của sympy.

Nguyên nhân: `src/modules/repository.py:46-62` dựng snapshot bằng `git archive`, nên thư mục snapshot không có `.git`. `get_current_commit(path)` (`repo_explorer/repository/git.py:35-38`) chạy `git rev-parse HEAD` với `cwd` là snapshot; git leo ngược cây thư mục và bắt trúng repo Jacc-v2, vì snapshot nằm dưới `.agent_runs/localization/source-cache/snapshots/`.

Sửa: truyền `base_commit` từ `BenchmarkInstance` vào thẳng, hoặc kiểm tra `.git` tồn tại trước khi gọi git.

### P0.4 Thêm `RAISES` / `CATCHES`

Cần truy vấn tree-sitter mới: `raise_statement` và `except_clause` cho Python; `throw_statement`, `catch_clause`, và `throws` clause cho Java. Java tách `THROWS` (khai trong signature) khỏi `RAISES` (phát sinh trong thân hàm).

Issue SWE-bench rất thường kèm traceback, nên đây là điểm neo mạnh nhất mà hệ hiện chưa có.

---

## P1 — cần cho tính đúng đắn của lập luận

### P1.1 Thêm cột `modality`

Hiện chuỗi `reason` ghi chiến lược phân giải và nhập nhằng: hậu tố `-ambiguous` đi cùng việc chọn ứng viên đầu tiên (`ingestion/call_processor.py:147-151`). Đây không phải ngữ nghĩa MUST/MAY đã được bảo đảm. Thêm trạng thái phân giải có cấu trúc; chỉ gán MUST khi có bảo đảm cho mệnh đề và giả định tương ứng, không suy MUST từ `same-file` hay confidence cao.

CKG bản gốc có cột `reviewLabel` đánh dấu `AMBIGUOUS`; bản port đã bỏ. Cần khôi phục hoặc thay bằng `modality` tường minh.

### P1.2 Thêm `extractor_version` và `evidence`

Cạnh hiện có `confidence`, `reason`, `step`, `in_cycle` (`graph/model/types.py:25-28`). Thiếu `extractor_version` nên không tái lập được kết quả giữa các lần chạy; thiếu `evidence{path, line_span}` nên biết cạnh `CALLS` tồn tại mà không biết nó phát sinh từ dòng nào. Thiếu `derived_from` nên `OVERRIDES` không truy ngược về `EXTENDS` sinh ra nó.

Ghi chú: cột `step` **không bao giờ được gán** — chỉ số bước nhét vào `reason=f"step-{n}"` (`ingestion/process_processor.py:250`), cột trong DB luôn rỗng.

### P1.3 Giữ lời gọi nhập nhằng và các đích khả dĩ

`ingestion/call_processor.py:145`: khi `call_form == "member"` và còn nhiều ứng viên sau lọc, hàm `return None` — không sinh cạnh, không đếm, không log. Lỗ thủng recall không đo được.

Sửa: giữ record call-site chưa phân giải và tập đích `CALLS(MAY)` có căn cứ, kèm nguồn và giới hạn. Nếu không có đích hợp lệ, giữ unresolved thay vì bịa cạnh. `REFERENCES` dành cho tham chiếu symbol, không dùng để đổi ngữ nghĩa của một lời gọi chỉ vì đích nhập nhằng.

### P1.4 Dọn phần khai báo mà không phát ra

Hoặc cài đặt, hoặc xóa.

Phải cài: `CodeElement` — nhãn dự phòng, có bảng DB nhưng không bao giờ phát ra. Thiếu nó thì định nghĩa mà parser không ánh xạ được sẽ biến mất im lặng.

Phải xóa: `ACCESSES`, `USES`, `DEFINES` trong allow-list `explore/_helpers.py:19,28,35`. `EDIT_RISK_RELATION_TYPES` gồm `ACCESSES` nhưng cạnh này có 0 vị trí phát sinh, nên `impact()` tưởng duyệt 5 loại cạnh, thực tế chỉ 4.

Không có bảng DB dù khai báo: `Project`, `Package`, `Variable`, `Decorator`, `Import`, `Type` (`graph/model/lables.py:7-21`). Chúng có mặt trong `storage/csv_generator.py:110-141` nên nếu lỡ phát ra sẽ hỏng bước nạp.

### P1.5 Sửa `COMMUNITY_INTERACTS.confidence`

Hiện là số đếm cạnh, không phải xác suất 0–1 (`ingestion/community_processor.py:344`). Mọi bộ lọc `confidence >= x` hiểu sai loại cạnh này. Chuẩn hóa về 0–1, đưa số đếm sang cột riêng.

### P1.6 Sửa `_owner_matches`

`ingestion/call_processor.py:154-156` so khớp bằng substring: `type_name.lower() in owner_id.lower()`. Kiểu `User` khớp owner `SuperUserManager`, sinh cạnh `CALLS` sai ở bậc confidence cao.

### P1.7 Sửa phân giải `self` / `super`

`extraction/type_env.py:131-169` phân giải `self` / `this` / `super` bằng cách đi ngược AST, nhưng `call_processor.py:181` gọi `type_env.lookup(call.receiver_name)` mà không truyền `call_node`. Nhánh này luôn trả `None` khi chạy thật.

### P1.8 Sửa tạo stub node cha

`ingestion/heritage_processor.py:156` tạo node stub cho lớp cha chưa phân giải **trước** lệnh kiểm tra `graph.get_node(parent_id) is not None` ở dòng 163, nên lệnh kiểm tra luôn qua. Các stub có `file_path=""` và lọt vào CSV của `Class` / `Interface` / `Trait`.

---

## P2 — mở rộng schema

### P2.1 Tầng DERIVED

`CO_CHANGED_WITH` khả thi: `src/modules/repository.py:42` có `git clone` đầy đủ lịch sử được cache, chỉ snapshot mới thiếu `.git`. **Bắt buộc dùng `git log <base_commit>` chứ không phải `git log HEAD`** — clone nằm ở HEAD nhánh mặc định, tức là sau `base_commit`; khai thác không cắt ngưỡng sẽ rò rỉ chính commit sửa lỗi.

`TESTS`: `is_test_file` đã có (`ingestion/support/entry_point_scoring.py:228-248`) nhưng chỉ dùng để **loại** file test khỏi entry point. Cần duyệt `CALLS` từ các node test để sinh cạnh.

`SIMILAR_TO`: MinHash + LSH, chưa có gì.

### P2.2 Bật embeddings

Bảng `CodeEmbedding` được tạo (`graph/schema/code_schema.py:276-281`) nhưng pipeline không bao giờ ghi vào — `ingestion/index_loader.py:120` luôn cho `embeddings: 0`. Cần cho neo hạt giống ngữ nghĩa.

### P2.3 Tách vùng `Community` / `Process`

Hiện là node canonical trong cùng đồ thị với FACT. Cần đánh dấu là DERIVED để bước bác bỏ giả thuyết không dùng nhầm.

### P2.4 Bổ sung truy vấn Java

`JAVA_DEFINITIONS` hiện chỉ bắt `class_declaration`, `interface_declaration`, `method_declaration`, `constructor_declaration`. Thiếu `enum_declaration`, `record_declaration`, `annotation_type_declaration`, `field_declaration`.

Ghi chú thêm: capture `implements` thật chỉ có ở 3 ngôn ngữ (TypeScript, Java, PHP). Nơi khác `IMPLEMENTS` dựa vào heuristic tên `I[A-Z]` hoặc luật Swift luôn implements (`ingestion/heritage_processor.py:54-58`).

### P2.5 Thêm `HAS_TYPE` / `RETURNS` dạng cạnh

Kiểu đã suy ra được và lưu thành thuộc tính node (`return_type`, `signature`). Chưa có ở dạng cạnh.

---

## Mã chết nên gỡ

- `graph/model/ids.py:generate_id` trùng lặp với `parsing/ast_helpers.py:14`; bản thực dùng là bản sau.
- `ingestion/extraction/extract_cache.py` — 188 dòng, không nơi nào import.
- `ingestion/extraction/import_rules.py` — 176 dòng, không nơi nào import; gần trùng `extraction/language_config.py` là bản đang dùng.
- `ingestion/heritage_processor.py:213-248` — nhánh `trait-impl` / `include` / `extend` / `prepend` không thể chạm tới, vì `_extract_heritage` (`infile_processor.py:622-655`) chỉ đặt `kind` là `extends` hoặc `implements`.
- `explore/search.py:16,86` (RRF hybrid search) và toàn bộ `_compress_*` + `_ResponseAccumulator` (`explore/_helpers.py:93-303`) — agent không bao giờ đi qua.
- `support/framework_detection.py:210-229` `detect_framework_from_ast` — không được gọi.
- Thuộc tính khai mà không bao giờ gán: `ast_framework_multiplier`, `ast_framework_reason`, `entry_point_score`, `entry_point_reason`, `level`, `enriched_by`, `keywords` (`graph/model/properties.py:19-44`). `fan_out` được tính nhưng không có cột DB nên mất khi lưu.
