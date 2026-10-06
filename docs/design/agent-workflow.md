# Non-graph agent workflow — thiết kế cho bug localization

**Trạng thái: thiết kế đề xuất, chưa triển khai hoặc chứng minh bằng thực nghiệm.** Tài liệu này thay thế bản mô tả khoảng cách agent trước đây. Không thay đổi mã chạy, không thêm chạy test của repo đích hoặc sinh patch.

Liên quan: [schema đồ thị](graph-schema.md), [roadmap đồ thị](roadmap.md). “Non-graph” nghĩa là nâng cấp bộ điều khiển agent ngoài bước xây graph, không phải bỏ graph khỏi giải pháp.

## 1. Bài toán và ranh giới trách nhiệm

Đầu vào là issue và snapshot mã nguồn tại `base_commit`; đầu ra là tập file/class/function có khả năng cần thay đổi. Một issue có thể cần sửa nhiều vị trí. Vị trí phát sinh triệu chứng, nơi truyền dữ liệu lỗi và nơi cần sửa có thể khác nhau.

**Mục tiêu không phải tìm càng nhiều code liên quan càng tốt, mà là tìm tập vị trí sửa có căn cứ trong ngân sách hữu hạn.** Chỉ đọc code không bảo đảm chứng minh được nguyên nhân hay một bản sửa duy nhất. Gold patch là một cách sửa được benchmark ghi nhận, không nhất thiết là mọi cách sửa đúng.

| Thành phần | Trách nhiệm |
|---|---|
| Graph, bước 0 | Thực thể, quan hệ, nguồn bằng chứng, snapshot và giới hạn phân tích |
| Tool truy hồi | Thực thi truy vấn có kiểu; trả bằng chứng, phần bị cắt và phần chưa biết |
| Bộ điều khiển agent | Quản lý ứng viên, giả thuyết, truy vấn đã thử, context và ngân sách |
| LLM | Diễn giải issue, đề xuất cơ chế lỗi, câu hỏi phân biệt giả thuyết và đánh giá code |
| Bộ kiểm tra tất định | Kiểm tra ID, parameter, schema, citation, snapshot và định dạng đầu ra; không thay LLM chứng minh nguyên nhân |

Giữ vòng gọi LLM/tool hiện có. Thay đổi quan trọng là **trạng thái ngoài hội thoại và quy tắc điều phối**, không phải thêm nhiều agent hay chia pipeline cứng thành nhiều lượt LLM.

### Ràng buộc đánh giá

- SWE-bench Lite, Loc-Bench V1 và Multi-SWE-bench Java; đánh giá file/class/function.
- Giữ adapter read-only và 7 tool đọc hiện có làm nền. Không nối công cụ tự sinh/chạy Python vào localization.
- Không chạy mã repo đích, không cài dependency, không sinh hoặc thử patch trong workflow này. Không gọi nhận định tĩnh là “đã kiểm chứng bằng test”.
- Gold locations, gold patch và test patch không được vào prompt, bộ nhớ hoặc graph. Test có sẵn trong snapshot được dùng làm tài liệu về hành vi mong đợi, không mặc nhiên là bằng chứng test đã chạy.
- Lịch sử tùy chọn chỉ lấy phần được phép tại snapshot/cutoff; không đọc dữ liệu tương lai hay PR sửa chính issue đang xét.

## 2. Hiện trạng và điểm yếu đã xác định

Các đường dẫn dưới đây tính từ thư mục gốc Jacc-v2, phản ánh lần kiểm tra mã trong phiên nghiên cứu.

| Hiện trạng | Vấn đề cần xử lý | Điểm mã |
|---|---|---|
| Vòng `call_model` / `tools` / `finalize` | Lịch khám phá chủ yếu do LLM quyết định trong hội thoại | `src/modules/agents/workflow.py:90–108` |
| Có `container_path` là chuyển sang `targeted` | Có địa chỉ code không đồng nghĩa đã tìm đúng hướng; dễ khóa vào hit đầu | `workflow.py:177–191`; `src/modules/agents/tools/ckg.py:248–253` |
| Giữ task và đuôi hội thoại gần nhất | Phản chứng hoặc ứng viên tốt cũ có thể rời context | `workflow.py:125–161` |
| Cắt danh sách và snippet theo ngưỡng | Cắt trước khi đánh giá liên quan; danh sách bị cắt không có hợp đồng đầy đủ về phần còn lại | `src/modules/agents/tools/ckg.py:259–284` |
| Dừng khi LLM không gọi tool hoặc hết bước | Có thể kết luận sớm hoặc hết bước trước khi tổng hợp | `workflow.py:58–88` |
| Prompt cho phép trả danh sách rỗng | Đã có quyền abstain; thiếu tiêu chí và lý do nội bộ, không phải thiếu quyền | `src/modules/agents/prompt.py:27–30` |

Các nhận định cần tránh: ReAct không nhất thiết chỉ xét một giả thuyết, nhưng không có trạng thái bảo đảm các giả thuyết được giữ lại; cùng hình thức ReAct không có nghĩa Jacc sẽ đạt cùng điểm số với một baseline khác.

## 3. Trạng thái ngoài hội thoại

Bộ nhớ làm việc thuộc **một instance + một snapshot**, tách khỏi graph mã nguồn. Khởi đầu bằng các record JSON và kho artifact cục bộ; chưa cần graph bộ nhớ mới, vector memory hoặc một agent chuyên tóm tắt.

| Record | Nội dung tối thiểu | Vai trò |
|---|---|---|
| `IssueContract` | Triệu chứng, kỳ vọng, điều kiện kích hoạt, tên/path/traceback được nhắc, nguồn trích, điểm chưa rõ | Giữ nguyên bài toán; tách điều issue nói khỏi diễn giải của LLM |
| `Candidate` | Entity ID, nguồn tìm thấy, vai trò, mức liên quan, trạng thái nghi vấn sửa | Một hit chưa phải một vị trí cần sửa |
| `Hypothesis` | Cơ chế lỗi, phạm vi ứng viên, triệu chứng giải thích được, dự đoán, phép kiểm phân biệt, bằng chứng ủng hộ/phản bác | Giữ các giải thích cạnh tranh, không chỉ một danh sách hàm |
| `Evidence` | Mệnh đề có phạm vi, citation nguồn, snapshot, phương pháp, giới hạn | Một quan sát có thể phục vụ nhiều giả thuyết |
| `QueryRecord` | Mục tiêu, parameter chuẩn hóa, kết quả, truncation, chi phí, thông tin mới | Khử truy vấn lặp và ghi nhận các hướng chưa kiểm tra |
| `Decision` | Hành động được chọn, lý do, giả thuyết bị hoãn, lý do dừng | Tái lập và đánh giá quyết định |

Trạng thái giả thuyết: `open`, `supported`, `contradicted`, `inconclusive`. `supported` không có nghĩa là đã chứng minh. Tách trạng thái xử lý `active`/`deferred` khỏi trạng thái bằng chứng: hoãn vì hết ngân sách không phải bác bỏ.

Một giả thuyết có thể cần nhiều vị trí sửa; một vị trí có thể xuất hiện trong nhiều giả thuyết. Không tự động bác bỏ mọi giả thuyết con khi giả thuyết cha sai: chỉ vô hiệu kết luận phụ thuộc tiền đề đó, giữ lại quan sát độc lập.

## 4. Chiến thuật truy vấn: rộng, sâu và quay lại

### 4.1 Rộng là đa dạng cơ chế, không phải lấy nhiều hàng xóm

Tìm rộng ban đầu theo các kênh độc lập: tên/path/traceback chính xác, từ khóa hành vi, mô tả ngữ nghĩa nếu có chỉ mục, cấu trúc được issue nhắc. LLM đề xuất cách diễn đạt; code phân giải ID và giữ các trường hợp nhập nhằng.

Gộp trùng theo entity ID, giữ provenance của từng kênh. Không lấy nhiều ứng viên chỉ vì chúng cùng khớp một từ; ưu tiên các ứng viên đại diện cho những cơ chế lỗi khác nhau. Không có số seed tối ưu mặc định: giới hạn là tham số cần đo theo ngân sách.

| Tình huống | Chiến thuật | Điều kiện chuyển |
|---|---|---|
| Chưa có anchor hoặc chỉ có từ chung chung | Rộng, trả ID/signature/snippet ngắn từ vài phạm vi khác nhau | Có ứng viên gắn được với điều kiện cụ thể của issue |
| Tên trùng, overload hoặc nhiều class cùng method | Khử nhập nhằng theo path, owner, signature; giữ nhiều ID nếu chưa đủ dữ kiện | Đủ thông tin chọn phạm vi, không chọn đại |
| Có cơ chế lỗi và câu hỏi kiểm tra cụ thể | Sâu, một quan hệ hoặc một đoạn code tại một thời điểm | Có bằng chứng mới giúp phân biệt giả thuyết |
| Hai giả thuyết cùng hợp lý | Chọn truy vấn mà các giả thuyết dự đoán kết quả khác nhau | Một giả thuyết được tăng/giảm mức ủng hộ có căn cứ |
| Kết quả lặp, chỉ thêm wrapper hoặc bị phản chứng | Quay lại nhánh khác hoặc mở rộng từ vựng/phạm vi | Có hướng chưa khám phá; không tăng hop mù quáng |
| Truy vấn rỗng do thiếu coverage, unsupported hoặc bị cắt | Đọc source hoặc bổ sung trang dữ liệu cần thiết; nếu không thể thì ghi `unknown` | Không diễn giải thành “không có quan hệ” |
| Sắp hết ngân sách | Dừng mở rộng không thiết yếu, tổng hợp từ bằng chứng đã đọc | Phát hành kết quả hoặc abstain có lý do |

Không chuyển sang sâu chỉ vì tool trả một path hoặc điểm retrieval cao. Cần liên hệ cụ thể giữa ứng viên và issue, kèm câu hỏi tiếp theo. Chuyển sâu là tạm thời; luôn giữ khả năng quay lại rộng.

### 4.2 Chọn hướng theo câu hỏi, không theo khoảng cách đơn thuần

- Giá trị sai: xem nơi đọc và nơi ghi, kiểm tra phép tính, trạng thái trước/sau, nguồn dữ liệu và cách hiển thị. Hàm chỉ đọc vẫn có thể đọc sai field hoặc định dạng sai.
- Exception: traceback xác định nơi quan sát; đọc precondition, caller, nơi raise và handler để phân biệt vi phạm hợp đồng với xử lý lỗi sai.
- Dispatch/kế thừa: kiểm tra receiver, method được chọn, override và hợp đồng lớp cha.
- Cấu hình: kiểm tra nguồn key, default, parse/validation và nơi tiêu thụ.
- Thiếu hành vi: kiểm tra điểm mở rộng hoặc nhánh đáng lẽ phải xử lý trường hợp đó. Code cần thêm có thể chưa có node; phải định vị chủ thể hiện có chịu trách nhiệm.

Khoảng cách trên graph chỉ giúp ưu tiên, không phải tiêu chí loại trừ. Hai symbol chung một `File` hoặc một `Community` không tự nhiên gần nhau về nguyên nhân. Không trộn cạnh chứa, similarity và dependence thành khoảng cách không phân biệt loại.

### 4.3 Sinh parameter: ý định từ LLM, ràng buộc từ code

LLM đề xuất một `QueryIntent` có dạng:

```yaml
hypothesis_id: h_discount_state
question: "Những hàm nào cập nhật giá trị total mà màn hình đang đọc?"
operation: find_writers
anchor_id: "<ID lấy từ kết quả tool trước>"
scope: "<snapshot và phạm vi đã xác nhận>"
expected_discrimination: "Phân biệt lỗi tính giảm giá với lỗi không cập nhật total"
```

Đây là hợp đồng mục tiêu, không phải tool đã tồn tại. Adapter chuyển intent sang tool hiện có hoặc báo `unsupported`; không giả vờ có `find_writers` khi graph chưa có `WRITES`.

Code phải kiểm tra:

1. Anchor tồn tại trong snapshot; tên chưa rõ phải qua bước phân giải, không để LLM bịa ID.
2. Operation và loại cạnh thực sự được hỗ trợ; chiều source/target đúng ngữ nghĩa.
3. Scope, độ sâu, giới hạn kết quả và ngân sách nằm trong chính sách.
4. Cache key gồm snapshot, phiên bản graph, operation, parameter chuẩn hóa và cursor. Truy vấn cùng phạm vi không được lặp chỉ vì LLM đổi cách viết câu hỏi.
5. Parameter sai trả lỗi sửa được; phân biệt `invalid_query`, `unsupported` và kết quả rỗng hợp lệ.

Bắt đầu bằng template truy vấn có kiểu trên tool hiện có. Chưa cần cho LLM sinh Cypher tùy ý hoặc thêm một DSL tổng quát.

### 4.4 Lập lịch theo thông tin giúp ra quyết định

Ưu tiên truy vấn có khả năng **đổi quyết định về vị trí sửa**, không phải truy vấn trả nhiều node. Tín hiệu thực dụng: phân biệt giả thuyết đang cạnh tranh, kiểm tra điều kiện của issue còn bỏ ngỏ, xác minh ứng viên cuối, chi phí thấp và ít trùng dữ liệu đã có.

Duy trì một hàng đợi giới hạn, có ngân sách cho hướng thay thế để tránh bám chặt hit đầu. Bộ đếm số lần LLM nhắc lại không phải bằng chứng độc lập. Chưa gọi điểm heuristic là “expected information gain” hay xác suất nếu chưa có mô hình được hiệu chuẩn.

## 5. Quản lý context: lưu đầy đủ, nạp chọn lọc

### 5.1 Ba mức lưu trữ

| Mức | Lưu gì? | Có đưa vào mỗi lượt LLM không? |
|---|---|---|
| Artifact gốc | Output đầy đủ mà hệ nhận được, query, source range, snapshot và hash | Không; đọc lại theo ID khi cần |
| Sổ bằng chứng | Record nhỏ, phân biệt quan sát với diễn giải và liên kết về nguồn | Chỉ phần liên quan tới quyết định hiện tại |
| Context của lượt hiện tại | Issue contract, giả thuyết đang xét, đối thủ chính, bằng chứng và phản chứng cần thiết, delta mới | Có, trong ngân sách token |

Lưu output **trước** `_compact_ckg_result`. Nếu backend đã LIMIT trước đó, artifact chỉ là phần đã lấy, không phải toàn bộ kết quả khả dĩ. Cần cursor/phân trang hoặc công cụ đọc đoạn source; lưu bản đã cắt không phục hồi được dữ liệu chưa từng nhận.

### 5.2 Hợp đồng output của tool

Envelope tối thiểu gồm `query_id`, `snapshot_id`, `status`, `items`, `returned_count`, `total_count` nếu biết, `truncated`, `cursor`, `coverage`, `artifact_ref`. Không bịa `total_count` khi backend không tính được.

Tách **trạng thái thực thi** (`ok`, `error`, `unsupported`) khỏi **kết luận về quan hệ** (`found`, `absent_within_scope`, `unknown`). Truy vấn thành công nhưng trả 0 hàng vẫn có thể là `unknown`.

Ví dụ record bằng chứng:

```yaml
id: e17
query_id: q6
kind: source_observation
subject_id: "<ID của apply_discount>"
statement: "Đoạn code đã đọc cập nhật discount nhưng không cập nhật total"
scope: "Chỉ đoạn source đã đọc; chưa kết luận về side effect của các callee"
source: {path: cart.py, start_line: 40, end_line: 55, content_hash: "..."}
snapshot_id: "..."
artifact_ref: "..."
```

Record này **không** tự chứa kết luận “apply_discount là lỗi”. Quan hệ ủng hộ/phản bác nằm trong `Hypothesis` và được đánh dấu là đánh giá của LLM. Tóm tắt phải có citation; bộ kiểm tra citation chỉ chứng minh nguồn tồn tại, không chứng minh câu diễn giải đúng.

### 5.3 Đóng gói context theo quyết định

Thay việc gửi mọi output và toàn bộ lịch sử bằng:

1. Ràng buộc issue và phần trích gốc liên quan, giữ nguyên identifier/điều kiện quan trọng.
2. Giả thuyết đang xét và giải thích thay thế mạnh nhất.
3. Bằng chứng, phản chứng và giới hạn liên quan trực tiếp.
4. Truy vấn gần nhất cùng thông tin mới; danh sách ngắn các hướng đã thử không hữu ích.
5. Câu hỏi cần quyết định và ngân sách còn lại.

Giới hạn token vẫn cần thiết, nhưng là **giới hạn gói context**, không phải quy tắc xóa bằng chứng theo tuổi. Ưu tiên phản chứng, chi tiết phân biệt giả thuyết và source cần kiểm tra; không chỉ giữ dữ liệu củng cố hướng hiện tại. Giữ trace đầy đủ ngoài prompt để audit.

Khử trùng theo nguồn/snapshot/mệnh đề, không theo câu chữ. `ckg_contract` và `ckg_symbol_context` cùng trả một cạnh không tạo thành hai bằng chứng độc lập. Một summary cũng không trở thành nguồn độc lập với code nó tóm tắt.

Khi summary có thể đã mất qualifier hoặc hai bằng chứng mâu thuẫn, đọc lại nguồn; không tóm tắt đệ quy qua nhiều lớp rồi coi là fact. Source/docstring/tool output là dữ liệu không đáng tin về mặt chỉ dẫn, không được thay đổi system policy.

## 6. Từ liên quan đến vị trí cần sửa

### 6.1 Tách vai trò của ứng viên

Một candidate có thể mang nhiều vai trò: `symptom_site` (nơi thấy sai), `propagation_site` (nơi truyền ảnh hưởng), `suspected_defect_site` (nơi nghi có sai sót), `proposed_edit_site` (nơi đề xuất cần sửa), `supporting_context` (ngữ cảnh). Vai trò chưa xác định thì giữ `unknown`.

Không đưa một node vào kết quả chỉ vì nằm trên đường CALLS, đọc/ghi cùng field, có fan-in cao, tương tự code lỗi hoặc cùng xuất hiện trong lịch sử thay đổi.

### 6.2 Hồ sơ đề xuất sửa cho từng vị trí

Trước khi một vị trí vào đầu ra, yêu cầu hồ sơ nội bộ trả lời được:

| Câu hỏi | Bằng chứng cần có |
|---|---|
| Hành vi mong đợi là gì? | Trích issue, contract hoặc test có sẵn; chỉ rõ phần còn suy đoán |
| Code hiện tại lệch ở đâu dưới điều kiện nào? | Source range cụ thể; không chỉ mô tả chức năng của hàm |
| Vì sao lệch đó có thể gây triệu chứng? | Lập luận nối điều kiện kích hoạt, giá trị/control flow và kết quả quan sát |
| Vì sao nên sửa tại đây? | Trách nhiệm của thành phần; phân biệt sửa nguyên nhân với che triệu chứng ở caller/UI |
| Còn giải thích nào cạnh tranh? | Phản chứng, điều chưa biết, truy vấn phân biệt đã làm hoặc bị hoãn |
| Có cần vị trí khác cùng thay đổi không? | Phụ thuộc hợp đồng hoặc phối hợp nhiều vị trí, không tự chọn một “thủ phạm” duy nhất |

Mô tả *ý định thay đổi* ở mức hành vi, không sinh patch. Phản thực “nếu sửa tại đây thì triệu chứng có hết không?” là phép kiểm tính hợp lý, **không phải can thiệp thực nghiệm**.

Không loại cứng ứng viên chỉ vì thiếu đường graph: có thể graph thiếu cạnh hoặc lỗi là thiếu code. Nếu chưa đủ hồ sơ, giữ ứng viên ở trạng thái chưa kết luận; không bịa lập luận để vượt tiêu chí.

### 6.3 Ví dụ phân biệt giả thuyết

Issue: “Sau khi áp dụng giảm giá, tổng tiền hiển thị vẫn là giá cũ.”

- H1: `apply_discount` tính sai giá trị giảm.
- H2: kết quả giảm đúng nhưng `update_cart` không cập nhật tổng/cache.
- H3: dữ liệu đúng nhưng `show_total` đọc giá trị cũ.

Truy vấn thêm caller của `show_total` có thể chỉ tăng số node liên quan. Truy vấn có giá trị hơn là xác định **giá trị mà show_total đọc và đường cập nhật giá trị đó**, rồi đọc logic tính giảm. Nếu graph chưa có READS/WRITES, dùng source theo phạm vi có chủ đích và ghi rõ giới hạn.

Nếu nguồn cho thấy `apply_discount` chỉ có trách nhiệm trả về giá trị mới còn caller chịu trách nhiệm cập nhật, việc nó không ghi `total` không chứng minh H1. Nếu reader chọn nhầm field/cache, chính hàm chỉ đọc có thể là nơi cần sửa. Đó là lý do phải xét contract, không suy “writer là thủ phạm”.

### 6.4 Kiểm chứng với ba giá trị, không ép đúng–sai

Bác bỏ bằng sự vắng mặt chỉ hợp lệ khi:

- H thực sự đòi hỏi quan hệ P tồn tại, không chỉ “P thường đi cùng H”.
- Bộ phân tích bảo đảm đủ quan hệ P trong phạm vi/snapshot đang xét, không chỉ parse thành công.
- Truy vấn đúng scope, đúng hướng, không bị cắt, không bỏ qua dynamic feature chưa giải được.

Không thỏa thì ghi `unknown`; không tự động hạ hạng chỉ vì thiếu dữ liệu. Có bằng chứng phù hợp làm H được ủng hộ, không chứng minh H là nguyên nhân duy nhất. Có phản chứng trực tiếp trong code có thể bác một tiền đề cụ thể ngay cả khi graph chưa phủ toàn repo.

`same-file`, `import-scoped` và điểm confidence cao không tự động có nghĩa MUST. MUST về đích tại call site cũng không chứng minh call site sẽ được thực thi. Không có cạnh MUST không chứng minh không có lời gọi MAY.

## 7. Vòng điều khiển và điều kiện dừng

Vòng mục tiêu, không bắt buộc mỗi bước là một lượt LLM riêng:

1. Lập `IssueContract`, phân giải các anchor có trong issue.
2. Tìm ứng viên đa dạng; hình thành giả thuyết có điều kiện kiểm tra.
3. Chọn câu hỏi có giá trị phân biệt; chuẩn hóa và kiểm tra parameter.
4. Thực thi tool chỉ đọc; lưu artifact và cập nhật sổ bằng chứng.
5. Cập nhật mức ủng hộ/phản bác, đóng gói context; quyết định đi sâu, đổi nhánh hoặc tìm rộng lại.
6. Kiểm tra hồ sơ sửa của tập ứng viên cuối và phát hành kết quả.

Không đặt số vị trí cuối cố định. Ưu tiên tập nhỏ có căn cứ nhưng cho phép lỗi nhiều vị trí; không tối ưu recall bằng cách trả tất cả node liên quan.

Lý do dừng nội bộ: `sufficient_evidence`, `budget_exhausted`, `no_progress`, `blocked_by_capability`, `insufficient_evidence`. “Không có thông tin mới” nghĩa là không thêm phân biệt hữu ích giữa giả thuyết, không phải chỉ không có node mới. Dành trước ngân sách cho tổng hợp cuối; không để tool cuối chiếm hết bước.

Giữ định dạng benchmark `found_files`, `found_modules`, `found_functions`. Hồ sơ sửa, mức bằng chứng và lý do dừng lưu riêng trong trace. Trả rỗng là abstention, không phải kết luận repo không có bug. Kiểm tra ID/path/class/method trước khi serialize; không tự động thêm class vào kết quả chỉ vì một method thuộc class đó.

## 8. Roadmap workflow và tiêu chí hoàn thành

Ưu tiên ở đây độc lập P0/P1/P2 của [roadmap đồ thị](roadmap.md). Không phải chờ graph hoàn thiện mới cải thiện agent; khi capability thiếu thì dùng source hoặc giữ unknown.

| Mức | Việc | Tiêu chí hoàn thành |
|---|---|---|
| W0 — quan sát và an toàn | Query log, snapshot, ngân sách, lưu output trước cắt; bỏ điều kiện `container_path` là đủ để khóa hướng; envelope truncation/error | Mọi quyết định cuối truy về được dữ liệu đã thấy; kết quả rỗng/unsupported/truncated phân biệt được |
| W1 — bộ nhớ bằng chứng | IssueContract, Candidate, Hypothesis, Evidence; context pack theo câu hỏi; khử truy vấn/bằng chứng trùng | Bằng chứng cũ đọc lại được; phản chứng không mất khi trượt cửa sổ; không tăng độ tin chỉ vì lặp output |
| W2 — điều phối truy vấn | Rộng/sâu/quay lại; intent có kiểu, phân giải ID, template, hàng đợi nhánh chưa khám phá | Có trace lý do chọn query; query sai được sửa; nhánh bế tắc không lặp vô hạn |
| W3 — lựa chọn vị trí sửa | Hồ sơ sửa, phân biệt các vai trò, kiểm tra giải thích thay thế, tập kết quả động và abstention | Mỗi vị trí có lập luận và citation; không tự đồng nhất graph relevance với defect |

Thêm fixture offline với model giả và tool response cố định: tên trùng; hit đầu sai; evidence quan trọng xuất hiện sớm rồi bị đẩy khỏi cửa sổ; cùng bằng chứng từ hai tool; quan hệ thiếu do coverage; lỗi cần hai vị trí; budget hết trước kết luận; output chứa chỉ dẫn độc hại. Không gọi provider thật để kiểm thử tự động.

## 9. Đánh giá để biết cải tiến đến từ đâu

Giữ model, prompt nền, instance, ngân sách và tool contract tương đương. Tách bốn cấu hình:

| | Workflow hiện tại | Workflow nâng cấp |
|---|---|---|
| Graph hiện tại | Baseline | Đo đóng góp workflow |
| Graph nâng cấp | Đo đóng góp graph | Đo kết hợp và tương tác |

Dùng cùng adapter/tool có khả năng báo unsupported, tránh cấu hình graph cũ bị ép thực hiện truy vấn không hỗ trợ. Thử workflow theo từng nhóm: memory, query policy, rồi selection gate; không đổi mọi thứ cùng lúc rồi quy công cho graph.

Ngoài SL/precision/recall/F1 ba mức và token/chi phí/latency, ghi:

- Gold có trong seed, trong kết quả tool, trong **context thực sự gửi LLM**, và trong đầu ra cuối hay không. Đây là bốn mốc khác nhau.
- Query trùng, số lần đổi nhánh, trường hợp unknown bị hiểu sai là absent, ngân sách đã dùng khi dừng.
- Tỷ lệ candidate liên quan được chọn sai làm edit site; review thủ công một tập để kiểm tra hồ sơ sửa và độ đúng citation.
- Tỷ lệ abstain và chất lượng trên toàn benchmark, không chỉ phần đã trả lời; false elimination của gold qua từng bước.

Gold chỉ dùng trong bộ đánh giá offline, không đưa vào trạng thái agent. Thử che tên/path trong issue như phép chẩn đoán bổ sung, không thay benchmark chính. Lặp nhiều seed khi khả thi và báo biến thiên; chưa tuyên bố workflow tốt hơn trước khi có kết quả.

## 10. Nền nghiên cứu và mức chắc chắn

Kế thừa các hướng đã khảo sát: đa giả thuyết có cấu trúc của GraphLocator; lịch tìm kiếm và lọc context của OrcaLoca; findings có giải thích của SHERLOC; ranh giới thực thi tất định và kiểm tra truy vấn của LogicLoc. Không suy rằng ghép các cơ chế sẽ tự động tốt hơn từng baseline.

Nguồn nội bộ: [REASONING_PIPELINE.vn.md](../../../research/codekg-survey/REASONING_PIPELINE.vn.md), [reasoning_analysis.vn.md](../../../research/codekg-survey/raw_scouts/phase8_reasoning/reasoning_analysis.vn.md), [JACC_V2_GAP.vn.md](../../../research/codekg-survey/JACC_V2_GAP.vn.md). Các phát biểu cũ trong khảo sát như “parse đầy đủ đủ để phủ định quan hệ” hoặc “agent không được trả rỗng” không áp dụng; dùng các điều kiện đã sửa ở tài liệu này.
