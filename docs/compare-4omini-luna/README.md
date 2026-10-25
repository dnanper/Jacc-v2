# gpt-4o-mini so với gpt-5.6-luna, từng bước LLM (held-out 6, 2026-10-21)

Thư mục này so output của hai model ở từng bước có gọi LLM, trên cùng 50 instance của held-out 6 (25 Lite + 25 LocBench, 114 hàm gold).

## Cấu hình gpt-4o-mini đã chốt (2026-10-25)

Sau các thí nghiệm ghi trong `DEEP_DIVE.md` và `EMBEDDING_DESIGN.md`, cấu hình dùng cho gpt-4o-mini được chốt như sau. Sơ đồ: `../design/jacc_v6_mini_a3luna.html`.

| Bước | Model, cài đặt | Biến môi trường, tham số |
|---|---|---|
| A1 IssueModel | gpt-4o-mini | `--model gpt-4o-mini-2024-07-18` |
| A2 seeds | gpt-4o-mini, có bước lập kế hoạch truy vấn (planner V4) | `JACC_A2_PLAN=1` |
| A3 hypotheses | **gpt-5.6-luna**, prompt frozen, 2 mẫu | `JACC_A3_MODEL=gpt-5.6-luna`, `--a3-samples 2`, không đặt `JACC_A3_PROMPT` |
| A3V verifier | gpt-4o-mini | — |
| Calibrator | calibrator luna (`calibrator_swetrain`), p ≥ 0.045 | `JACC_CALIBRATOR=src/modules/data/calibrator_swetrain.json` |

Code: branch `exp/embed`. Tắt ở cấu hình này: prompt C4, `JACC_A3_FILE_FUNCS`, `JACC_A3_SHUFFLE`, embedding. Calibrator mini (M, M+pw) không dùng vì SL/REC thấp hơn.

Kết quả trên held-out 6 (tập phát triển), mức function, SL / REC / PRE / F1:
- Lite: 60.0 / 66.7 / 21.4 / 29.3;
- LocBench: 36.0 / 50.3 / 22.1 / 27.3.

So với mini toàn bộ (A3 mini): Lite SL +16 [+4, +32], REC +14 [+2, +28]; LocBench REC +4.1 [+0.5, +9.0].

**Chưa có kết quả báo cáo được:** thí nghiệm cô lập hiệu ứng A3 luna và lần chạy đầy đủ hai benchmark đều chưa chạy (xem `DEEP_DIVE.md`).

Phần dưới đây là phân tích ban đầu (2026-10-21), so bản mini chưa cải tiến với luna.

## Hai lần chạy được so

| | luna | mini |
|---|---|---|
| Model | gpt-5.6-luna | gpt-4o-mini-2024-07-18 |
| Artifact | `final-results/lite_rest`, `final-results/loc_rest` (2026-10-17) | `.agent_runs/heldout6_4omini_r` (2026-10-21) |
| Code | `v6-threshold` | `v6-threshold` + `JACC_CALIBRATOR` (commit `e8d6086`, không đổi logic) |
| Graph | cùng bản lưu `jacc_lite_rest` / `jacc_loc_rest` | cùng |
| Calibrator | swe_train, p ≥ 0.045 | swe_train, p ≥ 0.045 |
| Số mẫu A3 | 2 (mặc định) | 1 (`--a3-samples 1`, như A13) |

Ngoài model, chỉ khác số mẫu A3. Phần A3 bên dưới tách riêng ảnh hưởng của yếu tố này.

Cả hai thứ hạng đều được dựng lại từ artifact bằng calibrator swe_train. Script kiểm rằng bản dựng lại khớp đúng với `recall_answer` đã lưu.

## Bước nào gọi LLM

| Bước | LLM làm gì | Lời gọi / instance (luna / mini) | Phần không dùng LLM trong bước |
|---|---|---|---|
| A0, A0.5 | — | 0 | Build graph, repo profile |
| **A1** issue model | Đọc issue, viết `IssueModel`: summary, observed/expected, `explicit_code_refs`, key concepts | 1 / 1 | — |
| **A2** seeds | (a) `SeedQueries`: viết query tìm kiếm ban đầu; (b) `Review`: mỗi vòng gắn nhãn relevant/maybe/irrelevant cho các node được đưa xem, và đề xuất query mới cho vòng sau | 4.0 / 3.8 | Tìm kiếm FTS + RRF, cửa sổ chọn node đưa reviewer, query lấy từ `explicit_code_refs` |
| **A3** hypotheses | Viết giả thuyết lỗi: claim, mechanism, target cần sửa, prediction | 2 / 1 | Kiểm tra hợp lệ, gộp trùng |
| **A3V** verifier | Đọc code của tối đa 40 candidate, gắn nhãn edited/maybe/not_edited, xếp hạng | 1 / 1 | Mở rộng candidate qua graph (root, target, call hop, region) |
| A6 | — | 0 | Calibrator logistic, ngưỡng p ≥ 0.045, quy về file/class |

## Kết quả cuối (mức function, SL / REC / PRE / F1, %)

| | Lite | LocBench |
|---|---|---|
| luna | 64.0 / 74.7 / 38.1 / 45.3 | 44.0 / 57.5 / 33.4 / 36.5 |
| mini | 40.0 / 44.0 / 18.0 / 22.4 | 32.0 / 48.1 / 23.0 / 27.3 |

Nguồn: `.agent_runs/heldout6_4omini_r/score.txt`. Theo instance, tính "trúng ít nhất một hàm gold": cả hai trúng 26, chỉ luna trúng 14, chỉ mini trúng 1, cả hai trượt 9.

## Phễu: % trong 114 hàm gold còn sống sau mỗi bước

| Bước | luna | mini | chênh |
|---|---|---|---|
| A2 tìm kiếm: kết quả của ít nhất một query chứa gold | 72.8 | 60.5 | −12.3 |
| … do query lấy từ code ref của A1 | 42.1 | 36.0 | −6.1 |
| … do query ban đầu LLM viết | 55.3 | 52.6 | −2.6 |
| … do query học thêm ở vòng 2/3 | 62.3 | 38.6 | **−23.7** |
| … **chỉ** query học thêm tìm thấy | 7.9 | 2.6 | −5.3 |
| A2: gold được đưa cho reviewer xem | 58.8 | 46.5 | −12.3 |
| A2: gold được giữ làm seed (relevant/maybe) | 57.0 | 46.5 | −10.5 |
| A3: gold là target của ít nhất một giả thuyết | 50.0 | 15.8 | **−34.2** |
| A3: gold là target của H1 | 35.1 | 10.5 | −24.6 |
| A3V: gold trong danh sách candidate | 67.5 | 57.9 | −9.6 |
| A3V: gold được đưa verifier xem | 64.9 | 50.0 | −14.9 |
| A3V: verifier gắn `edited` | 46.5 | 31.6 | −14.9 |
| Hạng 1 sau calibrator | 31.6 | 13.2 | −18.4 |
| Hạng ≤ 3 | 46.5 | 25.4 | −21.1 |
| **Đáp án cuối** | **52.6** | **35.1** | **−17.5** |

Bước đầu tiên làm rơi từng hàm gold (số hàm):

| Rơi ở | luna | mini |
|---|---|---|
| A2 tìm kiếm: không query nào tìm thấy | 22 | **38** |
| A2 cửa sổ duyệt: tìm thấy nhưng không đưa reviewer | 14 | 10 |
| A2 reviewer loại | 1 | 0 |
| A3V: là candidate nhưng không lọt vào 40 node verifier xem | 3 | 9 |
| A3V verifier: `not_edited` | 12 | 10 |
| A3V verifier: `maybe` (p dưới ngưỡng) | 2 | 3 |
| A3V verifier: không trả nhãn cho node đã xem | 0 | 4 |
| **Vào đáp án** | **60** | **40** |

## Từng bước LLM ảnh hưởng ra sao

### A1: ảnh hưởng nhỏ

- Mini ghi ít code ref hơn nhiều: trung bình 5.3 so với 16.7 mỗi instance.
- Chỉ 15/114 tên hàm gold xuất hiện nguyên văn trong issue. Code ref của luna bắt được 14 tên, của mini bắt được 8.
- Gold mà query từ code ref tìm thấy: 42.1% (luna) so với 36.0% (mini), chênh −6.
- Phần lớn issue không nêu tên hàm cần sửa, nên A1 không quyết định nhiều.
- Mini còn hay chép thông tin môi trường vào code ref. Ví dụ ở [home-assistant__core-136739](instances/home-assistant__core-136739.md), code ref của mini là `core-2024.2.5`, `Home Assistant OS`.

### A2: chênh nằm ở query học thêm, không ở reviewer

- **Query ban đầu gần như ngang nhau:** gold tìm thấy 55.3% so với 52.6%.
  - Hình thức vẫn khác: 41% query ban đầu của luna là tên code (`_print_Sum`, `FritzBoxSwitch`, `async_turn_on`), mini chỉ 21%.
  - Mini hay viết cụm từ chung chung. Ví dụ ở [sympy__sympy-16503](instances/sympy__sympy-16503.md): `pretty print bug`, `Sum output`, `alignment issue`.
- **Query học thêm là chỗ mất lớn nhất của A2:** gold tìm thấy 62.3% so với 38.6%.
  - Mini học ít query hơn (9.6 so với 14.0) và dừng sớm hơn (2.7 vòng so với 3).
  - Query học thêm của cả hai đều là tên code (88–93%). Khác ở chỗ mini chọn hướng: nó đi theo node đã thấy, kể cả khi lạc vùng. Ví dụ ở [home-assistant__core-136739](instances/home-assistant__core-136739.md), mini học query trong integration `fritz` (router) thay vì `fritzbox` (ổ cắm thông minh).
- **Reviewer không phải vấn đề:** khi gold được đưa xem, luna giữ 97%, mini giữ 100%.
  - Mini giữ rộng hơn (48 seed relevant/maybe, so với 46 của luna) và loại ít hơn (32 so với 43).
- **Hệ quả:** 38 hàm gold của mini không được query nào tìm thấy, luna là 22. Đây là chỗ rơi lớn nhất tính theo số hàm (+16).

### A3: bước yếu nhất của mini

- **Khi gold đã là seed**, luna đặt nó làm target 76.9% số lần, mini chỉ 34.0%.
  - Mini viết ít target: 0.97 mỗi giả thuyết, luna 1.83.
  - Target của mini thường là hàm khác trong cùng vùng. Ví dụ ở [home-assistant__core-136739](instances/home-assistant__core-136739.md), luna viết đúng `FritzboxSwitch.async_turn_on/off` ở H1, còn mini nhắm vào `async_setup_entry` và `config_flow`.
- **Tách ảnh hưởng của số mẫu:** nếu chỉ giữ giả thuyết từ mẫu đầu của luna, gold là target vẫn đạt 41.2%, so với 15.8% của mini. Số mẫu A3 (2 so với 1) giải thích khoảng 9 trong 34 điểm chênh. Khoảng 25 điểm còn lại do model.
- **A3 của luna còn kéo về gold mà A2 không tìm thấy:** đi qua cạnh graph từ seed, luna đặt target cho 6 hàm gold mà không query nào tìm ra, và 5 trong số đó vào đáp án. Mini làm được 0.
- **Bộ kiểm tra hợp lệ loại 42/150 giả thuyết thô của mini** vì "missing core prediction", sau khi bỏ các prediction đặt trên node Class/File (không đọc được). Luna chỉ bị loại 10 giả thuyết vì lý do này. Tuy vậy, các giả thuyết bị loại của mini chỉ chứa thêm 2 hàm gold, nên đây không phải nguồn mất chính.
- **A3 ảnh hưởng đến đáp án chủ yếu qua thứ hạng.** Danh sách candidate chỉ chênh −9.6, vì seed của A2 và graph vẫn đưa gold vào. Nhưng target của A3 là đặc trưng xếp hạng (`target_rank_inv`, `in_h1`). Hệ quả:
  - gold đứng hạng 1: 31.6% so với 13.2%;
  - gold là candidate nhưng nằm ngoài 40 node verifier xem: 9 hàm (mini) so với 3 (luna).

### A3V verifier: recall gần ngang, precision kém xa

- **Khi gold được đưa xem**, verifier gắn `edited` 71.6% (luna) so với 63.2% (mini).
- **Mini gắn `edited` gần gấp đôi số node:** 4.4 so với 2.3 mỗi instance.
  - Tỉ lệ node `edited` đúng là gold: luna 45.3%, mini 16.4%.
  - Đây là lý do PRE của mini thấp: đáp án to hơn (5.7 so với 5.0 hàm) và chỉ 14.1% là gold, luna 24.1%.
- **Mini bỏ sót nhãn** cho 4 hàm gold đã được đưa xem. Luna không bỏ sót lần nào.
- **Calibrator không làm rơi gold đã được gắn `edited`:** 100% các hàm này vào đáp án, ở cả hai model.

## Kết luận

Xếp theo mức ảnh hưởng đến đáp án cuối:

1. **A3 (sinh giả thuyết)** có chênh lớn nhất ở chính bước đó (−34 điểm, khoảng −25 điểm nếu cùng số mẫu). Nó tác động lên đáp án qua thứ hạng và qua việc đưa node vào tầm xem của verifier.
2. **A2 (query học thêm)** làm mất nhiều hàm gold nhất tính theo số tuyệt đối: thêm 16 hàm không bao giờ được tìm thấy.
3. **A3V verifier:** recall chỉ kém nhẹ, nhưng gắn `edited` quá rộng. Đây là nguồn chính khiến precision thấp.
4. **A1:** ảnh hưởng nhỏ.
5. **Reviewer A2 và calibrator:** không phải nguyên nhân.

**Giới hạn của phép phân tích này:**
- Các bước nối tiếp nhau, nên chênh ở một bước phản ánh cả input mà bước trước đưa cho nó. Tỉ lệ có điều kiện ở trên giảm được nhưng không loại hết yếu tố này.
- Muốn tách chắc chắn phải chạy chéo, ví dụ A1+A2 của luna cộng A3+A3V của mini. Việc này tốn tiền.
- n = 114 hàm gold trên 50 instance, nên chênh cỡ 5 điểm vẫn nằm trong nhiễu.

## Hướng cải thiện gợi ý

Chưa thử bước nào trong danh sách này.

- **A3V:** giới hạn số nhãn `edited` cho model nhỏ, hoặc fit calibrator trên output của mini, để đặc trưng `v_edited` mang trọng số đúng với model đó. Mục tiêu là precision.
- **A3:** bỏ bước sinh giả thuyết cho model nhỏ và cho verifier xem trực tiếp seed của A2 xếp theo điểm A2. Hoặc chạy A3 bằng model mạnh hơn, vì đó là 1–2 lời gọi.
- **A2:** sinh query học thêm theo luật tất định, ví dụ tên định nghĩa trong các file chứa seed relevant, thay cho query do mini viết. Bản thử offline trước đây cho kết quả nhỏ, nên cần đo lại trên artifact mới.

## Cách xem

- **`DEEP_DIVE.md`**: phân tích sâu A2, A3 và verifier. Phần này dựng lại prompt từ graph để tách lỗi do context khỏi lỗi do suy luận; chi tiết từng hàm gold ở `a2_gold_reach.csv` và `a3_gold_in_prompt.csv`. Kết luận ở đó thay cho các đoạn A2/A3V tương ứng bên dưới (ví dụ: recall của verifier mini thực ra ngang luna khi cùng được xem gold).
- `INDEX.md`: 50 instance theo nhóm (chỉ luna trúng, chỉ mini trúng, cả hai trượt, cả hai trúng), kèm số hàm gold mini làm rơi ở từng bước.
- `instances/<id>.md`: từng instance, đặt cạnh nhau:
  - mỗi hàm gold dừng ở bước nào với từng model;
  - bảng đếm;
  - output A1, query A2 (✅ là kết quả có chứa gold);
  - seed sau review;
  - giả thuyết A3 kèm target;
  - nhãn verifier;
  - top 10 sau calibrator và đáp án.

  Hàm gold được in đậm và đánh dấu ✅.
- `funnel.csv`: mỗi dòng là một hàm gold với một model, gồm trạng thái ở mọi bước. Dùng được cho pivot.
- `summary.json`: số liệu tổng hợp.

Tạo lại toàn bộ (offline, không gọi LLM):

```
cd Jacc-v2 && .venv/bin/python .tmp/audit_v6/compare_mini_luna.py
```

Lệnh này ghi lại `INDEX.md`, `funnel.csv`, `summary.json` và `instances/`; README viết tay. Output dạng text: `.tmp/audit_v6/compare_mini_luna.txt`.
