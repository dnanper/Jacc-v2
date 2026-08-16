# Bộ Benchmark – Metric – Baseline chuẩn cho luận văn "Tạo đồ thị + bộ công cụ truy vấn cho agent"

**Tài liệu quyết định.** Không khảo sát thêm — chọn dứt khoát, kèm số liệu baseline để đối chiếu trực tiếp.
Ngày: 08/08/2026

---

## 0. Kết luận chọn

Bạn cần **đúng 2 bộ dataset**. Một bộ phục vụ cả hai khía cạnh, một bộ chỉ phục vụ khía cạnh chất lượng đồ thị.

| | **BỘ 1 — SWE-bench Lite + Loc-Bench** | **BỘ 2 — PyCG Evaluation Suite** |
|---|---|---|
| **Vai trò** | Bộ chính. Phục vụ **cả** khía cạnh A (graph-intrinsic, không LLM) **và** khía cạnh B (hệ thống có agent) | Bộ phụ. Chỉ phục vụ khía cạnh A — độ đúng của cạnh so với ground truth |
| **Venue** | ICLR 2024 (SWE-bench) + ACL 2025 (Loc-Bench) | ICSE 2021 |
| **Public** | ✔ HuggingFace + GitHub | ✔ GitHub, có Docker, có script sinh bảng |
| **Ground truth** | Gold patch → file/function/line | Call graph thủ công (micro) + dynamic trace (macro) |
| **Mức phổ biến** | **100% paper code-KG 2025–2026** dùng SWE-bench Lite | Chuẩn de-facto cho call graph Python |
| **Số baseline có sẵn** | **16 baseline có số liệu đầy đủ** (§4) | 3 baseline (PyCG, Pyan, Depends) |

**Vì sao chọn đúng bộ này cho đề tài của bạn:**
- Đề tài của bạn = **đồ thị + toolset cho agent**. Đây chính xác là định vị của LocAgent (ACL 2025) và ARISE. Hai công trình đó dùng SWE-bench Lite + Loc-Bench, nên bạn **so sánh trực tiếp được với chúng mà không cần chạy lại**.
- Loc-Bench là benchmark **duy nhất được thiết kế riêng cho localization** — tức đo đúng thứ mà toolset của bạn ảnh hưởng trực tiếp — và nó **chống nhiễm dữ liệu** (issue sau 10/2024).
- PyCG là nơi duy nhất có ground truth cạnh công khai cho Python. Không có lựa chọn thay thế.

**Điều KHÔNG chọn và lý do:** CrossCodeEval/RepoBench (đo completion, không đo localization — sai trục với đề tài); Multi-SWE-bench/SWE-PolyBench (chỉ thêm nếu bạn làm đa ngôn ngữ); Defects4J (Java, không có issue description); GraphRAG-Bench (không phải code).

---

# PHẦN A — Đánh giá chất lượng ĐỒ THỊ

Chia 2 tầng. **A1 đo đồ thị có đúng không. A2 đo đồ thị có hữu ích không — cả hai đều không cần LLM.**

## A1. Độ đúng của cạnh — PyCG Evaluation Suite

**Nguồn:** Salis, V., Sotiropoulos, T., Louridas, P., Spinellis, D., Mitropoulos, D. *PyCG: Practical Call Graph Generation in Python.* **ICSE 2021.** arXiv:2103.00587
**Artifact:** `github.com/vitsalis/pycg-evaluation` · DOI artifact: 10.5281/zenodo · License Apache 2.0

### Dataset

| Thành phần | Nội dung | Ground truth |
|---|---|---|
| **Micro-benchmark** | **112 module Python tối giản**, mỗi module cô lập một đặc trưng ngôn ngữ (generators, closures, multiple inheritance, decorators, ...) | Thủ công |
| **Macro-benchmark** | **5 package Python thật** (Git submodules) | **Call graph ground-truth đi kèm sẵn** |

Có script sẵn: `compare_macro_benchmark_cg.py` sinh CSV precision/recall; `table4.py` (precision/recall), `table5.py` (thời gian) tái tạo bảng của paper.

**Mở rộng nếu cần quy mô lớn hơn:** Jarvis benchmark (arXiv:2305.05949, nộp TOSEM) — **135 chương trình micro** + **6 ứng dụng thật**. Cách dựng ground truth macro của Jarvis đáng sao chép: chạy test case, thu call trace bằng `python -m trace --listfuncs`, chuyển về format micro-benchmark, **lọc bỏ** call ẩn do interpreter sinh (ví dụ `_frozen_importlib` khi import), rồi **mở rộng thủ công** bằng cách kiểm tra các application function.

### Metric

```
Precision = |E_gen ∩ E_gold| / |E_gen|      ← cạnh sinh ra có đúng không
Recall    = |E_gen ∩ E_gold| / |E_gold|     ← có bỏ sót cạnh không
F1        = 2PR/(P+R)
+ Thời gian (giây), Bộ nhớ (MB) trên macro-benchmark
```

### Baseline có sẵn (§Table 4–5 của PyCG)

| Tool | Precision | Recall | Ghi chú từ paper |
|---|---|---|---|
| **PyCG** | **~99.2%** | **~69.9%** | Trên mọi case >98% cạnh sinh ra là true positive; có case 0 false positive |
| Pyan | Trung bình | **Thấp** | Precision trung bình vì thêm cạnh tới tên class thay vì `__init__`; recall thấp vì không theo dấu inter-procedural flow |
| Depends | Hơi thấp hơn PyCG | Thấp hơn Pyan | |
| **Jarvis** | **+84% so với PyCG** | **+≥20% so với PyCG** | Nhanh hơn ≥67% |

### ⚠️ Ba giới hạn phải nêu rõ trong luận văn

1. **PyCG chỉ đánh giá cạnh CALLS.** Không có ground truth cho `contains`, `imports`, `inherits`. Đây **không phải vấn đề** — lập luận đúng là: các cạnh đó **tất định từ AST**, precision/recall ≈ 1.0 theo cấu tạo, nên không cần đánh giá thực nghiệm. Chỉ cạnh cần phân giải symbol mới cần đo. Hãy nói thẳng điều này thay vì im lặng.

2. **Không có ground truth chuẩn công khai cho cạnh data-flow trong Python.** Nếu schema của bạn có def-use edge (như ARISE), bạn phải **tự dựng ground truth**. Cách khả thi nhất: chọn 3–5 package trong macro-benchmark, chạy dynamic trace hoặc dùng `ast` + kiểm tra thủ công trên tập function ngẫu nhiên (~200 function), báo cáo precision/recall trên tập đó và **nêu rõ đây là ground truth do bạn dựng**, kèm quy trình.

3. **Ranh giới giữa "cạnh thiếu" và "cạnh sai" có hệ quả khác nhau cho agent.** ARISE phát biểu rõ nguyên tắc này: *cạnh giả (false positive) khiến agent đi theo đường sai, có thể tai hại hơn cạnh thiếu (false negative)* — nên họ **chỉ resolve các trường hợp không mơ hồ** (direct call, qualified `module.function()` với alias đã biết) và **âm thầm bỏ** dynamic dispatch qua attribute access. CGM chọn **ngược lại**: over-approximation — với lời gọi method lớp cơ sở, đưa **tất cả** implementation override từ subclass vào tập calls; và dùng **Class Hierarchy Analysis (CHA)** cho đa kế thừa.
   → **Đây là điểm tranh luận thiết kế bạn nên khai thác.** Báo cáo precision và recall **riêng biệt**, không gộp thành F1, và thảo luận trade-off theo hướng "cái nào tốt hơn cho agent". Đây là đóng góp phân tích rẻ mà có giá trị.

---

## A2. Chất lượng đồ thị theo tác vụ — đo TRÊN SWE-bench Lite / Loc-Bench, KHÔNG cần LLM

Đây là tầng bị bỏ quên nhất và là chỗ bạn dễ tạo khác biệt. Ba metric dưới đây tính **hoàn toàn từ đồ thị + gold patch**, không gọi LLM lần nào, nên chạy nhanh và không nhiễu.

### A2.1. Gold-Reachability@h — đồ thị có CHỨA đường đi tới đáp án không?

Đây là **điều kiện cần** của mọi hệ dùng đồ thị: nếu node gold không tới được từ điểm xuất phát trong h hop, không agent nào tìm ra được.

**Cách tính** (dẫn xuất từ công thức phân tầng độ khó của LocAgent §C.2):

```
1. Trích tên function/class từ issue description  → tập C (candidate nodes)
   (LocAgent dùng GPT-4o; bạn có thể dùng regex + fuzzy match để giữ metric hoàn toàn LLM-free)
2. Ánh xạ gold patch → tập T (target nodes)
3. δ = (1/|T|) · Σ_{t∈T}  min_{c∈C} d(c, t)     ← d = khoảng cách hop ngắn nhất
4. Gold-Reachability@h = tỷ lệ instance có δ ≤ h
5. Báo cáo phân bố: Hop 0 / 1 / 2 / 3+
```

**Vì sao metric này mạnh:** nó chứng minh giá trị schema **độc lập với chất lượng LLM**. Nếu schema của bạn đưa 20% instance từ "Hop 3+" xuống "Hop 1", đó là bằng chứng cấu trúc thuần tuý — reviewer không thể phản biện "kết quả do model tốt".

**Bằng chứng schema quan trọng từ LocAgent:** hai module ở thư mục xa nhau (A và B) trông không liên quan khi duyệt theo cây thư mục, nhưng nếu chúng gọi nhau hoặc kế thừa nhau thì **gần nhau về mặt cú pháp** trong biểu diễn đồ thị. Đây chính là thứ Gold-Reachability đo được mà file-tree không đo được.

### A2.2. Coverage@budget — chất lượng retrieval tách rời khỏi reasoning của agent

**Nguồn:** ARISE §3.5. Định nghĩa: *tỷ lệ dòng gold được phủ bởi output của `build_context_bundle` dưới budget 8,000 token* — **đo chất lượng retrieval độc lập với reasoning của agent**.

Với điều kiện không dùng context bundling, ARISE tính Coverage@budget trên **cửa sổ BM25 top-k có kích thước token tương đương**, để so sánh công bằng.

**Số liệu tham chiếu (SWE-bench Lite, budget 8k token):**

| Điều kiện | Coverage@budget | Line IoU |
|---|---|---|
| RAG (BM25) | 20.0 | 0.06 |
| SWE-agent | 53.0 | 0.21 |
| ARISE-STRUCTURAL | 61.0 | 0.26 |
| ARISE-COARSE | 62.0 | 0.27 |
| ARISE-SLICING | 71.0 | 0.33 |
| ARISE-FULL | **75.0** | **0.36** |

Đây là bảng bạn nên nhắm tới để so sánh trực tiếp.

### A2.3. Thống kê đồ thị & chi phí dựng

| Metric | Số liệu tham chiếu |
|---|---|
| #node, #edge trung bình / repo | RepoGraph báo cáo cho SWE-bench dataset |
| **Thời gian dựng đồ thị** | CGM: **~3 phút/repo** trở lên tuỳ độ phức tạp; **offline, không ảnh hưởng inference**. LocAgent: **vài giây/codebase** |
| Dung lượng index | — |
| **Latency truy vấn / tool call** | ARISE: anchor matching + subgraph generation **3–7 giây/issue**, thao tác CPU nhẹ |

> **Lưu ý cho luận văn:** LocAgent nhấn mạnh rằng indexing chỉ mất vài giây/codebase khiến nó **thực tế cho dùng real-time**, và không cần sinh lại code embedding tốn kém khi codebase thay đổi. Nếu toolset của bạn dựng đồ thị nhanh, **đây là điểm bán hàng chính** so với dense retrieval — hãy đo và báo cáo.

---

# PHẦN B — Đánh giá HỆ THỐNG (agent dùng đồ thị)

## B1. Dataset

### SWE-bench Lite
Jimenez et al., **ICLR 2024**. arXiv:2310.06770 · `swebench.com` · `github.com/princeton-nlp/SWE-bench`

- **300 instance**, **11 repo Python** (Django, Flask, SymPy, Matplotlib, Pytest, Scikit-learn, ...)
- Mỗi instance: issue description + gold patch + test harness riêng, chạy trong **Docker**
- Oracle: **fail-to-pass testing** với **unit test do developer viết**
- **Cho localization:** LocAgent giữ **274/300** instance sau khi loại các instance không sửa function nào

**⚠️ Lệch phân bố nghiêm trọng** — đây là lý do bắt buộc phải có Loc-Bench:

| Category | SWE-bench Lite | **Loc-Bench** |
|---|---|---|
| Bug Report | 254 | 242 |
| Feature Request | 43 | **150** |
| Security Issue | **3** | **29** |
| Performance Issue | **0** | **139** |
| **Tổng** | **300** | **560** |

### Loc-Bench
Kèm LocAgent (**ACL 2025**). HuggingFace: `czlll/Loc-Bench_V1` · Repo: `github.com/gersteinlab/LocAgent`

- **560 instance**, 4 category cân bằng hơn nhiều
- **Chống nhiễm:** Bug Report thu từ issue **tạo sau 10/2024**, muộn hơn cutoff của phần lớn LLM hiện đại
- **Quy trình xây dựng** (nên trích khi mô tả dataset): repo Python **>5,000 stars**; mỗi PR gắn base commit; loại PR không giải quyết issue tường minh; **loại PR sửa >5 file Python hoặc >10 function**; loại PR không có function-level edit; nhãn category do GPT-4o phân loại **sample 3 lần**, review thủ công khi không nhất quán
- Security/Performance thu bằng GitHub Search API với keyword liệt kê ở Table 10 của paper

**Định nghĩa ground truth (thống nhất — dùng đúng như vậy):**
- **File gold** = tập file bị gold patch sửa
- **Function gold** = ánh xạ mỗi diff hunk về function/method bao quanh
- **Line gold** = hợp mọi dòng bị chạm (dòng +/−), **loại trừ** context line và dòng trống
- **Loại trừ khỏi target:** document, import statement, comment — *"chúng không ảnh hưởng trực tiếp tới chức năng hoặc thực thi của code"*

## B2. Metric — dùng đúng bộ này

### B2.1. Localization (metric chính cho đề tài của bạn)

| Metric | Định nghĩa chính xác | Nguồn |
|---|---|---|
| **Acc@k (STRICT)** | Thành công **chỉ khi TẤT CẢ** vị trí liên quan nằm trong top-k. Lấy cảm hứng từ R-Precision trong IR | LocAgent |
| **NDCG@k** | Chất lượng xếp hạng | LocAgent Table 11 |
| **Recall@k** | Có **ít nhất một** vị trí gold trong top-k (lỏng hơn Acc@k) | ARISE |
| **MRR** | Mean reciprocal rank của vị trí gold đầu tiên | ARISE |
| **F1@k** | Harmonic mean của precision@k và recall@k — **phạt over-prediction** | ARISE |
| **IoU** | Intersection-over-union trung bình của tập dòng dự đoán và gold | ARISE |
| **Empty Rate** | Tỷ lệ trả về rỗng — quan trọng cho hệ agent | CoSIL |

**Cấu hình k chuẩn:**

| Dataset | File | Module | Function | Line |
|---|---|---|---|---|
| SWE-bench Lite | Acc@1, @3, @5 | Acc@5, @10 | Acc@5, @10 | R@1, @5, @10 |
| **Loc-Bench** | Acc@**5**, @**10** | Acc@**10**, @**15** | Acc@**10**, @**15** | — |

> Loc-Bench dùng k lớn hơn vì instance có thể sửa **1–5 file**.

**Mức module là gì:** dự đoán được tính đúng nếu **bất kỳ function nào trong class bị patch** được xác định — đây là mức đánh giá lỏng hơn function, dùng để thấy hệ thống "đúng lớp nhưng sai hàm".

### B2.2. Downstream (metric phụ, để nối vào leaderboard)

- **Resolve Rate / %R**: tỷ lệ instance mà patch làm pass toàn bộ test. Định nghĩa của CGM: patch được coi resolved nếu nó **giải quyết đúng issue và là superset của gold edits**
- **Pass@1 / Pass@10**

### B2.3. Chi phí

$/instance · tokens/instance (**phân rã theo loại tool**) · số vòng agent · **cost-efficiency = Acc@10 / cost**

## B3. Giao thức chạy — 2 task ĐỘC LẬP

Đây là chi tiết dễ bỏ sót nhưng quyết định độ chặt của kết luận. ARISE chạy localization và repair **tách rời**, mỗi task có **system prompt riêng và output format riêng**:

- **Localization task** → trả về danh sách xếp hạng `{file, function, start_line, end_line, score}`, parse bằng regex tất định
- **Repair task** → trả về unified diff, apply vào repo snapshot, chạy test suite

**Lý do phải tách:** để đo được **tương quan Spearman ρ giữa Function Recall@1 và Pass@1**. Nếu chạy chung một lượt thì hai metric không độc lập và tương quan trở nên vô nghĩa.

**Yêu cầu công bằng bắt buộc:** baseline SWE-agent **phải dùng cùng system prompt localization và cùng output format** như các điều kiện của bạn, để evaluation protocol giống hệt nhau.

---

# PHẦN C — Bảng baseline đầy đủ

## C1. SWE-bench Lite — Localization (giao thức LocAgent, 274 instance)

Đây là bảng đối chiếu chính. Tất cả số liệu từ **LocAgent Table 4 (ACL 2025)**. Agent-based dùng GPT-4o-2024-0513 và Claude-3.5-Sonnet-20241022.

| Loại | Method | Model | File Acc@1 | @3 | @5 | Module @5 | @10 | Function @5 | @10 |
|---|---|---|---|---|---|---|---|---|---|
| Embedding | BM25 | — | 38.69 | 51.82 | 61.68 | 45.26 | 52.92 | 31.75 | 36.86 |
| Embedding | E5-base-v2 | — | 49.64 | 74.45 | 80.29 | 67.88 | 72.26 | 39.42 | 51.09 |
| Embedding | Jina-Code-v2 | — | 43.43 | 71.17 | 80.29 | 63.50 | 72.63 | 42.34 | 52.19 |
| Embedding | Codesage-large-v2 | — | 47.81 | 69.34 | 78.10 | 60.58 | 69.71 | 33.94 | 44.53 |
| Embedding | **CodeRankEmbed** | — | 52.55 | 77.74 | 84.67 | 71.90 | 78.83 | 51.82 | 58.76 |
| Procedure | Agentless | GPT-4o | 67.15 | 74.45 | 74.45 | 67.15 | 67.15 | 55.47 | 55.47 |
| Procedure | **Agentless** | Claude-3.5 | 72.63 | 79.20 | 79.56 | 68.98 | 68.98 | 58.76 | 58.76 |
| Agent | MoatlessTools | GPT-4o | 73.36 | 84.31 | 85.04 | 74.82 | 76.28 | 57.30 | 59.49 |
| Agent | MoatlessTools | Claude-3.5 | 72.63 | 85.77 | 86.13 | 76.28 | 76.28 | 64.60 | 64.96 |
| Agent | SWE-agent | GPT-4o | 57.30 | 64.96 | 68.98 | 58.03 | 58.03 | 45.99 | 46.35 |
| Agent | **SWE-agent** | Claude-3.5 | 77.37 | 87.23 | 90.15 | 77.74 | 78.10 | 64.23 | 64.60 |
| Agent | OpenHands | GPT-4o | 60.95 | 71.90 | 73.72 | 62.41 | 63.87 | 49.64 | 50.36 |
| Agent | **OpenHands** | Claude-3.5 | 76.28 | 89.78 | 90.15 | 83.21 | 83.58 | 68.25 | 70.07 |
| **Graph** | **LocAgent** | Qwen2.5-7B(ft) | 70.80 | 84.67 | 88.32 | 81.02 | 82.85 | 64.23 | 71.53 |
| **Graph** | **LocAgent** | Qwen2.5-32B(ft) | 75.91 | 90.51 | 92.70 | 85.77 | 87.23 | 71.90 | 77.01 |
| **Graph** | **LocAgent** | Claude-3.5 | **77.74** | **91.97** | **94.16** | **86.50** | **87.59** | **73.36** | **77.37** |

**Đây là 3 dòng bạn phải vượt.** Nếu không vượt được LocAgent+Claude-3.5, ít nhất phải vượt LocAgent+Qwen2.5-7B(ft) ở chi phí thấp hơn.

**Bảng NDCG tương ứng có sẵn ở LocAgent Table 11** — nhớ báo cáo cả hai.

### Baseline localization khác trên SWE-bench Lite (metric khác, không cùng bảng)

| Method | Venue | Metric | Kết quả |
|---|---|---|---|
| **OrcaLoca** | **ICML 2025** | Function match rate | **65.33%** |
| **CoSIL** | **ASE 2025** | **Top-1** accuracy | **43.3%** (Lite), **44.6%** (Verified), Qwen2.5-Coder-32B |
| **KGCompass** | preprint | Function-level fault location | **56.0%** |

## C2. Loc-Bench — Localization (560 instance)

Từ **LocAgent Table 7**. Tất cả agent-based dùng Claude-3.5.

| Loại | Method | Model | File Acc@5 | @10 | Module @10 | @15 | Function @10 | @15 |
|---|---|---|---|---|---|---|---|---|
| IR | CodeRankEmbed | — | 74.29 | 80.89 | 63.21 | 67.50 | 43.39 | 46.61 |
| Procedure | Agentless | Claude-3.5 | 67.50 | 67.50 | 53.39 | 53.39 | 42.68 | 42.68 |
| Agent | SWE-agent | Claude-3.5 | 77.68 | 77.68 | 63.57 | 63.75 | 51.96 | 51.96 |
| Agent | **OpenHands** | Claude-3.5 | 79.82 | 80.00 | 68.93 | 69.11 | 59.11 | 59.29 |
| **Graph** | LocAgent | Qwen2.5-7B(ft) | 78.57 | 79.64 | 63.04 | 63.04 | 51.43 | 51.79 |
| **Graph** | **LocAgent** | Claude-3.5 | **83.39** | **86.07** | **70.89** | **71.07** | **59.29** | **60.71** |

**Quan sát quan trọng cần trích:** LocAgent ghi nhận hiệu năng **giảm rõ rệt ở 3 category kia so với Bug Report**, và giải thích do phân bố dữ liệu training thiên về bug report. Nếu bạn báo cáo theo category, đây là một hướng phân tích có sẵn chỗ dựa.

## C3. SWE-bench Lite — Giao thức ARISE (cùng backbone Qwen2.5-Coder-32B-Instruct, 300 instance)

Bảng này quý vì **mọi dòng dùng cùng backbone, cùng harness, cùng prompt** — so sánh trực tiếp được, khác với C1.

### Localization

| Condition | File R@1 | R@3 | MRR | Fn R@1 | R@3 | F1@3 | MRR | Line R@1 | @5 | @10 | Cov@bud | IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RAG (BM25) | 30.0 | 42.0 | 0.33 | 15.0 | 25.0 | 0.14 | 0.18 | 5.0 | 12.0 | 18.0 | 20.0 | 0.06 |
| SWE-agent | 57.0 | 72.0 | 0.60 | 43.0 | 58.0 | 0.39 | 0.48 | 26.0 | 43.0 | 53.0 | 53.0 | 0.21 |
| **ARISE-STRUCTURAL** ← *parity LocAgent/RepoGraph* | 62.0 | 77.0 | 0.65 | 50.0 | 65.0 | 0.45 | 0.54 | 31.0 | 48.0 | 59.0 | 61.0 | 0.26 |
| **ARISE-COARSE** ← *control* | 62.0 | 77.0 | 0.65 | 51.0 | 65.0 | 0.46 | 0.54 | 32.0 | 49.0 | 60.0 | 62.0 | 0.27 |
| ARISE-SLICING | 65.0 | 80.0 | 0.68 | 57.0 | 72.0 | 0.52 | 0.60 | 38.0 | 59.0 | 71.0 | 71.0 | 0.33 |
| ARISE-EXPLAINSLICE | 65.0 | 80.0 | 0.68 | 57.0 | 72.0 | 0.52 | 0.60 | 38.0 | 59.0 | 71.0 | 71.0 | 0.33 |
| **ARISE-FULL** | **67.0** | **82.0** | **0.70** | **60.0** | **75.0** | **0.55** | **0.63** | **41.0** | **62.0** | **74.0** | **75.0** | **0.36** |

### Repair (cùng bảng, cùng backbone)

| Method | Backbone | Pass@1 | Resolved | Tokens (×1000) | **ρ (Spearman)** |
|---|---|---|---|---|---|
| RAG | Qwen2.5-Coder-32B | 2.67% | 8 | 13 | 0.05 |
| SWE-agent | Qwen2.5-Coder-32B | 17.3% | 52 | 510 | 0.38 |
| ARISE-STRUCTURAL | Qwen2.5-Coder-32B | 19.0% | 57 | 531 | 0.42 |
| ARISE-COARSE | Qwen2.5-Coder-32B | 19.5% | 59 | 535 | 0.43 |
| ARISE-SLICING | Qwen2.5-Coder-32B | 21.0% | 63 | 550 | 0.51 |
| **ARISE-FULL** | Qwen2.5-Coder-32B | **22.0%** | **66** | 560 | **0.53** |
| *Literature* SWE-agent | GPT-4o | 18.3% | 55 | 498 | — |
| *Literature* **RepoGraph**+SWE-agent | GPT-4o | 20.3% | 61 | 519 | — |
| *Literature* SWE-agent | Qwen3-4B | 12.0% | 36 | 391 | — |
| *Literature* RepoGraph+SWE-agent | Qwen3-4B | 12.7% | 38 | 422 | — |

**Cột ρ là metric mà gần như không ai báo cáo và bạn nên báo cáo.** Nó tăng đơn điệu 0.05 → 0.53, chứng minh cải thiện repair thực sự **đi qua** localization chứ không phải trùng hợp.

## C4. SWE-bench Lite / Verified — Resolve Rate (leaderboard)

| Method | Venue | Backbone | Lite %R | Verified %R | Cost |
|---|---|---|---|---|---|
| **KGCompass** | preprint | Claude-4 Sonnet | **58.3%** | — | **$0.2**/repair |
| KGCompass | preprint | Claude-3.5 Sonnet | 46.0% (137) | — | $0.2 |
| DARS Agent | — | Claude-3.5 | 47.00% | — | — |
| **CGM-SWE-PY** | **NeurIPS 2025** | Qwen2.5-72B | **43.00%** | **50.40%** | — |
| Lingxi | — | Claude-3.5 | 42.67% | — | — |
| **Agentless-v1.5** | **FSE 2025** | Claude-3.5 | **40.67%** | 50.80% | — |
| Moatless | — | Claude-3.5 | 39.00% | — | $1.3 (OpenHands ref) |
| CGM-Multi | NeurIPS 2025 | Qwen2.5-72B | 36.67% | — | — |
| **Prometheus** | preprint | DeepSeek-V3 | **35.33%** | — | $0.23/issue |
| Agentless Lite | — | o3-mini | 32.33% | 42.40% | — |
| Agentless-v1.5 | FSE 2025 | GPT-4o | 32.00% | 38.80% | — |
| Moatless | — | DeepSeek-V3 | 30.67% | — | — |
| **LocAgent** (+Agentless editing) | **ACL 2025** | Claude-3.5 | Pass@1 **27.92%** / Pass@10 **37.59%** | — | — |
| Agentless (baseline của LocAgent) | FSE 2025 | Claude-3.5 | Pass@1 26.31% / Pass@10 33.58% | — | — |
| **ARISE-FULL** | preprint | Qwen2.5-Coder-32B | **22.0%** | — | — |
| **OpenHands** | ICLR 2025 | — | 41.7% | **65.80%** | — |
| SWE-agent | NeurIPS 2024 | Claude-3.7 | — | 62.40% | — |

**⚠️ Các số này KHÔNG so sánh trực tiếp được với nhau vì khác backbone.** ARISE phát biểu rõ nguyên tắc: *"Pass@1 numbers from the original papers use different backbone models; they appear for context only and are not directly comparable."* Luận văn phải tuân thủ. Chỉ so trong C3 (cùng backbone) mới là so sánh hợp lệ.

## C5. Cost / Efficiency (LocAgent Table 5, SWE-bench Lite)

| Method | LM | #Round | Cost ($) | **Acc@10 / Cost** |
|---|---|---|---|---|
| MoatlessTools | GPT-4o | 5 | 0.46 | 1.3 |
| MoatlessTools | Claude-3.5 | 5 | 0.46 | 1.4 |
| SWE-agent | GPT-4o | 8 | 0.56 | 0.8 |
| SWE-agent | Claude-3.5 | 9 | 0.67 | 1.0 |
| OpenHands | GPT-4o | 15 | 0.83 | 0.6 |
| OpenHands | Claude-3.5 | 13 | 0.79 | 0.9 |
| LocAgent | Claude-3.5 | 7 | 0.66 | 1.2 |
| **LocAgent** | **Qwen2.5-7B(ft)** | 6 | **0.05** | **13.2** |
| LocAgent | Qwen2.5-32B(ft) | 9 | 0.09 | 8.6 |

---

# PHẦN D — Baseline NỘI BỘ bắt buộc

Ba baseline này quan trọng hơn mọi baseline ngoại vì chúng chứng minh **nhân quả**, không chỉ **hơn kém**.

| # | Tên | Cấu hình | Chứng minh điều gì | Số liệu tham chiếu |
|---|---|---|---|---|
| **D1** | **COARSE** | Giữ **nguyên tool schema** (agent vẫn thấy đủ tool), nhưng **dựng đồ thị thiếu thành phần mới của bạn** → tool đó luôn trả về rỗng | Cải thiện đến từ **dữ liệu đồ thị**, không từ việc agent có thêm tool | ARISE-COARSE ≈ ARISE-STRUCTURAL, chênh ≤1.0 điểm; Pass@1 19.5% vs 19.0% |
| **D2** | **FLATTEN** | Cùng đồ thị, nhưng **linearize thành text** theo thứ tự topo trước khi đưa vào model | Giá trị nằm ở **giữ nguyên cấu trúc**, không chỉ ở việc có đồ thị | CGM FlatGraph: **5.33%** vs CGM **43.00%** — chênh 37.67 điểm |
| **D3** | **PARITY** | Điều kiện tái hiện **đúng năng lực** của SOTA (LocAgent), chạy **cùng backbone, cùng harness, cùng prompt** | Mọi so sánh với C1 mới hợp lệ (C1 khác backbone) | ARISE-STRUCTURAL được mô tả là *"reproduce structural graph retrieval capabilities của LocAgent và RepoGraph under the same backbone and evaluation harness"* |

**Bổ sung nếu có ngân sách:** ablation từng tool (LocAgent Table 6) và ablation định dạng serialize đồ thị (LocAgent Table 9). Ablation tool của LocAgent cho số liệu tham chiếu:

| Setting | File Acc@5 | Module Acc@10 | Function Acc@10 |
|---|---|---|---|
| LocAgent full (Qwen2.5-7B ft) | 88.32 | 82.85 | 71.53 |
| w/o TraverseGraph | 86.13 | 78.47 | 66.06 |
| Relation types: chỉ `contain` | 86.50 | 79.56 | 66.42 |
| Traverse Hops = 1 | 86.86 | 80.29 | 66.79 |
| w/o RetrieveEntity | 87.59 | 81.39 | 69.34 |
| **w/o SearchEntity** | **68.98** | **61.31** | **53.28** |
| w/o BM25 index | 75.18 | 68.98 | 60.22 |

Ba kết luận từ bảng này bạn có thể dùng làm giả thuyết: (a) `SearchEntity` là tool quan trọng nhất; (b) chỉ có `contain` cải thiện rất ít → **3 loại quan hệ kia mới là thứ tạo giá trị**; (c) cố định Hops=1 làm giảm mạnh function-level → **multi-hop là thiết yếu**.

---

# PHẦN E — Kế hoạch chạy tối thiểu

## E1. Ma trận thực nghiệm

```
DATASET × ĐIỀU KIỆN × BACKBONE

DATASET (2)
  SWE-bench Lite  (300 / 274 cho localization)
  Loc-Bench       (560)

ĐIỀU KIỆN (6)
  [ngoại]  BM25                          ← lower bound bắt buộc
  [ngoại]  CodeRankEmbed                 ← SOTA embedding
  [ngoại]  SWE-agent (agentic baseline)  ← cùng prompt localization
  [nội]    PARITY   (D3)                 ← tái hiện LocAgent
  [nội]    COARSE   (D1)                 ← control tool-schema
  [nội]    FLATTEN  (D2)                 ← control cấu trúc
  [ours]   Hệ của bạn (full)

BACKBONE (3)
  Qwen2.5-Coder-7B-Instruct    ← open, nhỏ, chi phí thấp
  Qwen2.5-Coder-32B-Instruct   ← chuẩn của ARISE & CoSIL
  Claude-3.5-Sonnet hoặc GPT-4o ← để so trực tiếp với bảng C1
```

## E2. Thứ tự chạy (tối ưu chi phí)

| Giai đoạn | Chạy gì | Chi phí | Lý do làm trước |
|---|---|---|---|
| **1** | **A1 (PyCG suite)** — precision/recall cạnh | ~0 (không LLM) | Nếu đồ thị sai thì mọi thứ sau vô nghĩa. Chạy trong vài giờ |
| **2** | **A2 (Gold-Reachability@h, thống kê, thời gian dựng)** trên cả 2 dataset | ~0 (không LLM) | Cho biết ngay schema có tiềm năng không, **trước khi tốn tiền API** |
| **3** | **B — localization**, backbone rẻ nhất (Qwen 7B), đủ 7 điều kiện × 2 dataset | Thấp | Ra được toàn bộ bảng ablation |
| **4** | B — localization, backbone 32B + proprietary, chỉ điều kiện ours + PARITY + SWE-agent | Trung bình | Đủ để chứng minh generalization |
| **5** | B — repair (Pass@1) + Spearman ρ, **task độc lập** | Cao | Chỉ chạy khi localization đã tốt |
| **6** | Cost analysis, failure-mode taxonomy, unique-fix Venn | Thấp | Phân tích trên dữ liệu đã có |

**Ước lượng ngân sách API tham chiếu:** LocAgent $0.66/example với Claude-3.5, $0.05 với Qwen2.5-7B(ft). Với 274 + 560 = 834 instance × 7 điều kiện, backbone rẻ ≈ **$290**; chỉ chạy 3 điều kiện với Claude-3.5 ≈ **$1,650**. Cân nhắc dùng Qwen 7B/32B làm chủ lực và Claude-3.5 chỉ cho bảng cuối.

## E3. Fine-tune model nhỏ (nếu muốn giảm chi phí như LocAgent)

Công thức đã được kiểm chứng, chi phí thấp bất ngờ:
1. Thu **433 trajectory thành công** từ Claude-3.5
2. Fine-tune Qwen2.5-Coder-32B: **LoRA + SFT**, cross-entropy chuẩn, **5 epochs**, `max_token = 128k`, `lr = 2e-4`
3. Sample thêm **335 trajectory** từ chính model đã fine-tune (self-improvement)
4. Dùng **toàn bộ 768 sample** train model 7B

Kết quả: 32B(ft) ngang Claude-3.5, 7B(ft) ngang GPT-4o, chi phí giảm >80% (từ $0.66 → $0.09).

---

# PHẦN F — Ba lưu ý khi so sánh

**F1. Chỉ so cùng backbone.** Bảng C1 (LocAgent) và C3 (ARISE) **không so được với nhau** — LocAgent dùng Claude-3.5/GPT-4o/Qwen(ft), ARISE dùng Qwen2.5-Coder-32B. Cách xử lý đúng: đặt bảng C1 làm **bối cảnh** và bảng C3 là **so sánh có kiểm soát**, đúng như ARISE làm.

**F2. Acc@k strict ≠ Recall@k.** LocAgent dùng **Acc@k strict** (tất cả vị trí gold phải trong top-k); ARISE dùng **Recall@k** (ít nhất một). Con số của hai bảng **không cùng thang đo**. Nếu bạn báo cáo cả hai, phải ghi rõ định nghĩa từng cột.

**F3. Số instance khác nhau.** SWE-bench Lite có 300; LocAgent giữ **274** cho localization (loại instance không sửa function nào); ARISE dùng cả **300**. Luôn ghi mẫu số.

---

# PHỤ LỤC — Bảng truy nguyên

| Bảng trong tài liệu này | Nguồn gốc | Venue | Truy cập |
|---|---|---|---|
| C1 (SWE-bench Lite localization) | LocAgent Table 4 | ACL 2025 | `aclanthology.org/2025.acl-long.426` |
| C1 NDCG | LocAgent Table 11 | ACL 2025 | như trên |
| C2 (Loc-Bench) | LocAgent Table 7 | ACL 2025 | như trên |
| C3 (localization + repair cùng backbone) | ARISE Tables 3, 4, 5 | preprint arXiv:2605.03117 | arXiv |
| C4 (leaderboard) | CGM Table 1; KGCompass Tables 1–2; Prometheus | NeurIPS 2025 / preprint | arXiv:2505.16901, 2503.21710, 2507.19942 |
| C5 (cost) | LocAgent Table 5 | ACL 2025 | như trên |
| D2 (FlatGraph) | CGM Table 10 | NeurIPS 2025 | arXiv:2505.16901 |
| D-phụ (tool ablation) | LocAgent Table 6 | ACL 2025 | như trên |
| A1 (call graph P/R) | PyCG Tables 4–5 | ICSE 2021 | `github.com/vitsalis/pycg-evaluation` |
| Phân bố category | LocAgent Table 3 | ACL 2025 | như trên |

## Tài liệu tham khảo chính

1. Jimenez, C.E. et al. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* **ICLR 2024.** arXiv:2310.06770
2. Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A., Wang, X. (2025). *LocAgent: Graph-Guided LLM Agents for Code Localization.* **ACL 2025**, pp. 8697–8727. DOI: 10.18653/v1/2025.acl-long.426
3. Salis, V., Sotiropoulos, T., Louridas, P., Spinellis, D., Mitropoulos, D. (2021). *PyCG: Practical Call Graph Generation in Python.* **ICSE 2021.** arXiv:2103.00587
4. Seddik, S., Fard, F. (2026). *ARISE: A Repository-level Graph Representation and Toolset for Agentic Fault Localization and Program Repair.* arXiv:2605.03117 ⚠️ preprint
5. Tao, H. et al. (2025). *Code Graph Model (CGM).* **NeurIPS 2025.** arXiv:2505.16901
6. Ouyang, S. et al. (2025). *RepoGraph.* **ICLR 2025**, pp. 30361–30384. arXiv:2410.14684
7. Xia, C.S., Deng, Y., Dunn, S., Zhang, L. (2025). *Agentless: Demystifying LLM-Based Software Engineering Agents.* **PACMSE 2 (FSE 2025)**, pp. 801–824. DOI: 10.1145/3715754
8. Yang, J. et al. (2024). *SWE-agent.* **NeurIPS 2024.** arXiv:2405.15793
9. Wang, X. et al. (2025). *OpenHands.* **ICLR 2025.** arXiv:2407.16741
10. Suresh, T. et al. (2024). *CoRNStack / CodeRankEmbed.* arXiv:2412.01007
11. Jiang, Z. et al. (2025). *CoSIL: Issue Localization via LLM-Driven Iterative Code Graph Searching.* **ASE 2025.** arXiv:2503.22424
12. Yu, Z. et al. (2025). *OrcaLoca.* **ICML 2025**, PMLR 267, pp. 73416–73436
13. Yang, B. et al. (2025). *KGCompass.* arXiv:2503.21710 ⚠️ preprint
14. Li, Y. et al. (2024). *Jarvis: Scalable and Precise Application-Centered Call Graph Construction for Python.* arXiv:2305.05949

---

*Tài liệu liên quan: `code-kg-papers-2025-2026.md` (khảo sát đầy đủ), `code-kg-design.md` (thiết kế đồ thị), `code-kg-research.md` (cơ sở lý thuyết).*
