# Nguồn kiểm chứng các giải pháp Code Knowledge Graph, 2024-2026

**Mốc kiểm chứng:** 04-08-2026
**Mục đích:** nguồn ngắn gọn để dựng presentation từ
[`code_knowledge_graph_limitations_and_solutions_vi.md`](../direct_rival/code_knowledge_graph_limitations_and_solutions_vi.md).

## Kết luận dùng được ngay trên slide

1. Các paper gần đây chứng minh graph giúp **tìm và gom đúng ngữ cảnh** tốt hơn text/vector retrieval trong một số task, đặc biệt là code completion, localization và repository-level repair.
2. Phần lớn graph vẫn là **chỉ mục cấu trúc theo task**, không phải sự thật đầy đủ về hành vi runtime. RepoGraph chỉ có `invoke`/`contain`; CodexGraph còn thiếu function-call edge; GraphCoder chỉ tập trung statement-level completion.
3. Nút thắt chuyển từ retrieval sang **semantic reasoning và validation**. RepoGraph vẫn ghi nhận contextual misalignment và regressive fixes sau khi đã có graph context.
4. Tool mới như CodeGraph, GitNexus và Code-Graph-RAG có UX/MCP và hỗ trợ ngôn ngữ rộng hơn paper, nhưng hiện là **tool-only**. Claim hiệu quả chủ yếu đến từ README hoặc benchmark do maintainer tự chạy, chưa phải bằng chứng peer-reviewed về độ đúng edge hay patch.
5. Microsoft GraphRAG là giải pháp tạo entity graph từ **văn bản phi cấu trúc**, không phải code semantic graph. Chỉ nên dùng nó để giải thích GraphRAG tổng quát hoặc knowledge từ tài liệu, không dùng làm bằng chứng cho symbol/call/type resolution.
6. Khoảng trống hợp lý cho giải pháp mới là **versioned evidence graph**: semantic binding có provenance, revision/freshness rõ, các layer static/runtime/human/LLM tách authority, retrieval bị giới hạn, và vòng lặp edit-reindex-test trên đúng revision. Đây là tổng hợp kiến trúc, chưa phải claim đã được một paper duy nhất chứng minh trọn vẹn.

## Trạng thái publication đã xác minh

| Giải pháp | Trạng thái chính xác | Điểm mới có thể giới thiệu | Limitation/evidence cần nói cùng |
|---|---|---|---|
| [GraphCoder](https://conf.researchr.org/details/ase-2024/ase-2024-research/46/GraphCoder-Enhancing-Repository-Level-Code-Completion-via-Coarse-to-fine-Retrieval-B) | **ASE 2024 Research Paper**, 31-10-2024, pp. 570-581, DOI [10.1145/3691620.3695054](https://doi.org/10.1145/3691620.3695054). Không còn chỉ là arXiv preprint. | Code Context Graph ở statement level gồm control flow, data dependence và control dependence; coarse-to-fine retrieval cho repository-level completion. | Phạm vi là completion, không chứng minh repair/refactor/runtime truth. Đánh giá 8.000 task trên 20 repo Python/Java; paper tự ghi external-validity giới hạn ở hai ngôn ngữ và baseline Vanilla/Shifted RAG do tác giả tự cài đặt. [Paper/arXiv v2](https://arxiv.org/abs/2406.07003), [threats to validity](https://arxiv.org/html/2406.07003v2#S7). |
| [RepoGraph](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf) | **ICLR 2025 conference paper**. | Tree-sitter dựng graph ở code-line level; node definition/reference, edge `invoke`/`contain`; lấy ego graph làm navigation plug-in cho procedural và agent frameworks. | Main experiments chỉ Python, proprietary GPT-4 series và SWE-bench Lite. Error analysis còn incorrect localization, contextual misalignment, regressive fix; paper nói hiệu quả vẫn phụ thuộc backbone LLM và gợi ý thêm real-time execution/feedback. [Construction](https://arxiv.org/html/2410.14684v2#S3.SS1), [limitations](https://arxiv.org/html/2410.14684v2#A5). |
| [CodexGraph](https://aclanthology.org/2025.naacl-long.7/) | **NAACL 2025 Long Paper**, tháng 04-2025, pp. 142-160, DOI [10.18653/v1/2025.naacl-long.7](https://doi.org/10.18653/v1/2025.naacl-long.7). | Static index vào Neo4j; LLM phân tích câu hỏi, một translation agent chuyển truy vấn sang Cypher; đánh giá trên CrossCodeEval, SWE-bench và EvoCodeBench. | Chỉ evaluate Python; tác giả nêu indexing/schema chưa hoàn chỉnh và cần thêm function-call edges. 43 SymPy samples bị loại vì OOM. Query result có độ dài khó kiểm soát, có thể lặp không sinh được executable query, và hiệu quả phụ thuộc reasoning/coding của backbone LLM. Whole-repo scan tạo privacy risk. [PDF chính thức](https://aclanthology.org/2025.naacl-long.7.pdf). |
| [Knowledge Graph Based Repository-Level Code Generation](https://conf.researchr.org/details/icse-2025/llm4code-2025-papers/26/Knowledge-Graph-Based-Repository-Level-Code-Generation-Virtual-Talk-) | **LLM4Code 2025 workshop tại ICSE 2025**, 03-05-2025, pp. 169-176, DOI [10.1109/LLM4Code66737.2025.00026](https://doi.org/10.1109/LLM4Code66737.2025.00026). | Hybrid retrieval trên graph để giữ inter-file modular dependency cho repository-level generation; đánh giá EvoCodeBench. | Workshop paper ngắn, không phải ICSE main research paper. Scope và evidence hẹp hơn RepoGraph/CodexGraph/CGM. [arXiv metadata](https://arxiv.org/abs/2505.14394). |
| [LocAgent](https://aclanthology.org/2025.acl-long.426/) | **ACL 2025 Long Paper**, tháng 07-2025, pp. 8697-8727, DOI [10.18653/v1/2025.acl-long.426](https://doi.org/10.18653/v1/2025.acl-long.426). | Directed heterogeneous graph của directory/file/class/function với containment/import/invoke/inherit; graph-guided multi-hop localization. | Trọng tâm là localization. Paper ghi patch location chỉ là approximate ground truth và có alternative fixes; LocBench lọc task sửa quá 5 file hoặc 10 function, nên chưa đại diện large-scope maintenance. [PDF chính thức](https://aclanthology.org/2025.acl-long.426.pdf). |
| [OrcaLoca](https://proceedings.mlr.press/v267/yu25x.html) | **ICML 2025 conference paper**, 13-19/07/2025, PMLR 267:73416-73436. | Priority scheduling, action decomposition, relevance scoring và distance-aware context pruning trên code graph cho issue localization. | Kết quả chính trên SWE-bench Lite; graph distance chỉ hữu ích khi topology và trọng số phản ánh dependency có ý nghĩa. Paper báo 65,33% function match và tăng 6,33 điểm phần trăm resolved rate trong setup của họ, không phải guarantee chung cho mọi repo. |
| [Code Graph Model](https://proceedings.neurips.cc/paper_files/paper/2025/hash/178ae4ba29022eb7bf509c2e27bc8ab8-Abstract-Conference.html) | **NeurIPS 2025 Main Conference Track**. | Tích hợp code graph trực tiếp vào attention qua graph encoder/adapter; kết hợp agentless GraphRAG với open-weight Qwen2.5-72B. | Kiến trúc graph-in-model cần training/deploy riêng, khó đổi schema/model. Paper vẫn cần GraphRAG chọn subgraph; retrieval loss và semantic reasoning failure không biến mất. Claim 43,00% SWE-bench Lite là trong setup công bố, không đồng nghĩa graph artifact chính xác hoàn toàn. [PDF chính thức](https://proceedings.neurips.cc/paper_files/paper/2025/file/178ae4ba29022eb7bf509c2e27bc8ab8-Paper-Conference.pdf). |
| [RepoDistill](https://aclanthology.org/2026.findings-acl.217/) | **Findings of ACL 2026**, tháng 07-2026, pp. 4425-4443, DOI [10.18653/v1/2026.findings-acl.217](https://doi.org/10.18653/v1/2026.findings-acl.217). | Lightweight GraphRAG lấy logical-flow context, sau đó learned budget allocation và policy optimization nén context. | Chính paper xác nhận graph retrieval vẫn có excessive/redundant context và lost-in-the-middle. Compressor giảm token sau retrieval nhưng không thể phục hồi evidence mà retriever đã bỏ sót. Claim giảm tới 66% token là trong benchmark/setup của paper. |
| [KGCompass](https://arxiv.org/abs/2503.21710) | **arXiv preprint**, nộp 27-03-2025, bản v3 ngày 03-10-2025. Không thấy venue/DOI conference chính thức trên trang arXiv tại mốc kiểm chứng. | Nối issue/PR với file/class/function và dùng entity path để localization + repair. | Claim 58,3% resolved trên SWE-bench Lite và lợi ích multi-hop là claim preprint; cần ghi rõ chưa peer-reviewed/accepted nếu đưa lên slide. |

## Tool đang hoạt động nhưng chưa có paper peer-reviewed

### CodeGraph

- Đối tượng kiểm chứng ở đây là [`colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph), tool local dùng SQLite, Rust/tree-sitter kernel, MCP, caller/callee/impact, watcher auto-sync và hỗ trợ nhiều ngôn ngữ. License hiện là [MIT, copyright 2026 Colby Mchenry](https://github.com/colbymchenry/codegraph/blob/main/LICENSE).
- README công bố benchmark 7 repository, mỗi repo một câu hỏi kiến trúc, Claude Opus 4.8, median 4 runs mỗi arm; metric là tool calls, tokens, cost và time. Đây là **maintainer-run benchmark**, không đo node/edge precision, binding accuracy hay patch correctness.
- Không tìm thấy paper/venue peer-reviewed được liên kết trong repo chính thức. Vì vậy nên ghi nhãn **tool / product evidence**, không ghi “paper 2026”.
- Claim “index never stale” là claim sản phẩm. README có cơ chế watcher, staleness banner và connect-time catch-up, nhưng presentation không nên biến claim đó thành consistency guarantee đã được đánh giá độc lập.

### GitNexus

- [`nxpatterns/gitnexus`](https://github.com/nxpatterns/gitnexus) là tool-only: Tree-sitter, LadybugDB, BM25 + semantic + RRF, clustering/process detection, impact/trace/Cypher và MCP; CLI chạy local, Web UI chạy trong browser.
- License hiện là [PolyForm Noncommercial 1.0.0](https://github.com/nxpatterns/gitnexus/blob/main/LICENSE), không phải permissive open-source license cho mọi commercial use.
- Limitation trực tiếp từ README: browser Web UI bị giới hạn khoảng 5.000 file bởi memory; một số grammar có caveat native install; CFG/PDG mới ở subset; **incremental indexing vẫn nằm trong roadmap** tại mốc kiểm chứng.
- Không tìm thấy paper peer-reviewed trong repo. Câu “agent never misses code” là marketing claim, không phải kết quả benchmark độc lập.

### Code-Graph-RAG

- [`vitali87/code-graph-rag`](https://github.com/vitali87/code-graph-rag) là tool-only, [MIT](https://github.com/vitali87/code-graph-rag/blob/main/LICENSE): Tree-sitter đa ngôn ngữ, Memgraph, natural-language-to-Cypher, Qdrant semantic search, structural search/replace và MCP edit tools.
- README hiện nêu Python, TypeScript/TSX, JavaScript, Rust, Go, Java, C/C++, C#, PHP, Lua, Dart; Ruby mới ở structural tier và Scala còn phát triển. `FLOWS_TO` dataflow được nêu cho C#, Java, C và Go.
- Vận hành cần Memgraph/Docker, CMake và ripgrep. Không tìm thấy paper peer-reviewed hoặc benchmark chính thức về edge correctness/end-to-end repair trong repo.
- Việc natural language được đổi sang Cypher tạo cùng lớp rủi ro query-generation đã thấy ở CodexGraph. Đây là **suy luận kiến trúc**, không phải limitation do maintainer tự công bố.

## Microsoft GraphRAG: liên quan nhưng không phải direct code-graph rival

- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/) được Microsoft Research ghi là **Preprint, April 2024**; [arXiv:2404.16130](https://arxiv.org/abs/2404.16130).
- [Repository chính thức](https://github.com/microsoft/graphrag) nói rõ pipeline trích structured data từ **unstructured text**, và code là demonstration, không phải Microsoft offering được support chính thức.
- Standard GraphRAG dùng LLM để trích entity/relationship/claim, community detection và community summaries. [Tài liệu methods](https://microsoft.github.io/graphrag/index/methods/) ước tính graph extraction chiếm khoảng 75% indexing cost; FastGraphRAG rẻ hơn nhưng graph noisier.
- Nó không có compiler/LSP symbol binding, overload resolution, call graph hay runtime semantics mặc định. Vì vậy chỉ nên xếp ở lớp **generic GraphRAG/document knowledge**, không xếp ngang RepoGraph/CodexGraph như direct code-semantic competitor.

## Cảnh báo tên gọi `CodeGraph`

`CodeGraph` không định danh một công trình duy nhất. Cần luôn kèm URL/tác giả:

- [`colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph) là code knowledge graph tool.
- [`CodeGraph: Enhancing Graph Reasoning of LLMs with Code`](https://arxiv.org/abs/2408.13863) dùng code để giải bài toán graph reasoning tổng quát; **không phải** graph của source-code repository.
- `CodeGraph` trong OrcaLoca có thể chỉ là tên thành phần graph của chính framework, không tự động đồng nghĩa với một product/paper độc lập.

## Pain point có bằng chứng mạnh nhất

| Pain point | Bằng chứng nguồn chính | Ý nghĩa cho giải pháp mới |
|---|---|---|
| Graph cú pháp thiếu semantic edge | CodexGraph tự nêu schema còn thiếu function-call edge; RepoGraph chỉ có `invoke`/`contain`. | Dùng compiler/LSP/SCIP-style binding khi có thể; giữ heuristic edge với modality/confidence riêng. |
| Retrieval đúng chưa đủ để patch đúng | RepoGraph vẫn có contextual misalignment và regressive fixes; CGM còn unresolved semantic cases. | Graph là evidence/navigation layer; patch phải qua build, test, static/runtime verification. |
| LLM-generated query giòn và tốn context | CodexGraph báo query loop, uncontrolled query-result length, token cost cao và phụ thuộc backbone reasoning. | Typed tools, bounded traversal, pagination, query cost budget; raw Cypher chỉ là fallback read-only. |
| Graph context vẫn dư thừa | RepoDistill nói graph retrieval vẫn kéo excessive context và làm lost-in-the-middle. | Trả evidence path/task projection thay vì flatten toàn bộ k-hop neighborhood. |
| Scale bị che khỏi denominator | CodexGraph loại 43 SymPy samples vì OOM. | OOM/timeout/unsupported phải được báo và giữ trong evaluation denominator. |
| Language coverage không đồng nghĩa semantic parity | Paper thường chỉ Python hoặc Python/Java; tool có nhiều parser nhưng capability không đều theo language. | Công bố capability matrix theo language/edge kind; không dùng một nhãn “multi-language” chung. |
| Freshness và revision còn thiếu bằng chứng chuẩn | Tool có watcher/roadmap riêng, còn các paper chủ yếu đánh giá snapshot. | Mọi response gắn repo/worktree/revision, content hash, freshness và extractor version. |
| Product claim chưa phải scientific evidence | CodeGraph/GitNexus/Code-Graph-RAG không có paper peer-reviewed trong repo chính thức. | Đánh giá graph accuracy, retrieval và downstream correctness ở ba tầng, cùng model/budget. |

## Cách định vị solution mới mà không overclaim

Có thể nói:

> Các giải pháp hiện tại đã chứng minh graph hữu ích để localization, completion và context retrieval. Solution mới tập trung vào phần còn thiếu: graph gắn revision và provenance, tách deterministic facts khỏi runtime/human/LLM claims, truy hồi evidence có budget, rồi kiểm chứng patch trên đúng post-edit revision.

Không nên nói:

- “Graph hiểu toàn bộ codebase” hoặc “không bao giờ bỏ sót dependency”.
- “Microsoft GraphRAG đã giải quyết code knowledge graph”.
- “Nhiều language parser đồng nghĩa semantic correctness đồng đều”.
- “Giảm token đồng nghĩa patch chính xác hơn”.
- “Paper 2026” cho CodeGraph, GitNexus hoặc Code-Graph-RAG khi không có publication record.

## Nguồn ưu tiên để gắn link trong HTML

1. [RepoGraph, ICLR 2025 proceedings PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf)
2. [CodexGraph, NAACL 2025 ACL Anthology](https://aclanthology.org/2025.naacl-long.7/)
3. [GraphCoder, ASE 2024 official program](https://conf.researchr.org/details/ase-2024/ase-2024-research/46/GraphCoder-Enhancing-Repository-Level-Code-Completion-via-Coarse-to-fine-Retrieval-B)
4. [LocAgent, ACL 2025 ACL Anthology](https://aclanthology.org/2025.acl-long.426/)
5. [OrcaLoca, ICML 2025 PMLR](https://proceedings.mlr.press/v267/yu25x.html)
6. [Code Graph Model, NeurIPS 2025 proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/178ae4ba29022eb7bf509c2e27bc8ab8-Abstract-Conference.html)
7. [RepoDistill, Findings ACL 2026](https://aclanthology.org/2026.findings-acl.217/)
8. [Microsoft GraphRAG publication page](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/)
9. [CodeGraph official repository](https://github.com/colbymchenry/codegraph)
10. [GitNexus official repository](https://github.com/nxpatterns/gitnexus)
11. [Code-Graph-RAG official repository](https://github.com/vitali87/code-graph-rag)
