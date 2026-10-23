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
