# Thiết kế dùng embedding trong pipeline (ghi trước khi đo, 2026-10-23)

## Mục tiêu và điều kiện của claim

**Claim:** với gpt-4o-mini, pipeline đạt độ chính xác ít nhất ngang GraphLocator gpt-4o, mà **rẻ hơn và nhanh hơn**, kể cả khi đã tính chi phí embedding.

**Điều kiện:**
1. Đánh giá cuối trên held-out 7 (chưa dùng khi phát triển).
2. Chi phí và thời gian tính trọn gói (LLM + embedding), đo cùng cách cho cả hai bên.
3. Có ablation bản không embedding.

**Ước lượng hiện tại:**
- Port GraphLocator: khoảng 124 nghìn token input và 9 nghìn token output mỗi issue, tức khoảng $0.40 với giá gpt-4o.
- Pipeline mini: khoảng $0.03–0.04 mỗi issue.

## Nguyên tắc

- **Cấu trúc khoanh vùng → embedding xếp hạng trong vùng → LLM suy luận trên phần đầu.** Đây là hai tầng chuẩn của IR (truy xuất rồi xếp hạng lại), giống SweRank (embedding rồi LLM rerank) và RankGPT.
- **Không embed toàn repo.** Chỉ embed các node nằm trong những tập pipeline đã khoanh: tập A2 tìm ra, vùng explore quanh seed, danh sách candidate. Embed lười, cache theo hash nội dung, dùng chung giữa các instance và commit cùng repo.
- **Chỉ thay những chỗ đang xếp hạng bằng cách đếm từ khóa** (các phép đo trước cho thấy gold ở gần nhưng không trùng từ với issue: tên trong issue chỉ 3–5%).
- **Model:** `text-embedding-3-small` (OpenAI, 1536 chiều, $0.02/1M token), là model tổng quát, không huấn luyện riêng trên SWE-bench. Mọi lời gọi đều đi qua `llm_guard.guard("embed")`.

## Văn bản đưa vào embed

- **Code node (hàm, method):** `<đường dẫn>::<tên đủ>` + chữ ký + docstring (≤ 300 ký tự) + 30 dòng đầu thân hàm (≤ 1 500 ký tự).
- **Issue, hai biến thể** (chọn trên swe_train):
  - Q1: issue gốc đã làm sạch, ≤ 6 000 ký tự;
  - Q2: từ A1: tiêu đề + tóm tắt + hành vi quan sát được / mong đợi + code ref + thông báo lỗi.
- **Điểm:** cosine(query, node). Nếu dùng cả hai query thì lấy max.

## Embedding được dùng ở đâu (bốn điểm, mỗi điểm có thể bật riêng)

| # | Bước | Hiện tại | Với embedding |
|---|---|---|---|
| E1 | **A2, tìm kiếm** | Gộp các danh sách từ khóa bằng RRF; cửa sổ duyệt lấy 30 node đầu mỗi vòng; gold được tìm ra nhưng nằm ở hạng 150–250 thì không bao giờ được duyệt | **Gộp lai:** thêm một danh sách "dense" (toàn bộ tập A2 đã tìm ra, xếp theo cosine) vào RRF. Chỉ embed các node A2 đã tìm ra |
| E2 | **Discover / explore** | 12 thành viên mỗi vùng, xếp theo từ khóa; node tìm qua graph đứng cuối danh sách ưu tiên | Vùng explore (thành viên Class/File seed, method cùng class, class cha/con, hàm gọi / bị gọi trực tiếp, file được nêu trong issue) **xếp theo cosine**; lấy top M đưa vào candidate |
| E3 | **A3, suy luận** | Hàm cùng file (≤ 40 mỗi file) xếp theo từ khóa; mini bám đầu danh sách | Hàm cùng file xếp theo cosine. Seed **trong cùng mức verdict** xếp theo cosine, để node liên quan theo nghĩa lên đầu, nhắm vào thiên lệch vị trí |
| E4 | **Verifier / calibrator** | 40 node đầu theo thứ tự ưu tiên (target A3 → seed → node tìm qua graph); calibrator 20 đặc trưng | Thứ tự ưu tiên xen kẽ theo cosine, để node có cosine cao được verifier xem. Thêm đặc trưng `dense_sim` và `dense_rank_inv`, fit lại calibrator trên swe_train |

## Đánh giá theo giai đoạn (ít chi phí nhất)

**Giai đoạn 0 ($0):**
- module `src/modules/embed.py` có guard, cache sqlite theo hash, gọi theo lô;
- test dùng stub.

**Giai đoạn 1 (chỉ tốn tiền embedding, ước khoảng $1–2):**
- Tập: swe_train (100, dùng để chọn) + held-out 6 (50, dùng để kiểm). Dùng artifact mini `a2p_c4` đã có.
- (i) Thu văn bản (graph, mỗi instance một process có trần cgroup): tập A2, vùng explore, candidate, query.
- (ii) Embed (một process, không mở graph, có guard).
- (iii) Đo offline:
  - E1: số gold vào cửa sổ duyệt khi gộp lai, so với cửa sổ hiện tại (giả định reviewer giữ gold như đã đo: 95–100%).
  - E2: độ phủ gold bị bỏ sót khi lấy k node đầu (k = 30 / 60 / 100), so với O0–O3 (đang 22–67% ở k=100).
  - E3, E4: gold lọt vào 40 node verifier xem; đáp án cuối khi fit lại calibrator có đặc trưng dense (fit trên swe_train, kiểm trên held-out 6). Đây là phép đo đầu-cuối offline, vì candidate không đổi.

**Luật chọn (trên swe_train):** giữ một điểm Ex nếu nó cải thiện thước đo của chính nó ít nhất 20% tương đối so với cách hiện tại, và không làm thước đo khác giảm. Kiểm lại trên held-out 6; nếu đổi chiều thì không giữ.

**Giai đoạn 2 (có trả phí):** tích hợp các điểm được giữ, bật bằng biến môi trường. Pilot, rồi chạy held-out 6 (khoảng $2).

**Giai đoạn 3 (đánh giá cuối):** đóng băng cấu hình, chạy held-out 7 (150–300 id). Báo cáo SL / REC / PRE / F1, chi phí và thời gian của cả hai bên, kèm ablation không embedding.

## Kết quả giai đoạn 1 (2026-10-23; `.tmp/audit_v6/embed_eval.txt`)

**Chạy:**
- Thu văn bản: 150/150 instance, không lỗi, RAM đỉnh 0.6 GB.
- Embed: 119 373 văn bản khác nhau, 467 request, 18,77 triệu token, **$0.375**; khoảng 125 nghìn token mỗi instance, tức khoảng $0.0025.
- Đánh giá offline: 72 giây, 0.45 GB, không gọi API.

| Điểm | Thước đo | swe_train (chọn) | held-out 6 (kiểm) | Theo luật (≥ +20% tương đối trên swe_train, cùng chiều ở held-out 6) |
|---|---|---|---|---|
| **E2 explore** | gold bị bỏ sót được phủ ở k=60, so với O0 (xếp theo từ khóa, đang dùng) | **38% so với 18%** (+111%); thứ tự tốt nhất trước đó O2: 28% | **22% so với 16%** (+38%); O3: 22% | **Giữ** |
| E1 A2 lai | gold vào cửa sổ duyệt | 109 → 120 (+10%) | 56 → 61 (+9%) | Không đạt ngưỡng (cùng chiều nhưng nhỏ) |
| E3 hàm cùng file | gold nằm trong top 10 của file | 131 → 157 (+19.8%) | 66 → 75 (+14%) | Sát ngưỡng, không đạt. Top 40: +3% |
| E4 tầm xem verifier | gold trong 40 candidate đầu | 113 → 124 xen kẽ (+10%) | 60 → 64 (+7%) | Không đạt |
| E4 calibrator | F1 mức function trên held-out 6, so với calibrator mini (M) | — | Lite 28.3 → 29.2; LocBench 29.4 → 31.0 (M+dense) | Không đạt (+3–5%) |

**Biến thể query:** Q1 (issue gốc) ≈ Qmax > Q2 trên swe_train. Chọn Qmax (max của hai cosine).

Với E2, "A..C1 trước, D-file/C2 sau" kém hơn cosine thuần trên swe_train, nhưng tốt hơn ở k=30–60 trên held-out 6. Theo luật, chọn cosine thuần (chọn trên swe_train).

**Nhận xét:**
- Embedding có tác dụng rõ nhất ở chỗ cấu trúc graph không có tín hiệu từ khóa, tức xếp hạng **vùng explore** (E2).
- Ở các điểm khác, cải thiện **nhỏ nhưng cùng chiều trên cả hai tập** (+7–20%).
- Làm đặc trưng cho calibrator, `dense` cho kết quả **ngang** đặc trưng pointwise (M+dense: Lite 29.2, LocBench 31.0; M+pw: Lite 29.4, LocBench 31.8), với chi phí khoảng 1/4 ($0.0025 so với khoảng $0.01 mỗi instance). Gộp cả hai không tốt hơn.

## Giai đoạn 2: E2 và calibrator dense (2026-10-23; `.tmp/audit_v6/stage2_offline.txt`)

Cả hai phần đều đo **chính xác offline**, không gọi LLM: node E2 được đặt sau mọi candidate có sẵn, nên 40 node verifier xem và nhãn của verifier giữ nguyên như lần chạy đã lưu.

**Thiết kế (ghi trước khi đo):**
- E2: thêm M node của vùng explore có cosine cao nhất (Qmax) và chưa là candidate. M ∈ {0, 30, 60}.
- Calibrator: FEATURES_V5 + `dense_sim` + `dense_rank_inv` + cờ `e2`; logistic L2 1.0; ngưỡng theo luật A10.
- Chọn M trên swe_train theo SL out-of-fold.

**E2 nối cuối danh sách (sau verifier):**

| M | ngưỡng | swe_train out-of-fold SL / REC / PRE / F1 |
|---|---|---|
| **0** | 0.045 | **38.0** / 46.9 / 23.8 / 27.8 |
| 30 | 0.045 | 38.0 / 47.9 / 24.9 / 28.3 |
| 60 | 0.0425 | 37.0 / 46.4 / 23.8 / 27.3 |

Theo luật (SL bằng nhau thì lấy M nhỏ hơn), chọn **M = 0**.

Lý do E2 không giúp (`stage2_diag.py`):
- Với M = 30, E2 thêm 33 gold trên swe_train; 11 instance lần đầu có gold.
- Nhưng verifier không xem những node này, nên p của chúng thấp: 0.005–0.11, hầu hết dưới ngưỡng 0.045.
- Trên held-out 6, E2 chỉ thêm 8 gold, xếp hạng 16–90.

**E2 đưa vào tầm xem verifier** (40 − k node theo thứ tự ưu tiên + k node E2; đếm gold vào / ra tầm xem, `e2_k_choice.py`):

| k | swe_train | held-out 6 |
|---|---|---|
| 5 | +15 / −7 | +1 / −3 |
| 10 | +19 / −11 | +2 / −6 |
| 20 | +30 / −18 | +5 / −11 |

Chiều trên held-out 6 ngược với swe_train, nên **không giữ** và không chạy trả phí để thử thêm.

**Kết luận về E2:** mở rộng vùng explore bằng embedding đưa thêm gold vào danh sách, nhưng một mô hình nhỏ không xác nhận được chúng. Vì vậy E2 không cải thiện đáp án cuối.

**Calibrator dense (giữ):** `src/modules/data/calibrator_mini_dense.json`
- 22 đặc trưng: bỏ cờ `e2`, vốn có trọng số 0 khi M = 0.
- recall_p 0.045.
- Trọng số lớn: `v_edited` +1.63, `v_rank_inv` +1.53, `dense_rank_inv` +1.23, `dense_sim` +1.20, `seed_rank_inv` +1.17.

Kết quả trên held-out 6, mức function, SL / REC / PRE / F1:

| Benchmark | calibrator luna | mini + pointwise | **mini + dense** |
|---|---|---|---|
| Lite | 44.0 / 52.7 / 21.5 / 27.1 | 36.0 / 46.7 / 24.1 / 29.4 | **40.0 / 48.7 / 23.8 / 29.2** |
| LocBench | 36.0 / 46.2 / 21.5 / 26.3 | 32.0 / 42.2 / 31.3 / 31.8 | **32.0 / 43.2 / 30.7 / 31.0** |

Pointwise cần khoảng 64 lời gọi mini mỗi instance (khoảng $0.01); dense chỉ embed các candidate (khoảng $0.0025, phần lớn được cache).

**Tích hợp vào pipeline (branch `exp/embed`):**
- `load_or_verify` gọi `add_dense` khi calibrator có đặc trưng `dense_sim`; chọn bằng `JACC_CALIBRATOR=src/modules/data/calibrator_mini_dense.json`.
- Chỉ embed các candidate, qua `Embedder` có guard.
- Số token embedding được ghi vào `A3V_verify*.json` (khóa `embed`) để tính chi phí.
- Kiểm tra tương đương: pipeline trên graph thật cho p khớp bản offline, sai khác < 1e-7 trên 3 instance, 0 lời gọi API (`dense_equiv.py`).
- Test stub: `tests/test_embed.py`.

**Bước tiếp:**
- h7s50 (chỉ chẩn đoán): `bash .tmp/run_dense_h7s50.sh`. Chỉ tốn tiền embedding, khoảng $0.15; có thêm ablation không embedding (calibrator M).
- Sau đó là đánh giá cuối trên held-out 7.

## h7s50 (50 id mới, chỉ chẩn đoán; 2026-10-23, `.tmp/run_dense_h7s50.sh`)

- Pilot 2 id đạt; 50/50 instance chạy xong, không lỗi; RAM tối đa khoảng 0.47 GB mỗi process.
- Embedding: 320 nghìn token, **$0.0064** (phần lớn văn bản đã có trong cache).

Mức function, gộp 50 id, SL / REC / PRE / F1:

| Cấu hình | SL | REC | PRE | F1 |
|---|---|---|---|---|
| mini + calibrator dense (embedding) | 58.0 | 61.0 | 20.8 | 29.0 |
| mini + calibrator M (không embedding) | 58.0 | 60.6 | 20.8 | 28.6 |
| mini + calibrator pointwise | 58.0 | 61.0 | 25.1 | 33.4 |
| mini + calibrator luna | 64.0 | 66.6 | 16.9 | 25.0 |
| GraphLocator gpt-4o | 60.0 | 64.4 | 29.0 | 33.6 |

Theo từng benchmark, so dense với M:
- Lite: SL / F1 64.0 / 27.6 so với 64.0 / 28.4.
- LocBench: SL / F1 52.0 / 30.3 so với 52.0 / 28.8.

**Kết luận:**
- Trên dữ liệu mới, đặc trưng dense **gần như không thêm gì** so với calibrator không embedding (F1 +0.4, SL bằng nhau).
- Calibrator dense **kém** pointwise về precision (20.8 so với 25.1).
- Lợi thế thấy trên held-out 6 không lặp lại.
- Cùng với E1–E4 (giai đoạn 1–2), embedding chưa cho cải thiện nào đứng vững. Không đưa embedding vào cấu hình cuối.

## Vì sao embedding xếp gold tốt mà đáp án cuối không tốt lên (2026-10-23)

Script và output:
- `.tmp/audit_v6/gold_similarity.py` → `gold_similarity.txt`
- `.tmp/audit_v6/a2_window_dense.py` → `a2_window_dense.txt`

Chạy offline, chỉ đọc vector từ cache.

**Kiểm tra tính đúng của dữ liệu:**
- Không thiếu vector nào: 0 trên 177 197 (swe_train), 0 trên 82 659 (held-out 6).
- Mọi vector đều có độ dài 1, sai lệch tối đa 0.0002.
- 100% văn bản của gold có thân hàm.
- Luật cửa sổ A2 dựng lại khớp đúng tập node đã duyệt: 299/299 và 150/150 vòng.
- **Đối chứng âm:** chấm gold bằng issue của một instance khác cho AUC 0.499 / 0.506, đúng như kỳ vọng là không có tín hiệu.
- **Độ dài văn bản:** riêng độ dài cho AUC 0.69, nên một phần tín hiệu đến từ việc gold là hàm dài hơn. Cosine (0.90) vượt xa mức đó.
- Helper (AUC, BM25, thứ tự, `_loc`) có self-check.

**1. Embedding xếp gold rất tốt trong mọi vùng.**

AUC gold so với non-gold, và số gold trong top 10 / 60:

| Vùng | Bộ xếp | swe_train | held-out 6 |
|---|---|---|---|
| A2 đã tìm ra | **cosine Qmax** | **0.892**, 84 / 121 | **0.910**, 37 / 65 |
| | BM25 trên cùng văn bản | 0.876, 67 / 122 | 0.842, 27 / 60 |
| | RRF (A2 đang dùng) | 0.838, 65 / 105 | 0.813, 33 / 58 |
| | seed (max cosine tới seed) | 0.810, 32 / 114 | 0.751, 11 / 59 |
| Explore | **cosine Qmax** | **0.904**, 90 / 130 | **0.929**, 36 / 66 |
| | BM25 | 0.912, 64 / 118 | 0.917, 32 / 61 |

Với gold chưa từng thành candidate:
- Cosine vẫn có AUC 0.82–0.85.
- Trong vùng A2 (swe_train), RRF gần như ngẫu nhiên (AUC 0.597; top 60: 6 gold, so với 22 của cosine).
- So với BM25 trên cùng văn bản, cosine thắng rõ ở top 10, gần bằng ở AUC.
- Độ giống với seed yếu hơn độ giống với issue.

**2. Gold rơi ở đâu** (số hàm gold):

| Bước | swe_train | held-out 6 |
|---|---|---|
| gold | 229 | 114 |
| nằm trong một vùng (A2, explore hoặc candidate) | 220 | 94 |
| A2 tìm ra | 148 | 75 |
| vào cửa sổ duyệt A2 | 109 | 56 |
| seed | 104 | 53 |
| candidate | 131 | 69 |
| verifier xem (40) | 113 | 60 |
| verifier gán `edited` | 87 | **38** |
| đáp án (calibrator luna / calibrator dense) | 91 / 84 | 41 / 38 |

**3. Đổi cửa sổ duyệt A2 sang cosine:**

| Cửa sổ | swe_train: gold thấy được (mới) | held-out 6: gold thấy được (mới) |
|---|---|---|
| RRF (hiện tại) | 109 (4) | 56 (0) |
| cosine | 107 (18) | 56 (4) |
| xen kẽ | 120 (20) | 56 (1) |

Trên held-out 6, cosine chỉ đổi gold nào được thấy, không tăng tổng số.

**Kết luận:**
- Embedding **có** cải thiện xếp hạng khi retrieve và explore. Tín hiệu là thật, theo cả đối chứng âm lẫn so với RRF.
- Nhưng chỗ nghẽn của mini nằm sau bước tìm kiếm:
  - Verifier mini bác bỏ 37% số gold nó được xem trên held-out 6 (60 gold được xem, 38 được gán `edited`; trên swe_train 113 → 87).
  - Phần gold ở top của vùng explore mà chưa là candidate rất loãng: trên held-out 6, top 60 cosine chứa 10 / 23 gold như vậy, nằm giữa khoảng 3 000 node thêm vào. Mật độ đó thấp hơn mật độ gold ở cuối danh sách verifier đang xem, nên thêm vào là đẩy gold khác ra.
  - 20 / 114 gold trên held-out 6 không nằm trong vùng nào; embedding trong vùng đã khoanh không chạm tới được.
- Đòn bẩy lớn nhất còn lại là **khả năng phán đoán của verifier** (gold xem được nhưng không giữ), không phải xếp hạng khi tìm kiếm.

## Audit code embedding (2026-10-23)

Audit gồm tự đọc lại code và một reviewer độc lập chỉ đọc, không gọi API, không mở graph.

**Đã kiểm và đúng:**
- **Số chiều:** 121 058 vector trong cache, tất cả 1536 chiều (float16, 3072 byte); chuẩn ≈ 1. "Độ dài 1" ở mục trước là chuẩn (norm), không phải số chiều.
- **Đủ vector:** reviewer tính lại khóa sha256 cho mọi văn bản trong 150 file `embed_texts`: thiếu 0/300 query, 0/9 543 candidate, 0/250 313 node khác. Không kết quả offline nào bị vector 0 làm sai.
- **Văn bản khớp nhau:** văn bản lúc thu thập (`embed_collect.py`) giống từng byte với văn bản pipeline tạo ra (`node_texts`, `issue_queries`). Cắt `MAX_CHARS` trước khi băm ở cả hai đường. Vector mới gọi API được làm tròn float16 như vector lấy từ cache.
- **Đặc trưng lúc fit khớp lúc chạy:** cùng tập dòng, xếp hạng trong toàn bộ dòng, max của Q1 và Q2.
- **Không rò dữ liệu khi fit:** fold theo instance, ngưỡng chọn trên p out-of-fold, held-out 6 không dùng để fit.
- **Metric:** AUC tính hòa bằng một nửa; CI bootstrap lấy phân vị 2.5 / 97.5.

**Lỗi đã sửa** (`src/modules/embed.py`, `src/run_localize.py`; 4 test mới fail trên code cũ, pass trên code mới; 194 test pass):
1. Phản hồi API thiếu vector thì vector thiếu bị điền 0 mà không báo. Giờ ghép theo `index` và báo lỗi nếu thiếu.
2. Chạy offline với cache trống trả vector 1 chiều. Giờ dùng `DIM = 1536`.
3. Embedding chạy sau lời gọi verifier, nên embedding lỗi thì mất tiền verifier. Giờ embedding chạy trước verifier (tập candidate không đổi qua verifier; có assert), rồi đặc trưng dense được gắn lại vào các dòng.

Không lỗi nào ảnh hưởng số liệu đã báo: không lần chạy nào gặp phản hồi thiếu, cache trống, hay embedding lỗi.

**Lệch quy trình cần nêu rõ:**
- **Held-out 7 đã bị chạm:** 50 id h7s50 nằm trong held-out 7 (25/150 Lite, 25/150 LocBench). Quyết định bỏ embedding dựa trên chúng. Đánh giá cuối phải loại 50 id này (còn 250 id) hoặc nêu rõ.
- **Không theo đúng luật chọn đặt trước:** giai đoạn 1 ghi calibrator dense "không đạt" (+3–5%), nhưng giai đoạn 2 vẫn giữ và tích hợp, dựa trên held-out 6 (tập đã dùng để kiểm ở giai đoạn 1). h7s50 sau đó đảo lại quyết định này, nên kết quả ròng là không thay đổi gì.
- **Ablation không embedding phải chấm lại offline** trên A3V đã lưu, như h7s50 đã làm. Đổi `JACC_CALIBRATOR` sẽ làm verifier chạy lại vì khóa cache có phiên bản calibrator: tốn tiền, và nhãn mới làm lẫn hiệu ứng của embedding với độ dao động của verifier.
- **Chi phí:** `Embedder.tokens` chỉ đếm văn bản chưa có trong cache. Cache đã được làm nóng trong lúc phát triển, nên con số trên h7s50 ($0.0064) thấp hơn chi phí khi cache trống, khoảng $0.0025 mỗi issue (giai đoạn 1).
- **Nhỏ:**
  - `embed_eval.py` dùng một `add_dense` cũ (theo `_loc`, phá hòa khác). Chỉ ảnh hưởng dòng "E4 calibrator" của giai đoạn 1; giai đoạn 2 dùng bản đúng.
  - Số "answer (mini dense cal.)" trên swe_train trong `a2_window_dense.txt` là trong mẫu, vì calibrator fit trên swe_train.
  - Ngưỡng 3 000 node của vùng explore phụ thuộc thứ tự graph trả về, nên số E2 không hoàn toàn tái lập được.
