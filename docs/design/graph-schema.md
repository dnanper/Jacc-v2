# Schema đồ thị mục tiêu

Schema Jacc-v2 đang hướng tới. Trạng thái hiện tại và việc cần làm: xem `roadmap.md`.

Phạm vi: SWE-bench Lite (300 Python), Loc-Bench V1 (559 Python), Multi-SWE-bench Java (128 Java). Đánh giá ba mức: file / class / function. **Java nằm trong phạm vi** — schema không được thiết kế chỉ cho Python.

## Nguyên tắc

1. **Đơn vị nguyên tử là Function/Method.** Không lưu node ở mức câu lệnh. Repo 1M dòng sinh khoảng 10⁷ node statement và đổi gần như mỗi commit. Chi tiết AST/CFG/def-use tính khi cần cho một commit cụ thể, không lưu lâu dài.
2. **Nguồn và giới hạn phân tích nằm trên từng cạnh.** `same-file` hay `global` là chiến lược phân giải, không phải bảo đảm đúng. Ghi `extraction_method`; chỉ gọi `confidence` là xác suất khi đã hiệu chuẩn.
3. **Ba vùng tách bạch: FACT / DERIVED / CLAIM.** LLM không bao giờ tạo cạnh FACT.
4. **Không lưu cạnh ngược** (`CALLED_BY`, `REFERENCED_BY`). Suy tại thời điểm truy vấn.
5. **Vắng cạnh không có nghĩa là không có quan hệ.** Parse đầy đủ chưa đủ. Chỉ kết luận không tồn tại trong phạm vi xét khi bộ phân tích bảo đảm đủ quan hệ đó, snapshot khớp, query đầy đủ và không còn phần động chưa giải. Nếu không, kết quả là `unknown`.

Phân biệt quan hệ trong graph với vị trí cần sửa: xem [agent-workflow.md](agent-workflow.md), đặc biệt các mục 4–6.

## 1. FACT — Node

| Node | Thuộc tính | Ghi chú |
|---|---|---|
| `Repository` | `name`, `root_path`, `snapshot_id` | `snapshot_id` là `base_commit` của instance, gắn vào mọi cạnh |
| `Folder` | `path` | |
| `File` | `path`, `language`, `lines`, `fan_in`, `change_count`, `last_modified` | Hai trường cuối lấy từ git, dùng làm tín hiệu hotspot |
| `Module` / `Package` | `qualified_name` | |
| `Class` | `qn`, `name`, `span`, `docstring`, `decorators[]`, `base_classes[]`, `is_exported` | Là một mức đánh giá độc lập — span phải chính xác ngang `Function` |
| `Interface` / `Protocol` | như `Class` | Python: ABC, `typing.Protocol`. Java: `interface` |
| `Function` | `qn`, `span`, `signature`, `param_names[]`, `param_types[]`, `return_type`, `docstring`, `decorators[]`, `complexity`, `lines`, `fan_in`, `is_test`, `is_entry_point` | Chỉ Function/Method mang bộ metric đầy đủ |
| `Method` | như `Function` + `parent_class` | |
| `Field` / `Attribute` | `qn`, `declared_type?`, `span` | Đích của `READS` / `WRITES` |
| `GlobalVariable` | `qn`, `span` | Trạng thái dùng chung |
| `Symbol` | tối thiểu như `Function` | **Nhãn dự phòng bắt buộc.** Dùng khi parser gặp định nghĩa chưa ánh xạ được. Không có nó thì symbol biến mất im lặng. Đếm số lần rơi vào đây trong bảng coverage |

Node ghép nối, bật theo loại repo: `Route` (`__route__<METHOD>__<path>`), `Decorator`, `EnvVar` (`__env__<KEY>`).

Node đặc thù ngôn ngữ, chỉ tạo khi repo dùng ngôn ngữ tương ứng: `Struct`, `Trait`, `Enum`, `Record`, `Annotation`, `TypeAlias`, `Namespace`, `Impl`, `Constructor`, `Property`. Trong view chung đa ngôn ngữ, nhóm này quy về `Class` / `Interface` / `Method` / `Field` nhưng giữ liên kết ngược về nhãn gốc.

## 2. FACT — Edge

| Edge | Hướng | Thuộc tính riêng |
|---|---|---|
| `CONTAINS` | Folder→File; File→Class/Function/GlobalVariable; Class→Method/Field | |
| `IMPORTS` | File→File/Module | `local_name`, `alias`, `in_cycle` |
| `CALLS` | Function→Function | `dispatch` (direct / virtual / duck / heuristic), `call_line` |
| `REFERENCES` | Function→symbol bất kỳ | Tham chiếu symbol, kể cả dùng callable như một giá trị; không đồng nhất tham chiếu với lời gọi |
| `INHERITS` | Class→Class | `mro_order` |
| `IMPLEMENTS` | Class→Interface/Protocol | |
| `OVERRIDES` | Method→Method (bản ở lớp cha) | `derived_from` — id cạnh `INHERITS` sinh ra nó |
| `DECORATES` | Function/Class→Decorator | |
| `READS` | Function→Field/GlobalVariable | |
| `WRITES` | Function→Field/GlobalVariable | |
| `RAISES` | Function→Class (exception) | Phát sinh trong thân hàm |
| `THROWS` | Function→Class (exception) | Khai trong `throws` clause. Java tách khỏi `RAISES`; Python không dùng |
| `CATCHES` | Function→Class (exception) | |
| `HAS_TYPE` | Field/Parameter→Class | |
| `RETURNS` | Function→Class | |
| `HANDLES` | Function→Route | |
| `CONFIGURES` | Function→EnvVar | |

### Ý nghĩa của các cạnh hay bị bỏ qua

**`READS` / `WRITES`** nối hàm với dữ liệu hàm đó truy cập, giúp tìm nơi tạo hoặc sử dụng giá trị sai. Đây là quan hệ truy cập trạng thái, chưa phải def-use/dataflow đầy đủ và không chứng minh nguyên nhân. Hàm chỉ đọc vẫn có thể đọc nhầm field hoặc hiển thị sai; không loại nó chỉ vì không ghi dữ liệu.

**`RAISES` / `CATCHES`** neo traceback trong issue vào tập hàm. Issue SWE-bench rất thường kèm traceback, nên đây là điểm neo mạnh nhất cho bước tìm kiếm ban đầu.

**`REFERENCES`** biểu diễn việc tham chiếu, độc lập với độ chắc của phân giải. Với cú pháp thực sự là lời gọi nhưng chưa biết đích, giữ call-site chưa giải và các đích `CALLS(MAY)` có căn cứ; không đổi ngữ nghĩa thành reference hoặc chọn đại một đích.

## 3. Hợp đồng metadata trên cạnh FACT

```yaml
edge:
  type: CALLS
  source, target: symbol_id      # repo + snapshot + language + canonical key
  modality: MUST | MAY           # MUST = chắc chắn, MAY = có thể
  extraction_method: parser | type_resolver | static_analysis | heuristic
  extractor_version: <bắt buộc>
  confidence: 0..1
  evidence: {path, line_span}
  snapshot_id: <base_commit>
  derived_from: [edge_id]        # cho cạnh suy ra từ cạnh khác
```

Không tự động ánh xạ `same-file`, `import-scoped`, `member-resolved` thành `MUST`. `MUST` chỉ dùng khi có bảo đảm cho mệnh đề cụ thể dưới các giả định phân tích đã ghi; còn lại dùng `MAY` hoặc giữ quan hệ chưa phân giải. MUST về đích tại một call site không có nghĩa call site chắc chắn được thực thi. Không có cạnh MUST không loại trừ cạnh MAY.

Hai bảng phụ nằm ngoài đồ thị:

- **`index_coverage`** theo từng file: `ok`, `parse_partial` (kèm dải dòng lỗi), `unsupported_language`, `skipped`, `oversized`. Trả lời được câu hỏi "vắng cạnh vì thật sự không có, hay vì chưa parse tới".
- **`capabilities`** theo từng snapshot: `dynamic_dispatch`, `reflection`, `type_inference`, mức hỗ trợ từng ngôn ngữ.

## 4. DERIVED

Dùng để sinh giả thuyết và xếp hạng. **Không dùng làm tiền đề để bác bỏ giả thuyết.** Bắt buộc ghi nguồn.

| Đối tượng | Kiểu | Nguồn |
|---|---|---|
| `TESTS` | Edge: test Function→Function sản phẩm | Duyệt `CALLS` từ node `is_test`, hoặc dữ liệu coverage |
| `CO_CHANGED_WITH` | Edge: File↔File | `git log`, cửa sổ 6 tháng, bỏ commit chạm quá 20 file |
| `SIMILAR_TO` | Edge: Function↔Function | MinHash + LSH |
| `Community` | View | Leiden trên `CALLS` + `IMPORTS` |
| `Process` | View | BFS trên `CALLS` |

Tìm kiếm ngữ nghĩa bằng vector giữ làm chỉ mục riêng, **không biến độ tương đồng cosine thành cạnh** trong đồ thị.

## 5. EVOLUTION

`Commit`, `Issue`, `PullRequest` với `MODIFIES`, `FIXES`, `MENTIONS`.

Chỉ nạp artifact có trước thời điểm tạo issue đang xét. Bản clone được cache nằm ở HEAD của nhánh mặc định, tức là **sau** `base_commit` — khai thác lịch sử không cắt ngưỡng sẽ rò rỉ chính commit sửa lỗi.

## 6. ON-DEMAND

`Statement`, `Expression`, AST, CFG, SSA, def-use, alias, taint. Tính khi cần cho một commit và một tập symbol cụ thể, không lưu lâu dài. Cầu nối về đồ thị bền là `(repo, commit, path, byte_start, byte_end)`.

## 7. CLAIM

`Concept`, `Explanation`, `Hypothesis`, `ProposedRelation` do LLM sinh. Phải ghi model, prompt, tập bằng chứng, tập phản chứng, TTL. Muốn thành cạnh FACT phải qua một bộ kiểm chứng.

## 8. Ranh giới suy luận

| Bước | Được dùng gì |
|---|---|
| Neo hạt giống | Tìm kiếm toàn văn, khớp mờ, chỉ mục vector, `RAISES` từ traceback, `Route` |
| Mở rộng bằng chứng | Chỉ vùng FACT |
| Lọc theo khoảng cách | Chỉ cạnh FACT, cả `MUST` lẫn `MAY` |
| Bác bỏ giả thuyết | Kiểm tra một tiền đề cụ thể bằng bằng chứng mâu thuẫn. Nếu dùng sự vắng mặt, phải có bảo đảm đầy đủ theo predicate/phạm vi/snapshot, truy vấn không bị cắt và giả thuyết thật sự đòi hỏi quan hệ đó. Không có danh sách loại cạnh mặc nhiên closed-world |
| Sinh giả thuyết, xếp hạng | FACT + DERIVED + EVOLUTION + thuộc tính node |

Thiếu bằng chứng do capability, coverage hoặc truncation phải giữ là `unknown`, không tự động hạ hạng hay bác bỏ giả thuyết. Bằng chứng phù hợp chỉ ủng hộ giả thuyết, không chứng minh nguyên nhân duy nhất.
