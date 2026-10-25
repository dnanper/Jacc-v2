# Vì sao gpt-4o-mini kém luna: phân tích sâu A2, A3, verifier (2026-10-21)

Dữ liệu: 50 lần chạy mini mới (`.agent_runs/heldout6_4omini_r`) và luna bản cuối (`final-results/lite_rest`, `loc_rest`). Hai bên cùng graph, cùng calibrator. Có 114 hàm gold.

Không có lời gọi LLM nào trong phân tích này. Riêng prompt của reviewer A2 và của A3 không được lưu trong artifact, nên đã được dựng lại từ graph bằng chính code của pipeline. Prompt A3 dựng lại khớp đúng độ dài prompt đã lưu ở 100/100 lần chạy.

## Tóm tắt

| Bước | Vấn đề của mini | Loại lỗi |
|---|---|---|
| A2 review | Context đủ: cùng cỡ với luna, và có chứa tên dẫn tới gold. Nhưng mini (1) không dùng hết số query được phép và hay dừng sớm; (2) đôi khi viết cụm từ tiếng Anh thay vì tên code; (3) gắn relevant quá rộng. | Suy luận và tuân thủ chỉ dẫn, **không phải thiếu context** |
| A3 | (1) Input thiếu gold nhiều gấp đôi luna, do A2. (2) Khi gold có trong input, mini vẫn chọn gold làm target ít hơn hẳn, vì gần như chỉ chọn 3 seed đầu danh sách và bỏ qua danh sách hàm cùng file. | Cả input lẫn suy luận; phần suy luận lớn hơn |
| A3V verifier | Recall ngang luna, nhưng gắn `edited` gấp đôi: precision 26% so với 51%. Node xếp hạng 1 đúng là gold ở 13/30 instance, luna 26/30. | Khả năng phân biệt |
| Calibrator | Hệ số của `v_edited` fit trên nhãn của luna, nên nhãn `edited` kém chính xác của mini được tin như của luna. | Không khớp với model |
| A1 | Ít code ref, đôi khi chép tên phiên bản và hệ điều hành vào code ref. | Ảnh hưởng nhỏ |

## A2: reviewer thấy đủ nhưng chọn kém

**Cách bước này hoạt động** (`src/modules/seeds.py`): mỗi vòng, reviewer xem 30 candidate. Mỗi candidate gồm đường dẫn, chữ ký, docstring, tối đa 6 hàm được gọi, và các query đã tìm ra nó. Reviewer gắn nhãn từng candidate và đề xuất tối đa 8 query mới. Schema yêu cầu query mới phải là "code terms seen in relevant or maybe candidates". Như vậy query mới chỉ có thể lấy từ những gì reviewer đang nhìn thấy.

**Cách kiểm** (`.tmp/audit_v6/a2_review_audit.py`):
- Dựng lại đúng khối candidate ở từng vòng.
- Lấy mọi tên trong đó và chạy lại hàm `search` của pipeline với từng tên.
- Xếp mỗi hàm gold vào một trong bốn nhóm:
  - **found:** có query của lần chạy đã tìm ra nó;
  - **visible:** chưa được tìm ra, nhưng một tên trong candidate mà model gắn relevant/maybe sẽ tìm ra nó (lỗi chọn);
  - **irrel-only:** tên dẫn tới gold chỉ nằm trong candidate model gắn irrelevant (lỗi gắn nhãn);
  - **no bridge:** không tên nào reviewer thấy dẫn tới gold (thiếu context).

| | luna | mini |
|---|---|---|
| found | 83 | 69 |
| visible (lỗi chọn) | 12 | 21 |
| irrel-only (lỗi gắn nhãn) | 1 | 5 |
| no bridge (thiếu context) | 18 | 19 |

Ghép cặp theo từng hàm gold:
- **Luna tìm ra, mini không tìm ra: 15 hàm.**
  - 11 hàm thuộc nhóm visible: tên dẫn tới gold nằm ngay trong candidate mà mini tự gắn relevant/maybe.
  - 2 hàm thuộc nhóm irrel-only.
  - 2 hàm thuộc nhóm no bridge.
- **Thiếu context gần như bằng nhau ở hai model** (18 so với 19 hàm), và phần lớn trùng nhau (16 hàm). Đó là giới hạn chung của bước tìm kiếm, không phải điểm yếu riêng của mini.

**Context không phải nguyên nhân:**
- Mỗi vòng mini đọc khoảng 6.7 nghìn ký tự candidate, luna 6.9 nghìn.
- Phần candidate relevant/maybe của mini còn chứa nhiều tên khác nhau hơn: 280 so với 242.

**Những gì mini làm khác:**

| | luna | mini |
|---|---|---|
| Query học thêm mỗi instance (tối đa 16) | 14.0 | 9.6 |
| Lần chạy không học được query nào ở vòng 2 / vòng 3 | 0 / 0 | 5 / 11 |
| Lần chạy đủ 3 vòng | 50 | 39 (6 dừng ở vòng 2, 5 dừng ở vòng 1) |
| Query học thêm có trong khối candidate | 97% | 92% |
| Query học thêm có kết quả chứa gold | 21.7% | 16.5% |
| Số candidate gắn relevant / maybe / irrelevant | 20.5 / 25.5 / 43.2 | 25.1 / 23.3 / 31.8 |

- **Không dùng hết số query được phép.** Vòng nào không còn query mới sau khi lọc trùng là pipeline dừng tìm. Mini dừng sớm ở 11 trên 50 lần chạy. Không biết mini trả về 0 query, hay trả về toàn query đã tìm rồi bị lọc, vì output thô không được lưu.
- **Viết cụm từ thay vì tên code.**
  - Ví dụ ở [openlibrary-7929](instances/internetarchive__openlibrary-7929.md): query vòng 2 của mini là `loan status`, `patron account`, `loan eligibility`, và vòng 3 không có query nào. Luna viết `get_loans_of_user`, `get_current_loans`, `_get_ia_loans_of_user` và tìm ra gold.
  - Tên `get_loans_of_user` đã nằm sẵn trong candidate mini đọc.
  - Có 6 hàm gold bị mini bỏ lỡ mà tên của chính hàm đó đã hiện ra trước mắt reviewer (luna: 3).
- **Gắn nhãn kém phân biệt.** Mini gắn relevant nhiều hơn và irrelevant ít hơn. Query học thêm lấy từ candidate relevant, nên khi mini gắn nhầm một vùng code lạc đề là relevant, query vòng sau đi theo vùng đó.
  - Ví dụ ở [home-assistant-136739](instances/home-assistant__core-136739.md): mini đi vào integration `fritz` (router) thay vì `fritzbox` (ổ cắm thông minh).
  - Việc gắn relevant quá rộng còn làm hỏng A3, xem phần dưới.
- **Tiêu chí của nhóm visible khá rộng:** một tên chung chung (`fit`, `half`, `ASCII`) cũng tính là cầu nối nếu kết quả tìm kiếm có gold. Vì vậy con số 21 là trần trên. Các trường hợp tên gold hiện ngay trước mắt (6 hàm) mới là bằng chứng chắc chắn.

Chi tiết từng hàm gold, gồm nhóm của hai model, các tên cầu nối và query học thêm của mini: [a2_gold_reach.csv](a2_gold_reach.csv).

**Có thể thay đổi:**
1. **Bổ sung query bằng luật tất định.** 90% query học thêm của cả hai model chỉ là tên của các node đã duyệt hoặc tên hàm chúng gọi. Phần này làm bằng luật được: lấy tên các hàm được gọi bởi candidate relevant/maybe mà chưa tìm, xếp theo độ trùng với từ của issue, và bổ sung khi model trả về ít hơn 8 query.
   - Cách này chặn được việc dừng sớm và việc viết cụm từ.
   - Đo offline được trên artifact hiện có (chỉ tìm kiếm, không gọi LLM): có thêm bao nhiêu gold được tìm ra so với 21 hàm ở nhóm visible.
2. **Ép query đúng dạng.** Bỏ query có khoảng trắng hoặc không xuất hiện trong khối candidate. Nếu sau khi lọc còn ít hơn 4 query, hỏi lại một lần kèm danh sách đã tìm. Tốn thêm tối đa 1 lời gọi mỗi vòng.
3. **Giới hạn relevant.** Chỉ cho tối đa khoảng 8 candidate là relevant mỗi vòng, phần còn lại là maybe. Cách này giảm trôi đề cho query vòng sau và giảm phình input A3.

## A3: input thiếu gold, và có gold cũng không chọn

**Cách bước này hoạt động** (`src/modules/hypotheses.py`):
- Prompt gồm 40 seed đầu của A2 (relevant xếp trước maybe, kèm vài dòng code với seed relevant), chữ ký các hàm khác trong những file có seed relevant (`functions_in_seed_files`), và các cạnh graph giữa chúng.
- Model viết giả thuyết và chọn target bằng alias S1..Sn.

**Cách kiểm** (`.tmp/audit_v6/a3_target_audit.py`): dựng lại đúng prompt A3 của từng lần chạy, rồi xác định mỗi hàm gold nằm ở đâu trong prompt và có được chọn làm target không.

**Gold nằm ở đâu trong prompt A3:**

| Vị trí | luna | mini |
|---|---|---|
| seed relevant | 57 | 49 |
| seed maybe | 8 | 4 |
| hàm cùng file | 29 | 21 |
| **không có trong prompt** | **20** | **40** |

Phần do input: mini có 40 hàm gold không bao giờ xuất hiện trong prompt A3, luna 20. Đây là hậu quả từ A2.

**Khi gold có trong prompt, tỉ lệ được chọn làm target:**

| Vị trí của gold | luna (2 mẫu) | luna (mẫu 1) | mini (1 mẫu) |
|---|---|---|---|
| seed relevant | 86% | 72% | 35% |
| hàm cùng file | 24% | 14% | **0%** |
| seed maybe | 12% | 12% | 0% |

Trên 49 hàm gold là seed trong prompt của cả hai model: luna chọn 31 (mẫu 1), mini chọn 17. Vậy dù input tương đương và cùng số mẫu, mini vẫn chọn gold ít hơn khoảng một nửa. Đây là phần do suy luận, và lớn hơn phần do input.

**Mini chọn target thế nào:**

| | luna (mẫu 1) | mini |
|---|---|---|
| Số giả thuyết / số target mỗi giả thuyết | 3.1 / 1.77 | 2.1 / 1.08 |
| Vị trí trung vị của target trong danh sách | S9 | **S3** |
| Target nằm trong 3 seed đầu | 22% | **57%** |
| Target là hàm cùng file | 20% | 3% |
| Target là gold / nằm trong file gold | 27% / 50% | 18% / 41% |

Tỉ lệ được chọn khi gold là seed, theo vị trí của gold trong danh sách (mẫu 1):

| Vị trí của gold | S1–3 | S4–10 | S11–20 | S21+ |
|---|---|---|---|---|
| luna | 16/20 | 16/26 | 6/11 | 4/8 |
| mini | 10/15 | 5/13 | 2/12 | **0/13** |

**Diễn giải:**
- **Mini bám đầu danh sách.** Gold ở S1–3 thì mini chọn gần bằng luna. Gold ở sâu hơn thì mini gần như không chọn. Luna đọc hết danh sách.
- **Mini bỏ qua danh sách hàm cùng file.** Trong 21 lần gold chỉ nằm ở danh sách này, mini không chọn lần nào. Luna chọn được 7/29 và hay đặt target vào đây: đây là cách luna tìm ra hàm cần sửa nằm cạnh seed.
- **Prompt của mini dài hơn:** trung vị 37.7 nghìn ký tự so với 28.3 nghìn, với 257 hàm cùng file so với 131. Nguyên nhân là mini gắn relevant nhiều hơn ở A2 (24.7 so với 20.0 seed relevant trong prompt), nên nhiều file hơn được đưa vào. Prompt dài khiến gold bị chìm sâu hơn, mà mini lại chỉ đọc đầu danh sách.
- **Mini ít khi đặt target qua cạnh graph** (target `via` một node lân cận): 3/115, luna 19/494. 42/150 giả thuyết thô của mini bị loại vì đặt dự đoán chính lên node Class/File. Các giả thuyết này chỉ chứa thêm 2 hàm gold, nên không phải nguồn mất chính.

Ví dụ ở [home-assistant-136739](instances/home-assistant__core-136739.md): H1 của luna nhắm đúng `FritzboxSwitch.async_turn_on/off`. Các target của mini đều là seed ở đầu danh sách, trong integration sai.

Chi tiết từng hàm gold: [a3_gold_in_prompt.csv](a3_gold_in_prompt.csv).

**Có thể thay đổi:**
1. **Rút gọn và chia nhỏ input cho model yếu.**
   - Bớt danh sách hàm cùng file: chỉ giữ các hàm có tên trùng từ của issue, hoặc tối đa 10 hàm mỗi file.
   - Chia prompt theo từng file chứa seed relevant (mỗi lời gọi một file), để gold không nằm ở vị trí sâu.
2. **Xáo thứ tự seed giữa các mẫu và dùng 2–3 mẫu.** Thiên lệch vị trí là lỗi theo vị trí, nên xáo thứ tự rồi gộp kết quả sẽ phân tán nó. Lần thử K=3 ở A14 không xáo thứ tự, chỉ tăng temperature.
3. **Bỏ A3 cho model yếu.** A3 của mini làm thứ hạng xấu đi nhiều hơn là giúp. Để verifier xem trực tiếp seed của A2 kèm các hàm cùng file đã lọc. Cần đo vì calibrator đang dùng đặc trưng của A3.
4. **Chạy riêng A3 bằng model mạnh hơn** (1–2 lời gọi mỗi instance), các bước khác giữ mini.

## Verifier: bắt gold ngang luna, nhưng gắn `edited` quá rộng

Số liệu chỉ lấy từ artifact (`.tmp/audit_v6/a3v_verifier_audit.py`):

| | luna | mini |
|---|---|---|
| Nhãn `edited` mỗi instance | 2.3 | 4.4 |
| Instance có ≥ 6 nhãn `edited` | 6 | 15 |
| Precision của `edited`, mức function / mức file | 45% / 62% | 16% / 36% |
| Ước lượng số hàm bị sửa trừ số gold thật | +0.7 | +2.4 |
| Node không được gắn nhãn (trên 40 node) | 0 | 1.4 |
| Node xếp hạng 1 là gold | 35/50 | 13/50 |

Tính riêng trên **30 instance mà cả hai verifier đều được xem ít nhất một gold**:

| | luna | mini |
|---|---|---|
| Recall trên gold được xem | 68% | 64% |
| Precision của `edited` | 51% | 26% |
| Node xếp hạng 1 là gold | 26/30 | 13/30 |

Trên 53 hàm gold mà cả hai verifier đều được xem, luna gắn `edited` 35 lần, mini 36 lần.

**Diễn giải:**
- Verifier của mini **không bỏ sót gold nhiều hơn**. Nó **không phân biệt được** hàm nào thật sự bị sửa: gắn `edited` cho cả hàm liên quan, và đoán patch lớn hơn thực tế.
- Không có thiên lệch theo vị trí trong thứ tự xáo trộn (57% nhãn `edited` nằm ở nửa đầu, ở cả hai model).
- Nguồn mất recall của verifier mini là do không được xem gold (31 instance so với 42), tức lỗi từ phía trên.

**Có thể thay đổi:**
1. Với model yếu, dùng `ranking` (top 5) của verifier thay cho nhãn `edited` làm đặc trưng chính. Hoặc chỉ tin nhãn `edited` nằm trong top ranking.
2. Fit calibrator riêng cho mini trên `swe_train` (khoảng $1.8). Hệ số của `v_edited` hiện fit trên nhãn của luna (precision khoảng 50%), nên đang quá tin vào nhãn của mini (precision khoảng 20%).
3. Giới hạn số nhãn `edited` theo `edited_count`, hoặc theo ngưỡng 3.

## Các chỗ thụt lùi khác

- **Không được xem bởi verifier:** 9 hàm gold của mini là candidate nhưng nằm ngoài 40 node verifier xem (luna 3). Thứ tự để chọn 40 node này dựa trên đặc trưng của A3, nên đây là hậu quả từ A3.
- **Verifier bỏ sót nhãn:** 4 hàm gold đã được xem nhưng mini không gắn nhãn. Pipeline coi chúng là không có nhãn nên chúng rơi khỏi đáp án.
- **A1:** mini ghi 5.3 code ref so với 16.7 của luna, và đôi khi là thông tin môi trường (`core-2024.2.5`, `Home Assistant OS`). Gold do query từ code ref tìm ra kém 6 điểm. Ảnh hưởng nhỏ, vì issue hiếm khi nêu tên hàm cần sửa.
- **Calibrator:** xem phần verifier.

## Kết luận

1. **A2 thiếu do suy luận và tuân thủ chỉ dẫn, không do context.** Bằng chứng: context cùng cỡ, và 11/15 hàm gold mini bỏ lỡ có tên dẫn tới chúng ngay trong candidate mini tự gắn relevant/maybe. Sửa được bằng luật tất định, đo offline được.
2. **A3 thiếu do cả input (40 so với 20 hàm gold không có trong prompt) lẫn suy luận.** Khi gold có trong input, mini chọn được khoảng một nửa so với luna, vì bám vào 3 seed đầu và bỏ qua hàm cùng file. Phần suy luận lớn hơn phần input.
3. **Verifier không kém về recall mà kém về precision và xếp hạng.** Đây là nguồn chính khiến PRE thấp.

**Đề xuất thứ tự thử:**
1. Thay A2 bằng luật tất định: đo offline trước, $0.
2. Chạy A3 trên input rút gọn, xáo thứ tự, nhiều mẫu.
3. Fit calibrator riêng cho mini trên `swe_train`.

Mọi thay đổi cần đánh giá trên một tập chưa xem, không trên held-out 6.

## Tạo lại

Phân tích A2 và A3 mở graph. Mỗi instance chạy trong một process riêng có trần bộ nhớ cgroup, nên một instance vượt trần chỉ làm chết process đó. RAM đỉnh đo được là 0.52 GB (home-assistant).

```
cd Jacc-v2
bash .tmp/audit_v6/run_parts.sh .tmp/audit_v6/a3_target_audit.py .tmp/audit_v6/a3_parts 2G  # A3
.venv/bin/python .tmp/audit_v6/a3v_verifier_audit.py             # verifier: chỉ đọc artifact
```

`a2_review_audit.py` vẫn là script chạy một lần trong một process. Nó đã chạy xong 50/50 qua `capped.py` trước khi máy tràn RAM. Muốn chạy lại thì nên tách theo instance như A3.

## Thử các đề xuất offline (2026-10-21, $0)

Luật của cả hai phép thử được chốt trước khi đo và không chỉnh theo kết quả. Held-out 6 đã được xem nhiều lần, nên các số dưới đây chỉ dùng để chọn hướng, không dùng để báo cáo.

### A2: bổ sung query học thêm bằng tên hàm được gọi (`.tmp/audit_v6/a2_rule_sim.py`)

**Luật:** sau mỗi vòng review, giữ query của model. Nếu còn thiếu so với 8 query thì bổ sung bằng tên các hàm được gọi bởi candidate relevant (rồi tới maybe), lấy từ cạnh CALLS. Bỏ tên đã tìm, tên ngắn hơn 4 ký tự, dunder và builtin. Xếp theo số từ trùng với issue, rồi theo vị trí candidate.

**Giới hạn của mô phỏng:** đo xem gold có nằm trong kết quả tìm kiếm không. Không mô phỏng được việc reviewer gắn nhãn cho các node mới, vì việc đó cần LLM.

| | gold được tìm ra | thay đổi | query thêm / instance | node mới chưa duyệt / instance |
|---|---|---|---|---|
| mini thực tế | 69 / 114 (60.5%) | | | |
| mini + luật | 74 (64.9%) | +5 gold ở 3 instance; phục hồi 4/15 gold luna tìm được mà mini bỏ lỡ | 5.4 | 70 |
| mini + luật + bỏ query có khoảng trắng | 74 (64.9%) | +5 | 6.1 | 77 |
| luna + luật | 83 (72.8%) | 0 | 1.6 | 22 |

**Kết luận:** lợi ích nhỏ (+5 gold trên trần 21 của nhóm visible), trong khi mỗi instance có thêm khoảng 70 node cạnh tranh 30 chỗ trong cửa sổ duyệt. Tên hàm được gọi không phải cầu nối chính. Các cầu nối mà luna dùng là tên được chọn có suy luận theo issue, luật đơn giản không thay được.

### Verifier: chỉ tin `edited` khi node nằm trong ranking (`.tmp/audit_v6/verifier_variants.py`)

Calibrator giữ nguyên, không fit lại. V1: `edited` nằm ngoài top 5 của ranking thì hạ thành `maybe`. V2: chỉ giữ `edited` cho top 3.

Mức function, SL / REC / PRE / F1 | số hàm trong đáp án:

| | Lite | LocBench |
|---|---|---|
| luna base | 64.0 / 74.7 / 38.1 / 45.3 \| 4.3 | 44.0 / 57.5 / 33.4 / 36.4 \| 5.7 |
| luna V1 | 64.0 / 74.7 / 38.3 / 45.6 \| 4.2 | 44.0 / 57.5 / 33.9 / 37.0 \| 5.1 |
| luna V2 | 60.0 / 72.7 / 37.9 / 45.0 \| 4.1 | 44.0 / 57.5 / 34.0 / 37.0 \| 5.0 |
| mini base | 40.0 / 44.0 / 18.0 / 22.4 \| 5.8 | 32.0 / 48.1 / 23.0 / 27.3 \| 5.5 |
| mini V1 | 36.0 / 40.0 / 18.1 / 22.5 \| 4.8 | 32.0 / 48.1 / 24.1 / 28.4 \| 4.9 |
| mini V2 | 36.0 / 40.0 / 18.6 / 23.1 \| 4.6 | 32.0 / 48.1 / 24.7 / 29.1 \| 4.4 |

**Kết luận:** đáp án gọn hơn khoảng 1 hàm, nhưng precision của mini chỉ tăng 1–2 điểm, nằm trong nhiễu. Nhãn `edited` sai của mini phần lớn cũng nằm trong top ranking của chính nó, nên chỗ yếu là verifier xếp hạng sai (hạng 1 đúng gold ở 13/30 instance, luna 26/30). Lọc nhãn sau đó không sửa được. Fit lại calibrator cũng khó giúp nhiều: lần fit lại ở A15 cũng không có tác dụng.

### Ý nghĩa

Các cách sửa sau output (luật cho A2, lọc nhãn verifier) đều cho lợi ích trong vùng nhiễu. Chỗ thiếu của mini là chất lượng suy luận ở ba lời gọi: chọn query ở A2, chọn target ở A3, phân biệt ở verifier. Muốn cải thiện thật thì phải đổi input của các lời gọi đó, hoặc đổi model ở các bước đó. Cả hai đều cần chạy có trả phí.

## Thí nghiệm A3-x (ghi trước khi chạy, 2026-10-21)

**Code:** nhánh `exp/4omini-a3x`, commit `ee61ac9`. Hai biến môi trường, mặc định tắt. Khi tắt, prompt không đổi: đã kiểm khớp 50/50 với độ dài prompt đã lưu.
- `JACC_A3_FILE_FUNCS=10`: mỗi file có seed relevant chỉ liệt kê tối đa 10 hàm (bình thường 40).
- `JACC_A3_SHUFFLE=1` với `--a3-samples 3`:
  - mẫu 0 giữ thứ tự seed của A2;
  - mẫu 1 và 2 xáo thứ tự seed (seed cố định theo issue) và đánh lại alias theo thứ tự mới;
  - output được quy về một hệ alias chung trước khi kiểm tra và gộp.

**Chạy:** gpt-4o-mini, A1 và A2 chép từ `.agent_runs/heldout6_4omini_r`. Chỉ A3 (3 lời gọi) và verifier (1 lời gọi) gọi model. Calibrator swe_train. Workspace `.agent_runs/heldout6_4omini_a3x`. Script `.tmp/run_heldout6_4omini_a3x.sh`: chạy pilot 2 id trước, sau đó phần còn lại. Bộ nhớ được chặn bằng cgroup (trần 10 GB) và `capped.py`, giống `run_heldout7.sh`.

**Kiểm offline trước khi chạy** (`.tmp/audit_v6/a3x_precheck.py`):
- Prompt mỗi mẫu: trung vị 25.5 nghìn ký tự, so với 37.7 nghìn.
- Gold là seed nằm trong top 3 của ít nhất một mẫu: 21/53, so với 15/53 khi chỉ có thứ tự gốc.

**So với mini base, ghép cặp trên 50 id, cùng A1 và A2:**
1. Tỉ lệ gold có trong prompt được chọn làm target (base: 17/74).
2. Mức function, arm ngưỡng: SL, REC, PRE (base: Lite 40.0 / 44.0 / 18.0, Loc 32.0 / 48.1 / 23.0).
3. Chi phí thật mỗi instance.

Coi là có tác dụng nếu (1) tăng rõ và (2) không giảm. Với n = 50, thay đổi của SL hay REC dưới khoảng 5 điểm vẫn nằm trong nhiễu. Đây là bước phát triển trên held-out 6 đã xem; muốn báo cáo được thì cần một tập mới.

### Kết quả A3-x (2026-10-21; `.agent_runs/heldout6_4omini_a3x/score.txt`)

**Lần chạy:** 50/50, không lỗi, không tràn RAM. A3 cộng verifier tốn $0.015 mỗi instance; A1 và A2 dùng lại.

**Pilot:** ở cả 2 id pilot, verifier được xem đúng cùng 40 candidate như bản gốc, chỉ khác thứ tự. Riêng việc đổi thứ tự đã làm `pm4-graders__3ES-72` từ 0 lên 6 nhãn `edited` đúng gold, dù A3 không nhắm trúng gold nào. Verifier của mini rất nhạy với thứ tự candidate, nên điểm cuối lẫn nhiễu này.

**(1) A3 chọn gold làm target** (thước đo không phụ thuộc verifier):

| | base | A3-x | luna |
|---|---|---|---|
| Gold là target của ít nhất một giả thuyết (trên 114) | 18 | **24** | 57 |
| Gold là seed trong prompt, được chọn làm target (trên 53) | 18 | **23** | — |

**(2) Mức function, arm ngưỡng, SL / REC / PRE / F1:**

| | Lite | LocBench |
|---|---|---|
| base | 40.0 / 44.0 / 18.0 / 22.4 | 32.0 / 48.1 / 23.0 / 27.3 |
| A3-x | 36.0 / 42.7 / 21.0 / 24.7 | 32.0 / 48.2 / 23.5 / 26.6 |

Hiệu ghép cặp trên 50 id (KTC 95%): SL −2.0 [−10, +4], REC −0.6 [−7, +6], PRE +1.7 [−2, +6], F1 +0.8 [−3, +5].

**Kết luận:**
- Thay đổi A3 giúp mini chọn đúng gold nhiều hơn (+6 hàm), nhưng vẫn xa luna (24 so với 57).
- Phần cải thiện này không truyền tới đáp án cuối: mọi hiệu đều có KTC chứa 0.
- Đáp án cuối do verifier quyết định, mà verifier của mini vừa phân biệt kém vừa nhạy với thứ tự. Tiêu chí (1) chỉ tăng vừa phải, tiêu chí (2) không đổi. Không áp dụng thay đổi này.
- Hướng tiếp theo đáng thử là làm verifier ổn định hơn: chạy verifier nhiều lần với thứ tự khác nhau rồi gộp phiếu.

## Audit lại sau A3-x (2026-10-21)

Phễu từng bước của bản mới, sinh bằng `MINI_WS=.agent_runs/heldout6_4omini_a3x OUT=docs/compare-4omini-luna/a3x .venv/bin/python .tmp/audit_v6/compare_mini_luna.py`. Trang từng instance của bản mới nằm ở `a3x/instances/`. Mọi số tính trên 114 hàm gold của 50 instance.

| Bước | luna | mini gốc | mini A3-x |
|---|---|---|---|
| A2: gold được tìm ra | 72.8 | 60.5 | 60.5 (dùng lại A2) |
| A2: gold được giữ làm seed | 57.0 | 46.5 | 46.5 |
| A3: gold là target của ít nhất một giả thuyết | 50.0 | 15.8 | **21.1** |
| A3: gold là target của H1 | 35.1 | 10.5 | 11.4 |
| A3: chọn gold làm target, khi gold là seed | 76.9% | 34.0% | **43.4%** |
| Gold trong danh sách candidate | 67.5 | 57.9 | 56.1 |
| Gold được verifier xem | 64.9 | 50.0 | 50.0 |
| Verifier gắn `edited`, khi gold được xem | 71.6% | 63.2% | 71.9% (*) |
| Hạng 1 sau calibrator | 31.6 | 13.2 | 14.9 |
| Hạng ≤ 3 | 46.5 | 25.4 | 26.3 |
| **Đáp án cuối** | **52.6** | **35.1** | **37.7** |
| Nhãn `edited` mỗi instance / precision | 2.3 / 45% | 4.4 / 16% | 4.4 / 19% |
| Node verifier xếp hạng 1 là gold | 35/50 | 13/50 | 15/50 |

(*) Không phải tác dụng của A3. Verifier không thấy output của A3. Ở 24 instance mà bản gốc và A3-x đưa cho verifier đúng cùng 40 candidate (chỉ khác thứ tự):
- 39% số node được gắn `edited` ở một trong hai lần bị đổi nhãn (56/143);
- tỉ lệ nhãn trùng nhau là 88%;
- trên hàm gold, 7 hàm được gắn `edited` mới, 1 hàm mất nhãn `edited`.

Verifier của mini có nhiễu lớn theo thứ tự candidate, và phần tăng 63% → 72% nằm trong nhiễu đó.

Số hàm gold bị mất, theo bước đầu tiên làm rơi (luna / mini gốc / mini A3-x):
- A2 tìm kiếm: 22 / 38 / 39;
- A2 cửa sổ duyệt: 14 / 10 / 11;
- A3V không được đưa verifier xem: 3 / 9 / 7;
- verifier gắn `not_edited`: 12 / 10 / 13;
- verifier gắn `maybe`: 2 / 3 / 0;
- verifier không trả nhãn: 0 / 4 / 1;
- **vào đáp án: 60 / 40 / 43.**

**Khác biệt sau khi sửa:**
- **A3:** khi gold là seed, mini chọn nó làm target 43% số lần (trước 34%, luna 77%). Tổng số giả thuyết giữ lại tăng từ 2.1 lên 5.3, ngang luna, nhưng mỗi giả thuyết vẫn chỉ có 1.07 target (luna 1.83). Tỉ lệ giả thuyết thô bị loại vẫn cao: 98/452 bị loại vì thiếu dự đoán chính, thường do đặt dự đoán lên node Class/File (luna 10/332).
- **Các bước sau A3 gần như không đổi:** gold đứng hạng 1 từ 13.2 lên 14.9, gold trong top 3 từ 25.4 lên 26.3. Đáp án cuối thêm 3 hàm gold (40 → 43), nằm trong nhiễu của verifier.
- **A1, A2:** không đổi, vì dùng lại artifact. Đây vẫn là nguồn mất lớn nhất: 39 hàm gold không query nào tìm thấy, luna 22.

**Thứ tự nguồn mất hiện tại của mini so với luna:**
1. A2 tìm kiếm: chọn query, chủ yếu do suy luận.
2. Verifier: phân biệt kém, cộng nhiễu theo thứ tự.
3. A3: đã thu hẹp được một phần nhưng vẫn kém xa.

## Thí nghiệm prompt cho A2 (ghi trước khi chạy, 2026-10-21)

**Câu hỏi:** khoảng cách ở A2 có sửa được bằng prompt không?

**Cách làm:** dựng lại đúng vòng review 1 của 50 lần chạy mini (cùng graph, cùng candidate, cùng danh sách đã tìm), rồi gọi lại riêng bước review với các biến thể prompt. Mọi thứ khác giữ nguyên, nên chênh lệch chỉ đến từ prompt. Script `.tmp/audit_v6/a2_prompt_replay.py`, chạy bằng `.tmp/run_a2_prompt_replay.sh pilot|all`.

| Biến thể | Nội dung | Kỹ thuật |
|---|---|---|
| V0 | Prompt và schema hiện tại; lưu output thô | Đối chứng |
| V1 | V0 cộng luật viết query ngay trong thân prompt: đúng 8 query, chép nguyên tên code từ candidate, không lặp tên đã tìm | Chỉ dẫn rõ ràng |
| V2 | V1 cộng trường `analysis` (văn bản tự do) đặt trước `new_queries` | CoT, suy luận trước khi trả lời |
| V3 | Lời gọi riêng chỉ để lập kế hoạch query, chỉ đưa các candidate mini đã gắn relevant/maybe, có `analysis` | Tách tác vụ |
| V4 | V3 cộng 2 ví dụ lấy từ luna trên swe_train: `django__django-10316` và `django__django-13665`, chọn theo luật cố định, không lấy từ held-out 6 | Few-shot |
| L0 | luna với prompt V0 trên đúng context của mini | Trần của model |

**Thước đo** (không cần LLM):
- số query còn lại sau bộ lọc của pipeline (tối đa 8);
- số lần trả 0 query;
- số query là cụm từ;
- số query trùng với query đã tìm;
- tỉ lệ query chép từ candidate;
- **số hàm gold mà kết quả tìm kiếm chạm tới trong khi vòng 1 chưa chạm tới.**

Phép kiểm tính hợp lệ: V0 ở temperature 0 phải gần như trùng với query vòng 2 thật của lần chạy gốc.

**Giới hạn:** chỉ đo vòng 2 (một bước), không đo tác động lên các vòng sau và lên đáp án cuối. Đây là phép đo phát triển trên held-out 6.

### Kết quả thí nghiệm prompt A2 (2026-10-22; `.tmp/audit_v6/a2_replay_parts/`)

50/50 instance, không lỗi, RAM đỉnh 0.63 GB mỗi process. Chi phí: mini $0.49, luna 224 nghìn token.

Có 114 hàm gold; vòng 1 đã chạm tới 66 hàm, còn lại 48 hàm để vòng 2 tìm.

| | query hợp lệ / instance | lần ra 0 query | cụm từ | trùng query đã tìm | chép từ candidate | **gold mới** (instance) |
|---|---|---|---|---|---|---|
| V0, prompt hiện tại | 5.3 | 4 | 59 | 116 | 94% | **0** (0) |
| V1, luật trong thân prompt | 7.7 | 0 | 0 | 14 | 99% | 3 (3) |
| V2, V1 + CoT | 7.5 | 0 | 1 | 25 | 88% | 5 (4) |
| V3, lời gọi riêng + CoT | 7.6 | 0 | 0 | 22 | 85% | 4 (3) |
| **V4, V3 + few-shot** | 7.8 | 0 | 0 | 10 | 78% | **7 (5)** |
| L0, luna + prompt V0 | 7.5 | 0 | 4 | 11 | 88% | **7 (5)** |

V0 lặp lại 57% số query vòng 2 thật (pilot: 81%). API ở temperature 0 không hoàn toàn tất định, nên V0, chứ không phải lần chạy cũ, là nhóm đối chứng.

**Vì sao có vòng mini ra 0 query:** mini vẫn trả query, nhưng toàn query đã tìm hoặc cụm từ, nên bộ lọc của pipeline loại hết. Ví dụ:
- `django-12125`: `Outer`, `Inner`, `CreateModel` (đã tìm ở vòng 1);
- `sympy-11870`: `trigsimp limitations`, `trigsimp output`.

Trên cả 50 instance, V0 có 116 query trùng query đã tìm và 59 cụm từ. Chỉ cần thêm luật vào thân prompt (V1) là hết lỗi này.

Gold mới mà từng biến thể tìm thêm được (x = có):

| instance | gold | V0 | V1 | V2 | V3 | V4 | L0 |
|---|---|---|---|---|---|---|---|
| django-12125 | TypeSerializer.serialize | | | | | | x |
| gammasim-1183 | DatabaseHandler.get_simulation_c… | | x | | | x | x |
| gammasim-1183 | get_array_elements_of_type | | | | x | x | x |
| gammasim-1183 | main | | | x | | | |
| openlibrary-7929 | borrow.POST | | x | x | x | x | x |
| matplotlib-23314 | Axes3D.draw | | | | | | x |
| nautobot-6837 | CustomField.validate | | | | | x | |
| pytest-5103 | AssertionRewriter.visit_Call_35 | | | x | x | x | x |
| pytest-5103 | AssertionRewriter.visit_Call_legacy | | | x | x | x | x |
| sklearn-11281 | BaseMixture.fit | | | x | | x | |
| sklearn-25500 | IsotonicRegression.predict | | x | | | | |

**Kết luận:**
- Ở bước học query, khoảng cách giữa mini và luna phần lớn **do prompt**. Với cùng context, mini dùng prompt V4 (tách lời gọi + CoT + 2 ví dụ few-shot) tìm thêm 7 hàm gold ở 5 instance, bằng luna dùng prompt hiện tại; 5/7 hàm trùng với luna. Prompt hiện tại cho mini 0 hàm.
- Thứ tự đóng góp: luật rõ ràng trong thân prompt sửa lỗi lặp và lỗi cụm từ (+3); CoT thêm khoảng +1–2; few-shot thêm khoảng +2.
- **Giới hạn:**
  - Số nhỏ: 7/48 hàm gold, 5/50 instance. Kiểm dấu một phía V4 so với V0: p ≈ 0.03.
  - Chỉ đo một bước: vòng 2 tìm ra gold, chưa đo gold có được duyệt, có thành seed, có vào đáp án hay không.
  - Đây là phép đo phát triển trên held-out 6.
- **Bước tiếp:** đưa V4 vào `seeds.py` sau biến môi trường, rồi chạy lại mini từ A2 trên 50 id (dùng lại A1) để đo đáp án cuối.

## A2: đưa planner V4 vào pipeline (2026-10-22, chưa chạy)

Nhánh `exp/4omini-a2plan`, commit `253de18`. Bật bằng `JACC_A2_PLAN=1`. Sau mỗi vòng review, một lời gọi `QueryPlan` riêng chọn query cho vòng sau từ các candidate mà reviewer giữ lại. Prompt, luật và 2 ví dụ được chép nguyên từ biến thể V4 của thí nghiệm replay; ví dụ được cố định thành hằng số trong code. Khi không bật thì A2 không đổi. A2 đã cache chỉ được dùng lại nếu cờ planner khớp. Có test đơn vị.

## Thí nghiệm prompt cho A3 (ghi trước khi chạy, 2026-10-22)

**Input:** đúng prompt A3 của 50 lần chạy mini (`heldout6_4omini_r`, code đóng băng, 40 hàm mỗi file, thứ tự của A2). Mỗi biến thể 1 mẫu, temperature 0. Script `.tmp/audit_v6/a3_prompt_replay.py`, chạy bằng `.tmp/run_a3_prompt_replay.sh pilot|all`.

| Biến thể | Nội dung | Nhắm vào lỗi |
|---|---|---|
| C0 | Prompt hiện tại | Đối chứng |
| C1 | C0 cộng luật: thứ tự không phải xếp hạng; chỗ cần sửa thường là hàm cùng file; ít nhất 4 giả thuyết về các hàm khác nhau | Bám đầu danh sách, bỏ qua hàm cùng file |
| C2 | C1 cộng trường `analysis` đặt trước: lần theo kịch bản lỗi từng bước, gán mỗi bước cho một alias | Suy luận (CoT) |
| C3 | Mỗi file có seed một lời gọi (tối đa 6 file theo thứ tự seed); mỗi lời gọi chỉ thấy seed và hàm của file đó; luật C1 | Prompt dài, gold nằm sâu, hàm cùng file |
| C4 | C2 cộng 2 ví dụ của luna trên swe_train: `django__django-11377` (target là hàm cùng file) và `django__django-13689` (target là seed S14), chọn theo luật cố định | Few-shot |
| L0 | luna với prompt C0 | Trần của model |

**Thước đo** (không cần LLM):
- gold được chọn làm target, chia theo vị trí của gold trong prompt C0 (seed / hàm cùng file / không có);
- số target mỗi giả thuyết;
- tỉ lệ target nằm ở S1–S3;
- tỉ lệ target là hàm cùng file;
- số giả thuyết bị loại.

Tham chiếu từ trước (2 mẫu, luna trên input của chính nó): gold là seed được chọn 72% với mẫu 1. C3 còn đưa vào prompt các hàm của file chỉ có seed maybe, nên phần input cũng thay đổi; sẽ báo riêng.

**Giới hạn:** chỉ đo bước A3; phép đo phát triển trên held-out 6.

### Kết quả thí nghiệm prompt A3 (2026-10-22; `.tmp/audit_v6/a3_replay_parts/`)

50/50 instance, không lỗi, RAM đỉnh 0.58 GB mỗi process. Chi phí: mini $1.41, luna 740 nghìn token. Gold nằm trong prompt C0: 53 là seed, 21 là hàm cùng file, 40 không có trong prompt. Gold có trong ít nhất một prompt theo file của C3: 67.

| | giả thuyết / instance | target / giả thuyết | gold được chọn (seed / hàm cùng file) | target ở S1–3 | target là hàm cùng file | giả thuyết bị loại |
|---|---|---|---|---|---|---|
| C0 | 2.2 | 1.06 | 19 (19 / 0) | 55% | 2% | 85 |
| C1 luật | 3.0 | 1.28 | 23 (23 / 0) | 45% | 5% | 103 |
| C2 + CoT | 3.0 | 1.21 | 22 (21 / 1) | 42% | 4% | 98 |
| C3 chia theo file | 17.6 | 1.54 | **43** (39 / 4) | 10% | 45% | 714 |
| C4 + few-shot | 2.8 | 1.14 | 26 (23 / 3) | 48% | 6% | 117 |
| L0 luna | 3.0 | 1.93 | **44** (33 / 11) | 20% | 35% | 10 |

**So với cùng số target**, cắt còn k target đầu mỗi instance (C3 lấy xen kẽ theo file):

| | k=3 | k=6 | k=10 | tất cả | target / instance | precision |
|---|---|---|---|---|---|---|
| C0 | 19 | 19 | 19 | 19 | 2.2 | 17.0% |
| C1 | 22 | 23 | 23 | 23 | 3.4 | 13.5% |
| C2 | 21 | 22 | 22 | 22 | 3.1 | 14.0% |
| C3 | 19 | 23 | 32 | 43 | 17.9 | 4.8% |
| C4 | 22 | 26 | 26 | 26 | 2.9 | 18.2% |
| L0 | **36** | **40** | 40 | 44 | 4.8 | 18.3% |

Số instance có ít nhất một target là gold (k=6): C0 18, C1 20, C2 21, C3 21, C4 24, L0 32.

**Kết luận:**
- **Prompt chỉ thu hẹp một phần khoảng cách ở A3.** Với cùng số target, biến thể tốt nhất (C4: luật + CoT + few-shot) chọn trúng 26 hàm gold, so với 19 của C0 và 40 của luna. Phần còn lại là năng lực của model. Điều này khác với A2, nơi prompt kéo mini lên ngang luna.
- **Chia theo file (C3) tăng recall nhờ chọn nhiều** (43 hàm khi giữ hết target), nhưng thứ tự không tốt: với k=6 chỉ bằng C1. C3 cũng làm biến mất hiệu ứng bám đầu danh sách (10% target ở S1–3) và chọn được hàm cùng file (45% target). Muốn C3 có ích thì bước sau phải lọc được, mà verifier của mini lại kém ở chính việc lọc.
- **CoT tự nó không giúp:** phần `analysis` của mini chung chung và không gắn được vào alias nào.
- **Lựa chọn cho pipeline:**
  - C4: rẻ, giữ nguyên kích thước đầu ra, +7 hàm gold;
  - C3: tăng recall, nhưng phụ thuộc verifier;
  - chạy riêng A3 bằng model mạnh hơn: 1 lời gọi, bằng trần luna.

## Lần chạy pipeline: planner A2 + C4 cho A3 (ghi trước khi chạy, 2026-10-22)

**Code:** nhánh `exp/4omini-a2plan`:
- commit `253de18`: planner A2;
- commit `2c9055d`: C4 cho A3. Prompt C4 trong pipeline đã được kiểm khớp đúng với prompt dùng trong replay, trên 2 instance.

**Chạy:** gpt-4o-mini với `JACC_A2_PLAN=1 JACC_A3_PROMPT=c4`, 1 mẫu A3, calibrator swe_train. A1 chép từ `heldout6_4omini_r`; A2, A3 và verifier gọi model. Workspace `.agent_runs/heldout6_4omini_a2p_c4`, script `.tmp/run_heldout6_4omini_a2p_c4.sh pilot|all`. Bộ nhớ chặn bằng cgroup (trần 10 GB) cộng `capped.py`.

**So sánh:** ghép cặp với mini gốc (`heldout6_4omini_r`, cùng A1) và với luna, trên 50 id.
- Phễu từng bước bằng `compare_mini_luna.py`: gold được tìm ra ở A2, gold là seed, gold là target A3, gold được verifier xem, gold vào đáp án.
- Mức function, SL / REC / PRE / F1.
- Chi phí thật.

Lưu ý khi đọc kết quả: verifier của mini nhạy với thứ tự candidate, nên chênh lệch ở đáp án cuối lẫn nhiễu này. Các bước A2 và A3 đo được sạch hơn. Đây là phép đo phát triển trên held-out 6.

### Kết quả: planner A2 + C4 cho A3 trong pipeline (2026-10-22; `.agent_runs/heldout6_4omini_a2p_c4/score.txt`)

50/50, không lỗi, không tràn RAM. Cấu hình đúng ở cả 50 lần chạy: A2 có planner, A3 dùng C4 với 1 mẫu, calibrator swe_train. Chi phí $0.022 mỗi instance (mini gốc $0.019). Phễu sinh bằng `MINI_WS=.agent_runs/heldout6_4omini_a2p_c4 OUT=docs/compare-4omini-luna/a2p_c4 .venv/bin/python .tmp/audit_v6/compare_mini_luna.py`.

| Bước (% trên 114 hàm gold) | luna | mini gốc | mini A3-x | **mini A2p + C4** |
|---|---|---|---|---|
| A2: gold được tìm ra | 72.8 | 60.5 | 60.5 | **65.8** |
| … do query học thêm | 62.3 | 38.6 | 38.6 | **52.6** |
| … **chỉ** query học thêm tìm ra | 7.9 | 2.6 | 2.6 | **7.9** |
| Query học thêm / instance | 14.0 | 9.6 | 9.6 | **14.6** |
| A2: gold được đưa reviewer xem | 58.8 | 46.5 | 46.5 | 49.1 |
| A2: gold thành seed | 57.0 | 46.5 | 46.5 | 46.5 |
| A3: gold là target | 50.0 | 15.8 | 21.1 | **21.9** |
| A3: chọn gold khi gold là seed | 76.9% | 34.0% | 43.4% | 41.5% |
| Gold là candidate | 67.5 | 57.9 | 56.1 | 60.5 |
| Gold được verifier xem | 64.9 | 50.0 | 50.0 | 52.6 |
| Verifier gắn `edited`, khi gold được xem | 71.6% | 63.2% | 71.9% | 63.3% |
| Hạng ≤ 3 | 46.5 | 25.4 | 26.3 | 26.3 |
| **Đáp án cuối** | **52.6** | **35.1** | **37.7** | **36.0** |

Số hàm gold bị mất, theo bước đầu tiên làm rơi (mini gốc → mới):
- A2 tìm kiếm: 38 → 35;
- A2 cửa sổ duyệt: 10 → 10;
- không được đưa verifier xem: 9 → 9;
- **verifier gắn `not_edited`: 10 → 19**;
- vào đáp án: 40 → 41.

**Mức function, ghép cặp với mini gốc** (KTC 95%):
- Lite: 76.0 / 76.0 / 51.0 / 57.3 ở mức file. Mức function 44.0 / 52.7 / 21.5 / 27.1 (gốc 40.0 / 44.0 / 18.0 / 22.4). REC +8.7 [−0.7, +20].
- LocBench: function 36.0 / 46.2 / 21.5 / 26.3 (gốc 32.0 / 48.1 / 23.0 / 27.3).
- Gộp 50 id: SL +4.0 [−4, +12], REC +3.4 [−3, +10], PRE +1.0 [−5, +7], F1 +1.8 [−3, +7].

**Kết luận:**
- **A2 đạt đúng như replay:**
  - query học thêm ngang luna về số lượng (14.6 so với 14.0);
  - phần gold chỉ query học thêm tìm ra bằng luna (7.9%);
  - gold được tìm ra tăng 5.3 điểm.
  - Nhưng gold thành seed không tăng: gold mới phải tranh 30 chỗ trong cửa sổ duyệt, và reviewer giữ 94.6% gold được xem (trước là 100%).
- **A3 tăng như replay:** gold là target từ 15.8 lên 21.9.
- **Phần cải thiện phía trên không đến được đáp án.** Verifier làm rơi 19 hàm gold vì gắn `not_edited` (trước 10). Tỉ lệ verifier gắn `edited` khi gold được xem không đổi (63%). Verifier của mini giờ là chỗ nghẽn chính. Đáp án cuối tăng ở Lite, giảm nhẹ ở LocBench, và đều trong nhiễu.
- **Bước tiếp nên nhắm vào verifier:** thí nghiệm replay prompt cho verifier, chạy nhiều lần với thứ tự khác nhau rồi gộp phiếu, hoặc dùng model mạnh hơn riêng cho verifier.

## Thí nghiệm verifier (ghi trước khi chạy, 2026-10-22)

**Input:** đúng prompt verifier của 50 lần chạy pipeline mini hiện tại (`heldout6_4omini_a2p_c4`): cùng 40 candidate, cùng thứ tự đã đưa cho model. Script `.tmp/audit_v6/a3v_prompt_replay.py`, chạy bằng `.tmp/run_a3v_prompt_replay.sh pilot|all`.

**Phép kiểm trước khi chạy** (chế độ giả, 2 instance):
- prompt dựng lại khớp đúng độ dài prompt đã lưu (2/2);
- nhãn đã lưu đi qua phần còn lại của pipeline cho ra đúng đáp án đã lưu (2/2).

Vì vậy mỗi biến thể được chấm chính xác tới đáp án cuối mà không cần gọi LLM thêm.

| Biến thể | Nội dung | Nhắm vào |
|---|---|---|
| W0 | Prompt hiện tại, thứ tự đã lưu | Đối chứng; cũng đo độ lệch khi chạy lại |
| W1 | W0 chạy 3 thứ tự (thứ tự đã lưu + 2 lần xáo có seed), gộp phiếu | Nhiễu theo thứ tự |
| W2 | Luật: chỉ gắn `edited` khi chỉ ra được dòng code sẽ sửa; "liên quan / gọi / bị gọi" thì chưa đủ; phần lớn bản sửa đổi 1–3 hàm. Cộng trường `analysis` đặt trước các nhãn | Gắn `edited` quá rộng, phân biệt kém |
| W3 | W2 chạy 3 thứ tự, gộp phiếu | Cả hai |
| L0 | luna với prompt W0 | Trần; đồng thời là phương án "chỉ dùng luna cho verifier" |

**Cách gộp phiếu:**
- `edited` nếu ít nhất 2/3 lần nói `edited`;
- ngược lại `maybe` nếu ít nhất 2/3 lần nói `edited` hoặc `maybe`;
- còn lại `not_edited`.
- Ranking: Borda trên 3 danh sách top 5.
- `edited_count`: trung vị.

**Thước đo:**
- số nhãn `edited` mỗi instance và precision của nhãn;
- gold được gắn `edited` trên số gold được xem;
- hạng 1 là gold;
- **đáp án cuối**: SL / REC / PRE / F1, ghép cặp với nhãn đã lưu.

Calibrator không được fit lại. Nó được fit trên nhãn của một lần chạy luna, nên phân bố nhãn sau khi gộp phiếu có thể lệch so với lúc fit; sẽ ghi nhận khi đọc kết quả. Đây là phép đo phát triển trên held-out 6.

### Kết quả thí nghiệm verifier (2026-10-22; `.tmp/audit_v6/a3v_prompt_replay.txt`)

50/50, không lỗi, RAM đỉnh 0.59 GB mỗi process. Chi phí: mini $1.21, luna 412 nghìn token. Phép kiểm hợp lệ đạt cả 50/50:
- prompt dựng lại khớp đúng độ dài prompt đã lưu;
- nhãn đã lưu cho ra đúng đáp án đã lưu.

Chạy lại cùng prompt nhưng đổi thứ tự candidate: 82% nhãn trùng nhau.

**Ở bước verifier** (60 hàm gold được verifier xem):

| | `edited` / instance | precision | gold được gắn `edited` | hạng 1 là gold |
|---|---|---|---|---|
| nhãn đã lưu | 4.3 | 17.8% | 38 | 15 |
| W0 chạy lại | 4.8 | 16.2% | 39 | 14 |
| W1 gộp phiếu 3 thứ tự | 3.9 | 21.5% | 42 | 19 |
| W2 luật + phân tích | 2.4 | 25.4% | 31 | 17 |
| W3 W2 + gộp phiếu | 2.1 | 35.0% | 36 | 23 |
| L0 luna | 1.7 | 41.0% | 34 | **26** |

**Đáp án cuối** (mức function, SL / REC / PRE / F1, hiệu so với nhãn đã lưu, KTC 95%):

| | Lite | LocBench |
|---|---|---|
| nhãn đã lưu | 44.0 / 52.7 / 21.5 / 27.1 | 36.0 / 46.2 / 21.5 / 26.3 |
| W1 | PRE −5.7 [−12, −0.4], F1 −4.1 | REC +2.9, F1 +1.1 (trong nhiễu) |
| W2 | SL −8, PRE +2.4, F1 +1.8 | SL −4, F1 +0.2 |
| W3 | SL −8, F1 +0.2 | SL −4, F1 +0.8 |
| **L0 luna** | **PRE +7.7 [+3, +13], F1 +7.5 [+3, +12]**, SL −4 | **PRE +7.7 [+2, +15]**, F1 +5.5 |

**Kết luận:**
- **Pilot 2 id đã đánh giá quá cao việc gộp phiếu.** Trên 50 id, W1 chỉ nhỉnh hơn ở bước verifier (gold `edited` 42 so với 38, hạng 1 đúng 19 so với 15). Ở đáp án cuối, W1 không tốt hơn: PRE ở Lite còn giảm.
- **Luật + gộp phiếu (W3) cải thiện rõ nhãn** (precision 35% so với 18%, hạng 1 đúng 23 so với 15), nhưng **không truyền tới đáp án cuối**: SL giảm, F1 không đổi. Nguyên nhân khả dĩ:
  - calibrator được fit trên nhãn một lần chạy của luna, nên với nhãn chặt hơn, ít node vượt ngưỡng 0.045 hơn, kéo recall xuống;
  - phần gold mất đi là gold mà prompt mới khiến mini gắn `maybe` thay vì `edited`.
- **Chỉ đổi model ở verifier mới cải thiện đáp án:** dùng luna cho verifier, các bước khác giữ mini, thì PRE +7.7 ở cả hai benchmark và F1 +7.5 ở Lite (KTC không chứa 0). SL không tăng vì recall bị giới hạn ở phía trên.
- **So với luna chạy toàn bộ pipeline,** mini + verifier luna vẫn còn cách xa: Lite SL 40 so với 64, PRE 29 so với 38.
- **Bước tiếp, nếu muốn làm verifier của mini có ích:** fit lại calibrator trên output của mini (W3) ở swe_train. Hoặc chấp nhận cấu hình lai, chỉ dùng model mạnh cho verifier (1 lời gọi mỗi instance).

## Audit lần chạy mini mới nhất so với luna (2026-10-22)

**Lần chạy:** `.agent_runs/heldout6_4omini_a2p_c4` (planner A2 + C4 cho A3). Log của cả 50 instance không có cảnh báo hay lỗi. Verifier chạy ok 50/50. Có 3 instance A3 không giữ được giả thuyết nào.

**Công cụ** (A2 và A3 dựng lại prompt từ graph, mỗi instance một process có trần cgroup; RAM đỉnh 0.61 GB; prompt A3 dựng lại khớp 100/100):
- phễu: `MINI_WS=… compare_mini_luna.py`;
- A2: `MINI_WS=… PARTS=.tmp/audit_v6/a2_review_parts_a2pc4 run_parts.sh a2_review_audit.py`;
- A3: `MINI_WS=… MINI_A3_PROMPT=c4 PARTS=.tmp/audit_v6/a3_parts_a2pc4 run_parts.sh a3_target_audit.py`.

### Khoảng cách nằm ở đâu

Luna đưa 60 hàm gold vào đáp án, mini 41, chênh 19. Cụ thể:
- 27 hàm luna giữ được mà mini làm rơi;
- 8 hàm mini giữ được mà luna làm rơi. Cả 8 hàm này đều bị verifier của luna gắn `not_edited`.

Gán mỗi hàm gold vào nguyên nhân:

| Nguyên nhân | Luna giữ, mini mất | Mini giữ, luna mất | Ròng |
|---|---|---|---|
| **A3 / thứ hạng:** mini không nhắm gold, nên gold không được verifier xem (4); hoặc luna chạm tới gold không phải nhờ query mà nhờ target A3 hay mở rộng graph, còn mini thì không (5) | 9 | 0 | **+9** |
| **A2:** query (3) và cửa sổ duyệt 30 chỗ (4) | 7 | 0 | **+7** |
| **Verifier:** gold được xem nhưng gắn `not_edited` | 11 | 8 | **+3** |
| **Tổng** | 27 | 8 | **+19** |

Về precision (PRE), đáp án của mini có 6.0 hàm mỗi issue, luna 5.0. Verifier của mini gắn `edited` cho 4.3 node mỗi instance với precision 17.8%; luna 2.3 node, precision 45.3%.

### A3: khoảng cách lớn nhất với SL/REC

| | luna | mini mới | mini gốc |
|---|---|---|---|
| Gold không có trong prompt A3 | 20 | 38 | 40 |
| Prompt A3 (trung vị ký tự) / số seed relevant trong prompt | 28.3k / 20.0 | **42.4k / 26.3** | 37.7k / 24.7 |
| Gold là seed relevant, được chọn làm target | 41/57 (72%, mẫu 1) | 22/47 (**47%**) | 35% |
| Gold là hàm cùng file, được chọn làm target | 4/29 (14%, mẫu 1) | 3/25 (12%) | 0% |
| Vị trí trung vị của target | S9–S11 | S5 | S3 |
| Gold có trong prompt của cả hai model, được chọn làm target | 44/74 (mẫu 1) | **25/74** | — |

- C4 có cải thiện (chọn đúng gold là seed từ 35% lên 47%, và lần đầu chọn được hàm cùng file), nhưng khi gold có trong prompt của cả hai model, mini vẫn chỉ chọn được khoảng một nửa so với luna.
- **Prompt dài hơn:** planner A2 mang về nhiều candidate hơn, và mini gắn relevant nhiều hơn (27.2 so với 20.5 mỗi lần chạy). Prompt A3 tăng lên 42 nghìn ký tự, gấp 1.5 lần của luna.
- **3 instance A3 trống** (`home-assistant-136739`, `django-14752`, `sklearn-11281`): cả 4 giả thuyết thô của mỗi instance đặt dự đoán chính lên node Class (`via=self`). Bộ kiểm loại hết, nên các instance này không có target A3 nào. Ở `home-assistant-136739`, luna giữ được 2 hàm gold nhờ target A3.

### A2: còn 7 hàm gold

- Gold được tìm ra: luna 83, mini mới 75, mini gốc 69.
- 9 hàm luna tìm ra mà mini không tìm ra:
  - 7 hàm có tên dẫn tới gold nằm trong candidate mini đã xem, nhưng phần lớn là từ chung chung (`joining`, `analyzer`, `objpath`);
  - 2 hàm không có tên nào dẫn tới.
- Query học thêm: 14.6 mỗi instance, 92% chép từ candidate, 18.2% có kết quả chứa gold (luna 21.7%).
- Mini gắn relevant/maybe/irrelevant là 27.2 / 29.0 / 33.6, luna 20.5 / 25.5 / 43.2. Mini vẫn gắn rộng.

### Verifier: recall ngang luna, precision và thứ hạng kém

Trên 33 instance mà cả hai verifier đều được xem gold:
- trên cùng 56 hàm gold, cả hai đều gắn `edited` cho 38 hàm (mini đổi 10 nhãn của luna từ `edited` sang `not_edited`, và ngược lại 8 hàm);
- precision: mini 27%, luna 52%;
- node xếp hạng 1 là gold: mini 15/33, luna 29/33.

Thí nghiệm replay: thay riêng verifier bằng luna thì PRE +7.7 ở cả hai benchmark, SL không đổi.

### Kết luận

1. **SL/REC thấp chủ yếu do A3** (ròng 9 hàm gold), **tiếp đến là A2** (7 hàm). Verifier chỉ làm mất thêm 3 hàm ròng.
2. **PRE thấp chủ yếu do verifier:** nó gắn `edited` quá rộng và xếp hạng kém. Thay verifier bằng model mạnh hơn bù được khoảng một nửa khoảng cách PRE.

**Hướng sửa, theo thứ tự lợi ích / chi phí:**
- **A3, $0:** khi dự đoán chính trỏ vào node Class/File với `via=self`, chuyển thành `via=members` thay vì loại cả giả thuyết. Cứu được 3 instance A3 trống. Cần đo lại xem các giả thuyết đó có nhắm trúng gold không.
- **A3:** rút gọn input cho mini, vì prompt hiện dài 1.5 lần của luna do A2 gắn relevant quá rộng. Có thể giới hạn số seed relevant đưa vào A3, hoặc chạy riêng A3 bằng model mạnh hơn.
- **A2:** chỉ còn 7 hàm gold; 4 trong số đó mất ở cửa sổ duyệt. Có thể ưu tiên chỗ trong cửa sổ cho các node do query học thêm tìm ra.
- **Verifier:** muốn tăng PRE thì cần model mạnh hơn ở bước này; prompt và gộp phiếu đã thử nhưng không có tác dụng.

## Thực hiện 3 hướng sửa sau audit (2026-10-22)

### Hướng 3, A2: ưu tiên chỗ trong cửa sổ cho query học thêm (`.tmp/audit_v6/a2_window_sim.py`, offline, $0)

Luật chọn cửa sổ dựng lại khớp 50/50 với cửa sổ đã lưu. Luật thay thế, chốt trước khi đo: ở vòng 2–3, dành K chỗ cho các kết quả chưa duyệt đứng đầu của mỗi query mới.
- Với K=2 hoặc K=3: thêm 1 hàm gold vào cửa sổ (56 → 57), không mất hàm nào.
- 18/19 hàm gold đã được tìm ra mà không vào cửa sổ nằm ở hạng gộp rất sâu (74–331 trên 199–593 node). 15/19 hàm được tìm ra ngay từ vòng 1, ở hạng ≥ 6 trong danh sách của query.

Ba vòng duyệt chỉ xem được 90 node, nên muốn cứu các hàm này phải tăng ngân sách duyệt lên nhiều lần. **Không thay đổi.**

### Hướng 1, A3: giữ giả thuyết có dự đoán chính trên node Class/File (`.tmp/audit_v6/a3_rescue_check.py`, offline, $0)

Dựng lại bảng alias của lần chạy `a2p_c4`, rồi xem target của các giả thuyết bị loại:
- 45 giả thuyết ở 26 instance sẽ được giữ lại;
- target: 49 Class, 4 File, 11 Function/Method;
- **không target nào là hàm gold**; 19/64 target "chứa" gold (Class chứa method gold, hoặc File chứa gold).
- Ba instance A3 trống: `django-14752` nhắm `AutocompleteJsonView` (chứa gold `.get`); `home-assistant` và `sklearn-11281` nhắm Class không chứa gold.

Lỗi thật là mini chọn **Class** làm target thay cho method. Giữ các giả thuyết này lại không tạo thêm target là hàm gold. **Không đưa vào pipeline.** Việc chuyển Class thành method được làm ở hướng 2.

### Hướng 2, A3: map-reduce (ghi trước khi chạy)

Script `.tmp/audit_v6/a3_mapreduce_replay.py`, chạy bằng `.tmp/run_a3_mapreduce_replay.sh pilot|all`. Input giống hệt thí nghiệm prompt A3 (A2 của `heldout6_4omini_r`), nên so trực tiếp được với C0 / C4 / L0. Với k=6 các con số đó là 19 / 26 / 40 hàm gold, ở 18 / 24 / 32 instance.

- **Map:** mỗi file có seed một lời gọi mini (tối đa 8 file). Prompt gồm seed của file đó, mọi hàm trong file (tối đa 40) và các cạnh graph. Model chọn tối đa 3 hàm/method có khả năng bị sửa nhất, xếp theo khả năng, hoặc không chọn gì. Nếu chọn Class/File thì thay bằng tối đa 3 hàm của Class/File đó, ưu tiên hàm trùng từ với issue.
- **Reduce:** một lời gọi mini với prompt C4 (luật, phân tích, ví dụ), chỉ trên danh sách rút gọn (tối đa 15 node, xen kẽ giữa các file theo thứ tự chọn). Không có danh sách hàm cùng file. Prompt trung vị khoảng 9 nghìn ký tự khi chạy giả, so với 37 nghìn của prompt hiện tại.
- **Cơ sở:** Lost in the Middle (Liu et al., TACL 2024); permutation self-consistency (Tang et al., NAACL 2024); RankGPT với cửa sổ trượt (Sun et al., EMNLP 2023); Setwise (Zhuang et al., SIGIR 2024).
- **Thước đo:** gold được chọn làm target với k = 3/6/10 và khi giữ hết; số target; precision; gold có trong danh sách rút gọn.

### Kết quả A3 map-reduce (2026-10-22; `.tmp/audit_v6/a3_mapreduce_parts/`)

**Thiết kế đã sửa sau pilot 2 id**, trước khi chạy toàn bộ:
1. Mini trả tên hàm thay cho alias; harness chấp nhận cả hai: alias, tên đủ, hoặc tên trần nếu là duy nhất trong batch.
2. Bước map ép mỗi file chọn 3 hàm, làm danh sách rút gọn đầy nhiễu. Đã thêm phần đánh giá file (`here` / `maybe` / `no`): file `here` xếp trước, file `no` bị bỏ.

**Lần chạy:** 50/50, không lỗi, RAM đỉnh 0.58 GB, chi phí $0.40, 399 lời gọi map.
- Đánh giá file: `here` 276, `maybe` 19, `no` 104. Bộ lọc file yếu: mini gắn `here` cho phần lớn file.
- Danh sách rút gọn (trung vị 15 node) chứa 35 hàm gold. Prompt reduce trung vị 10 nghìn ký tự.

| Cùng input (A2 của `heldout6_4omini_r`) | gold được chọn, k=3 | k=6 | k=10 | tất cả | instance có gold trong 6 target đầu |
|---|---|---|---|---|---|
| C0 prompt hiện tại | 19 | 19 | 19 | 19 | 18 |
| C4 | 22 | 26 | 26 | 26 | 24 |
| **Map-reduce** (3.8 target / instance) | 25 | 25 | 25 | 25 | 25 |
| **Chỉ map** (thứ tự danh sách rút gọn, không gọi reduce) | 20 | 27 | 33 | 35 | 26 |
| L0 luna | 36 | 40 | 40 | 44 | 32 |

**Kết luận:**
- Map-reduce chỉ ngang C4 ở k=6 (25 so với 26). Không thu hẹp được khoảng cách với luna (40).
- Bước map làm tốt việc tìm ứng viên (35 hàm gold trong danh sách rút gọn), nhưng bước reduce bỏ mất 10 hàm. Phần đánh giá file của mini cũng không lọc được nhiễu.
- "Chỉ map" với 10 target tìm được 33 hàm gold. Đổi lại phải chấp nhận nhiều target hơn và precision thấp, nên phụ thuộc verifier.
- **Tổng hợp các thử nghiệm cho A3** (luật, CoT, few-shot, xáo thứ tự, chia file, map-reduce): mini dừng ở khoảng 25–27 hàm gold với k=6, luna 40. Các kỹ thuật chống thiên lệch vị trí đã loại được lỗi bám đầu danh sách, nhưng phần còn lại là năng lực chọn đúng chỗ sửa của model.

## Thí nghiệm verifier chấm từng candidate (pointwise, logprob) (ghi trước khi chạy, 2026-10-22)

**Nền:** pipeline mini mới nhất (`heldout6_4omini_a2p_c4`: planner A2 + C4 cho A3). Đáp án mức function ở Lite: 44.0 / 52.7 / 21.5 / 27.1. Map-reduce chỉ là thí nghiệm riêng cho A3, không nằm trong pipeline này. Input là đúng 40 candidate mà verifier đã thấy, giống thí nghiệm W0–W3 và L0, nên so được trực tiếp.

**Thiết kế:**
- Mỗi candidate một lời gọi gpt-4o-mini: issue + luật của verifier, rồi code của riêng hàm đó; hỏi "patch có sửa hàm này không? yes/no".
- Output 1 token, bật logprob. p = P(yes) / (P(yes) + P(no)), tính trên 5 token có xác suất cao nhất ở vị trí đầu.
- Issue đặt trước để phần đầu giống nhau giữa 40 lời gọi được cache.
- Script `.tmp/audit_v6/a3v_pointwise_replay.py`, chạy bằng `.tmp/run_a3v_pointwise_replay.sh pilot|all`.

**Chấm điểm, không fit gì:**
- **P1:** xếp hạng theo p; đáp án là các hàm có p ≥ 0.5 (ít nhất 1 hàm).
- **P2:** dùng p như output verifier, cho qua calibrator hiện tại (swe_train, p ≥ 0.045):
  - nhãn `edited` nếu p ≥ 0.5, `maybe` nếu p ≥ 0.2, còn lại `not_edited`;
  - ranking là top 5 theo p;
  - `edited_count` = số node được gắn `edited`.

**So với** nhãn đã lưu, W3 và L0 luna trên cùng candidate, theo các thước đo:
- gold đứng hạng 1 / trong top 3 / trong top 5;
- p trung bình của gold so với non-gold;
- đáp án cuối, ghép cặp với nhãn đã lưu.

**Mục đích:** biết mini có phân biệt được hàm cần sửa khi mỗi lần chỉ nhìn một hàm hay không. Nếu có tín hiệu, bước sau là fit lại calibrator trên swe_train với p làm đặc trưng.

### Kết quả verifier pointwise (2026-10-22; `.tmp/audit_v6/a3v_pointwise_parts/`)

50/50, 2000 lời gọi, không lỗi, RAM đỉnh 0.58 GB, chi phí $0.50 (phần issue được cache).

**Xếp hạng trên 40 candidate được xem** (33 instance có gold trong số đó):
- p trung bình: gold 0.745, non-gold 0.113;
- p ≥ 0.5: gold 45/60, non-gold 144/1260 (khoảng 2.9 node non-gold mỗi instance);
- gold đứng hạng 1: pointwise 17, nhãn đã lưu 15, W3 23, luna 26; gold trong top 3: 27; trong top 5: 29.
- AUC trong cùng instance (gold so với non-gold):

| Điểm | AUC |
|---|---|
| p pointwise | **0.843** |
| p của calibrator hiện tại (verifier + đặc trưng A2/A3) | 0.824 |
| trung bình hai điểm (mô tả) | **0.869** |

**Đáp án cuối** (mức function, ghép cặp với nhãn đã lưu):
- P1 (p ≥ 0.5) và P2 (p đổi thành nhãn rồi qua calibrator) không tốt hơn: Lite F1 −2.0 / −4.3, LocBench +3.5 / −0.9, đều trong nhiễu.
- Mô tả các cách cắt khác (không chọn trên held-out 6), F1 Lite / LocBench:

| Cách cắt | F1 Lite | F1 LocBench |
|---|---|---|
| nhãn đã lưu | 27.1 | 26.3 |
| verifier luna | 34.6 | 31.7 |
| p ≥ 0.9 | 29.2 | 31.9 |
| top 2 | 27.6 | 29.2 |

**Kết luận:**
- Riêng p pointwise đã xếp hạng tốt ngang toàn bộ calibrator hiện tại (AUC 0.843 so với 0.824). Gộp hai điểm lên 0.869, nghĩa là p mang thông tin bổ sung.
- Nhưng dùng p với ngưỡng cố định thì đáp án không tốt hơn. Cần học cách gộp p với các đặc trưng khác.
- Đây chính là **hướng 1**: fit lại calibrator có p làm đặc trưng, trên dữ liệu ngoài benchmark (swe_train), rồi đánh giá trên held-out 6. Phần p của held-out 6 đã có, không cần gọi lại.

## Hướng 1: fit calibrator cho mini trên swe_train (ghi trước khi chạy, 2026-10-22)

**Dữ liệu fit:** đúng 100 id swe_train đã dùng để fit `calibrator_swetrain` cho luna (`.tmp/swe_train_swe_bench_train.json`, nằm ngoài Lite và LocBench). Graph của cả 100 id vẫn còn trên máy (đã kiểm bằng `check_graphs.py`).

**Bước 1, chạy pipeline mini mới nhất trên swe_train:**
- cấu hình: planner A2, C4 cho A3, 1 mẫu;
- workspace `.agent_runs/swe_train_4omini_a2p_c4`;
- script `.tmp/run_swetrain_4omini_a2p_c4.sh pilot|all`, dùng cùng harness với lần chạy luna (`register.py`, không có Node.js, cgroup, `capped.py`);
- khoảng $2.2.

**Bước 2, chấm pointwise trên swe_train:**
- `WS=.agent_runs/swe_train_4omini_a2p_c4/.. PARTS=.tmp/audit_v6/a3v_pointwise_swetrain SETS="swe_bench_train:.tmp/swe_train_swe_bench_train.json" run_parts.sh a3v_pointwise_replay.py`;
- khoảng $1.

**Bước 3, fit offline (không gọi LLM):** cùng mô hình với `calibrator_swetrain` (logistic, L2 1.0, ngưỡng theo luật A10 trên dự đoán out-of-fold 5 fold). Hai biến thể:
- **M:** 20 đặc trưng hiện tại, fit trên output của mini;
- **M+pw:** thêm đặc trưng `pw_p` (xác suất pointwise; bằng 0 nếu candidate không được verifier xem).

**Đánh giá:** trên held-out 6 (lần chạy `a2p_c4`, p pointwise đã có sẵn), ghép cặp với calibrator hiện tại (fit trên luna). Đo SL / REC / PRE / F1, kèm AUC xếp hạng.

Held-out 6 không được dùng để chọn bất kỳ tham số nào.

### Kết quả hướng 1 (2026-10-22; `.tmp/audit_v6/fit_mini_calibrator.txt`)

**Dữ liệu chạy:**
- pipeline mini trên swe_train: 100/100 hoàn tất, $2.40. A3 trống 8/100. Verifier ok 100/100.
- pointwise: 100/100, $1.00, RAM đỉnh 0.48 GB.

**Fit** (100 id swe_train, 131 dòng dương; cùng quy trình với `recalibrate.py train`):

| | recall_p | SL / REC / PRE / F1 out-of-fold | top 3 out-of-fold |
|---|---|---|---|
| M (20 đặc trưng) | 0.0425 | 38.0 / 46.9 / 23.2 / 27.5 | 30.0 / 40.0 / 23.0 / 26.3 |
| M+pw (+ `pw_p`) | 0.0575 | 37.0 / 45.6 / 27.9 / 31.0 | 32.0 / 41.3 / 23.7 / 27.1 |

Trọng số lớn nhất của M+pw: `v_edited` +1.60, `v_rank_inv` +1.48, `seed_rank_inv` +1.29, **`pw_p` +1.27**, `same_file_h1` +0.87, `v_maybe` −0.81.

**Đánh giá trên held-out 6** (lần chạy `a2p_c4`; ghép cặp với calibrator hiện tại, vốn fit trên luna; KTC 95%). Phép kiểm: dựng lại bằng calibrator hiện tại cho ra đúng đáp án đã lưu, 50/50.

| | Lite SL / REC / PRE / F1 \| số hàm | LocBench SL / REC / PRE / F1 \| số hàm |
|---|---|---|
| calibrator hiện tại (fit trên luna) | 44.0 / 52.7 / 21.5 / 27.1 \| 6.0 | 36.0 / 46.2 / 21.5 / 26.3 \| 6.1 |
| M | 36.0 / 46.7 / 23.2 / 28.3 \| 3.9 | 32.0 / 43.2 / 26.6 / 29.4 \| 3.8 |
| **M+pw** | 36.0 / 46.7 / 24.1 / 29.4 \| 3.4 | 32.0 / 42.2 / **31.3 / 31.8** \| 2.9 |
| *tham chiếu: verifier luna (replay L0)* | *40.0 / 48.7 / 29.2 / 34.6* | *36.0 / 45.8 / 29.2 / 31.7* |

Hiệu ghép cặp của M+pw so với calibrator hiện tại:
- Lite: SL −8 [−20, 0], PRE +2.6 [−0.4, +5.7], F1 +2.3 [−1.3, +5.7];
- LocBench: SL −4 [−12, 0], **PRE +9.8 [+2.4, +19.0], F1 +5.5 [+0.8, +10.3]**.

AUC trong cùng instance, trên mọi dòng candidate:

| Calibrator | AUC |
|---|---|
| hiện tại | 0.812 |
| M | 0.851 |
| **M+pw** | **0.872** |

**Kết luận:**
- **Fit lại trên output của mini và thêm điểm pointwise làm thứ hạng tốt hơn rõ** (AUC 0.812 → 0.872). Ở LocBench, PRE và F1 tăng có ý nghĩa (KTC không chứa 0) và ngang mức dùng luna cho verifier. Ở Lite, PRE và F1 tăng nhưng trong nhiễu.
- **Đổi lại, đáp án nhỏ hơn** (3.4 / 2.9 hàm so với 6.0) **nên SL giảm 4–8 điểm.** Ngưỡng do luật A10 chọn trên swe_train cho đáp án chặt hơn với mini. Không chỉnh ngưỡng trên held-out 6.
- **Chi phí:** thêm khoảng $0.01 mỗi instance cho bước pointwise (40 lời gọi rất ngắn, có cache).
- **Muốn báo cáo thì cần xác nhận trên tập chưa xem,** ví dụ một phần held-out 7, sau khi đưa bước pointwise và calibrator `mini_Mpw` vào pipeline.

### Kết hợp calibrator luna với calibrator mini + pointwise (2026-10-22; `.tmp/audit_v6/combine_calibrators.txt`)

Đặt tên lại cho thống nhất:
- **calibrator luna** = `calibrator_swetrain`, fit trên output của luna; đang dùng trong pipeline;
- **calibrator mini** = M;
- **calibrator mini + pointwise** = M+pw.

Hai luật kết hợp, chốt trước khi xem số trên held-out 6, không chọn gì trên held-out 6:
- **K1:** cỡ đáp án theo calibrator luna (số node có p ≥ 0.045), nhưng chọn node theo thứ hạng của mini + pointwise.
- **K2:** trung bình xác suất của hai calibrator. Ngưỡng 0.07, chọn theo luật A10 trên swe_train (phần mini + pointwise dùng dự đoán out-of-fold).

Phép kiểm: dựng lại bằng calibrator luna cho ra đúng đáp án đã lưu, 50/50.

Mức function, SL / REC / PRE / F1, gộp 50 id:

| | SL | REC | PRE | F1 | số hàm |
|---|---|---|---|---|---|
| calibrator luna | 40.0 | 49.4 | 21.5 | 26.7 | 6.0 |
| mini + pointwise | 34.0 | 44.4 | 27.7 | 30.6 | 3.2 |
| **K1** | **40.0** | **51.1** | **22.1** | **27.5** | 6.0 |
| K2 | 36.0 | 46.9 | 25.4 | 29.1 | 4.2 |

So với calibrator luna, theo từng benchmark:
- **K1, Lite:** giống hệt calibrator luna. Với khoảng 6 hàm mỗi issue, hai thứ hạng chọn ra cùng một tập.
- **K1, LocBench:** REC +3.3 [0, +8.7], PRE +1.2 [0, +3.2], F1 +1.6 [0, +4.1], SL không đổi. Cận dưới của mọi KTC là 0: K1 không làm instance nào tệ đi.
- **K2:** nằm giữa hai calibrator. LocBench PRE +5.5 [+0.8, +12.4], nhưng SL −4.

**Kết luận:**
- K1 là cải thiện "không mất gì": giữ nguyên SL, tăng nhẹ REC và PRE. Nhưng mức tăng nhỏ (gộp lại: REC +1.7, PRE +0.6) và chỉ xuất hiện ở LocBench.
- Lý do: thứ hạng tốt hơn của mini + pointwise chủ yếu đổi thứ tự trong top 1–3. Khi lấy khoảng 6 hàm, tập hàm được chọn gần như trùng nhau.
- Muốn SL, REC và PRE cùng tăng đáng kể thì phải đưa thêm gold vào danh sách candidate, tức cải thiện A2/A3. Calibrator không làm được việc này.

## Audit điểm nghẽn: mini (pipeline `a2p_c4` + K1) so với luna (2026-10-22; `.tmp/audit_v6/bottleneck_k1.txt`)

**Kiểm log:**
- pipeline `a2p_c4`: không có cảnh báo hay lỗi;
- pointwise trên held-out 6 và swe_train: 0 instance lỗi; 3/2000 lời gọi không trả token yes/no (p = 0.5);
- phép kiểm dựng lại: đáp án của luna khớp đáp án đã lưu ở mọi hàm gold.

**Bước đầu tiên làm rơi mỗi hàm gold** (114 hàm, 50 instance):

| Bước | luna | mini K1 |
|---|---|---|
| A2: không query nào tìm ra | 22 | 35 |
| A2: tìm ra nhưng ngoài cửa sổ duyệt | 14 | 10 |
| Không thành candidate | 1 | 0 |
| Là candidate nhưng ngoài 40 node verifier xem | 3 | 9 |
| Được xem nhưng dưới ngưỡng cắt (verifier + calibrator) | 14 | 17 |
| **Vào đáp án** | **60** | **43** |

**Ghép cặp** (mini làm rơi mà luna qua được / ngược lại / ròng):

| Bước | mini mất | luna mất | ròng |
|---|---|---|---|
| A2 tìm kiếm | 14 | 1 | **+13** |
| cửa sổ duyệt | 5 | 4 | +1 |
| không được verifier xem | 6 | 0 | **+6** |
| dưới ngưỡng cắt | 9 | 8 | +1 |
| **tổng** | 34 | 13 | **+21** |

Theo audit A2 trước đó (cùng artifact A2): trong 14 hàm mini mất ở "A2 tìm kiếm" mà luna qua được, có 8 hàm luna tìm ra bằng query, còn 6 hàm luna chạm tới nhờ target A3 hoặc mở rộng graph. Cả 6 hàm "không được verifier xem" đều không phải target A3 của mini, nên bị xếp hạng thấp trước bước verifier.

**Trần khi xếp hạng hoàn hảo** (giữ nguyên danh sách candidate và cỡ đáp án của từng hệ):

| | gold trong candidate | gold vào đáp án nếu xếp hạng hoàn hảo | thực tế | instance có ≥ 1 gold: trần / thực tế |
|---|---|---|---|---|
| luna | 77 | 71 | 60 (85% của trần) | 42 / 40 |
| mini K1 | 69 | 64 | 43 (67% của trần) | 35 / 30 |

**Kết luận, khoảng cách 17 hàm gold** (60 so với 43):
1. **Độ phủ candidate: khoảng 7 hàm** (trần 71 so với 64). Phần lớn là A2 và khả năng của A3 kéo về các hàm không có query nào tìm ra.
2. **Xếp hạng trên danh sách candidate: khoảng 10 hàm** (luna bỏ phí 11/71, mini bỏ phí 21/64). Theo ghép cặp, phần lớn mất **trước verifier** (6 hàm không được xem, do A3 không nhắm trúng); ở verifier/calibrator gần ngang luna (ròng +1, nhờ K1).
3. Ở mức instance (có ít nhất 1 gold): luna 40, mini 30. Thiếu 7 instance vì candidate, 3 instance vì xếp hạng.

**Điểm nghẽn chính bây giờ là A3** (chọn target):
- nó quyết định gold nào được kéo về qua mở rộng graph (6 hàm);
- nó quyết định gold nào được ưu tiên vào 40 node verifier xem (6 hàm).

Tiếp theo là **query của A2** (8 hàm). Verifier và calibrator sau K1 gần ngang luna về số gold giữ lại được; PRE vẫn thấp hơn vì đáp án có ít gold hơn.

## Kiểm tra trên 50 id mới của held-out 7 (2026-10-23; `.agent_runs/h7s50_4omini_a2p_c4`)

**Mẫu:** `.tmp/h7s50_*.json` = `random.Random(20261022).sample(sorted(held-out 7 ids), 25)` cho mỗi benchmark. Luật chọn cố định trước khi chạy. Các id này chưa từng dùng khi phát triển bản mini. Graph lấy từ bản lưu `jacc_heldout7`.

**Chạy:**
- pipeline `a2p_c4`: 50/50 hoàn tất, $1.18, 2 instance A3 trống;
- pointwise: 50/50, $0.51;
- chấm bằng `.tmp/audit_v6/score_h7s50.py`.
- Lỗi script ở lần pilot đầu (ghi đè `$1`) đã sửa; các process lỗi khi đó không gọi LLM.

Mức function, SL / REC / PRE / F1:

| | Lite | LocBench | Gộp 50 |
|---|---|---|---|
| mini + calibrator luna | 72.0 / 72.0 / 15.3 / 24.5 | 56.0 / 61.1 / 18.4 / 25.6 | 64.0 / 66.6 / 16.9 / 25.0 |
| mini K1 | 68.0 / 68.0 / 14.0 / 22.5 | 52.0 / 57.1 / 17.9 / 24.6 | 60.0 / 62.6 / 15.9 / 23.5 |
| **mini + calibrator mini + pointwise** | 68.0 / 68.0 / 23.3 / **34.0** | 48.0 / 53.9 / 26.9 / 32.8 | 58.0 / 61.0 / 25.1 / **33.4** |
| luna (bản đóng băng) | 84.0 / 84.0 / 48.1 / 57.8 | 56.0 / 65.4 / 44.5 / 49.2 | 70.0 / 74.7 / 46.3 / 53.5 |
| GraphLocator gpt-4o | 80.0 / 80.0 / 26.2 / 33.9 | 40.0 / 48.7 / 31.8 / 33.4 | 60.0 / 64.4 / 29.0 / 33.6 |
| GraphLocator claude-3.5 | 72.0 / 72.0 / 21.8 / 30.2 | 60.0 / 69.4 / 28.7 / 32.5 | 66.0 / 70.7 / 25.3 / 31.3 |

So cặp với GraphLocator gpt-4o, gộp 50 id (KTC 95%):

| | SL | REC | PRE | F1 |
|---|---|---|---|---|
| mini + calibrator luna | +4.0 [−8, +16] | +2.2 | **−12.1 [−21.6, −3.1]** | −8.6 [−17.8, +0.3] |
| mini K1 | 0.0 | −1.8 | **−13.0 [−22.3, −4.2]** | **−10.1 [−18.9, −1.5]** |
| **mini + calibrator mini + pointwise** | −2.0 [−14, +10] | −3.4 [−16, +9] | −3.9 [−13.3, +5.4] | **−0.2 [−9.6, +9.3]** |

**Kết luận:**
- **K1 không giữ được trên dữ liệu mới.** Trên held-out 6, K1 không thua calibrator luna; trên 50 id mới, K1 thấp hơn ở cả hai benchmark. Lựa chọn K1 dựa trên held-out 6 là sai.
- **Bản mini + calibrator mini + pointwise ngang GraphLocator gpt-4o:** không khác biệt có ý nghĩa ở cả bốn chỉ số (F1 33.4 so với 33.6). Đây là bản mini duy nhất như vậy.
  - Lite: F1 bằng nhau (34.0 so với 33.9), SL thấp hơn (68 so với 80).
  - LocBench: SL cao hơn (48 so với 40), F1 gần bằng.
- **Hai bản dùng ngưỡng của calibrator luna** (calibrator luna, K1) có SL/REC ngang hoặc cao hơn GraphLocator gpt-4o, nhưng **PRE thấp hơn có ý nghĩa** (khoảng −12 điểm): đáp án có 5–7 hàm, nhưng ít gold.
- Khoảng cách với luna vẫn lớn (F1 33.4 so với 53.5).
- **Đề xuất:** dùng **calibrator mini + pointwise** làm cấu hình mini. Muốn khẳng định chắc hơn thì chạy phần còn lại của held-out 7 (250 id, khoảng $8.5).

## Explore: pattern của gold bị bỏ sót và thứ tự ưu tiên rẻ (2026-10-23)

### Pattern (`.tmp/audit_v6/miss_pattern.py`, `reach_audit.py`)

Gold không bao giờ thành candidate:
- 62–76% là method, tên công khai; tên có trong issue chỉ 3–5%; chỉ 22–41% được query A2 nào đó tìm ra (hạng gộp trung vị 150–250).
- Đều cách seed/target 1–2 cạnh trên graph. Seed/target gần nhất là seed A2 ở 81–95% số ca.

Bốn pattern:
- **A:** thành viên của Class/File đang là seed (`HAS_METHOD`, `CONTAINS`): luna 59%, mini 20–33%.
- **B:** method của class cha/con (`EXTENDS`): luna 19%, mini 4–5%.
- **C:** gọi hàm 1–2 bước (`CALLS`): 16–38%.
- **D:** cùng file / file import, 2 bước: mini 19–47%, luna 5%.

Bước `discover` hiện tại bỏ sót cả pattern A vì giới hạn: tối đa 6 vùng seed A2, 12 thành viên mỗi vùng xếp theo từ khóa của issue, tổng tối đa 48 candidate.

### Độ phủ của các lớp explore (`.tmp/audit_v6/explore_coverage.py`)

- Mọi gold bị bỏ sót đều nằm trong các lớp A … D-import.
- Luna: A + A' + B (khoảng 250 node) phủ 84%.
- Mini: cần tới C2 (khoảng 1 000 node trở lên) mới phủ 87–90%.

### Thứ tự ưu tiên rẻ (`.tmp/audit_v6/explore_rank.py`, `explore_rank.txt`)

Cách làm:
- Vùng explore gồm A, A', B, C1, D-file, C2: trung vị khoảng 1 250 node mỗi instance; tỉ lệ gold trong vùng dưới 0.1%.
- Đặc trưng rẻ, không cần LLM. Bốn thứ tự: O0 theo lớp rồi từ khóa; O1 theo vị trí seed; O2 theo số seed nối tới; O3 logistic học trên swe_train.
- Chọn trên swe_train, kiểm trên held-out 6 và 50 id mới.
- 250 instance, không lỗi, RAM đỉnh 0.46 GB.

% gold bị bỏ sót được phủ khi giới hạn ngân sách k node:

| Tập | Thứ tự | k=30 | k=60 | k=100 | k=200 |
|---|---|---|---|---|---|
| swe_train (tập chọn) | O0 | 11% | 18% | 21% | 34% |
| | **O2** | **20%** | **28%** | **30%** | **40%** |
| | O3 (CV) | 13% | 18% | 24% | 32% |
| mini held-out 6 | O0 | 13% | 16% | 22% | 33% |
| | O2 | 18% | 20% | 27% | 27% |
| | O3 | 18% | 22% | 24% | 42% |
| mini 50 id mới | O0 | 33% | 43% | 57% | 67% |
| | O2 | 24% | 43% | 43% | 62% |
| | O3 | 43% | 52% | 67% | 71% |
| luna held-out 6 | O0 | 22% | 32% | 41% | 73% |
| | O2 | 30% | 30% | 46% | 49% |

Trọng số của O3 (logistic): `same_name` +1.57, `via_rel` +0.87, `words` +0.85, `links` +0.76, lớp A +0.71, lớp C1 +0.61, lớp C2 −0.79.

**Kết luận:**
- Đặc trưng rẻ (cấu trúc, từ khóa) không xếp hạng được vùng explore một cách ổn định. Thứ tự tốt nhất trên swe_train (O2) không giữ được trên tập kiểm tra. Ở k=100, mọi thứ tự chỉ phủ khoảng 22–67%.
- Gold nằm gần seed nhưng không có tín hiệu từ khóa. Vì vậy cần một tín hiệu **ngữ nghĩa** để chọn trong vùng explore: embedding của code so với issue, hoặc chấm bằng LLM.

## A3 chạy bằng luna, các bước khác giữ mini (held-out 6, 2026-10-23)

**Cấu hình** (`.tmp/run_heldout6_a3luna.sh`; branch `exp/embed`; `JACC_A3_MODEL=gpt-5.6-luna`, commit `65206b8`):
- A1 và A2 (có planner) dùng lại từ `heldout6_4omini_a2p_c4`; đã kiểm từng file cho cả 50 instance.
- A3: luna, prompt frozen, 2 lần lấy mẫu, như pipeline luna đã chốt.
- Verifier: mini. Calibrator: calibrator_swetrain.
- 50/50 instance, không lỗi.
- Luna tốn khoảng 29–40 nghìn token mỗi instance (khoảng nửa là cache).

Chấm bằng `.tmp/audit_v6/score_a3luna.py`. Mức function, SL / REC / PRE / F1 (metric GraphLocator):

| | Lite | LocBench |
|---|---|---|
| mini a2p_c4 | 44.0 / 52.7 / 21.5 / 27.1 | 36.0 / 46.2 / 21.5 / 26.3 |
| **mini + A3 luna** | **60.0 / 66.7** / 21.4 / 29.3 | 36.0 / **50.3** / 22.1 / 27.3 |
| luna (pipeline đầy đủ) | 64.0 / 74.7 / 38.1 / 45.3 | 44.0 / 57.5 / 33.4 / 36.4 |
| GraphLocator gpt-4o | 48.0 / 55.3 / 24.5 / 28.6 | 28.0 / 36.7 / 20.9 / 21.5 |

Hiệu ghép cặp của mini + A3 luna (KTC 95%):
- So với mini a2p_c4: Lite **SL +16 [+4, +32], REC +14 [+2, +28]**, PRE −0.1, F1 +2.2; LocBench **REC +4.1 [+0.5, +9.0]**, SL +0.
- So với GraphLocator gpt-4o: Lite SL +12 [−8, +32], F1 +0.7; LocBench **REC +13.6 [+4.2, +23.4]**, F1 +5.8 [−3.9, +15.3].

**Theo từng bước** (`compare_mini_luna.py`; % trên 114 gold; luna đầy đủ / mini + A3 luna / mini a2p_c4 trước đó):

| Bước | luna | mini + A3 luna | mini a2p_c4 |
|---|---|---|---|
| A3: gold là target | 50.0 | **42.1** | 21.9 |
| A3: khi gold là seed, được chọn làm target | 76.9% | **62.3%** | 41.5% |
| gold được verifier xem | 64.9 | 60.5 | 52.6 |
| verifier gán `edited` | 46.5 | 35.1 | 33.3 |
| gold hạng 1 sau calibrator | 31.6 | 11.4 | 12.3 |
| đáp án cuối (gold theo `gold_sets`) | 52.6 | **43.9** | 36.0 |

**Kết luận:**
- Thay riêng A3 bằng luna kéo **recall và SL** lên rõ, nhất là ở Lite (+16 SL, ngang luna đầy đủ trong khoảng tin cậy).
- **Precision không đổi** (khoảng 21–22%) và gold hiếm khi đứng hạng 1 (11%, so với 32% của luna đầy đủ): verifier mini vẫn gán `edited` quá tay.
- Phần chênh còn lại so với luna đầy đủ nằm ở A2 (seed 46.5 so với 57.0) và ở verifier, xếp hạng.
- Phép đo này làm trên held-out 6, tập đã dùng khi phát triển. Cần xác nhận trên id chưa dùng.

## A3 luna: cô lập hiệu ứng (thiết kế chốt trước khi chạy, 2026-10-24)

So sánh ở mục trên (mini a2p_c4 so với mini + A3 luna) thay đổi cùng lúc 4 yếu tố:
1. model ở A3;
2. prompt A3: C4 so với frozen;
3. số lần lấy mẫu: 1 so với 2;
4. lần gọi verifier: nhãn cũ đã lưu so với nhãn mới (gọi lại cùng prompt chỉ trùng khoảng 82% nhãn).

Script: `.tmp/audit_v6/a3_isolation.py`, `a3_isolation_score.py`, `.tmp/run_a3_isolation.sh`.

Mọi nhánh dùng chung A1/A2 đã lưu và cùng code discover / candidates / prompt verifier / calibrator_swetrain / export như `load_or_verify`. Mỗi nhánh gọi verifier mini 3 lần; chỉ số của mỗi instance là trung bình 3 lần.

| Nhánh | A3 |
|---|---|
| M_c4 | mini, prompt C4, 1 mẫu (đã lưu) |
| M_fz | mini, prompt frozen, 1 mẫu (gọi mới) |
| L_fz1 | luna, prompt frozen, chỉ mẫu 0 (`restrict_samples`, không gọi) |
| L_fz2 | luna, prompt frozen, 2 mẫu (đã lưu) |

Các hiệu ứng đo được (bootstrap ghép cặp theo instance):
- **model** = L_fz1 − M_fz: cùng prompt, cùng số mẫu;
- **số mẫu** = L_fz2 − L_fz1;
- **prompt** = M_c4 − M_fz;
- **tổng** = L_fz2 − M_c4;
- kèm độ lệch chuẩn giữa các lần gọi verifier, và so L_fz2 với GraphLocator gpt-4o.

**Phép kiểm ghi vào kết quả:** discover tái lập graph đã lưu; danh sách verifier xem và độ dài prompt khớp; nhãn đã lưu dựng lại đúng đáp án đã lưu. Đã chạy thử với model giả trên 4 instance: mọi phép kiểm đạt.

Ghi chú về so sánh trước với GraphLocator gpt-4o (n = 25 mỗi benchmark):
- Lite: SL +12, khoảng tin cậy [−8, +32]; F1 +0.7, [−11.9, +13.1]. Chưa phân biệt được.
- LocBench: REC +13.6, [+4.2, +23.4], có ý nghĩa; F1 +5.8, [−3.9, +15.3], chưa phân biệt được.

## Kết hợp offline: lần chạy A3 luna với các calibrator fit cho mini (2026-10-24, $0)

Lần chạy `heldout6_4omini_a2p_a3luna` được chấm lại offline bằng các calibrator đã fit cho mini trên swe_train:
- **M:** 20 đặc trưng;
- **M+pw:** thêm điểm pointwise. Điểm pointwise lấy từ lần chạy `a2p_c4`; nó có cho 91% số node verifier xem trong lần chạy A3 luna, node thiếu nhận p = 0.

Cả hai calibrator được fit trên output của mini có A3 **mini**, nên chưa khớp với cấu hình A3 luna. Đây chỉ là phép ước lượng hướng đi, trên held-out 6 (tập phát triển).

Mức function, SL / REC / PRE / F1 | số hàm:

| | Lite | LocBench |
|---|---|---|
| A3 luna + calibrator luna (đã chạy) | 60.0 / 66.7 / 21.4 / 29.3 \| 7.4 | 36.0 / 50.3 / 22.1 / 27.3 \| 6.7 |
| A3 luna + calibrator M | 56.0 / 64.7 / 28.2 / **35.4** \| 4.6 | 32.0 / 40.5 / 27.1 / 27.2 \| 4.2 |
| A3 luna + calibrator M+pw (p cũ) | 48.0 / 58.7 / **31.2 / 37.6** \| 3.5 | 32.0 / 41.9 / 25.5 / 28.6 \| 3.2 |
| A3 mini (a2p_c4) + calibrator M+pw | 36.0 / 46.7 / 24.1 / 29.4 \| 3.4 | 32.0 / 42.2 / 31.3 / 31.8 \| 2.9 |
| GraphLocator gpt-4o | 48.0 / 55.3 / 24.5 / 28.6 | 28.0 / 36.7 / 20.9 / 21.5 |

**Đọc kết quả:**
- Ở Lite, calibrator mini tăng PRE và F1 (F1 +6 đến +8), đổi lại SL giảm 4–12.
- Ở LocBench không có lợi.
- Muốn dùng đúng cách cần fit lại M+pw trên swe_train với output của cấu hình A3 luna.

## Chốt cấu hình gpt-4o-mini (2026-10-25)

Người dùng chốt cấu hình: **A2 planner + A3 luna + calibrator luna**.
- A1, A2 và verifier chạy gpt-4o-mini.
- `JACC_A2_PLAN=1`.
- `JACC_A3_MODEL=gpt-5.6-luna`, prompt frozen, `--a3-samples 2`.
- `JACC_CALIBRATOR=src/modules/data/calibrator_swetrain.json`, p ≥ 0.045.

Held-out 6: Lite 60.0 / 66.7 / 21.4 / 29.3, LocBench 36.0 / 50.3 / 22.1 / 27.3.

**Lý do không dùng calibrator mini (M, M+pw):** chúng tăng PRE và F1 ở Lite nhưng làm SL/REC giảm (mục "Kết hợp offline" ở trên). Người dùng ưu tiên SL/REC.

**Không giữ:** prompt C4, A3-x, map-reduce, gộp phiếu và luật cho verifier, verifier pointwise, K1/K2, embedding, các cách hiện mã V1–V3.

**Bước tiếp:**
1. Thí nghiệm cô lập hiệu ứng A3 luna (`.tmp/run_a3_isolation.sh`, đã thiết kế, chưa chạy).
2. Chạy đầy đủ hai benchmark (Lite 300, LocBench 559), cùng tập id và cùng graph với lần chạy luna trong `final-results/`.
   - Báo kết quả chính trên held-out 7 trừ 50 id h7s50, vì 50 id này đã dùng khi chọn cấu hình.
   - Báo kèm số toàn benchmark để so với Bảng 2 của GraphLocator.
