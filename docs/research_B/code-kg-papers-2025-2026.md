# Code Knowledge Graph 2025–2026: Khảo sát paper, phương pháp thực nghiệm, và bộ baseline–benchmark–metric chuẩn

**Báo cáo khảo sát**
Ngày: 08/08/2026 · Phạm vi thời gian: 01/2025 → 08/2026 (kèm một số công trình 2024 bắt buộc phải có làm nền)

---

## 0. Tiêu chí lọc đã áp dụng

**Được đưa vào:**
- Paper tại hội nghị/tạp chí uy tín: ICLR, NeurIPS, ICML, ACL, NAACL, ICSE, FSE, ASE, ISSTA, TOSEM, TSE.
- Preprint arXiv **chỉ khi** đã được chấp nhận tại venue uy tín (ghi rõ), hoặc có ảnh hưởng đo được (được các paper hạng A trích dẫn làm baseline).

**Bị loại:** blog công nghiệp, repo GitHub không kèm paper, preprint chưa có venue và chưa được trích dẫn làm baseline.

**Ghi chú trung thực:** một số công trình 2026 tôi tìm được vẫn ở dạng preprint (ARISE, Codebase-Memory, RANGER, Trust-Aware Traceability). Tôi vẫn đưa vào **vì phương pháp thực nghiệm của chúng có giá trị tham khảo cao**, nhưng đánh dấu rõ trạng thái venue. Đừng trích chúng như công trình đã bình duyệt.

---

## 1. Executive summary

**1.1. Trường này đã hội tụ về một chuẩn thực nghiệm, và chuẩn đó là SWE-bench.** Toàn bộ paper code-KG hạng A giai đoạn 2025–2026 mà tôi khảo sát đều đánh giá trên **SWE-bench Lite (300 instances, 11 repo Python)** và/hoặc **SWE-bench Verified (500 instances)**. Không có ngoại lệ. Nếu luận văn của bạn không báo cáo trên SWE-bench Lite, reviewer sẽ hỏi ngay.

**1.2. Nhưng SWE-bench đo *kết quả cuối*, không đo *chất lượng đồ thị*.** Đây là khoảng trống phương pháp luận lớn nhất. Trường này hiện có **bốn tầng đánh giá** và hầu hết paper chỉ làm tầng 2–3:

| Tầng | Đo gì | Ai làm tốt |
|---|---|---|
| **L0 — Intrinsic** | Đồ thị có đúng không? (precision/recall cạnh so với ground truth) | **Gần như không paper code-KG nào làm.** Chỉ có dòng static analysis (PyCG, Jarvis) |
| **L1 — Retrieval / Localization** | Đồ thị có tìm đúng chỗ không? Acc@k, Recall@k, MRR, NDCG | LocAgent, ARISE, CoSIL, KGCompass |
| **L2 — Downstream task** | Có sửa được bug không? Resolve rate / Pass@1 | Tất cả |
| **L3 — Cost / Efficiency** | Tốn bao nhiêu? $/instance, tokens, rounds, thời gian dựng đồ thị | LocAgent, KGCompass, ARISE, Prometheus |

**1.3. Bài kiểm tra quan trọng nhất mà rất ít paper làm — và bạn nên làm.** ARISE (2026) thiết kế một điều kiện ablation tên **ARISE-COARSE**: giữ nguyên **tool schema** (agent vẫn thấy `get_dataflow_slice` trong danh sách tool) nhưng **dựng đồ thị không có Statement node và không có data-flow edge**, nên mọi lời gọi slice trả về rỗng. Kết quả ARISE-COARSE nằm trong phạm vi 1.0 điểm so với ARISE-STRUCTURAL, chứng minh cải thiện đến từ **dữ liệu đồ thị**, không phải từ việc **có thêm một tool trong schema**. Đây là chứng minh nhân quả sạch nhất tôi tìm được trong toàn bộ tài liệu, và nó trực tiếp trả lời câu hỏi "làm thế nào biết đồ thị là thứ tạo ra hiệu quả".

**1.4. Ba kết quả thực nghiệm định hình toàn bộ hướng thiết kế:**

- **Localization là nút thắt, không phải patch generation.** ARISE đo tương quan Spearman giữa Function Recall@1 và Pass@1: nó tăng đơn điệu 0.05 (RAG) → 0.38 (SWE-agent) → 0.42 (structural graph) → 0.51 (+ data-flow) → 0.53 (full). Càng có công cụ định vị chính xác, repair càng bị ràng buộc chặt bởi localization.
- **Giá trị của đồ thị nằm ở multi-hop, không ở lookup.** KGCompass báo cáo **89.7% số bug nó định vị thành công KHÔNG có gợi ý vị trí tường minh trong issue** và chỉ tìm được qua duyệt đồ thị nhiều bước. Đây là con số thuyết phục nhất cho việc "tại sao cần đồ thị thay vì embedding search".
- **Cải thiện từ structural graph thuần tuý đã bão hoà ở ~2%.** ARISE ghi nhận SWE-agent → ARISE-STRUCTURAL là +1.7% Pass@1, rất gần với gap SWE-agent → SWE-agent+RepoGraph trên GPT-4o (+2.0%). Hai backbone khác nhau, cùng một con số. Muốn vượt qua ngưỡng này phải thêm **thông tin mà structural graph không có**: data-flow (ARISE), metadata issue/PR (KGCompass), hoặc tích hợp vào attention (CGM).

**1.5. Cảnh báo phải đọc:** GraphRAG-Bench (ICLR 2026) chỉ ra rằng **GraphRAG thường xuyên thua vanilla RAG trên nhiều tác vụ thực tế**, và đề xuất metric theo từng giai đoạn (graph construction / knowledge retrieval / contextual synthesis) để lộ ra chỗ mô hình hỏng. Luận văn về code KG phải trả lời được câu "tại sao đồ thị, chứ không phải BM25 + embedding" bằng số liệu, không bằng lập luận.

---

## 2. Bản đồ paper 2025–2026

### 2.1. Nhóm A — Đồ thị làm plugin / index cho retrieval

#### **RepoGraph** — ICLR 2025
Ouyang, S., Yu, W., Ma, K., Xiao, Z., Zhang, Z., Jia, M., Han, J., Zhang, H., Yu, D. *RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph.* ICLR 2025, pp. 30361–30384. arXiv:2410.14684.

- **Schema:** đồ thị mức dòng (line-level), node = function/class, cạnh = reference. Không có data-flow.
- **Chiến lược:** ego-graph retrieval — trích subgraph có search term làm tâm.
- **Định vị:** **plug-in module**, cắm vào framework có sẵn, không phải hệ thống độc lập.
- **Thực nghiệm:** cắm vào **4 framework** thuộc **2 dòng** (agent-based và procedural/agentless). SWE-bench Lite là chính; CrossCodeEval để kiểm tra transferability.
- **Kết quả:** cải thiện tương đối trung bình **32.8%**; tuyệt đối **+2.66** cho RAG và **+2.34** cho Agentless (tức 99.63% và 8.56% tương đối).
- **Phân tích thêm:** so sánh **các thuật toán subgraph retrieval khác nhau** và các cách tích hợp; có error analysis; báo cáo số node/cạnh trung bình.
- **Giá trị thiết kế thực nghiệm:** đây là **hình mẫu chuẩn cho "graph as plugin"** — chứng minh tính phổ quát bằng cách cắm vào nhiều host framework thay vì xây một hệ riêng rồi so với hệ khác. Rất khó bị phản biện "kết quả do phần khác của hệ thống".

#### **CodexGraph** — NAACL 2025
Liu, X., Lan, B., Hu, Z., Liu, Y., Zhang, Z., Wang, F., Shieh, M.Q., Zhou, W. *CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases.* NAACL 2025 (Volume 1: Long Papers), pp. 142–160. arXiv:2408.03910.

- **Schema:** module / class / function; cạnh contains, calls, inherits. **Không có data-flow.**
- **Chiến lược:** index repository vào **Neo4j**; LLM agent sinh **truy vấn Cypher** để truy xuất.
- **Thực nghiệm:** **ba benchmark** — CrossCodeEval (Lite, Python), SWE-bench Lite, EvoCodeBench (full test set). **Ba LLM backbone** — GPT-4o, DeepSeek-Coder-V2, Qwen2-72B-Instruct. So với RACG baselines và AutoCodeRover (mở rộng AutoCodeRover sang CrossCodeEval và EvoCodeBench để so công bằng).
- **Giá trị thiết kế thực nghiệm:** mẫu chuẩn cho **ma trận benchmark × backbone**. Việc mở rộng baseline sang benchmark mà baseline gốc không hỗ trợ là điểm cộng lớn về tính công bằng.
- **Hạn chế được các paper sau chỉ ra:** schema chỉ có quan hệ cấu trúc, không có data-flow.

#### **LocAgent** — ACL 2025 ⭐ *paper có phương pháp thực nghiệm chuẩn chỉnh nhất*
Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A., Wang, X. *LocAgent: Graph-Guided LLM Agents for Code Localization.* ACL 2025, pp. 8697–8727. DOI: 10.18653/v1/2025.acl-long.426.

- **Schema:** đồ thị **có hướng, không đồng nhất** G(V,E,A,R). Node types A = {directory, file, class, function}. Edge types R = {contain, import, invoke, inherit}. Đây là **bộ 4×4 đầy đủ nhất** trong nhóm (xem bảng so sánh §2.6).
- **Indexing:** **sparse hierarchical entity index** 4 tầng — (1) entity ID index dùng fully qualified name (`src/utils.py:MathUtils.calculate_sum`); (2) dictionary tên → node; (3) BM25 inverted index trên entity ID; (4) inverted index code chunk → entity cho keyword không thuộc ID.
- **Tool API:** rút gọn về **3 tool** — `SearchEntity`, `TraverseGraph` (BFS type-aware, điều khiển hướng + số hop + entity/relation types), `RetrieveEntity`. Output của SearchEntity có **3 mức chi tiết**: fold / preview / full code, chọn tự động theo số lượng kết quả.
- **Kết quả:** Claude-3.5 đạt file Acc@5 = 94.16, module Acc@10 = 87.59, function Acc@10 = 77.37. Qwen2.5-32B(ft) đạt file Acc@5 = 92.70. Chi phí giảm từ $0.66 → $0.09/example (~86%).
- **Downstream:** Acc@5 = 73.36 → Pass@1 = 27.92, Pass@10 = 37.59 (so với Agentless: 58.39 → 26.31 / 33.58).

**LocAgent đóng góp 5 kỹ thuật thực nghiệm mà bạn nên sao chép:**

1. **Metric nghiêm ngặt.** Acc@k được định nghĩa theo tinh thần R-Precision: chỉ tính thành công khi **TẤT CẢ** vị trí liên quan nằm trong top-k. Không phải "có ít nhất một vị trí đúng". Báo cáo thêm **NDCG@k** để đo chất lượng xếp hạng.
2. **Phân tầng độ khó bằng khoảng cách hop trên chính đồ thị.** Trích tên hàm từ issue description bằng GPT-4o → ánh xạ vào node → tính khoảng cách hop ngắn nhất trung bình tới node ground truth: δ = (1/|T|)·Σ_{t∈T} min_{c∈C} d(c,t). Rồi vẽ hiệu năng theo Hop 0 / 1 / 2 / 3+. **Kết quả then chốt:** retrieval-based methods sập ở hop ≥ 1; Agentless còn tệ hơn cả retrieval khi cần khám phá ngoài query. Đây là cách chứng minh "đồ thị cần thiết khi nào" bằng số.
3. **Ablation định dạng output đồ thị.** Trên 37 sample khó (không baseline nào giải được), so 6 định dạng: `row`, `row + entity attributes`, `incident`, Graphviz DOT, JSON, và tree-based. Kết quả: **tree-based tốt nhất**; `row + attributes` **kém hơn** `row` (attributes gây nhiễu). Đây là ablation mà gần như không ai làm nhưng ảnh hưởng lớn.
4. **Benchmark mới chống nhiễm dữ liệu — Loc-Bench.** Xem §4.
5. **Efficiency table:** #rounds, $ cost, và **cost-efficiency = Acc@10 / cost**. Qwen2.5-7B(ft) đạt 13.2, so Claude-3.5 1.2.

#### **CoSIL** — ASE 2025
Jiang, Z., Ren, X., Yan, M., Jiang, W., Li, Y., Liu, Z. *Issue Localization via LLM-Driven Iterative Code Graph Searching.* ASE 2025. arXiv:2503.22424.

- **Điểm khác biệt:** **không training, không indexing**. Call graph được **LLM dựng động** để tránh context thừa.
- **Chiến lược 2 pha:** pha 1 khám phá rộng mức file bằng **module call graph**; pha 2 phân tích sâu mức function bằng cách mở rộng thành **function call graph** và tìm kiếm lặp. Có **pruner** lọc hướng và context không liên quan, và **reflection mechanism** dùng truy vấn ngắn độc lập để giữ đúng format trong context dài.
- **Kết quả:** Top-1 localization accuracy **43.3%** (SWE-bench Lite) và **44.6%** (SWE-bench Verified) với Qwen2.5-Coder-32B; trung bình vượt SOTA **96.04%**.
- **Ablation:** loại bỏ riêng từng thành phần trong 4 thành phần (reflective alignment, module call graph, function call graph, pruning). Có metric **empty rate (ER)** — tỷ lệ trả về rỗng, một metric ít ai báo cáo nhưng rất quan trọng cho hệ agent.
- **Đánh giá đa backbone:** Qwen2.5-Coder 7B / 14B / 32B.

#### **OrcaLoca** — ICML 2025
Yu, Z., Zhang, H., Zhao, Y., Huang, H., Yao, M., Ding, K., Zhao, J. *OrcaLoca: An LLM Agent Framework for Software Issue Localization.* ICML 2025, PMLR vol. 267, pp. 73416–73436.

- Đồ thị đơn giản hoá + **priority-based action scheduling**, **action decomposition với relevance scoring**, **distance-aware context pruning**.
- Đạt **65.33% function match rate** trên SWE-bench Lite.

---

### 2.2. Nhóm B — Đồ thị tích hợp vào bên trong mô hình

#### **Code Graph Model (CGM)** — NeurIPS 2025
Tao, H., Zhang, Y., Tang, Z., Peng, H., Zhu, X., Liu, B., Yang, Y., Zhang, Z., Xu, Z., Zhang, H., Zhu, L., Wang, R., Yu, H., Li, J., Di, P. (Ant Group). *Code Graph Model (CGM): A Graph-Integrated Large Language Model for Repository-Level Software Engineering Tasks.* NeurIPS 2025. arXiv:2505.16901.

Đây là paper **khác biệt nhất về mặt kỹ thuật** trong toàn bộ nhóm: thay vì dùng đồ thị để retrieval rồi làm phẳng thành text, CGM **đưa cấu trúc đồ thị vào trong attention mask của LLM**.

- **Schema:** 7 node types — REPO, PACKAGE, FILE, TEXTFILE, CLASS, FUNCTION, ATTRIBUTE. 5 edge types — contains, calls, extends, imports, implements (implements chỉ cho Java). Hỗ trợ Python và Java.
- **Xử lý dependency phức tạp (đáng chú ý cho thiết kế schema):** với **dynamic calls**, dùng nguyên tắc **over-approximation** — khi gặp lời gọi method lớp cơ sở (`Base.method()`), đưa **tất cả** implementation override từ subclass vào tập calls. Với **multiple inheritance**, dùng thuật toán **Class Hierarchy Analysis (CHA)**.
- **Semantic Integration:** node text → encoder CodeT5+ → adapter (MLP 2 lớp, GELU) → node token trong không gian embedding của LLM. Chunk 512 token → **nén thành 1 node token**, tức mở rộng context length **512 lần**.
- **Structural Integration:** thay causal attention mask giữa các node token bằng **graph-aware attention mask** dẫn xuất từ adjacency matrix → attention chỉ xảy ra giữa node kề, mô phỏng message passing của spatial GNN.
- **Training:** 2 pha — (1) **Subgraph Reconstruction Pre-training** (Graph-to-Code: tái tạo code từ subgraph), (2) **Noisy Fine-tuning** trên issue-patch pairs với **nhiễu cố ý**: 10% prompt thêm file không liên quan, 10% thiếu ít nhất một oracle file.
- **Graph RAG 4 module:** Rewriter (Extractor + Inferer) → Retriever → Reranker (2 stage) → Reader (CGM).

**Kết quả:**

| Benchmark | Model | Kết quả |
|---|---|---|
| SWE-bench Lite | CGM-SWE-PY (Qwen2.5-72B) | **43.00%** — #1 trong open-weight models |
| SWE-bench Verified | CGM-SWE-PY | **50.40%** |
| SWE-bench-java Verified | CGM-Multi | **14.29%** — #1, vượt SWE-agent+DeepSeek-V2 (9.89%) |
| SWE-bench Lite | CGM-Multi | 36.67% |

**Ablation của CGM là bài học lớn nhất về "component nào thực sự quan trọng":**

| Điều kiện | Resolve rate | Δ |
|---|---|---|
| CGM full | 43.00% | — |
| w/o Rewriter | 34.67% | −8.33 |
| w/o Retriever | 31.67% | −11.33 |
| **w/o Reranker** | **18.33%** | **−24.67** |
| w/o R³ (cả 3 module) | 9.67% | −33.33 |
| **w/o CGM Reader (FlatGraph)** | **5.33%** | **−37.67** |

Hai dòng in đậm là kết luận quan trọng nhất: (a) **Reranker — module quyết định file nào cần sửa — là thành phần quan trọng nhất trong pipeline retrieval**; (b) baseline **FlatGraph** (làm phẳng code snippet theo thứ tự topo, tức "dùng đồ thị nhưng linearize") chỉ đạt 5.33%, chứng minh **giá trị nằm ở việc giữ nguyên modality đồ thị**, không ở việc có đồ thị.

**Recall theo từng module (Table 7)** — metric mà rất ít paper báo cáo nhưng cực kỳ hữu ích:

| Module | SWE-bench Lite | SWE-bench-java Verified |
|---|---|---|
| Retriever | 94% | 87% |
| Reranker Stage 1 | 89% | 74% |
| Reranker Stage 2 | 87% | 60% |

Đây là cách chẩn đoán pipeline: recall giảm dần qua từng stage cho biết chính xác chỗ nào mất thông tin.

**Ablation kiến trúc CGM (trên CrossCodeEval):** freeze all → train A → train D → train A+D → train E+A+D; và **w/o graph-aware mask** (giảm 8.61% EM Java, 5.56% Python); **w/o subgraph reconstruction pre-training** (giảm 7.65% EM).

**Generalization backbone:** Qwen2.5-72B 43.00% / Llama3.1-70B 25.33% / Qwen2.5-Coder-32B 28.67% / Qwen2.5-Coder-7B 4.00%.

**Cost:** dựng code graph ~3 phút/repo (offline, không ảnh hưởng inference); inference 3.9s @1k token → 8.6s @8k token; 68.79 GB → 72.02 GB memory.

---

### 2.3. Nhóm C — Knowledge Graph có metadata phi-code

#### **KGCompass** — arXiv:2503.21710 (v3, 10/2025; ⚠️ preprint, đã có 14 trích dẫn)
Yang, B., Tian, H., Ren, J., Jin, S., Liu, Y., Liu, F., Le, B. *Enhancing Repository-Level Software Repair via Repository-Aware Knowledge Graphs.*

Đây là paper **gần nhất với khái niệm "knowledge graph" đúng nghĩa** — nó không chỉ có code, mà **liên kết repository artifacts (issues, pull requests) với code entities (files, classes, functions)**.

- **Hai đổi mới:** (1) repository-aware KG thu hẹp không gian tìm kiếm về **20 function liên quan nhất**; (2) **path-guided repair mechanism** — dùng các entity path khai thác từ KG làm ngữ cảnh bổ sung, sinh patch kèm giải thích.
- **Kết quả:** SWE-bench Lite — repair **58.3%** (single-LLM, open-source approaches), function-level fault location **56.0%**, chi phí **$0.2/repair**.
- **Kết quả có ý nghĩa nhất cho lập luận "tại sao cần KG":** **89.7% số bug KGCompass định vị thành công không có gợi ý vị trí tường minh trong issue** và chỉ tìm được qua duyệt đồ thị nhiều bước.

**KGCompass đóng góp 3 kỹ thuật phân tích mà bạn nên sao chép:**

1. **Phân tích model-agnostic.** Đo mức cải thiện so với pure-LLM baseline **cùng backbone**: +50.8% (Claude-4 Sonnet), +30.2% (Claude-3.5 Sonnet), +115.7% (DeepSeek-V3), +156.4% (Qwen2.5-Max). Chứng minh lợi ích không phụ thuộc model — và **lợi ích càng lớn khi model càng yếu**, đó là một phát hiện có giá trị.
2. **Tách subset direct-hint vs no-hint.** Với Claude-3.5: 65.3% vs 55.1% (có hint) và 36.6% vs 25.7% (không hint). Với Claude-4: 76.5% vs 57.2% và 49.5% vs 29.2%. **Khoảng cách rộng ra ở subset no-hint** — đây chính xác là nơi đồ thị tạo giá trị, và tách subset là cách duy nhất để thấy điều đó.
3. **Phân tích unique fixes / complementarity.** Dưới Claude-3.5, 5 tool chia sẻ 66 bug chung; ngoài phần chung, KGCompass đóng góp **16 unique fixes** (nhiều nhất), ExpeRepair 12, DARS/Lingxi/OpenHands mỗi cái 4. Đây là cách chứng minh phương pháp của bạn **bổ sung** chứ không **trùng lặp** với SOTA — quan trọng hơn nhiều so với chỉ hơn 1-2 điểm.

#### **Prometheus** — arXiv:2507.19942 (⚠️ preprint, đang review)
Pan, Y., Chen, Z., Cohan, A., Wang, X. *Prometheus: Unified Knowledge Graphs for Issue Resolution in Multilingual Codebases.*

- **Schema:** thống nhất **file structure + AST + natural language text** vào một đồ thị. Node types: File Node, AST Node, Text Node. **5 edge types tổng quát** để hỗ trợ đa ngôn ngữ. Persistence bằng **Neo4j**, truy vấn Cypher (ví dụ: `[:PARENT_OF*1..5]->(child:ASTNode)`).
- **Multi-agent:** workflow đa tác tử theo module cho context-aware retrieval, issue classification, và automated patch verification.
- **Kết quả:** **35.33%** SWE-bench Lite và **25.7%** SWE-bench Multilingual với DeepSeek-V3; chi phí $0.23 và $0.38/issue; **7 ngôn ngữ**; **10 unique issues** không được các phương pháp trước giải.
- **Điểm thực nghiệm đáng học:** đánh giá **ngoài benchmark** — chọn 3 project open-source theo tiêu chí (>10k stars, >2k forks, ≥100 open issues có nhãn bug, có commit trong 3 ngày trước khi thu thập), sinh patch và **gửi thẳng vào issue discussion thread thật**. Đây là dạng external validity mà benchmark không cho được.

---

### 2.4. Nhóm D — Đồ thị có data-flow (biên giới hiện tại)

#### **ARISE** — arXiv:2605.03117 (05/2026; ⚠️ preprint)
Seddik, S., Fard, F. (University of British Columbia). *ARISE: A Repository-level Graph Representation and Toolset for Agentic Fault Localization and Program Repair.*

Đây là paper có **thiết kế thực nghiệm chặt chẽ nhất** trong toàn bộ khảo sát, dù mới là preprint.

- **Schema:** đồ thị property có hướng, có kiểu, **xuống tới statement**. Nodes: {Directory, Module, Class, Function, Method, **Statement**} kèm `file_path`, `start_line`, `end_line`. Edges: {Contains, Imports, ImportedBy, Calls, CalledBy, Inherits, **DataflowDefUse**, **DataflowUseDef**}.
- **Nguyên tắc dựng call graph đáng chú ý:** *"cạnh giả (false positive) khiến agent đi theo đường sai, có thể tai hại hơn cạnh thiếu (false negative)"* → **chỉ resolve các trường hợp không mơ hồ** (direct call, qualified `module.function()` với alias đã biết), **âm thầm bỏ** dynamic dispatch qua attribute access. Đây là lựa chọn **ngược với CGM** (over-approximation) — một điểm tranh luận thiết kế đáng đưa vào luận văn.
- **Tool API 3 tầng:** Tier 1 structural (`search_entities` TF-IDF, `traverse_relations` BFS, `get_enclosing_scopes`, `get_code_span`, `get_entity_info`); Tier 2 **`get_dataflow_slice`** (backward/forward/both, BFS có giới hạn, dừng ở biên function, trả về ordered SliceStep records); Tier 3 `build_context_bundle` (scoring: `score(c) = α·rel(c) + β·prox(c) + γ·1[c∈D]`, α=1.0, β=0.5, γ=1.5, greedy packing dưới budget 8000 token) và `rank_suspect_regions`.
- **Kết quả:** SWE-bench Lite với Qwen2.5-Coder-32B-Instruct — Function Recall@1 **+17.0 điểm**, Line Recall@1 **+15.0 điểm** so với SWE-agent; Pass@1 **22.0% (66/300)** vs SWE-agent 17.3% (52/300).

**Bảng ablation của ARISE là template chuẩn cho luận văn của bạn:**

| Condition | Tools | Mục đích |
|---|---|---|
| RAG | BM25 trên raw file, không graph không agent | Static retrieval lower bound |
| SWE-agent | Built-in tools, không graph | Agentic baseline |
| ARISE-STRUCTURAL | Tier 1 | **Parity với LocAgent / RepoGraph** |
| **ARISE-COARSE** | **Tier 1+2 schema; KHÔNG có STMT node** | **Tách tool API khỏi graph data** |
| ARISE-SLICING | Tier 1+2 | Novelty chính |
| ARISE-FULL | Tier 1+2+3 | Best system |
| ARISE-EXPLAINSLICE | Tier 1+2 + NL summary | Ablation trung gian ngôn ngữ tự nhiên |

**Phân rã đóng góp:** SWE-agent → ARISE-FULL = **+1.7%** (structural graph) + **+2.0%** (data-flow slicing) + **+1.0%** (context bundling).

**Ba phát hiện phản trực giác:**
1. **ARISE-COARSE ≈ ARISE-STRUCTURAL** (Function R@1 51.0 vs 50.0; Pass@1 19.5% vs 19.0%) → cải thiện đến từ **dữ liệu đồ thị**, không từ tool schema.
2. **explain_slice không đóng góp gì** (Δ = 0.0 trên mọi metric, p > 0.99 với paired bootstrap n=10,000) trong khi tốn thêm 5,000 token/instance → **mô hình 32B đọc trực tiếp structured slice output, không cần lớp tóm tắt ngôn ngữ tự nhiên**. Hàm ý thiết kế: đầu tư vào chất lượng biểu diễn có cấu trúc, không vào post-processing.
3. **Token substitution.** Từ ARISE-STRUCTURAL → ARISE-SLICING: +23,300 token cho slice nhưng **−3,300 token cho traverse** (24,900 → 21,600). Agent **thay thế** khám phá cấu trúc rộng bằng slicing có mục tiêu, chứ không làm cả hai. Đây là bằng chứng hành vi, mạnh hơn bằng chứng kết quả.

**Failure-mode breakdown** (ARISE-SLICING, n=237 failed):

| Loại lỗi | Count | % |
|---|---|---|
| Wrong file | 107 | 45% |
| Right file, wrong function | 59 | 25% |
| Right function, failed repair | 47 | 20% |
| Incomplete localization | 24 | 10% |

Nguyên nhân của 45% "wrong file": `get_dataflow_slice` **không vượt qua Calls edge** (intra-procedural), nên bug có root cause trong callee thì backward slice không thấy. Đây là giới hạn được thừa nhận thẳng và chỉ ra hướng tiếp theo.

---

### 2.5. Nhóm E — Multi-agent + Code Graph

#### **SWE-Debate** — ICSE 2026 Research Track
Li, H., Shi, Y., Lin, S., Gu, X., Lian, H., Wang, X., Jia, Y., Huang, T., Wang, Q. *SWE-Debate: Competitive Multi-Agent Debate for Software Issue Resolution.* arXiv:2507.23348.

- **Cơ chế:** duyệt **code dependency graph** để tạo nhiều **fault propagation trace** làm localization proposal. Duyệt có giới hạn độ sâu L, chọn entity tiếp theo bằng **composite scoring function** kết hợp semantic similarity với issue và structural importance trong dependency graph → tạo top-K × top-W localization chain.
- **Chọn chain:** lấy chain dài nhất + (m−1) chain khác biệt nhất theo semantic embedding. Nhiều agent chuyên biệt **xếp hạng cạnh tranh** các chain này, mỗi agent bảo vệ lựa chọn của mình qua **3 vòng debate**.
- **Patch generation:** tích hợp fix plan hợp nhất vào agent sửa code dựa trên **MCTS**.
- **Đánh giá:** SWE-bench Verified. Ablation cho thấy **cơ chế sinh nhiều chain đóng góp lớn nhất**.
- **Giá trị cho hướng agent:** đây là mẫu chuẩn nhất cho "đồ thị làm không gian đề xuất cho đa tác tử" — đồ thị không dùng để trả lời trực tiếp mà để **sinh ra tập giả thuyết đa dạng** cho agent tranh luận.

#### **Trust-Aware Multi-Agent Traceability** — arXiv:2606.17203 (06/2026; ⚠️ preprint)
*Confidence-Calibrated Knowledge Graphs for Consistent Software Artifact Management.*

Rất liên quan tới phần provenance/confidence trong báo cáo nền tảng của bạn:
- Shared knowledge graph vừa là **semantic memory tập trung** vừa là **coordination surface** để các agent đánh giá và xây tiếp trên đóng góp của nhau bằng **confidence score đã hiệu chỉnh**.
- **Pipeline dự đoán trace link 2 giai đoạn:** embedding-based retrieval + LLM-based multi-criteria analysis.
- **Traceability seeding** cho phép so sánh confidence tại **thời điểm suy diễn** với **thời điểm kiểm chứng**.
- **Consistency protocol:** confidence threshold gating, confidence divergence detection, conflict resolution.
- Ablation xác nhận **confidence calibration là thiết yếu** cho phối hợp pipeline.

#### **GraphCodeAgent** — arXiv:2504.10046
Li, J., Shi, X., Zhang, K., Li, G., Jin, Z. et al. *GraphCodeAgent: Dual Graph-Guided LLM Agent for Retrieval-Augmented Repo-Level Code Generation.* Xây **dual requirement-structural graph**.

#### **SWE-Search** — ICLR 2025
Antoniades, A., Örwall, A., Zhang, K., Xie, Y., Goyal, A., Wang, W. *SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement.* Có **Discriminator Agent** thực hiện debate có cấu trúc trên các lời giải do MCTS sinh.

---

### 2.6. Bảng so sánh schema — dữ liệu gốc từ hai paper

**Bảng 1 của LocAgent (ACL 2025):**

| Method | Contain | Import | Inherit | Invoke | Directory | File | Class | Function | Search/Traversal |
|---|---|---|---|---|---|---|---|---|---|
| CodexGraph | ✔ | ✗ | ✗ | ✔ | ✔ | ✗ | ✔ | ✔ | Cypher queries |
| RepoUnderstander | ✔ | ✗ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | MCTS |
| RepoGraph | ✔ | ✗ | ✗ | ✔ | ✔ | ✗ | ✔ | ✔ | Ego-graph retrieval |
| OrcaLoca | ✔ | ✗ | ✗ | ✔ | ✔ | ✔ | ✔ | ✔ | Simple search tools |
| **LocAgent** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | Unified retrieval tools |

**Bảng 1 của ARISE (2026):**

| System | Graph granularity | Data-flow edges | Agent tool API | Slice API |
|---|---|---|---|---|
| KGCompass | File / function | None (issue/PR metadata) | Yes (GPT-4) | No |
| RepoGraph | Line-level | Reference edges only | Plugin | No |
| LocAgent | File / class / fn | None | Yes | No |
| CodexGraph | Module / class / fn | None | LLM queries | No |
| **ARISE** | **Package → statement** | **AST def-use (intra-proc.)** | Yes | ✔ |

**Nhận xét tổng hợp:** trục tiến hoá của trường này rõ ràng — **độ mịn của schema tăng dần** (file → function → statement) và **loại thông tin mở rộng dần** (structural → + issue/PR metadata → + data-flow). Vùng còn trống theo báo cáo nền tảng của bạn: **test execution, runtime telemetry, IaC, evolution** — **chưa paper nào trong khảo sát này chạm tới**.

---

## 3. Cách thực nghiệm: làm thế nào để đánh giá một phương pháp tạo đồ thị là "chuẩn chỉnh"

### 3.1. Bốn tầng đánh giá

#### **L0 — Intrinsic: đồ thị có ĐÚNG không?**

**Đây là tầng bị bỏ quên.** Không paper code-KG nào trong §2 báo cáo precision/recall của chính các cạnh mà nó dựng. Nhưng dòng static analysis có sẵn hạ tầng:

- **PyCG** (Salis et al., ICSE 2021, arXiv:2103.00587) — bộ đánh giá công khai tại `github.com/vitsalis/pycg-evaluation`:
  - **Micro-benchmark:** 112 module Python tối giản, ground truth thủ công.
  - **Macro-benchmark:** 5 package Python (Git submodules) **kèm ground-truth call graph**.
  - Script so sánh sinh precision/recall CSV; script `table4.py`, `table5.py` tái tạo bảng trong paper.
  - Baseline sẵn có: **PyCG, Pyan, Depends**.
  - Kết quả tham chiếu: PyCG precision ~**99.2%**, recall ~**69.9%**.
- **Jarvis** (arXiv:2305.05949, đã nộp TOSEM) — micro-benchmark **135** chương trình, macro-benchmark **6** ứng dụng thật. **Cách dựng ground truth cho macro-benchmark rất đáng học:** chạy test case và thu call trace bằng `python -m trace --listfuncs`, chuyển về format của micro-benchmark, **lọc bỏ** các call ẩn do interpreter sinh (ví dụ `_frozen_importlib` khi import), sau đó **mở rộng thủ công** bằng cách kiểm tra các application function. Kết quả: Jarvis vượt PyCG ≥67% về thời gian, ≥84% precision, ≥20% recall.

> **Khuyến nghị:** nếu luận văn đề xuất **cách dựng đồ thị mới**, bắt buộc phải có L0. Nếu chỉ đề xuất **cách dùng đồ thị**, có thể bỏ L0 nhưng phải nói rõ mình dùng extractor nào và precision/recall đã biết của nó.

#### **L1 — Retrieval / Localization**

Metric chuẩn của trường (định nghĩa lấy từ LocAgent và ARISE):

| Metric | Định nghĩa | Nguồn |
|---|---|---|
| **Acc@k (strict)** | Thành công **chỉ khi TẤT CẢ** vị trí liên quan nằm trong top-k. Cảm hứng R-Precision | LocAgent |
| **Recall@k** | Tỷ lệ instance có **ít nhất một** vị trí gold trong top-k | ARISE |
| **MRR** | Mean reciprocal rank của vị trí gold đầu tiên | ARISE |
| **NDCG@k** | Chất lượng xếp hạng | LocAgent (Table 11) |
| **F1@k** | Harmonic mean của precision@k và recall@k — **phạt over-prediction** | ARISE |
| **IoU** | Intersection-over-union trung bình của tập dòng dự đoán và gold | ARISE |
| **Coverage@budget** | Tỷ lệ dòng gold được phủ bởi context bundle dưới budget token — **đo chất lượng retrieval độc lập với reasoning của agent** | ARISE |
| **Empty Rate (ER)** | Tỷ lệ trả về rỗng | CoSIL |

Ba mức granularity chuẩn: **file / module (class) / function**; ARISE thêm mức **line**.

**Định nghĩa ground truth (thống nhất giữa các paper):**
- File gold = tập file bị gold patch sửa.
- Function gold = ánh xạ mỗi diff hunk về function/method bao quanh.
- Line gold = hợp của mọi dòng bị chạm bởi gold patch (dòng +/−, **loại trừ** context line và dòng trống).
- **Loại trừ khỏi target:** document, import statement, comment (theo Loc-Bench).

#### **L2 — Downstream task**
- **Resolve rate / %R** (SWE-bench): tỷ lệ instance mà patch làm pass toàn bộ test. Định nghĩa của CGM: patch được coi là resolved nếu nó **giải quyết đúng issue và là superset của gold edits**.
- **Pass@1 / Pass@k**: patch đầu tiên (hoặc trong k lần thử) pass toàn bộ instance test.
- **EM / ES** (code completion): Exact Match và **Levenshtein Edit Similarity**: `ES = 1 − Lev(y,y*)/max(‖y‖,‖y*‖)`.

#### **L3 — Cost / Efficiency**
- $/instance (LocAgent: $0.66 → $0.09; KGCompass: $0.2; Prometheus: $0.23–0.38)
- Tokens/instance, phân rã theo loại tool (ARISE Table 8)
- Số vòng tương tác agent (LocAgent Table 5)
- **Cost-efficiency ratio** = Acc@k / cost (LocAgent)
- **Cost per additionally resolved instance** (ARISE: ≈3,333 token/instance thêm)
- Thời gian dựng đồ thị (CGM: ~3 phút/repo, offline; LocAgent: "vài giây/codebase")
- Memory (CGM Table 8)

### 3.2. Bảy kiểm chứng nhân quả bắt buộc

Đây là phần trả lời trực tiếp câu hỏi của bạn. Một phương pháp tạo đồ thị được coi là **chuẩn chỉnh** khi nó vượt qua các kiểm chứng sau:

**KC1 — Tách graph data khỏi tool schema** ⭐ *quan trọng nhất*
Giữ nguyên tool API, **rút ruột đồ thị**. Nếu hiệu năng không giảm → cải thiện là do agent có thêm tool, không phải do đồ thị.
*Nguồn:* ARISE-COARSE.

**KC2 — Parity condition với SOTA cùng backbone**
Tạo một điều kiện tái hiện **đúng năng lực** của phương pháp cạnh tranh, chạy **cùng backbone, cùng harness, cùng prompt**. ARISE-STRUCTURAL được thiết kế để "reproduce structural graph retrieval capabilities của LocAgent và RepoGraph under the same backbone and evaluation harness". Không làm điều này thì mọi so sánh với số liệu từ paper gốc đều **không so sánh được** (khác backbone).

**KC3 — Phân tầng độ khó theo khoảng cách trên đồ thị**
Tính hop distance từ entity nêu trong issue tới entity ground truth, rồi báo cáo hiệu năng theo Hop 0/1/2/3+. **Đồ thị phải chứng minh giá trị ở hop ≥ 1**; nếu chỉ hơn ở hop 0 thì bạn đang cạnh tranh với BM25, không cần đồ thị.
*Nguồn:* LocAgent §C.2.

**KC4 — Tách subset theo mức gợi ý**
Chia benchmark thành **direct-hint** (issue nêu rõ file/function) và **no-hint**. Báo cáo riêng. Khoảng cách phải **rộng ra** ở subset no-hint.
*Nguồn:* KGCompass Table 4; con số 89.7%.

**KC5 — Liên kết cơ chế giữa L1 và L2**
Chạy localization và repair **độc lập** (prompt riêng, output format riêng), rồi đo **tương quan Spearman giữa Function Recall@1 và Pass@1**. Nếu tương quan tăng khi thêm công cụ định vị → cải thiện repair thực sự đi qua localization, không phải trùng hợp.
*Nguồn:* ARISE §3.5, §5.2.

**KC6 — Ablation từng thành phần + baseline "linearize"**
Loại bỏ từng module. **Và phải có baseline flatten** — dùng cùng đồ thị nhưng làm phẳng thành text theo thứ tự topo. CGM: FlatGraph đạt 5.33% so với CGM 43.00%, chênh 37.67 điểm. Nếu baseline flatten của bạn gần bằng phương pháp của bạn, đồ thị không đóng vai trò gì.
*Nguồn:* CGM Table 10; CoSIL RQ2.

**KC7 — Generalization đa backbone**
Chạy ít nhất 3 backbone khác quy mô/họ. CGM: Qwen2.5-72B 43.00 / Llama3.1-70B 25.33 / Qwen2.5-Coder-32B 28.67 / Qwen2.5-Coder-7B 4.00. KGCompass: 4 backbone. CoSIL: 7B/14B/32B.

### 3.3. Bốn kiểm chứng bổ sung nên có

**KC8 — Ablation định dạng biểu diễn đồ thị cho LLM.** So ≥3 định dạng serialize (row / incident / DOT / JSON / tree-based). LocAgent chứng minh **tree-based tốt nhất** và **thêm entity attributes làm giảm hiệu năng**.

**KC9 — Phân tích unique fixes / complementarity.** Venn giữa phương pháp của bạn và SOTA. Số bug **chỉ mình bạn giải được** có sức thuyết phục cao hơn +1 điểm resolve rate.

**KC10 — Failure-mode taxonomy.** Phân loại toàn bộ instance thất bại (ARISE: wrong file / right file wrong fn / right fn failed repair / incomplete). Chỉ ra rõ giới hạn nào của schema gây ra loại lỗi nào.

**KC11 — Recall theo từng stage của pipeline.** CGM Table 7. Cho biết chính xác thông tin bị mất ở đâu.

### 3.4. Checklist tự đánh giá

```
□ L0  Precision/recall của cạnh đồ thị so với ground truth (nếu đề xuất extractor mới)
□ L1  Acc@k STRICT + Recall@k + MRR + NDCG@k ở 3 mức granularity
□ L1  Coverage@budget (chất lượng retrieval độc lập với agent reasoning)
□ L2  Resolve rate trên SWE-bench Lite (bắt buộc) + Verified
□ L3  $/instance, tokens (phân rã theo tool), #rounds, thời gian dựng graph
□ KC1 Điều kiện COARSE: tool schema giữ nguyên, graph data rút ruột
□ KC2 Parity condition tái hiện SOTA cùng backbone/harness/prompt
□ KC3 Phân tầng theo hop distance
□ KC4 Tách subset direct-hint / no-hint
□ KC5 Spearman ρ giữa localization và repair, chạy 2 task độc lập
□ KC6 Ablation từng module + baseline FLATTEN
□ KC7 ≥3 backbone
□ KC8 Ablation định dạng serialize đồ thị
□ KC9 Unique-fix / Venn analysis
□ KC10 Failure-mode taxonomy
□ KC11 Recall theo từng stage
□ Kiểm soát nhiễm dữ liệu: báo cáo trên ≥1 benchmark post-cutoff
□ Kiểm định thống kê (ARISE dùng paired bootstrap n=10,000)
```

---

## 4. Bộ baseline–benchmark–data–metric chuẩn

### 4.1. Tier 1 — Bắt buộc (public, được dùng bởi 100% paper trong khảo sát)

#### **SWE-bench Lite / Verified**
Jimenez, C.E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., Narasimhan, K. *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* **ICLR 2024**. arXiv:2310.06770. · `swebench.com` · `github.com/princeton-nlp/SWE-bench`

| Biến thể | Kích thước | Repo | Ghi chú |
|---|---|---|---|
| SWE-bench full | 2,294 issue-PR pairs | 12 Python repos | Ít dùng vì tốn kém |
| **SWE-bench Lite** | **300** | **11 Python repos** | **Chuẩn de-facto.** Django, Flask, SymPy, Matplotlib, Pytest, Scikit-learn... |
| **SWE-bench Verified** | **500** | 12 Python repos | OpenAI + SWE-bench team **xác minh thủ công** |
| SWE-bench-java Verified | 91 | 6 Java repos | Zan et al., arXiv:2408.14354 |

- **Metric:** Resolve Rate (%R) / Pass@1 — đánh giá bằng **Docker executable environment** với **developer-written unit tests**, oracle là **fail-to-pass testing**.
- **Dùng bởi:** RepoGraph, CodexGraph, LocAgent, CGM, KGCompass, CoSIL, OrcaLoca, ARISE, Prometheus, SWE-Debate — **toàn bộ**.
- **Leaderboard công khai:** swebench.com (dùng để định vị kết quả của bạn).
- **Tài nguyên phụ trợ quan trọng:** cache **repository structure** do Agentless team cung cấp — CoSIL và nhiều paper khác dùng lại để tránh regenerate.

**Cảnh báo bắt buộc:** SWE-bench Lite **cực kỳ lệch phân bố**. Theo Loc-Bench Table 3: 254/300 là Bug Report, 43 Feature Request, **3** Security, **0** Performance. Nếu luận văn chỉ đánh giá trên đây, bạn chỉ chứng minh được năng lực trên bug fixing.

#### **Loc-Bench** — benchmark localization chuyên biệt
Kèm LocAgent (ACL 2025). HuggingFace: `czlll/Loc-Bench_V1`. Repo: `github.com/gersteinlab/LocAgent`

| | SWE-Bench Lite | **Loc-Bench** |
|---|---|---|
| Bug Report | 254 | 242 |
| Feature Request | 43 | **150** |
| Security Issue | 3 | **29** |
| Performance Issue | **0** | **139** |
| **Tổng** | 300 | **560** |

- **Chống nhiễm:** issue **tạo sau 10/2024**, muộn hơn ngày release của phần lớn LLM hiện đại.
- **Quy trình xây dựng (đáng sao chép):** repo Python >5,000 stars; mỗi PR gắn với codebase xác định bởi base commit; **lọc bỏ** PR không giải quyết issue tường minh, PR sửa >5 file Python hoặc >10 function, PR không có function-level edit; nhãn category do GPT-4o phân loại, **sample 3 lần**, review thủ công khi không nhất quán. Keyword tìm kiếm cho Security/Performance được liệt kê trong Table 10 của paper.
- **Metric riêng:** vì Loc-Bench có instance sửa 1–5 file, đánh giá file ở **top-5 và top-10**, function/module ở **top-10 và top-15**.

### 4.2. Tier 2 — Repository-level completion / generation

| Benchmark | Nguồn | Quy mô | Metric | Dùng bởi |
|---|---|---|---|---|
| **CrossCodeEval** | Ding et al., **NeurIPS 2023** | Python: 471 repo / 1,368 file / 2,665 example. Java: 239 / 745 / 2,139. Cũng có TypeScript, C# | **EM, ES** | RepoGraph, CodexGraph, CGM |
| **RepoBench** | Liu, Xu, McAuley, **ICLR 2024**, arXiv:2306.03091 | Repo-level auto-completion | EM, ES | Nhiều |
| **RepoEval** | Zhang et al. (RepoCoder), EMNLP 2023 | Repo-level completion | EM, ES | CodeRAG-Bench |
| **EvoCodeBench** | Li et al., NeurIPS 2024 | Evolutionary, có annotation đầy đủ | Pass@k | CodexGraph |
| **ComplexCodeEval** | Feng et al., **ASE 2024** | 3,897 Java (1,055 repo), 7,184 Python (2,107 repo) | EM, ES | CGM |
| **RepoQA** | Liu et al., ICLR 2024 workshop | 500 test, 5 ngôn ngữ | Long-context understanding | ReSAT |
| **CoderEval / DevEval / FEA-Bench** | — | — | Pass@k | Bổ sung |

**Baseline RACG chuẩn cho nhóm này (từ CGM Table 4):** NoRAG · **BM25** · RepoFuse · RLCoder · R²C² — trên các base model CodeLlama-7B, StarCoder-7B, DeepSeek-Coder-7B, Qwen2.5-Coder-7B.

### 4.3. Tier 3 — Đa ngôn ngữ

| Benchmark | Nguồn | Quy mô | Ghi chú |
|---|---|---|---|
| **Multi-SWE-bench** | Zan et al., **NeurIPS 2025 Datasets & Benchmarks** | 7–8 ngôn ngữ; **mini 400 instances**, **flash 300 instances** | Expert annotation + manual verification. `multi-swe-bench.github.io` |
| **SWE-PolyBench** | Rashid et al. (AWS), arXiv:2504.08703 | **2,110 instances / 21 repos**; Java, JS, TS, Python. Verified subset **384**; stratified subsample **500** | **Có retrieval metrics dựa trên syntax tree analysis** — hiếm và rất hợp cho code-KG |
| SWE-bench Multilingual | — | 7 ngôn ngữ | Dùng bởi Prometheus (25.7%) |
| SWE-bench-java / SWE-Sharp | Zan et al. 2024 / Mhatre et al. 2025 | Java / C# | |

**SWE-PolyBench đặc biệt đáng dùng cho luận văn code-KG** vì nó là benchmark duy nhất có sẵn **retrieval metric dựa trên phân tích cây cú pháp**, tức là metric đo trực tiếp chất lượng định vị cấu trúc chứ không chỉ resolve rate.

### 4.4. Tier 4 — Chống nhiễm dữ liệu (bắt buộc có ≥1)

| Benchmark | Nguồn | Cơ chế |
|---|---|---|
| **Loc-Bench** | ACL 2025 | Issue sau 10/2024 |
| **SWE-bench-Live** | Zhang et al. 2025 | Làm mới liên tục từ issue mới |
| **SWE-rebench** | Badertdinov et al., **NeurIPS 2025 D&B**, arXiv:2505.20411 | **Pipeline tự động hoàn toàn**; khai thác liên tục issue-PR mới, timestamped release, LLM-driven recipe để validate build/test env, secondary LLM chấm điểm cấu trúc |
| **SWE-MERA** | Adamenko et al., **EMNLP 2025 Demos**, arXiv:2507.11059 | Dynamic benchmark |
| **SWE-bench+** | Aleithan et al. 2024 | Lọc post-cutoff, **loại instance có leaked solution trong issue/PR description** |
| **SWE-bench Pro** | Deng et al. 2025 | Khó hơn; thêm structured requirements + interface specs để **giảm false negative** khi patch đúng chức năng nhưng đặt tên symbol khác test |

### 4.5. Tier 5 — Intrinsic graph quality

| Tài nguyên | Nguồn | Nội dung |
|---|---|---|
| **PyCG evaluation suite** | Salis et al., **ICSE 2021**; `github.com/vitsalis/pycg-evaluation` | Micro: 112 module. Macro: 5 package **kèm ground-truth call graph**. Script sinh precision/recall. Baseline: PyCG, Pyan, Depends |
| **Jarvis benchmark** | arXiv:2305.05949 | Micro: 135 chương trình. Macro: 6 ứng dụng thật. Ground truth từ dynamic trace |
| **GraphRAG-Bench** | Xiang et al., **ICLR 2026**, arXiv:2506.05690; `github.com/GraphRAG-Bench/GraphRAG-Benchmark` | **Stage-specific metrics**: graph construction / knowledge retrieval / contextual synthesis. Không phải code nhưng **phương pháp luận trực tiếp áp dụng được** |

### 4.6. Baseline chuẩn — trích dẫn kèm số liệu

#### Nhóm Retrieval (không agent)
| Baseline | Nguồn | Vai trò |
|---|---|---|
| **BM25** | Robertson et al. 1994/2009 | **Lower bound bắt buộc.** ARISE: Pass@1 2.67%, File R@1 30.0 |
| E5-base-v2 | Wang et al. 2022 | General embedding |
| Jina-Code-v2 | Günther et al. 2023 | Code embedding |
| Codesage-large-v2 | Zhang et al., **ICLR 2024** | Code embedding |
| **CodeRankEmbed** | Suresh et al. 2024 (CoRNStack) | **SOTA code embedding.** LocAgent: file Acc@5 84.67, function Acc@10 58.76 |

#### Nhóm Agentless / Procedural
| Baseline | Nguồn | Số liệu SWE-bench Lite |
|---|---|---|
| **Agentless** | Xia et al., **FSE 2025** (PACMSE 2), arXiv:2407.01489 | **40.67%** (Claude-3.5), 32.00% (GPT-4o). Pipeline 10 bước, 4 bước cho localization |
| Agentless Lite | — | 32.33% (o3-mini) |

#### Nhóm Agent
| Baseline | Nguồn | Số liệu SWE-bench Lite |
|---|---|---|
| **SWE-agent** | Yang et al., **NeurIPS 2024** | 18.3% (GPT-4o); 17.3% (Qwen2.5-Coder-32B, đo bởi ARISE) |
| **OpenHands** | Wang et al., **ICLR 2025** | 41.7% (Claude-3.5); **65.80% Verified** |
| **AutoCodeRover** | Zhang et al., **ISSTA 2024** | Program-structure-aware search APIs |
| **MoatlessTools** | Örwall 2024 | 39.00% (Claude-3.5); 30.67% (DeepSeek-V3) |
| Lingma SWE-GPT / LingmaAgent | Ma et al., **FSE Companion 2025** | 22.00% (Qwen2.5-72B) |
| SWE-Fixer | Xie et al. 2025 | 24.67% |

#### Nhóm Graph-based (SOTA hiện tại — đây là những gì bạn phải vượt)
| Method | Venue | SWE-bench Lite %R | Localization |
|---|---|---|---|
| **KGCompass** | preprint (14 cites) | **58.3%** (single-LLM) | Function acc **56.0%**, $0.2/repair |
| **CGM-SWE-PY** | NeurIPS 2025 | **43.00%** | Verified 50.40%; java 14.29% |
| CGM-Multi | NeurIPS 2025 | 36.67% | |
| Prometheus | preprint | 35.33% | Multilingual 25.7%, 7 ngôn ngữ |
| **LocAgent** | ACL 2025 | (Pass@1 27.92 / Pass@10 37.59) | **File Acc@5 94.16**, Function Acc@10 77.37 |
| OrcaLoca | ICML 2025 | — | Function match **65.33%** |
| CoSIL | ASE 2025 | — | **Top-1 43.3%** Lite / 44.6% Verified |
| RepoGraph (+host) | ICLR 2025 | +2.66 / +2.34 tuyệt đối | rel. +32.8% trung bình |
| ARISE | preprint | 22.0% (Qwen2.5-Coder-32B) | Function R@1 60.0, Line R@1 41.0 |

> **Lưu ý so sánh:** các số này **không so sánh trực tiếp được với nhau** vì khác backbone. ARISE nói rõ điều này: *"Pass@1 numbers from the original papers use different backbone models; they appear for context only and are not directly comparable."* Luận văn phải tuân thủ nguyên tắc này.

### 4.7. Bộ tối thiểu khuyến nghị cho một luận văn

```
BENCHMARK
  Bắt buộc:      SWE-bench Lite (300)  +  Loc-Bench (560)
  Rất nên có:    SWE-bench Verified (500)
  Nếu đa ngôn ngữ: SWE-PolyBench Verified (384)  hoặc  Multi-SWE-bench mini (400)
  Nếu có completion: CrossCodeEval (Python + Java)
  Nếu đề xuất extractor mới: PyCG macro-benchmark (5 package có ground truth)

BASELINE
  Lower bound:   BM25
  Embedding:     CodeRankEmbed
  Agentless:     Agentless (Xia et al., FSE 2025)
  Agent:         SWE-agent  +  OpenHands
  Graph SOTA:    LocAgent (localization)  +  KGCompass hoặc CGM (repair)
  Nội bộ:        FLATTEN (cùng graph, linearize thành text)  ← BẮT BUỘC
  Nội bộ:        COARSE (cùng tool schema, graph rút ruột)   ← BẮT BUỘC

METRIC
  L1: Acc@k strict {1,3,5} file / {5,10} module / {5,10} function + MRR + NDCG@k
      + Coverage@budget + IoU (nếu có mức line)
  L2: Resolve rate / Pass@1 (+ Pass@10 nếu multi-attempt)
  L3: $/instance, tokens (phân rã theo tool), #rounds, graph build time

BACKBONE
  ≥3, gồm ≥1 open-weight nhỏ (7B) và ≥1 lớn (32B/72B)

PHÂN TÍCH
  Hop-distance stratification · direct-hint vs no-hint split
  Spearman ρ (L1↔L2) · unique-fix Venn · failure-mode taxonomy
  Per-stage recall · paired bootstrap significance
```

---

## 5. Hướng Agent / đa tác tử sử dụng Code KG

### 5.1. Bốn mẫu kiến trúc đã xuất hiện

| Mẫu | Cơ chế | Đại diện | Trade-off |
|---|---|---|---|
| **Graph as Tool** | Đồ thị là backend cho tool API; agent tự chọn khi nào gọi | LocAgent (3 tools), ARISE (3 tiers) | Linh hoạt; phụ thuộc năng lực tool-use của model |
| **Graph as Query Language** | Agent sinh Cypher truy vấn graph DB | CodexGraph, Prometheus (Neo4j) | Biểu đạt mạnh; agent phải biết viết Cypher |
| **Graph inside Model** | Adjacency matrix thay attention mask | CGM | Không cần agent; cần training; khó thay schema |
| **Graph as Hypothesis Space** | Duyệt đồ thị sinh nhiều đề xuất → agent tranh luận / MCTS chọn | SWE-Debate, RepoUnderstander (MCTS) | Đa dạng hoá tốt; đắt |

### 5.2. Năm phát hiện thực nghiệm quan trọng cho thiết kế agent

**PH1 — Tool phải TRẢ LỜI CHÍNH XÁC, không phải TRẢ VỀ NHIỀU.**
ARISE phát biểu nguyên tắc này rõ nhất: *giá trị của một retrieval primitive tỉ lệ với mức độ chính xác nó trả lời truy vấn của agent, không tỉ lệ với lượng thông tin nó trả về.* Một `get_dataflow_slice` trả về 5–8 statement span có quan hệ nhân quả hữu ích hơn một `traverse_relations` trả về 50 node kề về cấu trúc.

**PH2 — Multi-hop traversal trong MỘT lời gọi tool.**
LocAgent ablation: cố định Hops=1 làm giảm function-level accuracy đáng kể. `TraverseGraph` cho phép agent chỉ định hướng, số hop, entity types **và** relation types trong một action — tức agent tự sinh **meta-path** cho đồ thị không đồng nhất.

**PH3 — Output format quyết định khả năng suy luận.**
Định dạng tree-based với indentation (thể hiện khoảng cách từ root), **entity ID đầy đủ** cho mỗi node, và **relation type tường minh kèm quan hệ đảo** (`contains-by`, `imports-by`) cho kết quả tốt nhất. Thêm entity attributes vào output **làm giảm** hiệu năng.

**PH4 — Không cần lớp trung gian ngôn ngữ tự nhiên ở quy mô 32B.**
ARISE `explain_slice`: Δ = 0.0 trên mọi metric (p > 0.99), tốn thêm 5,000 token. Đầu tư vào **chất lượng biểu diễn có cấu trúc** (def-use edge chính xác, role label thông tin, fallback message hữu ích) hiệu quả hơn nhiều so với thêm bước summarization.

**PH5 — Fine-tune model nhỏ trên trajectory là con đường chi phí thấp.**
LocAgent: thu 433 trajectory thành công từ Claude-3.5 → fine-tune Qwen2.5-32B (LoRA, SFT, cross-entropy) → sample thêm 335 trajectory từ chính model đã fine-tune (self-improvement) → dùng toàn bộ dataset train model 7B. Kết quả: 32B(ft) ngang Claude-3.5, 7B(ft) ngang GPT-4o, chi phí giảm >80%. Tổng chỉ **768 training samples**, 5 epochs, lr 2e-4, max_token 128k.

### 5.3. Vùng còn trống ở hướng agent

1. **Chia sẻ đồ thị giữa nhiều agent.** SWE-Debate dùng đồ thị để **sinh** đề xuất rồi agent tranh luận trên text. Chưa có hệ nào để nhiều agent **cùng đọc-ghi** một đồ thị với protocol nhất quán. Công trình gần nhất: Trust-Aware Multi-Agent Traceability (preprint 2606.17203) với confidence threshold gating + divergence detection + conflict resolution — nhưng chưa áp dụng cho code KG mức repository.

2. **Cập nhật đồ thị trong lúc agent làm việc.** Mọi hệ trong khảo sát dựng đồ thị **offline một lần** trên base commit. Không hệ nào cập nhật đồ thị khi agent sửa code — dù agent sửa code thì đồ thị lập tức lỗi thời. **Đây là gap rõ ràng và có thể là đóng góp của luận văn.**

3. **Provenance / confidence trên cạnh.** Chưa hệ nào gắn `confidence` hay `evidence_type` lên cạnh và cho agent dùng thông tin đó để quyết định. ARISE **né** vấn đề bằng cách chỉ resolve cạnh không mơ hồ (drop dynamic dispatch); CGM **né** theo hướng ngược bằng over-approximation. Không ai **biểu diễn** độ không chắc chắn. Kết hợp với báo cáo nền tảng của bạn, đây là đóng góp khả thi nhất.

4. **Đồ thị vượt tầng code.** Chưa có test-execution node, telemetry node, IaC node, hay evolution node trong bất kỳ hệ nào trong khảo sát. KGCompass là hệ duy nhất đưa metadata phi-code (issue, PR) vào.

---

## 6. Khoảng trống & đề xuất thiết kế thực nghiệm cho luận văn

### 6.1. Năm khoảng trống có thể khai thác

| # | Khoảng trống | Bằng chứng | Độ khó | Rủi ro |
|---|---|---|---|---|
| **G1** | **Không có benchmark đo "độ phủ câu hỏi comprehension" của một code KG** | Mọi paper đo resolve rate/localization; không ai đo "graph này trả lời được bao nhiêu loại câu hỏi". 44 câu hỏi Sillito et al. (2006/2008) chưa từng được chuyển thành benchmark thực thi | Trung bình | Thấp — có thể xây trên hạ tầng SWE-bench có sẵn |
| **G2** | **Không có L0 evaluation cho code KG** | Không paper nào báo cáo precision/recall của chính cạnh mình dựng. Hạ tầng có sẵn (PyCG suite) nhưng không ai nối vào | Thấp | Thấp |
| **G3** | **Confidence/provenance trên cạnh chưa từng được biểu diễn hay khai thác** | ARISE drop cạnh mơ hồ; CGM over-approximate; không ai gắn confidence | Trung bình | Trung bình — cần chứng minh agent thực sự dùng được confidence |
| **G4** | **Đồ thị không cập nhật trong lúc agent sửa code** | Mọi hệ dựng offline trên base commit | Cao | Trung bình |
| **G5** | **Inter-procedural data-flow slicing** | ARISE tuyên bố đây là hướng chính tiếp theo; 45% lỗi của họ do slice không vượt Calls edge | Cao | Cao — bài toán static analysis khó |

### 6.2. Thiết kế thực nghiệm gợi ý (nếu chọn G1 + G3)

**Nghiên cứu chính:** xây bộ benchmark **CQ-Bench** (Comprehension Question Benchmark) từ 44 câu hỏi của Sillito et al., chuyển thành truy vấn thực thi được trên SWE-bench Lite repos, đo tỷ lệ câu hỏi mà mỗi schema đồ thị trả lời được.

**Ma trận đối chứng:**

| Điều kiện | Schema | Mục đích |
|---|---|---|
| BM25 | không graph | Lower bound |
| G-Structural | RepoGraph/LocAgent parity (4 node, 4 edge) | Baseline nhóm A |
| G-Dataflow | + Statement + DefUse (ARISE parity) | Baseline nhóm D |
| G-Meta | + Issue/PR node (KGCompass parity) | Baseline nhóm C |
| **G-Evidence (ours)** | + `evidence_type`, `confidence` trên cạnh | Đóng góp |
| **G-Evidence-COARSE** | schema đầy đủ nhưng confidence = 1.0 cho mọi cạnh | **KC1 control** |
| **G-Flatten** | cùng graph, linearize | **KC6 control** |

**Đo:**
- **Chính:** CQ-Bench coverage (tỷ lệ câu hỏi trả lời được) + precision/recall trên từng câu hỏi.
- **Phụ (để nối vào chuẩn của trường):** Acc@k/Recall@k/MRR/NDCG trên SWE-bench Lite + Loc-Bench; resolve rate; $/instance.
- **Nhân quả:** KC1 (COARSE), KC3 (hop stratification), KC4 (hint split), KC5 (Spearman), KC6 (FLATTEN), KC7 (3 backbone).

**Vì sao thiết kế này khó bị phản biện:**
- G-Structural / G-Dataflow / G-Meta là **parity conditions** chạy cùng backbone cùng harness — vượt KC2.
- G-Evidence-COARSE tách đóng góp của **thông tin confidence** khỏi đóng góp của **schema mở rộng** — vượt KC1.
- CQ-Bench đo cái mà resolve rate không đo được, nhưng vẫn báo cáo resolve rate để so được với leaderboard.

---

## 7. Tài liệu tham khảo

### Benchmark nền tảng
1. Jimenez, C.E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., Narasimhan, K. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* **ICLR 2024**. arXiv:2310.06770. https://swebench.com
2. OpenAI (2024). *Introducing SWE-bench Verified.* https://openai.com/index/introducing-swe-bench-verified/
3. Zan, D. et al. (2024). *SWE-bench-java: A GitHub Issue Resolving Benchmark for Java.* arXiv:2408.14354.
4. Zan, D. et al. (2025). *Multi-SWE-bench: A Multi-Lingual GitHub Issue Resolving Benchmark.* **NeurIPS 2025 Datasets & Benchmarks.** https://multi-swe-bench.github.io/
5. Rashid, M. et al. (2025). *SWE-PolyBench: A Multi-Language Benchmark for Repository-Level Evaluation of Coding Agents.* arXiv:2504.08703.
6. Badertdinov, I. et al. (2025). *SWE-rebench: An Automated Pipeline for Task Collection and Decontaminated Evaluation of Software Engineering Agents.* **NeurIPS 2025 D&B.** arXiv:2505.20411.
7. Zhang, L. et al. (2025). *SWE-bench-Live.* arXiv (05/2025).
8. Adamenko, P. et al. (2025). *SWE-MERA: A Dynamic Benchmark for Agenticly Evaluating LLMs on Software Engineering Tasks.* **EMNLP 2025 Demos.** arXiv:2507.11059.
9. Aleithan, R. et al. (2024). *SWE-bench+.*
10. Deng, X. et al. (2025). *SWE-bench Pro.*
11. Ding, Y. et al. (2024). *CrossCodeEval: A Diverse and Multilingual Benchmark for Cross-File Code Completion.* **NeurIPS 2023.**
12. Liu, T., Xu, C., McAuley, J. (2024). *RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems.* **ICLR 2024.** arXiv:2306.03091.
13. Li, J. et al. (2024). *EvoCodeBench.* **NeurIPS 2024.**
14. Feng, J. et al. (2024). *ComplexCodeEval: A Benchmark for Evaluating Large Code Models on More Complex Code.* **ASE 2024**, pp. 1895–1906.
15. Wang, Z.Z., Asai, A., Yu, X.V., Xu, F.F., Xie, Y., Neubig, G., Fried, D. (2025). *CodeRAG-Bench: Can Retrieval Augment Code Generation?* **NAACL 2025 Findings**, 2025.findings-naacl.176. arXiv:2406.14497.
16. Xiang, Z., Wu, C., Zhang, Q., Chen, S., Hong, Z., Huang, X., Su, J. (2026). *When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation.* **ICLR 2026.** arXiv:2506.05690. https://github.com/GraphRAG-Bench/GraphRAG-Benchmark

### Code Knowledge Graph — công trình chính
17. **Ouyang, S., Yu, W., Ma, K., Xiao, Z., Zhang, Z., Jia, M., Han, J., Zhang, H., Yu, D. (2025). *RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph.* ICLR 2025, pp. 30361–30384.** arXiv:2410.14684. https://github.com/ozyyshr/RepoGraph
18. **Liu, X., Lan, B., Hu, Z., Liu, Y., Zhang, Z., Wang, F., Shieh, M.Q., Zhou, W. (2025). *CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases.* NAACL 2025, pp. 142–160.** arXiv:2408.03910.
19. **Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A., Wang, X. (2025). *LocAgent: Graph-Guided LLM Agents for Code Localization.* ACL 2025, pp. 8697–8727.** DOI: 10.18653/v1/2025.acl-long.426. arXiv:2503.09089. https://github.com/gersteinlab/LocAgent
20. **Tao, H., Zhang, Y., Tang, Z. et al. (2025). *Code Graph Model (CGM): A Graph-Integrated Large Language Model for Repository-Level Software Engineering Tasks.* NeurIPS 2025.** arXiv:2505.16901. https://github.com/codefuse-ai/CodeFuse-CGM
21. **Jiang, Z., Ren, X., Yan, M., Jiang, W., Li, Y., Liu, Z. (2025). *Issue Localization via LLM-Driven Iterative Code Graph Searching (CoSIL).* ASE 2025.** arXiv:2503.22424. https://github.com/ZhonghaoJiang/CoSIL
22. **Yu, Z., Zhang, H., Zhao, Y., Huang, H., Yao, M., Ding, K., Zhao, J. (2025). *OrcaLoca: An LLM Agent Framework for Software Issue Localization.* ICML 2025, PMLR 267, pp. 73416–73436.**
23. Yang, B., Tian, H., Ren, J., Jin, S., Liu, Y., Liu, F., Le, B. (2025). *Enhancing Repository-Level Software Repair via Repository-Aware Knowledge Graphs (KGCompass).* arXiv:2503.21710 (v3, 10/2025). ⚠️ preprint
24. Pan, Y., Chen, Z., Cohan, A., Wang, X. (2025). *Prometheus: Unified Knowledge Graphs for Issue Resolution in Multilingual Codebases.* arXiv:2507.19942. ⚠️ preprint
25. Seddik, S., Fard, F. (2026). *ARISE: A Repository-level Graph Representation and Toolset for Agentic Fault Localization and Program Repair.* arXiv:2605.03117. ⚠️ preprint
26. **Liu, W., Yu, A., Zan, D., Shen, B., Zhang, W., Zhao, H., Jin, Z., Wang, Q. (2024). *GraphCoder: Enhancing Repository-Level Code Completion via Coarse-to-Fine Retrieval Based on Code Context Graph.* ASE 2024, pp. 570–582.** DOI: 10.1145/3691620.3695054. arXiv:2406.07003
27. Ma, Y., Yang, Q., Cao, R., Li, B., Huang, F., Li, Y. (2024/2025). *How to Understand Whole Software Repository? (RepoUnderstander)* / *Alibaba LingmaAgent.* **FSE Companion 2025.** DOI: 10.1145/3696630.3728549
28. Liang, M. et al. (2024). *RepoFuse: Repository-Level Code Completion with Fused Dual Context.* arXiv:2402.14323.
29. Wang, X. et al. (2026). *GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion.* **ICSE 2026.** arXiv:2509.05980.
30. Li, J., Shi, X., Zhang, K., Li, G., Jin, Z. et al. (2025). *GraphCodeAgent: Dual Graph-Guided LLM Agent for Retrieval-Augmented Repo-Level Code Generation.* arXiv:2504.10046.

### Agent frameworks (baseline)
31. **Yang, J., Jimenez, C.E., Wettig, A., Lieret, K., Yao, S., Narasimhan, K., Press, O. (2024). *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* NeurIPS 2024.** arXiv:2405.15793.
32. **Wang, X. et al. (2025). *OpenHands: An Open Platform for AI Software Developers as Generalist Agents.* ICLR 2025.** arXiv:2407.16741.
33. **Xia, C.S., Deng, Y., Dunn, S., Zhang, L. (2025). *Demystifying LLM-Based Software Engineering Agents (Agentless).* PACMSE 2 (FSE), pp. 801–824.** DOI: 10.1145/3715754. arXiv:2407.01489
34. **Zhang, Y., Ruan, H., Fan, Z., Roychoudhury, A. (2024). *AutoCodeRover: Autonomous Program Improvement.* ISSTA 2024, pp. 1592–1604.** DOI: 10.1145/3650212.3680384
35. Örwall, A. (2024). *Moatless Tools.* https://github.com/aorwall/moatless-tools
36. **Antoniades, A., Örwall, A., Zhang, K., Xie, Y., Goyal, A., Wang, W. (2025). *SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement.* ICLR 2025.** arXiv:2410.20285.
37. **Li, H., Shi, Y., Lin, S., Gu, X., Lian, H., Wang, X., Jia, Y., Huang, T., Wang, Q. (2026). *SWE-Debate: Competitive Multi-Agent Debate for Software Issue Resolution.* ICSE 2026 Research Track.** arXiv:2507.23348.

### Static analysis & intrinsic evaluation
38. **Salis, V., Sotiropoulos, T., Louridas, P., Spinellis, D., Mitropoulos, D. (2021). *PyCG: Practical Call Graph Generation in Python.* ICSE 2021.** arXiv:2103.00587. https://github.com/vitsalis/pycg-evaluation
39. Li, Y. et al. (2024). *Scalable and Precise Application-Centered Call Graph Construction for Python (Jarvis).* arXiv:2305.05949 (submitted to TOSEM).
40. **Yamaguchi, F., Golde, N., Arp, D., Rieck, K. (2014). *Modeling and Discovering Vulnerabilities with Code Property Graphs.* IEEE S&P 2014**, pp. 590–604. DOI: 10.1109/SP.2014.44
41. **Guo, D. et al. (2021). *GraphCodeBERT: Pre-training Code Representations with Data Flow.* ICLR 2021.**
42. **Ferrante, J., Ottenstein, K.J., Warren, J.D. (1987). *The Program Dependence Graph and Its Use in Optimization.* ACM TOPLAS 9(3):319–349.** DOI: 10.1145/24039.24041
43. Horwitz, S., Reps, T., Binkley, D. (1990). *Interprocedural Slicing Using Dependence Graphs.* ACM TOPLAS 12(1):26–60.

### Fault localization (nền tảng metric)
44. Hossain, S.B., Jiang, N., Zhou, Q., Li, X., Chiang, W.-H., Lyu, Y., Nguyen, H., Tripp, O. (2024). *A Deep Dive into Large Language Models for Automated Bug Localization and Repair.* **PACMSE 1 (FSE)**, pp. 1471–1493.
45. Youm, S. et al. (2018). *Bench4BL: Reproducibility Study on the Performance of IR-based Bug Localization.* **ISSTA 2018.** DOI: 10.1145/3213846.3213856
46. Qin, Y., Wang, S., Lou, Y., Dong, J., Wang, K., Li, X., Mao, X. (2024). *AgentFL: Scaling LLM-based Fault Localization to Project-Level Context.* arXiv:2403.16362.
47. Jones, J.A., Harrold, M.J. (2005). *Empirical Evaluation of the Tarantula Automatic Fault-Localization Technique.* **ASE 2005**, pp. 273–282.

### Survey & meta
48. Tao, Y., Qin, Y., Liu, Y. (2025/2026). *Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches.* arXiv:2510.04905 (v3, 05/2026).
49. Peng, B. et al. (2024). *Graph Retrieval-Augmented Generation: A Survey.* arXiv:2408.08921.
50. *Agentic Software Issue Resolution with Large Language Models: A Survey.* arXiv:2512.22256.

---

## 8. Ba điều phải nhớ

1. **SWE-bench Lite + Loc-Bench là bắt buộc; PyCG suite là thứ khiến bạn khác biệt.** Mọi paper đều báo cáo trên SWE-bench; gần như không ai đo chất lượng nội tại của đồ thị. Đây là lỗ hổng dễ lấp và khó phản biện.

2. **Hai baseline nội bộ quan trọng hơn mọi baseline ngoại: COARSE và FLATTEN.** COARSE (giữ tool schema, rút ruột graph) chứng minh cải thiện đến từ *dữ liệu*. FLATTEN (cùng graph, linearize thành text) chứng minh cải thiện đến từ *cấu trúc*. Không có hai baseline này, reviewer sẽ hỏi và bạn sẽ không trả lời được.

3. **Cải thiện từ structural graph thuần tuý đã bão hoà ở ~2% Pass@1.** Hai đo lường độc lập (RepoGraph+GPT-4o: +2.0%; ARISE-STRUCTURAL+Qwen32B: +1.7%) cho cùng con số. Nếu đóng góp của luận văn chỉ là "thêm một schema structural nữa", kết quả sẽ nằm trong nhiễu. Phải thêm **loại thông tin mới** — data-flow, metadata phi-code, evidence/confidence, hoặc chiều thời gian.

---

*Kết thúc báo cáo. Tài liệu nền tảng lý thuyết: `code-kg-research.md`. Tài liệu thiết kế rút gọn: `code-kg-design.md`.*
