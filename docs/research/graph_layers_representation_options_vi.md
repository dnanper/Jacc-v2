# Biểu diễn layer CKG: graph, fact store và projection

## Kết luận

Không nên mặc định thêm node/edge cho toàn bộ 18 layer. CKG hiện là một
**property graph nguồn-code**; nó tốt làm *semantic/navigation spine*. Với dữ
liệu có mật độ lớn, thay đổi theo lần chạy, hoặc chỉ cần trong một loại truy vấn,
hãy lưu **fact sidecar** (SQLite/Parquet/Kuzu node-table không tham gia traversal)
và materialize một *task projection* khi agent hỏi. Mô hình này vẫn là code
knowledge graph: identity và quan hệ semantic ổn định vẫn nằm trong graph; fact
store chỉ tránh graph hoá mọi occurrence, CFG block, trace span và thuộc tính
evidence.

## Schema CKG hiện tại (đã kiểm tra source)

- Node table: `File`, `Folder`, các symbol (`Function`, `Class`, `Method`,
  `Interface`, `Struct`, `Enum`, ...), `Section`, `Community`, `Process`.
  `Process` và `Community` là derived node.
  [code_schema.py](../../src/modules/repo_explorer/graph/schema/code_schema.py)
  và [lables.py](../../src/modules/repo_explorer/graph/model/lables.py).
- Tất cả quan hệ dùng một `CodeRelation` có `id`, `type`, `confidence`,
  `reason`, `step`, `inCycle`; các loại gồm `CONTAINS`, `CALLS`, `IMPORTS`,
  `INHERITS`, `OVERRIDES`, `USES`, `DEFINES`, `IMPLEMENTS`, `ACCESSES`,
  `STEP_IN_PROCESS`, ...
  [relationships.py](../../src/modules/repo_explorer/graph/model/relationships.py).
- Node chỉ lưu span định nghĩa (`filePath`, `startLine`, `endLine`) và metadata
  summary. `schema_entities` là list tên table phát hiện bằng pattern, chưa phải
  node/edge DB.
  [properties.py](../../src/modules/repo_explorer/graph/model/properties.py)
  và [schema_extraction.py](../../src/modules/repo_explorer/ingestion/support/schema_extraction.py).

Do đó `CALLS(A,B)` hiện không giữ được: call-site nào, occurrence nào, build/config
nào, hay runtime observation nào tạo nên kết luận. Nhét JSON vào `reason` có thể
chạy tạm, nhưng không query/index được theo evidence, validity hay context và
không nên là schema lâu dài.

## Khi nào phải thêm graph primitive?

| Nhu cầu | Cần node/edge mới? | Khuyến nghị |
|---|---|---|
| File/symbol/containment/call/import/inheritance source-level | Không | Giữ node/`CodeRelation` hiện có; bổ sung property typed nếu thiếu. |
| Reference, definition, read/write hoặc call-site cụ thể | Không bắt buộc | Thêm `Occurrence` fact: `snapshot_id, file_id, range, role, symbol_id, enclosing_symbol_id`; materialize `Anchor` node + `REF/CALL` edges chỉ cho truy vấn cần path graph ở call-site. |
| Revision/file content/snapshot | Thường không | Dùng versioned sidecar `Snapshot`, `FileVersion`, hash, indexer version. Chỉ graph hoá `Revision` nếu phải traverse history/impact qua commit. |
| Build target, API operation, DB table, deployment component | Có, khi là cross-layer root | Chúng là thực thể bền vững mà agent sẽ bắt đầu/kết thúc traversal: node `BuildTarget`/`ApiOperation`/`DbEntity`/`RuntimeResource`, với typed edge như `BUILDS`, `EXPOSES`, `READS`, `WRITES`, `DEPLOYS`. Nếu chỉ parse declaration để hiển thị, fact sidecar là đủ. |
| CFG, SSA/def-use, alias, taint, AST detail | Thường không | Fact/IR sidecar keyed by `symbol_id + snapshot_id`; project thành graph slice on-demand. Toàn cục sẽ làm graph quá lớn và phụ thuộc language/analyser. |
| Config/flag/effective environment | Không mặc định | Immutable `ConfigSnapshot` fact có hash, source/effective values và scope. Tạo node chỉ khi flag/config là root cho nhiều impact query. |
| Trace/span/log/metric, test run/coverage | Không cho từng event/span | Giữ nguyên OTLP/test artefact; một `TraceRun`/`TestRun` node hoặc fact summary có thể liên kết `RuntimeResource`/symbol. Suy ra `OBSERVED_CALL` là projection có filter thời gian, workload và sample rate. |
| Evidence/provenance của một assertion | Có điều kiện | Nếu evidence cần được share, audit, traverse hoặc có nhiều nguồn: reify `Assertion` + `Evidence` + `AnalysisRun`. Nếu chỉ là 1 source span, columns/fact record trên relation projection đủ. |
| Community/process/LLM summary/risk | Không mặc định | Đây là derived view/claim, không canonical code fact. Lưu predicate/view có `generator_version`, inputs, TTL và citations; materialize node chỉ khi UI/traversal cần nó. |

**Quy tắc:** node cho thực thể ổn định, độc lập-addressable và là điểm bắt đầu/kết
thúc của nhiều traversal. Edge cho quan hệ canonical, có hướng, giữa hai thực thể.
Fact/artefact cho dữ liệu high-cardinality, temporal, payload lớn, hoặc chỉ phục
vụ một query. Điều này tránh biến mỗi token AST hoặc mỗi span thành một node.

## Cơ sở từ các chuẩn chính thức

1. [SCIP proto](https://raw.githubusercontent.com/scip-code/scip/main/scip.proto)
   tách `SymbolInformation` khỏi `Document.occurrences`: occurrence là record
   range + symbol + role, không phải graph node. Chính proto nói indexer có thể ở
   phổ precision compiler-backed đến heuristic syntax-directed. Đây là mẫu tốt
   cho CKG: symbol graph hiện có + occurrence index sidecar trước; `Anchor` chỉ
   materialize khi cần truy vấn reference/call-site.
2. [Kythe schema overview](https://kythe.io/docs/schema-overview.html) là mẫu
   graph-native khi cần provenance span: `anchor --ref/call--> callee` và
   `anchor --childof--> caller`; vì vậy chỉ `CALLS(caller,callee)` là mất call
   site. Nhưng [Kythe storage model](https://kythe.io/docs/kythe-storage.html)
   lưu entry/fact compact và serving index có thể denormalize: graph semantics
   không buộc object vật lý phải là node/edge.
3. [Glean facts](https://glean.software/docs/schema/basic/) dùng predicate/fact
   thay cho property graph bắt buộc; [derived predicates](https://glean.software/docs/derived/)
   cho phép facts stored hoặc tính on-demand để đóng gói query phức tạp và tránh
   client lấy quá nhiều raw fact. Đây là tiền lệ trực tiếp cho task projection.
4. [OpenTelemetry Resource](https://opentelemetry.io/docs/specs/otel/resource/)
   và [Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/) gắn span
   với resource/context/attributes, parent-link-event/time; đây là observation
   runtime, không phải static fact. Giữ OTLP sidecar rồi map sang graph qua
   `RuntimeResource`/symbol mapping có evidence.
5. [W3C PROV-O](https://www.w3.org/TR/prov-o/) dùng `Entity`, `Activity`,
   `Agent` và các quan hệ generation/usage/derivation để provenance tăng dần.
   Có thể áp dụng tối giản: `AnalysisRun` dùng source snapshot và sinh fact/
   assertion, thay vì nhân bản evidence vào mọi edge.

## Thiết kế hybrid đề xuất cho CKG

### 1. Giữ graph canonical nhỏ

- Giữ `File`/symbol/containment/import/call/inheritance hiện có.
- Không lưu edge đảo (`CALLED_BY`, `REFERENCED_BY`) làm source of truth; derive/index
  lúc query. Kythe cũng yêu cầu reverse edge được dựng ở post-processing, không
  do indexer emit ([schema reference](https://kythe.io/docs/schema/#edge-kinds)).
- Bổ sung node/edge cross-layer chỉ khi input thực sự tồn tại và entity được dùng
  trong nhiều traversal: `ApiOperation`, `DbEntity`, `BuildTarget`,
  `RuntimeResource`; không tạo chúng từ regex không có evidence.

### 2. Fact sidecars có schema rõ

Mỗi record tối thiểu có `fact_id`, `kind`, `subject_id`, `object_id?`,
`snapshot_id`, `extractor`, `extractor_version`, `source_span?`, `modality`
(`MUST`/`MAY`/`OBSERVED`/`CLAIMED`), `confidence?`, `valid_from/to?`,
`artefact_uri/hash`. Bảng riêng: `Occurrence`, `AnalysisRun`, `Evidence`,
`ConfigSnapshot`, `BuildRun`, `TraceSummary`, `TestRun`, `CfgEdge`, `DefUse`.

Không phải tất cả field phải xuất hiện ngay. Phase đầu chỉ cần `snapshot_id`,
source span, extractor version và modality; các bảng không có input trả về
`unavailable`, không sinh relation giả.

### 3. Agent không query raw graph/fact trực tiếp

Expose capability/view thay vì dump graph:

`resolve_symbol -> occurrences -> static relations -> optional evidence facts -> source spans`

Ví dụ `trace_request(as_of, environment, route)` join static `CALLS` với
`TraceSummary` rồi trả: path có `MAY` (static) và cạnh `OBSERVED` riêng, kèm
snapshot/config/trace IDs. `impact(symbol, snapshot)` chỉ traverse canonical
edges, sau đó dùng `Occurrence`/CFG/TestRun để chứng minh từng candidate. Một
view phải giới hạn hop/result/token và báo coverage/truncation.

## Quyết định cho roadmap

1. **Không đổi graph schema lớn ngay.** Thêm `snapshot_id` + source span/extractor
   provenance vào ingestion output/fact store trước.
2. **Occurrence sidecar trước Anchor node.** Nó lấp khoảng trống lớn nhất của
   `CALLS`/reference mà không nổ graph; đo nhu cầu path query trước khi
   materialize Anchor.
3. **Derived views thay Community/Process thành fact có provenance.** Chúng vẫn
   có thể render thành node cho UI, nhưng không được lẫn với source fact.
4. **Mỗi connector runtime/build/test là optional.** Chỉ tạo graph node/edge sau
   khi có artefact thật và query use-case vượt qua source-only.

