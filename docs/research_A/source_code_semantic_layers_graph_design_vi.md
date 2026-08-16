# Thiết kế graph đa tầng để biểu diễn bản chất mã nguồn và phần mềm cho Agent/LLM

> **Mục tiêu:** thiết kế một Code Knowledge Graph đủ giàu để Agent/LLM không chỉ “tìm được file/hàm”, mà có thể lý giải cấu trúc, hành vi, dữ liệu, build, cấu hình, runtime, kiến trúc, ý định và lịch sử của một hệ thống phần mềm — đồng thời biết giới hạn và nguồn bằng chứng của từng kết luận.
>
> **Ngày chốt nghiên cứu:** 04-08-2026. Đây là file mới, bổ sung cho báo cáo literature review và báo cáo limitations/pain points; không thay thế hai file đó.

---

## 0. Kết luận điều hành

### 0.1 Luận điểm trung tâm

“Mã nguồn” không chỉ là văn bản và phần mềm không chỉ là tập hợp AST. Nghĩa của một hệ thống được xác định bởi một hàm nhiều biến:

**Software meaning = f(source, language semantics, dependencies, build variant, configuration, environment, input, persistent state, schedule, workload, revision, intent).**

Vì vậy, một graph chỉ có **file → class → function → calls** biểu diễn tốt navigation, nhưng không đủ để trả lời đáng tin cậy những câu như:

- Lời gọi nào thực sự có thể xảy ra dưới dynamic dispatch, dependency injection hoặc reflection?
- Dữ liệu người dùng đi qua những phép biến đổi nào trước khi được ghi vào cột database?
- Nhánh nào được bật cho tenant này bởi feature flag và cấu hình production?
- Cùng source revision đó tạo ra artifact nào với target, compiler flag và dependency version cụ thể?
- Trace lỗi production tương ứng với call site và source revision nào?
- Test nào chỉ “chạy qua” code, test nào thực sự kiểm chứng một invariant?
- Component triển khai có tuân theo kiến trúc dự kiến hay chỉ được LLM suy đoán là có?
- Quan hệ nào là sự thật từ compiler, quan hệ nào chỉ là static over-approximation, runtime observation hoặc human/LLM claim?

Thiết kế đề xuất trong báo cáo này là một **Versioned Software Evidence Graph đa tầng**. Nó là mô hình logic hợp nhất nhiều loại fact và evidence; không yêu cầu mọi dữ liệu phải nằm trong một graph database vật lý.

### 0.2 Mười hai quyết định thiết kế quan trọng nhất

1. **Graph phải biểu diễn software system, không chỉ source tree.** Build, config, contracts, data stores, deployment và runtime là những phần cấu thành nghĩa thực tế của code.
2. **Revision và context là thực thể bậc nhất.** Không có một graph “đúng cho mọi build”; tối thiểu mỗi fact phải được scope bởi repository, source revision và khi cần bởi build variant, environment, workload và thời gian.
3. **Source anchor và semantic entity phải tách rời.** Một identifier xuất hiện trong file không đồng nhất với symbol mà nó trỏ tới; một symbol có thể có nhiều declaration/definition/implementation và có thể không có source span trực tiếp.
4. **Quan hệ quan trọng phải được reify.** Call site, branch, data transfer, flag evaluation, build action và runtime event là các event/assertion có ngữ cảnh, không nên bị nén thành một edge nhị phân mất evidence.
5. **Graph phải giữ modality:** **MUST**, **MAY**, **OBSERVED**, **CLAIMED**, **REFUTED**, **UNKNOWN**. Runtime trace chứng minh “đã xảy ra trong workload này”, không chứng minh “luôn xảy ra”; static call graph thường là tập candidate, không phải call truth tuyệt đối.
6. **Không đồng nhất syntax với semantics.** Tree-sitter/CST là nền lossless và incremental rất tốt, nhưng binding, overload, generics, dispatch, alias, CFG và data-flow cần compiler/LSP/SCIP hoặc program analysis chuyên biệt.
7. **Không đồng nhất graph đầy đủ với graph hữu ích.** Fact base có thể giàu; Agent/LLM cần các task view bị giới hạn, có typed query, evidence path, budget và capability report.
8. **Architecture và domain meaning là assertion có thể kiểm chứng.** Chúng phải được map xuống source/build/runtime facts, giữ tác giả, phê duyệt và divergence thay vì được promote thành compiler truth.
9. **Derived fact và LLM claim không được overwrite evidence.** Summary, community, risk score, intent và agent memory phải có derivation, TTL, model/prompt và supporting/contradicting evidence.
10. **“Không tìm thấy edge” không mặc nhiên nghĩa là “không tồn tại quan hệ”.** Chỉ được kết luận phủ định nếu layer tương ứng khai báo closed-world và coverage đủ cho đúng revision/context.
11. **Graph cần cả static possibility và dynamic actuality.** Hai lớp bổ sung nhau: static analysis mở rộng phạm vi có thể xảy ra; runtime telemetry cho biết điều đã xảy ra dưới workload cụ thể.
12. **Mục tiêu thực tế không phải “complete semantics”.** Mục tiêu là representation có độ phủ cao, bằng chứng rõ, bất định trung thực, cập nhật được và phục vụ đúng câu hỏi của agent.

### 0.3 Ranh giới lý thuyết: vì sao không thể “biểu diễn hết” theo nghĩa tuyệt đối

[Rice, 1953](https://www.ams.org/journals/tran/1953-074-02/S0002-9947-1953-0053041-6/S0002-9947-1953-0053041-6.pdf) đặt giới hạn nền tảng cho các thuộc tính ngữ nghĩa không tầm thường có thể được quyết định tổng quát. [Abstract interpretation](https://dl.acm.org/doi/10.1145/512950.512973) cung cấp nền tảng để tính các xấp xỉ an toàn, chứ không xóa giới hạn đó. Trong thực tế còn có:

- input và persistent state không bị chặn;
- code được tải động, reflection, eval, FFI, native extension và generated code;
- compiler/linker flags, undefined hoặc implementation-defined behavior;
- scheduler, race, network, external service và con người;
- sampling runtime không bao phủ mọi execution;
- requirement và intent có thể mơ hồ hoặc mâu thuẫn.

Do đó, “biểu diễn hết mọi khía cạnh” trong báo cáo này có nghĩa là:

1. có **chỗ biểu diễn** cho mọi lớp ý nghĩa quan trọng;
2. có **extractor/evidence contract** phù hợp cho từng lớp;
3. biểu diễn rõ cái gì đã biết, có thể xảy ra, đã quan sát, được tuyên bố hoặc chưa biết;
4. có thể tạo projection phù hợp để agent lý giải và hành động an toàn.

---

## 1. Cơ sở nghiên cứu và cách tổng hợp

### 1.1 Các dòng nghiên cứu được dùng

Báo cáo tổng hợp năm dòng nền tảng, thay vì chọn một schema rồi mở rộng tùy ý:

| Dòng nghiên cứu/chuẩn | Đại diện chính | Bài học đưa vào thiết kế |
|---|---|---|
| Metamodel toàn hệ thống | [OMG KDM 1.4](https://www.omg.org/spec/KDM/1.4/About-KDM) | Phần mềm có nhiều facet độc lập: source/code/action, platform/UI/event/data, structure/conceptual/build. |
| Semantic source indexing | [Kythe](https://kythe.io/docs/schema-overview.html), [SCIP](https://github.com/scip-code/scip), [Glean](https://glean.software/) | Tách source anchor khỏi semantic entity; symbol ID có kiểu; schema riêng theo ngôn ngữ và view chung; fact theo revision. |
| Program representation/analysis | [PDG](https://dl.acm.org/doi/10.1145/24039.24041), [SDG](https://dl.acm.org/doi/10.1145/77606.77608), [SSA](https://dl.acm.org/doi/10.1145/115372.115320), [CPG](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf), [Joern CPG spec](https://cpg.joern.io/) | AST phải được bổ sung bởi control-, data-, dependence-, call- và memory semantics; nhiều quan hệ là xấp xỉ phân tích tĩnh. |
| Whole-system contracts/evidence | [SPDX 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/), [OpenAPI 3.2](https://spec.openapis.org/oas/v3.2.0.html), [AsyncAPI 3.1](https://www.asyncapi.com/docs/reference/specification/latest), [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/), [OpenLineage](https://openlineage.io/docs/), [W3C PROV-O](https://www.w3.org/TR/prov-o/) | Build/supply chain, protocol, runtime, data lineage và provenance đã có ontology/contract chuyên ngành; nên liên kết thay vì phát minh lại. |
| Graph cho LLM/coding agent | [RepoGraph, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf), [CodexGraph, NAACL 2025](https://aclanthology.org/2025.naacl-long.7/), [LocAgent, ACL 2025](https://aclanthology.org/2025.acl-long.426/), [RepoDistill, Findings ACL 2026](https://aclanthology.org/2026.findings-acl.217/) | Graph nhẹ đã chứng minh giá trị cho retrieval/navigation, nhưng query fragility, context noise và downstream reasoning cho thấy agent cần typed views, evidence và closed loop. |

### 1.2 KDM là checklist độ phủ, không phải schema cần sao chép nguyên khối

[KDM](https://www.omg.org/spec/KDM/1.4/PDF) tổ chức tri thức thành bốn layer lớn:

1. **Infrastructure**;
2. **Program Elements** — Source, Code và Action;
3. **Runtime Resources** — Platform, UI, Event và Data;
4. **Abstractions** — Structure, Conceptual và Build.

Điểm đặc biệt quan trọng là KDM thừa nhận cùng source có thể tạo mô hình logic khác nhau theo compilation, linking, target platform và build flags. Nó cũng tách tri thức tự động trích xuất được khỏi abstraction kiến trúc/nghiệp vụ thường ẩn trong hệ thống. Đây là khung coverage rất tốt, nhưng KDM quá rộng và nặng nếu dùng trực tiếp làm query surface cho coding agent hiện đại. Thiết kế ở đây giữ độ phủ của KDM, rồi bổ sung:

- stable source anchors và semantic indexes kiểu Kythe/SCIP;
- CFG/PDG/SSA/points-to/CPG;
- revision, provenance và uncertainty;
- runtime trace và distributed causality;
- task-specific projections cho Agent/LLM.

### 1.3 Không nên có một “universal lowest-common-denominator schema”

[Glean](https://engineering.fb.com/2024/12/19/developer-tools/glean-open-source-code-indexing/) đưa ra pattern thực dụng: giữ fact chi tiết theo từng ngôn ngữ, sau đó cung cấp các view trung lập ngôn ngữ. Cách này tốt hơn việc ép Rust lifetime, C++ template, Java annotation, Python decorator và JavaScript prototype vào một lớp “Function/Class” quá nghèo.

Thiết kế đề xuất dùng hai tầng schema:

- **Language-specific semantic schema:** giữ fidelity của compiler/runtime/framework.
- **Cross-language canonical view:** cung cấp các khái niệm chung như callable, type, value, module, call site, data transfer, build target, API operation.

View chung không được làm mất liên kết quay lại fact chi tiết.

---

## 2. Bản đồ 18 lớp ý nghĩa

### 2.1 Ba miền lớn

~~~mermaid
flowchart TD
    A["Artifact: code tồn tại ở đâu và phiên bản nào"] --> B["Language semantics: code biểu thị và có thể thực thi gì"]
    B --> C["System context: code được build, cấu hình và tích hợp thế nào"]
    C --> D["Observed behavior: hệ thống thực sự chạy ra sao"]
    D --> E["Intent and evolution: tại sao nó tồn tại và thay đổi thế nào"]
    E --> F["Agent knowledge: kết luận nào được suy ra và bằng chứng gì"]
~~~

- **L0–L7:** semantic spine của source/program.
- **L8–L13:** software system quanh source.
- **L14–L17:** validation, intent, evolution và knowledge dành cho agent.

### 2.2 Ma trận tổng quan

| Lớp | Bản chất cần biểu diễn | Node/edge tiêu biểu | Nguồn authority chính |
|---|---|---|---|
| L0. Identity & revision | Cái gì, ở repo/snapshot/path/revision nào | Repository, Revision, FileContent, FileOccurrence, Anchor | VCS, content hash, ingestion manifest |
| L1. Text, token, docs | Ký tự, token, comment, docstring, tài liệu | Token, Comment, DocumentSection, DOCUMENTS, REF_DOC | Parser, raw source, docs |
| L2. Syntax & expansion | Cấu trúc ngữ pháp, macro/template/generated mapping | CSTNode, ASTNode, MacroExpansion, GeneratedUnit | Parser, preprocessor, compiler/codegen |
| L3. Symbols, binding & types | Identifier nào trỏ tới thực thể nào; type/signature/generic | Symbol, Occurrence, Scope, Type, BINDS_TO, HAS_TYPE | Compiler, SCIP/LSP/indexer |
| L4. Static relations & dispatch | Containment, import, inheritance, override, call candidate | CallSite, ImportSite, Reference, MAY_TARGET | Semantic resolver, call-graph analysis |
| L5. Control, exception & state | Thứ tự có thể thực thi, branch, throw/catch, lifecycle | BasicBlock, Branch, Handler, State, CONTROL_FLOW | Compiler IR, CFG/CPG |
| L6. Value, memory & data | Def-use, SSA, alias, points-to, data/taint dependence | ValueVersion, MemoryRegion, Phi, DataTransfer | SSA, PDG/SDG, MemorySSA, pointer analysis |
| L7. Concurrency & causality | Thread/task, synchronization, happens-before, race | Task, Lock, AtomicOp, Message, HAPPENS_BEFORE | Language memory model, analyzer, runtime |
| L8. Build & supply chain | Source nào tạo artifact nào dưới variant/toolchain nào | Target, Action, Artifact, PackageVersion, SBOM | Build system, lockfile, SPDX/attestation |
| L9. Config & policy | Flag/config/env/tenant nào kích hoạt behavior nào | ConfigKey, Flag, EvaluationContext, GUARDS | Config schema, OpenFeature, deployment/runtime |
| L10. Interface & protocol | API/RPC/event/message contract và implementation | Operation, Endpoint, Channel, MessageSchema | OpenAPI, AsyncAPI, protobuf, framework |
| L11. Persistence & lineage | Table/column/query/migration; dữ liệu đi và biến đổi ra sao | Dataset, Table, Column, Query, Transaction | DDL, ORM, query analyzer, OpenLineage |
| L12. UI & interaction | Screen/route/component/state/event/user flow | View, UIComponent, Action, Transition | UI framework, route/config, tests |
| L13. Deployment & runtime | Service/process/container/instance/trace/log/metric/profile | DeploymentUnit, Span, Trace, Failure, Observation | IaC/orchestrator, OpenTelemetry |
| L14. Tests, contracts & findings | Điều gì được kỳ vọng/kiểm chứng; quality/security evidence | TestCase, Assertion, Invariant, Coverage, Finding | Test/build run, analyzer, human oracle |
| L15. Architecture & domain intent | Component/layer/capability/business rule/requirement/ADR | Component, Boundary, Concept, Requirement, Decision | Architecture docs, approved mapping, LLM claim |
| L16. Evolution, ownership & provenance | Ai/tại sao/khi nào thay đổi; lineage qua revision | Commit, ChangeSet, Issue, Release, Owner, Activity | VCS/forge, CODEOWNERS, W3C PROV |
| L17. Derived/LLM knowledge | Summary, hypothesis, risk, agent memory và plan | Claim, Summary, Hypothesis, TaskMemory | Derivation rule, model run, verifier |

---

## 3. Bóc tách từng lớp và cách graph biểu diễn

## L0. Identity, artifact và revision

### Bản chất

Mọi kết luận về code trước hết phải trả lời: **đang nói về artifact nào, tại revision nào, xuất hiện ở path nào?** Nội dung giống nhau có thể xuất hiện ở nhiều path/repository; một path có thể trỏ tới nội dung khác theo revision; symbol có thể bị move/rename.

[Software Heritage](https://docs.softwareheritage.org/devel/swh-model/data-model.html) mô hình hóa archive như Merkle DAG gồm content, directory, revision, release và snapshot. [SWHID](https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html) còn tách intrinsic identifier khỏi context/fragment qualifiers — một pattern phù hợp với Code Graph.

### Biểu diễn đề xuất

| Node | Ý nghĩa |
|---|---|
| Repository | Không gian source và quyền truy cập ổn định |
| Revision | Commit immutable hoặc workspace snapshot có manifest |
| FileContent | Blob xác định bởi content hash |
| FileOccurrence | FileContent tại một path trong một Revision |
| SourceAnchor | Byte span/line-column trong FileOccurrence, có surrounding hash |
| WorkspaceOverlay | Revision tạm chứa edit chưa commit của agent |

Quan hệ tối thiểu:

- Repository **HAS_REVISION** Revision;
- Revision **CONTAINS_OCCURRENCE** FileOccurrence;
- FileOccurrence **HAS_CONTENT** FileContent;
- SourceAnchor **LOCATED_IN** FileOccurrence;
- Revision **PARENT_OF** Revision;
- WorkspaceOverlay **BASED_ON** Revision.

### Quy tắc quan trọng

- ID symbol trong một revision không được dùng như bằng chứng rằng symbol ở revision khác là cùng thực thể.
- **RENAMED_FROM / MOVED_FROM / CONTINUES_AS** là continuity claim có evidence từ diff/refactor detector, không phải intrinsic identity.
- Mọi query agent phải trả source revision, graph revision và freshness lag.

## L1. Text, lexical form, comment và documentation

### Bản chất

Whitespace, punctuation, token, literal, comment, docstring, annotation text và README đều mang thông tin khác nhau. AST thường bỏ trivia; trong khi formatter, codemod, license, suppression, macro và agent patch cần source fidelity.

[Tree-sitter](https://tree-sitter.github.io/) tạo concrete syntax tree, cập nhật incremental và vẫn hữu ích khi file có syntax error. [CodeQL JavaScript library](https://codeql.github.com/docs/codeql-language-guides/codeql-library-for-javascript/) cũng phân biệt rõ textual, lexical, syntactic, name-binding, control-flow và data-flow levels.

### Biểu diễn đề xuất

- **Token**, **Comment**, **Docstring**, **Literal**, **AnnotationText**, **DocumentSection**;
- **NEXT_TOKEN**, **PART_OF_ANCHOR**, **DOCUMENTS**, **REF_DOC**, **SUPPRESSES_RULE**, **MENTIONS_SYMBOL**;
- raw text/blob ở object store; graph giữ anchor, kind, hash và quan hệ.

Documentation không phải semantic truth. Một docstring “returns cached value” là **DocumentClaim**, được support hoặc contradict bởi code/test/runtime evidence. Embedding của docs phải trỏ về node/anchor/revision gốc; vector similarity không thay thế relation.

## L2. Concrete syntax, abstract syntax, macro và generated code

### Bản chất

CST cho biết code được viết thế nào; AST loại bỏ chi tiết bề mặt để thể hiện cấu trúc ngôn ngữ; compiler IR thể hiện ngữ nghĩa ở mức thấp hơn. Preprocessor, macro, decorator transform, annotation processor, template instantiation và code generation tạo thêm program elements không tồn tại nguyên dạng trong source.

### Biểu diễn đề xuất

- **CSTNode**, **ASTNode**, **Expression**, **Statement**, **DeclarationSyntax**;
- **MacroDefinition**, **MacroInvocation**, **Expansion**, **GeneratedUnit**, **IRInstruction**;
- **AST_CHILD**, **LOWERS_TO**, **EXPANDS_TO**, **GENERATED_FROM**, **ORIGINATES_AT**, **DESUGARS_TO**.

Mọi generated/expanded node cần source map hai chiều:

1. user-written anchor → expanded/generated element;
2. generated element → generator/template/schema/build action;
3. generated artifact → build variant.

Nếu chỉ graph generated code, agent có thể sửa nhầm output sẽ bị overwrite. Nếu chỉ graph source, agent không thấy implementation thực sự compiler/runtime dùng.

### Extraction

- Tree-sitter/CST cho lossless, partial và fast incremental layer.
- Compiler/preprocessor cho expansion, desugaring, template instantiation và IR.
- Codegen/build plugin cho protobuf/OpenAPI/ORM/template outputs.
- Parse error là node **Diagnostic**, không phải lý do loại toàn file.

## L3. Symbol, scope, binding, type và signature

### Bản chất

Identifier chỉ có nghĩa trong scope, import environment, overload set, generic instantiation và build context. “foo” ở hai module không phải một node; một method declaration, definition và override cũng không nên bị merge chỉ vì cùng tên.

[Kythe](https://kythe.io/docs/schema-overview.html) tách anchor khỏi semantic node. [SCIP](https://github.com/scip-code/scip/blob/main/scip.proto) tách **Occurrence** (range trong source) khỏi **SymbolInformation** (stable symbol, documentation, kind, signature và relationships). Đây là mô hình nền nên áp dụng.

### Biểu diễn đề xuất

| Nhóm node | Ví dụ |
|---|---|
| Semantic entity | Module, Namespace, Type, Trait, Interface, Function, Method, Field, Variable, Parameter |
| Binding context | Scope, ImportEnvironment, OverloadSet, GenericContext |
| Type system | NominalType, StructuralType, TypeArgument, Constraint, Lifetime, Effect |
| Source occurrence | DeclarationOccurrence, DefinitionOccurrence, ReferenceOccurrence |

Quan hệ:

- Occurrence **BINDS_TO** Symbol;
- Symbol **DECLARED_AT / DEFINED_AT / IMPLEMENTED_AT** Anchor;
- Symbol **HAS_TYPE / RETURNS / PARAMETER** Type;
- Scope **DECLARES** Symbol; Occurrence **RESOLVED_IN** Scope;
- GenericInstance **INSTANTIATES** GenericDefinition;
- Type **SATISFIES / SUBTYPES / ALIASES** Type.

### Authority và bất định

- Compiler/SCIP index trong đúng build context: **RESOLVED_FACT**.
- LSP incomplete workspace: resolved fact nhưng capability có thể partial.
- Heuristic name match: **CLAIMED** hoặc **MAY_BIND**, không phải **BINDS_TO**.
- Dynamic language type inference: **MAY_HAVE_TYPE**, kèm analysis/configuration.

Glean cho thấy nên giữ schema chi tiết theo ngôn ngữ rồi derive language-neutral predicates; không nên mất Rust lifetime/effect hay C++ specialization để đổi lấy một schema chung dễ nhìn.

## L4. Static structure, reference, inheritance và dispatch

### Bản chất

Đây là lớp quen thuộc nhất của Code Graph: containment, imports, exports, references, inherits, implements, overrides, calls. Nhưng call relation không chỉ là Function A **CALLS** Function B:

- call xảy ra tại một source site;
- site nằm trong caller và một control context;
- callee có thể là overload/virtual target/callback candidate;
- target thay đổi theo type, points-to set, dependency injection, feature flag hoặc build;
- runtime có thể quan sát một subset.

[Kythe call graph](https://kythe.io/docs/schema/callgraph.html) dùng call-site anchor liên kết tới callee và **childof** caller, thay vì chỉ lưu caller→callee. Đây là bước đầu đúng; thiết kế đề xuất reify call site đầy đủ hơn.

### Biểu diễn call site

~~~mermaid
flowchart TD
    C["Caller symbol"] -->|CONTAINS_CALL| S["CallSite"]
    S -->|AT| A["SourceAnchor"]
    S -->|MAY_TARGET| T["Callee candidate"]
    S -->|UNDER| X["Build/config/control context"]
    S -->|SUPPORTED_BY| E["Resolver evidence"]
~~~

Properties của **CallSiteTarget assertion**:

- dispatch: direct, virtual, interface, function-pointer, closure, reflective, FFI;
- modality: MUST hoặc MAY;
- receiver/type/points-to context;
- revision và build variant;
- resolution algorithm/version;
- evidence anchor và confidence nếu đã calibration.

### Các quan hệ khác

- **CONTAINS**, **IMPORTS**, **EXPORTS**, **REFERENCES**;
- **EXTENDS**, **IMPLEMENTS**, **SATISFIES**, **OVERRIDES**;
- **READS_FIELD**, **WRITES_FIELD**, **ALLOCATES**, **INSTANTIATES**;
- **REGISTERS_CALLBACK**, **INJECTS_IMPLEMENTATION**, **BINDS_ROUTE**.

Framework adapters rất quan trọng: route decorators, Spring dependency injection, React hooks, ORM relations hoặc plugin registries mang semantics vượt ngoài grammar. Heuristic framework edge phải khai báo coverage và evidence.

## L5. Control flow, exception, lifecycle và state transition

### Bản chất

AST nói code lồng nhau thế nào; Control-Flow Graph nói execution có thể đi đâu tiếp theo. Muốn agent lý giải “nhánh nào dẫn tới lỗi”, “resource có luôn được đóng không”, “exception bị bắt ở đâu”, cần:

- basic blocks và branch guards;
- normal/exceptional edges;
- return, break, continue, defer/finally;
- coroutine suspend/resume;
- lifecycle và explicit state machine.

[Joern CPG specification](https://cpg.joern.io/) định nghĩa CFG, dominator/post-dominator và Program Dependence Graph trên cùng Code Property Graph. [KDM Action](https://www.omg.org/spec/KDM/1.4/PDF) cũng xem các computational elements là facet riêng của program.

### Biểu diễn đề xuất

- **Entry**, **Exit**, **BasicBlock**, **Branch**, **Guard**, **CallReturn**, **Throw**, **Catch**, **Finally**, **Suspend**, **Resume**;
- **State**, **Transition**, **LifecyclePhase**, **Resource**;
- **CONTROL_FLOW**, **TRUE_BRANCH**, **FALSE_BRANCH**, **EXCEPTION_FLOW**, **DOMINATES**, **POST_DOMINATES**;
- **TRANSITIONS_FROM/TO**, **GUARDED_BY**, **ACQUIRES**, **RELEASES**.

Một transition nên là node/event khi cần mang trigger, guard, action và evidence. Không nên tạo transitive CFG closure thành edge vật lý toàn cục; dùng summary/on-demand view để tránh explosion.

## L6. Value, memory, alias, data-flow và dependence

### Bản chất

Đây là lớp quyết định agent có “hiểu dữ liệu” hay chỉ hiểu navigation. Các câu hỏi chính:

- Giá trị này được định nghĩa ở đâu và dùng ở đâu?
- Giá trị nào có thể chảy tới sink?
- Hai expression có thể trỏ tới cùng object/memory region không?
- Branch này phụ thuộc vào dữ liệu nào?
- Input API biến đổi thế nào trước khi ghi DB hoặc log?

[Program Dependence Graph](https://dl.acm.org/doi/10.1145/24039.24041) hợp nhất control- và data-dependence; [System Dependence Graph](https://dl.acm.org/doi/10.1145/77606.77608) mở rộng slicing liên thủ tục; [SSA](https://dl.acm.org/doi/10.1145/115372.115320) tạo version cho mỗi definition. [LLVM MemorySSA](https://llvm.org/docs/MemorySSA.html) cung cấp def-use/use-def cho memory, còn pointer/alias analysis phải cân bằng precision và cost.

### Biểu diễn đề xuất

- **ValueVersion**, **Definition**, **Use**, **Phi**, **ExpressionResult**;
- **AllocationSite**, **AbstractObject**, **MemoryRegion**, **FieldLocation**, **AliasSet**;
- **DataTransfer**, **Sanitizer**, **Source**, **Sink**, **FlowLabel**;
- **DEFINES**, **USES**, **REACHING_DEF**, **DATA_DEPENDS_ON**, **CONTROL_DEPENDS_ON**;
- **MAY_ALIAS / MUST_ALIAS / NO_ALIAS**, **POINTS_TO**, **FLOWS_TO**, **SANITIZES**.

DataTransfer cần mang:

- operation/transform;
- path/context sensitivity;
- field/index sensitivity;
- interprocedural summary;
- modality và analysis configuration;
- source/sink labels và provenance.

Không nên lưu “tainted=true” vĩnh viễn trên symbol. Taint là kết quả của một query/model gồm source, sink, sanitizer, flow labels và analysis version. Joern cũng coi một **Finding** là kết quả có evidence, không phải thuộc tính bản thể của code.

## L7. Concurrency, asynchronous execution và causality

### Bản chất

CFG đơn luồng không đủ cho thread, process, coroutine, actor, callback queue, stream hoặc distributed message. Thứ tự source không đồng nghĩa thứ tự quan sát; hai access có thể concurrent; synchronization và memory ordering quyết định visibility.

[Lamport](https://dl.acm.org/doi/10.1145/359545.359563) định nghĩa quan hệ “happened-before” như một partial order của event trong hệ phân tán. [C++ memory model](https://eel.is/c%2B%2Bdraft/intro.races) định nghĩa data race dựa trên conflicting actions, potential concurrency và absence of happens-before; data race có thể dẫn đến undefined behavior. Những quan hệ này phải là graph primitive, không thể suy từ một call graph phẳng.

### Biểu diễn đề xuất

- **Thread**, **Task**, **Coroutine**, **Actor**, **Process**, **ExecutionLane**;
- **Spawn**, **Join**, **Await**, **Suspend**, **Resume**, **Send**, **Receive**;
- **Lock**, **CriticalSection**, **AtomicOperation**, **Fence**, **Channel**, **Queue**;
- **SEQUENCED_BEFORE**, **SYNCHRONIZES_WITH**, **HAPPENS_BEFORE**, **MAY_RUN_CONCURRENTLY**;
- **ACQUIRES_LOCK**, **RELEASES_LOCK**, **READS_FROM**, **CONFLICTS_WITH**, **POTENTIAL_RACE**.

### Hai graph cần đặt cạnh nhau

1. **Static concurrency graph:** những schedule/target có thể xảy ra, thường là MAY.
2. **Observed event graph:** những task/span/message đã xảy ra trong một run, với clock/time/trace context.

Một trace không quan sát race không chứng minh chương trình race-free. Ngược lại, static analyzer báo potential race không chứng minh race đã xảy ra. Agent cần thấy cả hai cùng evidence.

## L8. Build graph, artifact, dependency và software supply chain

### Bản chất

Source không tự trở thành chương trình. Build system lựa chọn file, macro, feature, target, toolchain, dependency và code generator để tạo artifact. [Bazel query](https://bazel.build/query/language) hoạt động trên build dependency graph trừu tượng; [cquery](https://bazel.build/query/cquery) xử lý configured target và ảnh hưởng của option; [aquery](https://bazel.build/query/aquery) đi xuống action/artifact graph. Sự phân tầng này là bằng chứng rõ rằng “dependency graph” không phải một graph duy nhất.

[SPDX 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/) mô hình hóa package, file, snippet, build và security/licensing relationships. Build profile còn có thể biểu diễn input, output, procedure, environment, actor và evidence của build.

### Biểu diễn đề xuất

| Nhóm | Node |
|---|---|
| Selection | BuildVariant, ConfiguredTarget, FeatureSet, PlatformTarget |
| Action | CompileAction, LinkAction, TestAction, CodegenAction, PackageAction |
| Artifact | ObjectFile, Library, Binary, ContainerImage, GeneratedSource |
| Toolchain | Compiler, Linker, SDK, Runtime, ToolVersion |
| Dependency | Package, PackageVersion, LockEntry, Module, License, Vulnerability |
| Evidence | BuildRun, BuildLog, Attestation, SBOM |

Quan hệ:

- **SELECTS_SOURCE**, **DEPENDS_ON_TARGET**, **USES_TOOLCHAIN**;
- **ACTION_INPUT**, **ACTION_OUTPUT**, **COMPILES**, **LINKS**, **PACKAGES**;
- **GENERATES**, **CONTAINS_COMPONENT**, **RESOLVES_VERSION**;
- **DECLARED_LICENSE**, **CONCLUDED_LICENSE**, **AFFECTED_BY**, **MITIGATED_BY**.

### Quy tắc

- **BuildVariant** là context bắt buộc cho resolved dependency, generated symbol và executable call graph.
- Không merge package chỉ theo name; identity gồm ecosystem, namespace, version/digest và source.
- Dependency declared, resolved, bundled, loaded và observed là các relation khác nhau.
- Không đưa CVE trực tiếp lên repository nếu chưa có path từ affected package/version tới artifact/deployment và VEX/evidence.

## L9. Configuration, feature flag, environment, secret reference và policy

### Bản chất

Configuration là “code ngoài code”: nó chọn implementation, endpoint, timeout, permission, rollout và branch. [OpenFeature](https://openfeature.dev/specification/sections/evaluation-context/) cho thấy flag value phụ thuộc evaluation context như user, service, host, locale hoặc thời gian; resolution còn có variant và reason. Vì vậy, **Flag → Value** không phải edge tĩnh toàn cục.

### Biểu diễn đề xuất

- **ConfigKey**, **ConfigSchema**, **ConfigSource**, **ConfigValueVersion**;
- **FeatureFlag**, **FlagVariant**, **TargetingRule**, **EvaluationContext**;
- **Environment**, **Tenant**, **Region**, **Policy**, **SecretReference**;
- **READS_CONFIG**, **GUARDED_BY**, **EVALUATES_TO**, **OVERRIDES**, **CONFIGURES**, **ENFORCES**.

**FlagEvaluation** nên là event/assertion:

- flag và rule version;
- evaluation context được redact;
- result variant/value class;
- reason và timestamp;
- call site/build/deployment/run;
- evidence từ SDK/telemetry.

### Quy tắc an toàn

- Graph chỉ giữ secret name/reference, classification, rotation metadata và consumer; không ingest secret value.
- Config value nhạy cảm cần access label riêng.
- Các condition chưa biết được giữ như symbolic guard, không tự chọn default.
- Để tránh nổ tổ hợp variant, fact base lưu predicate/condition; chỉ materialize những build/config phổ biến hoặc được query.

## L10. External interface, protocol, event và workflow

### Bản chất

Software được hiểu qua ranh giới: HTTP API, RPC, CLI, library API, message/event, webhook, file format và callback. Source handler chỉ là implementation; contract còn có request/response schema, auth, error, compatibility và consumer.

[OpenAPI 3.2](https://spec.openapis.org/oas/v3.2.0.html) là interface description trung lập ngôn ngữ cho HTTP API. [AsyncAPI 3.1](https://www.asyncapi.com/docs/reference/specification/latest) mô hình hóa channel, operation và message cho protocol message-driven. [Arazzo 1.1](https://spec.openapis.org/arazzo/latest.html) bổ sung sequence of calls và dependencies để đạt một outcome — rất gần task/use-case view mà agent cần.

### Biểu diễn đề xuất

- **Interface**, **Operation**, **Endpoint**, **Route**, **RPCMethod**, **CLICommand**;
- **RequestSchema**, **ResponseSchema**, **ErrorContract**, **SecurityScheme**;
- **Channel**, **Topic**, **Subscription**, **MessageSchema**, **EventType**;
- **Workflow**, **WorkflowStep**, **Outcome**, **ExternalSystem**.

Quan hệ:

- **DECLARES_OPERATION**, **IMPLEMENTS_OPERATION**, **CALLS_OPERATION**;
- **BINDS_ROUTE_TO_HANDLER**, **ACCEPTS**, **RETURNS**, **MAY_RETURN_ERROR**;
- **AUTHENTICATED_BY**, **AUTHORIZED_BY**, **RATE_LIMITED_BY**;
- **PUBLISHES**, **SUBSCRIBES**, **SERIALIZES_AS**, **DESERIALIZES_AS**;
- **PRECEDES_STEP**, **SUPPLIES_INPUT_TO**, **ACHIEVES_OUTCOME**.

### Drift phải được biểu diễn

Contract, code và runtime có thể lệch:

- declared operation nhưng không có handler;
- handler có route nhưng spec thiếu;
- schema declared khác payload observed;
- producer/consumer dùng message version khác;
- auth policy trong deployment khác annotation.

Graph phải tạo **ConformanceFinding** với expected, implemented, observed và evidence; không âm thầm merge ba nguồn.

## L11. Persistence, database semantics và data lineage

### Bản chất

Để hiểu behavior nghiệp vụ, agent phải thấy data vượt qua boundary của process: schema, constraint, query, transaction, migration, cache, stream, object/file store và ETL. ORM class không đồng nhất table; SQL string động không luôn resolve được; stored procedure/trigger có behavior ngoài application source.

[OpenLineage](https://openlineage.io/docs/spec/object-model/) tách **Job**, **Run** và **Dataset**; static job metadata khác runtime run event. Đây là pattern phù hợp để liên kết code-level data-flow với system-level lineage.

### Biểu diễn đề xuất

- **Database**, **Schema**, **Table**, **Column**, **View**, **Index**, **Constraint**;
- **Query**, **PreparedStatement**, **ORMModel**, **Mapping**, **Migration**;
- **Transaction**, **IsolationLevel**, **StoredProcedure**, **Trigger**;
- **Dataset**, **DataJob**, **DataRun**, **DataQualityAssertion**;
- **Cache**, **FileFormat**, **ObjectStore**, **Stream**.

Quan hệ:

- **MAPS_TO**, **READS**, **WRITES**, **UPDATES**, **DELETES**;
- **FILTERS_BY**, **JOINS_ON**, **DERIVES_COLUMN_FROM**, **VALIDATES**;
- **BEGINS/COMMITS/ROLLS_BACK_TRANSACTION**, **MIGRATES_FROM/TO**;
- **CONSUMES_DATASET**, **PRODUCES_DATASET**, **TRIGGERS**.

### Granularity

- Table-level lineage phù hợp overview nhưng không đủ cho privacy/impact.
- Column/field-level lineage cần cho PII, schema change và security.
- Row/value-level lineage thường chỉ nên lưu observation/summary có retention, vì chi phí và privacy.
- Dynamic SQL unresolved phải tạo **UnresolvedQuery** và capability gap, không giả lập edge chắc chắn.

## L12. UI, interaction, presentation và client state

### Bản chất

UI code có ngữ nghĩa riêng: screen/route, component tree, rendered state, event handler, navigation, form validation, accessibility, local/global state và user journey. KDM dành hẳn UI và Event package vì call graph backend không biểu diễn được interaction semantics.

### Biểu diễn đề xuất

- **ApplicationView**, **Screen**, **Route**, **UIComponent**, **RenderedElement**;
- **UserAction**, **UIEvent**, **Handler**, **FormField**, **ValidationRule**;
- **ClientState**, **Store**, **Reducer**, **Effect**, **NavigationTransition**;
- **AccessibilityRole**, **PermissionGate**, **ExperimentVariant**.

Quan hệ:

- **ROUTE_RENDERS**, **COMPONENT_CONTAINS**, **BINDS_DATA**;
- **EVENT_HANDLED_BY**, **DISPATCHES_ACTION**, **UPDATES_STATE**;
- **STATE_RERENDERS**, **NAVIGATES_TO**, **VALIDATES_FIELD**;
- **VISIBLE_WHEN**, **ENABLED_WHEN**, **ACCESSIBLE_AS**.

Agent có thể dùng layer này để truy từ bug “nút Save biến mất” tới condition, state, flag, backend operation và test UI. Framework adapter cần giữ lifecycle semantics; chỉ dựa vào JSX/template AST sẽ bỏ qua state/effect/data binding.

## L13. Deployment topology, runtime event và observability

### Bản chất

Code deployment tạo service/process/container/function instance trong một môi trường cụ thể. Runtime layer trả lời:

- implementation nào thực sự được deploy;
- call/message/query nào thực sự xảy ra;
- latency/error/resource profile ở đâu;
- source/build/config nào tương ứng với observation.

[OpenTelemetry](https://opentelemetry.io/docs/specs/otel/overview/) mô hình hóa trace bằng span, event và link; link có thể biểu diễn causal relation trong/cross trace. [Dapper](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/) là nền tảng production tracing quy mô lớn. OpenTelemetry còn chuẩn hóa [code attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/code/) như file, function, line/column, giúp map observation về source anchor — nhưng map bằng revision/build ID vẫn cần được bổ sung.

### Biểu diễn đề xuất

| Static/deployment | Runtime observation |
|---|---|
| Service, DeploymentUnit, ContainerImage, FunctionVersion | ServiceInstance, Process, Thread, RuntimeModule |
| Environment, Cluster, Namespace, Pod, Node | DeploymentObservation, HealthState |
| Config/Artifact/Revision mapping | Trace, Span, SpanEvent, LogEvent, MetricPoint, ProfileSample |
| Declared endpoint/channel/database | ObservedCall, ObservedMessage, ObservedQuery, Failure |

Quan hệ:

- **DEPLOYS_ARTIFACT**, **RUNS_REVISION**, **USES_CONFIG_SNAPSHOT**;
- **SPAN_EXECUTES_SYMBOL**, **OBSERVED_AT_ANCHOR**, **OBSERVED_CALL**;
- **PARENT_SPAN**, **LINKED_TO**, **SEND_CAUSES_RECEIVE**, **EMITS_LOG**;
- **OBSERVED_QUERY**, **OBSERVED_FLAG_EVALUATION**, **FAILED_AT**;
- **SAMPLED_UNDER_WORKLOAD**, **MEASURED_BY**, **AGGREGATES**.

### Không được suy diễn quá mức

- Trace có sampling và missing spans.
- Function name/file path runtime có thể mơ hồ sau minify, obfuscate hoặc optimization.
- Metric aggregate không chứng minh path cho một request cụ thể.
- Production observation có retention/privacy constraints.
- **OBSERVED_CALL** không được promote thành **MUST_CALL**; absence of observation không thành **NO_CALL**.

## L14. Test, specification, invariant, quality và security evidence

### Bản chất

Test không chỉ là một function gọi production code. Cần biểu diễn setup, fixture, input, oracle/assertion, expected behavior, environment, result và coverage. Code coverage trả lời “đã thực thi”; không trả lời “đã kiểm chứng đúng”. [LLVM source-based coverage](https://clang.llvm.org/docs/SourceBasedCodeCoverage.html) phân biệt function, region, branch và MC/DC coverage. [Mutation testing](https://pitest.org/quickstart/basic_concepts/) kiểm tra test có phát hiện thay đổi hành vi nhân tạo hay không.

### Biểu diễn đề xuất

- **TestSuite**, **TestCase**, **ParameterizedCase**, **Fixture**, **TestInput**;
- **Assertion**, **Oracle**, **ExpectedOutcome**, **Property**, **Invariant**;
- **TestRun**, **TestResult**, **CoverageObservation**, **Mutation**, **MutantResult**;
- **StaticRule**, **Finding**, **EvidencePath**, **CWE**, **Risk**, **Waiver**.

Quan hệ:

- **SET_UP_BY**, **USES_FIXTURE**, **EXECUTES**, **ASSERTS**, **VERIFIES**;
- **COVERS_REGION/BRANCH**, **KILLS_MUTANT**, **SURVIVES_MUTANT**;
- **DETECTS_FINDING**, **EVIDENCED_BY**, **VIOLATES_INVARIANT**;
- **REPRODUCES_ISSUE**, **REGRESSES_CHANGE**, **WAIVED_BY**.

### Phân biệt bốn loại evidence

| Evidence | Điều nó chứng minh | Điều nó không chứng minh |
|---|---|---|
| Static reachability | Path có thể tồn tại theo model | Path sẽ chạy ở production |
| Test execution | Path chạy trong test/run đó | Assertion có chất lượng |
| Assertion pass | Observed output phù hợp oracle | Requirement/oracle là đầy đủ |
| Production observation | Event đã xảy ra dưới workload | Mọi behavior khác không tồn tại |

Security/quality finding phải là node có rule version, analysis configuration, affected anchors, evidence path, severity và state triage. Không gắn “vulnerable=true” như property vĩnh viễn lên function.

## L15. Architecture, domain, requirement và design intent

### Bản chất

Đây là tầng giúp LLM hiểu “vì sao” thay vì chỉ “ở đâu/thế nào”:

- system, container/service, component, layer và boundary;
- domain concept, entity, value object, capability, use case;
- business rule, decision, invariant và compliance obligation;
- requirement, ADR, trade-off và intended dependency.

[ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html) xem architecture description qua stakeholder, concern, viewpoint và view. [Kruchten 4+1](https://www.cs.ubc.ca/~gregor/teaching/papers/4%2B1view-architecture.pdf) cũng nhấn mạnh nhiều concurrent views. [C4](https://c4model.com/diagrams) cung cấp các mức zoom system context, container, component và code. Những nguồn này cùng chỉ ra: không có một projection duy nhất phù hợp mọi câu hỏi.

### Biểu diễn đề xuất

- **SoftwareSystem**, **Actor**, **Container**, **Component**, **Layer**, **Boundary**;
- **Capability**, **UseCase**, **DomainConcept**, **DomainEntity**, **ValueObject**;
- **BusinessRule**, **Decision**, **Invariant**, **Requirement**, **Risk**, **Obligation**;
- **ArchitectureDecision**, **Alternative**, **Tradeoff**, **Constraint**, **Viewpoint**.

Quan hệ:

- **CONTAINS_COMPONENT**, **ALLOWED_TO_DEPEND_ON**, **FORBIDS_DEPENDENCY**;
- **IMPLEMENTS_CAPABILITY**, **REALIZES_REQUIREMENT**, **ENFORCES_RULE**;
- **REPRESENTS_CONCEPT**, **OWNS_DATA**, **CROSSES_BOUNDARY**;
- **DECIDED_BY**, **SUPERSEDES_DECISION**, **MOTIVATED_BY**;
- **VERIFIED_BY_TEST**, **OBSERVED_IN_TRACE**, **IMPLEMENTED_BY_SYMBOL**.

### Bottom-up và top-down phải gặp nhau

[Software Reflexion Models](https://dl.acm.org/doi/10.1145/222132.222136) so sánh high-level model dự kiến với source model và biểu diễn convergence/divergence. Đây là pattern tốt hơn việc LLM tự cluster code rồi gọi cluster là “architecture”.

Mỗi mapping architecture/domain → code cần:

- nguồn: human-approved doc, naming rule, trace hoặc LLM;
- mapping rule/version;
- support và contradiction evidence;
- trạng thái proposed, reviewed, approved, deprecated;
- scope revision/build/deployment.

Một LLM có thể đề xuất “PaymentService implements Payment capability”, nhưng chỉ được lưu như **CLAIMED_REALIZATION** cho tới khi được rule/evidence/human xác nhận. [DMN](https://www.omg.org/spec/DMN/1.5/About-DMN) có thể được dùng để import decision/business-rule model thay vì chỉ giữ prose.

## L16. Evolution, change intent, ownership và provenance

### Bản chất

Code chỉ có thể được hiểu đầy đủ trong lịch sử: ai đổi, đổi vì issue/requirement nào, review ra sao, release nào chứa change, symbol nào move/rename/split/merge. Ownership cũng có nhiều nghĩa: author, current maintainer, reviewer, operational owner, data owner.

[Software Heritage graph](https://docs.softwareheritage.org/devel/swh-export/graph/) liên kết content, directory, commit, release và snapshot. [W3C PROV-O](https://www.w3.org/TR/prov-o/) cung cấp Entity, Activity, Agent và các relation provenance có thể specialize theo domain.

### Biểu diễn đề xuất

- **Commit**, **ChangeSet**, **DiffHunk**, **PullRequest**, **Review**, **Issue**;
- **Release**, **Deprecation**, **MigrationEpisode**, **Refactoring**;
- **Person**, **Team**, **Role**, **OwnershipAssignment**;
- **ProvenanceActivity**, **ExtractorRun**, **DerivationRun**, **Approval**.

Quan hệ:

- **MODIFIES**, **INTRODUCES**, **REMOVES**, **MOVES**, **RENAMES**, **SPLITS**, **MERGES**;
- **FIXES_ISSUE**, **IMPLEMENTS_REQUIREMENT**, **REVIEWED_BY**, **RELEASED_IN**;
- **AUTHORED_BY**, **MAINTAINED_BY**, **OPERATED_BY**, **OWNS_DATA**;
- **WAS_DERIVED_FROM**, **WAS_GENERATED_BY**, **WAS_ATTRIBUTED_TO**.

### Temporal semantics

- Fact immutable theo revision; “current view” là projection.
- Tombstone giữ identity và reason khi symbol/file bị xóa.
- Edge có valid time và transaction/ingestion time nếu cần bitemporal audit.
- “Introduced bug” là derived claim cần causal evidence, không suy chỉ từ blame line.
- Dữ liệu con người/ownership phải có privacy, retention và access policy.

## L17. Derived knowledge, LLM claim và agent memory

### Bản chất

Agent cần summary, hypothesis, importance score, predicted owner, architecture cluster, likely intent, task state và plan. Đây là knowledge hữu ích nhưng có authority khác compiler/build/runtime fact.

[Oracle Poisoning](https://arxiv.org/abs/2605.09822) cho thấy một agent có thể suy luận nhất quán nhưng sai nếu graph oracle đã bị sửa. Vì vậy, derived/LLM layer cần thiết kế như untrusted-by-default assertion layer.

### Biểu diễn đề xuất

- **Claim**, **Summary**, **Hypothesis**, **Explanation**, **RiskAssessment**;
- **SemanticCluster**, **PredictedRelation**, **SuggestedMapping**;
- **Task**, **Goal**, **PlanStep**, **AgentObservation**, **PatchProposal**, **ValidationResult**.

Quan hệ:

- **SUPPORTED_BY**, **CONTRADICTED_BY**, **DERIVED_FROM**;
- **ABOUT_ENTITY**, **ANSWERS_QUESTION**, **PROPOSES_RELATION**;
- **CREATED_BY_MODEL**, **VERIFIED_BY**, **EXPIRES_AT**;
- **TASK_USES_EVIDENCE**, **PATCH_CHANGES**, **VALIDATED_BY**.

### Contract bắt buộc cho LLM claim

| Trường | Ý nghĩa |
|---|---|
| claim_type và normalized proposition | Điều đang được khẳng định |
| subject/object/context | Phạm vi cụ thể |
| evidence set | Anchor/fact/trace/doc hỗ trợ |
| counter-evidence set | Bằng chứng mâu thuẫn |
| model, prompt/template, tool trace | Reproducibility |
| confidence/calibration | Chỉ dùng nếu được đo |
| created_at, TTL, status | Freshness và lifecycle |
| verifier/approval | Ai hoặc rule nào xác nhận |
| access label | Ngăn leak qua summary |

LLM claim không được tạo edge canonical như **CALLS**, **IMPLEMENTS** hoặc **OWNS** trực tiếp. Nó tạo **ProposedAssertion**; promotion cần validator tương ứng.

---

## 4. Mô hình graph hợp nhất

### 4.1 Đơn vị cơ bản không phải triple trần

Một fact phần mềm cần ít nhất:

**Assertion = (subject, predicate, object, context, modality, provenance, validity).**

Trong đó:

- **context:** repository, revision, build variant, configuration, environment, workload/test run;
- **modality:** MUST, MAY, OBSERVED, CLAIMED, REFUTED, UNKNOWN;
- **provenance:** extractor/evidence/derivation/author;
- **validity:** revision interval hoặc observation time.

SPDX 3 mô hình **Relationship** như một grouping của assertion và các đặc tính riêng của quan hệ; [PROV-O](https://www.w3.org/TR/prov-o/) cho provenance. Hai pattern này ủng hộ việc reify quan hệ giàu ngữ cảnh.

### 4.2 Bảy họ node canonical

| Họ | Nội dung |
|---|---|
| Artifact | Repo, revision, file content/occurrence, anchor, build artifact |
| ProgramEntity | Symbol, type, syntax/action/value/memory entity |
| BehaviorEvent | Call site, branch, transition, data transfer, runtime span |
| Context | Build variant, config, environment, workload, execution run |
| Contract | API, schema, message, requirement, invariant, policy |
| Evidence | Source span, build/test/trace/analyzer/provenance activity |
| Claim | Derived relation, summary, intent, risk, agent memory |

### 4.3 Sáu họ relation

1. **Containment/identity:** contains, declares, occurs-in, version-of.
2. **Semantic/reference:** binds-to, has-type, overrides, may-target.
3. **Behavior/dependence:** control-flow, data-depends, happens-before.
4. **Construction/context:** builds, configures, deploys, activates.
5. **Traceability/intent:** realizes, verifies, motivated-by, owned-by.
6. **Evidence/derivation:** supported-by, observed-by, derived-from, contradicted-by.

Tên relation phải có chiều đọc được. Tránh một edge chung chung **RELATED_TO**.

### 4.4 Context lattice

Không tạo một bản copy graph khổng lồ cho mọi tổ hợp. Fact có scope tăng dần:

1. repository;
2. revision;
3. build variant/toolchain;
4. config/environment/tenant;
5. execution/test/workload;
6. time/event instance.

Một query lấy fact ở context hẹp có thể kế thừa fact từ context rộng nếu không bị override và semantics cho phép. Config/flag và runtime relation thường không được “nâng” ngược thành revision-global fact.

### 4.5 Authority không phải một thang điểm đơn

| Assertion class | Ví dụ | Cách đọc |
|---|---|---|
| Syntactic fact | node/span, containment | Chính xác theo parser/grammar version |
| Resolved semantic fact | binding/type/direct call | Chính xác trong compilation/index context |
| Static approximation | may-call, points-to, taint path | Sound/unsound và precision phụ thuộc analyzer config |
| Build fact | action/input/output/resolved dep | Chính xác cho build run/variant |
| Runtime observation | observed call/span/query | Chính xác cho observation nếu instrumentation đúng; coverage partial |
| Test evidence | assertion/coverage/result | Chứng minh run cụ thể, phụ thuộc oracle |
| Human assertion | ADR/owner/requirement map | Authority theo role/approval, có thể stale |
| LLM claim | intent/summary/predicted map | Giả thuyết cho tới khi verified |

Một runtime observation không “cao hơn” static fact theo mọi nghĩa; chúng trả lời câu hỏi khác nhau.

### 4.6 Data contract tham chiếu

~~~yaml
assertion:
  id: assertion-content-hash
  subject: symbol-or-event-id
  predicate: MAY_TARGET
  object: candidate-symbol-id

  context:
    repository: stable-repo-id
    source_revision: immutable-revision
    build_variant: linux-x86_64-release
    configuration: config-snapshot-id-or-null
    environment: staging-or-null
    workload_run: trace-or-test-run-id-or-null

  semantics:
    modality: MAY
    closed_world: false
    precision_scope: context-sensitive

  evidence:
    anchors: [anchor-id]
    extractor_run: callgraph-run-id
    extractor_version: analyzer-version
    analysis_config: analysis-config-hash
    derived_from: [binding-id, points-to-id]

  validity:
    valid_from_revision: commit-id
    valid_to_revision: null
    observed_at: null

  governance:
    access_label: repository-internal
    signature: ingestion-signature
~~~

### 4.7 Capability contract và negative knowledge

Mỗi graph snapshot/view phải công bố:

~~~yaml
capabilities:
  syntax: complete_for_parsed_files
  bindings: complete_for_compiled_targets
  dynamic_dispatch: sound_over_approximation
  reflection: partial
  generated_code: build-variant-specific
  runtime_calls: sampled_workload_only
  config: known-keys-partial-values
  data_lineage: table-complete-column-partial
  architecture: human-approved-subset
  freshness_lag_seconds: 12
~~~

Chỉ được suy **NO_RELATION** khi:

1. predicate có closed-world semantics trong context;
2. extractor coverage bao trùm subject/object;
3. graph revision khớp source/build/config;
4. query không bị truncate/budget;
5. không có unresolved dynamic feature liên quan.

---

## 5. Nên lấy gì và không nên lấy gì từ các representation hiện có

| Representation | Nên lấy | Không nên nhầm |
|---|---|---|
| Tree-sitter CST | Lossless anchors, error recovery, incremental parse, broad languages | CST không resolve symbol/type/call/data-flow |
| AST/compiler IR | Language semantics và lowering chính xác hơn | IR có thể mất source-level intent và phụ thuộc build/optimization |
| Kythe | Anchor ↔ semantic node, definition/reference/call-site pattern | Schema navigation không bao phủ behavior/runtime/intent |
| SCIP | Stable symbol syntax, occurrence, relationship và enclosing range | Protocol index không phải whole-software graph |
| Glean | Typed facts, language-specific schema + common views, revision DB, derived predicates | Fact platform không tự làm program analysis hay runtime correlation |
| LSP | Interface tương tác tốt cho definition/reference/type/call hierarchy | LSP là service protocol, state có thể partial và không phải durable provenance store |
| CPG/Joern | AST + CFG + DDG/CDG, finding/evidence, graph query cho analysis | Fine-grained CPG toàn repo rất lớn; static graph vẫn là approximation |
| CodeQL | Multi-level semantic libraries, data-flow/taint và framework modeling | Query result phụ thuộc database build và library model; không phải live runtime truth |
| KDM | Coverage metamodel cho source/code/action/platform/UI/event/data/build/conceptual | Quá nặng làm direct agent surface; thiếu nhiều requirement hiện đại về uncertainty/LLM |
| OpenAPI/AsyncAPI/Arazzo | Machine-readable boundary contract và workflow | Contract không bảo đảm implementation/runtime conformance |
| SPDX/CycloneDX | Package/artifact/build/security/supply-chain identity | SBOM không thay call/data-flow/architecture graph |
| OpenTelemetry | Observed span/event/link, standardized attributes | Sampling và instrumentation gap; trace không phải exhaustive behavior |
| OpenLineage | Job/run/dataset và static-vs-runtime lineage | Không tự nối chính xác tới symbol/column nếu thiếu source mapping |
| C4/42010/Reflexion Model | Viewpoint theo concern, multi-level architecture, intended-vs-implemented divergence | Architecture view không phải compiler fact và không nên auto-promote |
| RepoGraph/LocAgent | Lightweight task graph và constrained navigation cho LLM | Hiệu quả retrieval không chứng minh semantic completeness |
| CodexGraph | Graph-as-tool và natural-language-to-query | Raw LLM-generated query có thể invalid, sâu, dài hoặc vượt quyền |
| RepoDistill | Context budget là biến thiết kế riêng | Nén không thể phục hồi evidence đã bị retrieval bỏ sót |

### 5.1 Synthesis

Không representation nào ở trên thất bại vì “thiếu mọi thứ”; mỗi loại giải một concern khác nhau. Sai lầm phổ biến là chọn một representation rồi coi phần còn lại là enrichment:

- AST-centric system coi build/runtime/domain là metadata phụ;
- knowledge-ontology system coi compiler semantics là string relation;
- trace-centric system coi observed path là system behavior;
- agent-centric repo graph coi relation phục vụ localization là whole-program meaning.

Thiết kế đúng là **federate semantics qua stable identity, context và evidence contract**, sau đó materialize view theo task.

---

## 6. Agent/LLM nên tiêu thụ graph thế nào

### 6.1 Không đưa “toàn bộ graph” vào prompt

[RepoGraph](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf) và [LocAgent](https://aclanthology.org/2025.acl-long.426/) cho thấy graph-guided retrieval/navigation có ích. Nhưng [RepoDistill](https://aclanthology.org/2026.findings-acl.217/) cho thấy context truy hồi vẫn có redundancy và context quá dài có thể làm giảm hiệu quả; [CodexGraph](https://aclanthology.org/2025.naacl-long.7/) ghi nhận missing edge/deep query và năng lực query của model là failure source.

Vì vậy, graph phục vụ agent nên có hai tầng:

1. **rich fact base** cho truy vấn có kiểm soát;
2. **task view** nhỏ, có typed relations, evidence paths và expandable summaries.

### 6.2 Mười task view chuẩn

| View | Câu hỏi điển hình | Layer chính | Output dành cho agent | Guardrail |
|---|---|---|---|---|
| Symbol/navigation | “Định nghĩa và các reference của X ở đâu?” | L0–L4 | Symbol candidates, definitions, refs, signatures | Không tự chọn khi overload/ambiguity |
| Explain entity | “Hàm này làm gì và phụ thuộc vào gì?” | L1–L6, L14–L16 | Summary + direct evidence + calls/data/state/tests/intent | Summary là claim; cite anchors |
| Execution slice | “Request này đi qua path nào?” | L4–L7, L9–L13 | Path có guards, calls, exceptions, messages | Tách MAY path và OBSERVED path |
| Data/security lineage | “PII từ input có tới log/DB không?” | L6, L9–L11, L13–L15 | Field-sensitive flow, transforms, sanitizers, sinks | Kèm analysis model/coverage |
| Change impact | “Sửa symbol/schema này ảnh hưởng gì?” | L3–L16 | Direct/transitive dependents, builds, APIs, tests, owners | Rank theo evidence, không traversal vô hạn |
| Test selection | “Cần chạy test nào?” | L4–L8, L14, L16 | Static affected tests + observed coverage + risk | Coverage observation có run context |
| Incident/root cause | “Trace lỗi này map về code/config nào?” | L0, L4–L7, L9, L13–L16 | Trace slice → artifact/revision → code/flag/data/change | Không suy từ function name mơ hồ |
| Architecture conformance | “Có dependency phá layer không?” | L4, L8, L10–L16 | Intended rule, implemented/observed edges, divergence | Kiến trúc cần approved mapping |
| API/dependency migration | “Upgrade này cần đổi gì?” | L3–L6, L8–L11, L14, L16 | Usage sites, contract diff, data/build/test impact | Resolve exact versions/variants |
| Generation/refactor | “Tạo/sửa code mà vẫn giữ behavior” | Tất cả layer liên quan | Constraints, invariants, edit sites, validation plan | Graph guides; compiler/build/test phê chuẩn |

### 6.3 View không chỉ là subgraph

Một agent view nên chứa bốn phần:

1. **Topology:** node/edge phù hợp với task.
2. **Evidence bundle:** source spans, trace/test/build IDs, docs.
3. **Coverage envelope:** layer nào complete/partial/unavailable.
4. **Reasoning affordance:** path explanation, rank reason, alternative candidates và next-expand actions.

Ví dụ output execution slice:

~~~json
{
  "question_context": {
    "revision": "abc123",
    "build_variant": "prod-linux",
    "environment": "eu-prod",
    "workload": "trace-7"
  },
  "paths": [
    {
      "modality": "OBSERVED",
      "steps": ["endpoint-1", "handler-8", "flag-eval-3", "query-2"],
      "evidence": ["span-1", "span-2", "anchor-18"]
    },
    {
      "modality": "MAY",
      "steps": ["handler-8", "fallback-4"],
      "evidence": ["cfg-edge-91", "config-rule-6"]
    }
  ],
  "coverage": {
    "runtime": "sampled-trace",
    "reflection": "partial",
    "column_lineage": "complete-for-resolved-sql"
  },
  "truncated": false
}
~~~

### 6.4 Typed tool surface tốt hơn raw graph query làm mặc định

| Tool | Trả lời | Layer |
|---|---|---|
| resolve_symbol | Symbol candidates và ambiguity | L0–L4 |
| get_entity_card | Signature, docs, relations, tests, owners, claims | L1–L4, L14–L17 |
| trace_execution | Static/observed path có guard/evidence | L4–L7, L9–L13 |
| trace_data | Def-use/data lineage/taint theo field/label | L6, L10–L13 |
| impact_of_change | Symbol/build/API/data/test/deployment impact | L3–L16 |
| tests_for_change | Test candidates, coverage, mutation/risk | L4–L8, L14 |
| architecture_diff | Intended vs implemented vs observed | L4, L8, L10–L16 |
| graph_diff | Node/edge/claim diff giữa revision/context | L0–L17 |
| get_evidence | Anchor/run/extractor/provenance của assertion | mọi layer |
| get_capabilities | Coverage, freshness, unsupported features | mọi layer |
| validate_patch | Parse/type/build/test/analyzer/graph delta | closed loop |

Raw Cypher/GQL/SPARQL có thể giữ như read-only expert fallback, nhưng:

- có schema allowlist;
- max depth/rows/time/token;
- parameterization và RBAC;
- không cho query vượt access label;
- luôn trả query plan, truncation và revision.

### 6.5 Quy trình reasoning của agent

~~~mermaid
flowchart TD
    Q["Question or change goal"] --> A["Resolve task, context and anchors"]
    A --> V["Choose typed graph view"]
    V --> E["Retrieve evidence paths and gaps"]
    E --> R["Reason with alternatives and uncertainty"]
    R --> X["Inspect live source or edit overlay"]
    X --> C["Compiler/build/test/runtime validation"]
    C --> D["Publish graph delta and evidence"]
~~~

Graph không thay thế source inspection hoặc validation. Nó tổ chức search/reasoning, chỉ ra constraint và tạo auditable evidence chain.

---

## 7. Ví dụ xuyên suốt: biểu diễn một use case đặt hàng

Giả sử hệ thống có **POST /orders**. Người dùng báo: “Một số order được ghi DB mà không chạy fraud check.” Nếu graph chỉ có handler **CALLS** service, agent khó thấy bản chất lỗi. Graph đa tầng biểu diễn:

| Lớp | Node/fact trong ví dụ | Quan hệ |
|---|---|---|
| L0 | revision R, file occurrence, source anchors | anchor located in handler file at R |
| L1 | doc/API prose “all orders are screened” | DocumentClaim about Requirement FR-17 |
| L2 | route decorator và generated client | RouteSyntax; client GENERATED_FROM OpenAPI |
| L3 | OrderHandler, FraudChecker interface, implementations | occurrence BINDS_TO symbol; implementation SATISFIES interface |
| L4 | call site check(order), repository.save(order) | handler CONTAINS_CALL; MAY_TARGET checker implementations |
| L5 | branch if fraud_check_v2; exception/fallback path | Branch GUARDED_BY flag; false path reaches save |
| L6 | request.customer_id → risk input; result → decision | FLOWS_TO, DATA_DEPENDS_ON, sanitized/validated fields |
| L7 | async fraud task và timeout race | SPAWNS task; timeout MAY_RUN_CONCURRENTLY; join missing on one path |
| L8 | prod artifact built with optional fraud module | BuildVariant SELECTS module; artifact DEPLOYS revision R |
| L9 | flag targeting rule cho tenant/region | FlagEvaluation OBSERVED false for affected tenant |
| L10 | OpenAPI operation, auth, error response; Fraud RPC | handler IMPLEMENTS operation; service CALLS RPC |
| L11 | orders table/status/fraud_score; transaction | query WRITES columns; transaction COMMIT after branch |
| L12 | checkout screen và Submit action | action CALLS POST /orders; error state handling |
| L13 | trace/span shows DB call without fraud RPC | ObservedCall handler→DB; missing span only weak negative evidence |
| L14 | test covers flag=true only; invariant/test gap | test COVERS branch true; no assertion for flag=false invariant |
| L15 | FR-17 and rule “persist only after screening” | handler/service expected to ENFORCE rule |
| L16 | PR changed timeout fallback and flag rule | ChangeSet MODIFIES branch; FIXES issue or possibly INTRODUCES claim |
| L17 | agent hypothesis: fallback bypasses invariant | Claim SUPPORTED_BY CFG + flag eval + trace + test gap |

### 7.1 Evidence path agent cần

~~~mermaid
flowchart TD
    T["Production trace"] --> F["Observed flag evaluation: false"]
    F --> B["CFG false/fallback branch"]
    B --> Q["Observed DB write"]
    Q --> I["Business invariant FR-17"]
    I --> G["Missing test assertion"]
~~~

Từ đó agent có thể nói:

- **Observed:** trong trace cụ thể, flag resolve false và DB write xảy ra.
- **Static MAY:** CFG có path từ fallback tới save mà không qua fraud result.
- **Contract/intent:** FR-17 yêu cầu mọi order được screen.
- **Validation gap:** test suite không kiểm tra invariant ở flag=false/timeout.
- **Unknown:** instrumentation gap có thể làm thiếu fraud span; cần kiểm tra RPC logs hoặc replay test.

Đây là “understanding” tốt hơn một answer chắc chắn giả tạo.

### 7.2 Patch plan dựa trên graph

1. Sửa state/branch để **save** phụ thuộc explicit screening outcome hoặc policy-approved failure state.
2. Thêm test property/invariant cho flag true/false, timeout và checker error.
3. Chạy impacted build target, unit/integration tests và query/data migration checks.
4. Tạo workspace overlay graph; xác nhận path bypass biến mất trong CFG.
5. Chạy trace/replay; liên kết observed spans vào overlay artifact.
6. Chỉ sau validation mới promote agent hypothesis thành verified resolution.

---

## 8. Pipeline extraction đa tầng

### 8.1 Pipeline tổng thể

~~~mermaid
flowchart TD
    S["Source, VCS and manifests"] --> P["Parse and anchors"]
    P --> M["Semantic index and language facts"]
    M --> A["Program analyses"]
    A --> W["Build, config, contracts and data adapters"]
    W --> O["Tests, deployment and runtime observations"]
    O --> K["Architecture, domain and claim layer"]
    K --> V["Validate and publish contextual snapshot"]
~~~

### 8.2 Stage 0 — Snapshot và identity

Input:

- repository/commit/worktree;
- submodules/dependency lockfiles;
- build configuration manifest;
- access labels.

Output:

- immutable revision/workspace overlay;
- file contents/occurrences/anchors;
- content hashes và ingestion provenance.

Invariant:

- không index “current path” mà thiếu revision;
- không publish partial snapshot như complete;
- source và graph ACL phải tương thích.

### 8.3 Stage 1 — Lossless syntax

- Tree-sitter parse tất cả file được hỗ trợ;
- giữ parse diagnostics và error nodes;
- tạo CST anchors, declarations sơ bộ, comments/docs;
- nhận diện generated/vendored/test/config/docs classification;
- incremental reparse theo changed ranges.

Output layer L1–L2 có thể sẵn sàng sớm để basic navigation, nhưng capability phải nói semantic binding chưa có.

### 8.4 Stage 2 — Semantic index

- compiler/SCIP/LSP extractor theo compilation unit;
- symbol/occurrence/scope/type/signature;
- import/export, override/implements, direct calls;
- framework resolver cho route/DI/ORM/plugin;
- map generated/expanded entities về source.

Mỗi extractor nhận đúng build arguments/dependencies. [Kythe indexer model](https://kythe.io/docs/schema/writing-an-indexer.html) đóng gói program, dependency và compiler arguments — một lesson quan trọng để tránh parse file cô lập.

### 8.5 Stage 3 — Program analysis có chọn lọc

- CFG/exception flow cho callables liên quan;
- SSA/def-use/PDG summaries;
- points-to/call graph theo sensitivity phù hợp;
- taint/data-flow theo security/domain model;
- concurrency/synchronization graph.

Không nhất thiết materialize full CPG cho mọi file. Có ba mức:

1. summaries toàn repo;
2. fine-grained graph cho hot/security-critical modules;
3. on-demand analysis cho task slice.

### 8.6 Stage 4 — Whole-system adapters

- build system: target/config/action/artifact/toolchain;
- dependency/SBOM/attestation;
- config/flag/schema/IaC;
- OpenAPI/AsyncAPI/protobuf/Arazzo;
- SQL/DDL/ORM/migration/data lineage;
- UI route/state/event mappings.

Adapter tạo conformance assertions thay vì merge spec/code/runtime.

### 8.7 Stage 5 — Test, deployment và runtime

- test discovery, fixture/assertion, coverage/mutation/result;
- deployment manifests và artifact digests;
- OpenTelemetry trace/log/metric/profile;
- flag evaluations, runtime queries/messages;
- source-map correlation bằng artifact/revision/build ID.

Runtime event có retention/sampling/privacy policy riêng; graph core có thể giữ aggregate/edge summary và pointer tới telemetry store.

### 8.8 Stage 6 — Intent, architecture và derived claims

- ingest approved ADR/requirement/domain model;
- import C4/architecture-as-code/DMN nếu có;
- mapping rule + human review;
- LLM đề xuất summary/concept/mapping;
- verifier tìm support/contradiction;
- TTL và invalidation khi evidence đổi.

### 8.9 Stage 7 — Validation và transactional publish

Validation gates:

- schema/type và dangling reference;
- source span/hash;
- duplicate/collision/identity;
- revision/build/config coherence;
- provenance/signature;
- access-control non-escalation;
- graph delta sanity và capability computation.

Publish atomically:

- immutable facts snapshot;
- derived views/version;
- vector index version;
- freshness/capability metadata;
- tombstones và invalidation queue.

### 8.10 Incremental invalidation

| Change | Tối thiểu phải invalidate/recompute |
|---|---|
| Body-only local edit | CST/AST, local CFG/data-flow, callers summary, tests/claims liên quan |
| Public signature/type | References, overload/binding, call sites, API/build dependents |
| Import/build file | Compilation closure, targets/actions/artifacts, generated code |
| Config/flag rule | Guard/context views, affected runtime/config assertions |
| API/schema | Client/server mappings, workflows, compatibility, tests |
| DB migration | ORM/query/column lineage, data contracts, rollout plan |
| Dependency version | resolved API/types, build artifacts, SBOM/security, behavior claims |
| Architecture/requirement doc | mappings/conformance/LLM summaries, không cần rewrite static facts |
| New trace/test run | observed/coverage summaries; static graph giữ nguyên trừ dynamic discovery |

Incrementality phải theo semantic dependency closure, không chỉ changed file. Glean mô tả mục tiêu update theo changes nhưng fan-out thực tế vẫn quyết định chi phí; graph phải đo invalidation fan-out và freshness.

---

## 9. Kiến trúc lưu trữ và triển khai thực dụng

### 9.1 Một logical graph, nhiều physical stores

~~~mermaid
flowchart TD
    I["Ingestion and extractors"] --> F["Versioned fact service"]
    F --> G["Property/fact graph"]
    F --> B["Blob and artifact store"]
    F --> T["Telemetry/analysis stores"]
    F --> X["Lexical and vector indexes"]
    G --> Q["Typed query and view planner"]
    B --> Q
    T --> Q
    X --> Q
    Q --> M["MCP/agent tools"]
~~~

Vai trò:

- **Property/fact graph:** identity, topology, contextual assertions, provenance, materialized views.
- **Blob/artifact store:** raw source, CST/IR dumps, build logs, SBOM, trace chunks.
- **Analysis store:** fine-grained CPG/SSA/data-flow hoặc Datalog facts.
- **Telemetry store:** high-volume spans/logs/metrics/profiles.
- **Lexical/vector index:** tìm anchor/doc/claim bằng natural language; trả node IDs.
- **Query/view planner:** join theo stable IDs/context, enforce budget/RBAC/capability.

### 9.2 Áp dụng vào stack Tree-sitter + KuzuDB + FAISS + FastAPI/MCP

Một lộ trình phù hợp với stack hiện có:

| Thành phần | Trách nhiệm nên giữ | Không nên ép vào |
|---|---|---|
| Tree-sitter | L1–L2, anchors, syntax summaries, changed ranges | Binding/type/call truth |
| Language adapters | SCIP/LSP/compiler facts L3–L4 | Cross-language ontology chung quá sớm |
| KuzuDB | Core identity/symbol/context/assertion graph; task projections | Mọi token/AST instruction/trace event thô |
| Optional CPG engine | L5–L7 fine-grained/on-demand | Default neighborhood cho mọi query |
| FAISS | Semantic retrieval của docs, summaries, issue/requirement và code chunks | Source of truth cho relation |
| FastAPI ingestion/query | Snapshot lifecycle, capability, typed services, RBAC | Cho client bypass context/provenance |
| MCP tools | Task views, evidence, graph diff, impact, validation | Raw unrestricted Cypher làm default |

### 9.3 Core schema tối thiểu trong KuzuDB

**Core nodes:**

- Repo, Revision, FileContent, FileOccurrence, Anchor;
- Symbol, Type, Occurrence, CallSite;
- Context, BuildVariant, ConfigKey, Artifact;
- Contract, TestCase, RuntimeObservation;
- Assertion, Evidence, Claim, Activity.

**Core direct edges** chỉ dùng cho relation context-free hoặc đã scope bởi node version:

- revision containment;
- occurrence→symbol binding;
- symbol→anchor definition;
- symbol containment/type;
- evidence/derivation links.

**Reified Assertion** dùng cho:

- may/must call targets;
- data-flow/alias;
- config-dependent relation;
- build/deployment;
- architecture/domain mapping;
- observed runtime relation;
- ownership và LLM claim.

### 9.4 Không lưu full AST mặc định

Đề xuất:

- Kuzu giữ named semantic nodes và source anchors;
- compressed CST/blob giữ ngoài graph;
- AST/CFG detail được materialize cho changed/hot/task slice;
- summary edge có derivation pointer về fine-grained evidence;
- TTL/LRU cho on-demand analysis cache, nhưng evidence snapshot có thể tái tạo.

Điều này giảm degree/storage mà vẫn giữ khả năng drill-down.

### 9.5 Stable ID strategy

| Entity | ID đề xuất |
|---|---|
| FileContent | content hash |
| FileOccurrence | repo + revision + normalized path |
| Anchor | file occurrence + byte range + local content hash |
| SymbolVersion | repo + revision + language + canonical symbol key |
| Cross-revision lineage | separate continuity assertion |
| BuildVariant | target + normalized options/toolchain/dependency lock hash |
| Artifact | digest + artifact kind |
| Runtime instance/event | trace/run-native ID + tenant/access scope |
| Claim | normalized proposition + context + producer run hash |

Không dùng filename + simple name làm symbol ID.

---

## 10. Roadmap xây graph mà không over-engineer

Không nên triển khai 18 layer với cùng độ chi tiết ngay từ đầu. Cần xây **semantic spine bắt buộc**, sau đó thêm view theo tác vụ có giá trị.

### Phase A — Versioned semantic spine

**Layer:** L0–L4, phần cốt lõi L8, L14, L16–L17.

**Phải có:**

- revision/file occurrence/source anchor;
- symbol/occurrence/scope/type/signature;
- containment/import/reference/direct call + may-target;
- build target/variant/dependency tối thiểu;
- test discovery;
- provenance/capability;
- fact/claim separation.

**Agent làm được:**

- navigation và explain entity có evidence;
- cross-file localization;
- basic impact/test selection;
- graph diff theo revision;
- không nhầm heuristic/LLM summary là fact.

**Definition of done:** binding/call precision-recall được đo trên fixture; stale/freshness và unsupported feature hiển thị trong mọi tool response.

### Phase B — On-demand behavioral semantics

**Layer:** L5–L7.

Ưu tiên:

1. CFG + exception flow;
2. def-use/SSA và field-sensitive data flow;
3. call/points-to summaries;
4. concurrency/happens-before cho module cần thiết.

Chạy fine-grained analysis cho task slice hoặc security-critical area trước. Materialize summary toàn repo; không full-expand mọi expression.

**Agent làm được:**

- execution/data slice;
- bug/security reasoning tốt hơn;
- kiểm tra bypass path, resource lifecycle và propagation;
- refactor constraint ở mức behavior.

### Phase C — Whole-system graph

**Layer:** L8–L13.

Thứ tự thường mang lại giá trị:

1. build variant + artifacts;
2. OpenAPI/RPC/event contract;
3. config/feature flag;
4. DB/schema/query/data lineage;
5. deployment/runtime correlation;
6. UI/state model theo nhu cầu.

**Agent làm được:**

- change impact qua boundary;
- API/dependency/schema migration;
- incident-to-code correlation;
- config/build-specific explanation;
- end-to-end use-case reasoning.

### Phase D — Validation, architecture và domain

**Layer:** L14–L17 hoàn chỉnh.

- test assertion/oracle/invariant, coverage và mutation;
- architecture-as-code/ADR/requirements;
- reflexion/conformance view;
- ownership/change intent/provenance;
- LLM claim lifecycle, verification và TTL.

**Agent làm được:**

- hiểu “vì sao” và constraint tổ chức/nghiệp vụ;
- nhận ra divergence giữa intended, implemented và observed;
- lập validation plan và giải thích quyết định.

### Phase E — Closed-loop agent

1. Query graph ở exact base revision.
2. Tạo workspace overlay và patch.
3. Reparse/re-resolve changed semantic closure.
4. Chạy build/test/analyzer/replay.
5. So sánh expected graph delta với actual delta.
6. Chỉ publish claim/summary mới khi evidence hoàn tất.

### 10.1 Ma trận ưu tiên theo sản phẩm

| Tác vụ sản phẩm | Layer bắt buộc | Layer tăng giá trị mạnh |
|---|---|---|
| Code search/navigation | L0–L4 | L16–L17 |
| Bug localization/repair | L0–L6, L14, L16 | L7, L9, L13, L15 |
| Security analysis | L0–L8, L10–L14 | L9, L15–L17 |
| Modernization/refactor | L0–L8, L10, L14–L16 | L9, L11–L13 |
| Incident response | L0, L3–L7, L9–L16 | L8, L17 |
| Architecture understanding | L0, L3–L5, L8, L10–L17 | L6–L7, L9 |
| Repository generation | L0–L6, L8, L10, L14–L17 | L7, L9, L11–L13 |

---

## 11. Cách đánh giá graph có thực sự “biểu diễn được phần mềm”

### 11.1 Không dùng downstream score làm proxy duy nhất

Agent sửa được nhiều task hơn có thể do model, prompt, search policy hoặc test harness, không chứng minh graph đúng. Evaluation cần bốn tầng độc lập:

1. **Representation correctness** — node/edge/assertion có đúng không?
2. **View/retrieval quality** — task view có lấy đủ evidence đúng budget không?
3. **Agent outcome** — answer/patch có đúng và an toàn không?
4. **Operational integrity** — freshness, cost, provenance, RBAC và poisoning resistance.

### 11.2 Metrics theo layer

| Layer | Metric tối thiểu |
|---|---|
| L0 | identity collision, anchor exactness, revision mismatch, rename lineage precision |
| L1–L2 | parse coverage, source round-trip fidelity, source-map accuracy, error-file coverage |
| L3 | symbol binding/type/signature precision-recall; ambiguity calibration |
| L4 | call/reference/override target precision-recall; direct vs dynamic coverage |
| L5 | CFG edge/exception edge precision-recall; path/guard equivalence trên fixture |
| L6 | def-use/alias/points-to/data-flow precision-recall; source-to-sink path validity |
| L7 | spawn/join/synchronization coverage; happens-before/race truth trên litmus tests |
| L8 | configured-target/action/artifact/dependency match với build system |
| L9 | flag/config resolution match theo context; unknown/secret handling |
| L10 | declared–implemented–observed API/message conformance và version drift |
| L11 | query resolution; table/column lineage precision-recall; migration mapping |
| L12 | route/component/event/state transition coverage |
| L13 | artifact→revision và span→symbol link rate; sampling/missingness report |
| L14 | test→assertion/coverage mapping; flaky/oracle/mutation evidence |
| L15 | approved mapping coverage; architecture convergence/divergence correctness |
| L16 | graph-diff/rename/move/change-intent/provenance correctness |
| L17 | evidence coverage, contradiction detection, claim calibration, TTL invalidation |

### 11.3 Metrics cho agent view

- **Evidence recall@budget:** bao nhiêu evidence bắt buộc xuất hiện trong token/row budget?
- **Path precision:** evidence path có thật sự nối các semantic steps cần thiết?
- **Context correctness:** revision/build/config/workload có đúng không?
- **Modality correctness:** agent có phân biệt MUST/MAY/OBSERVED/CLAIMED?
- **Negative-claim safety:** tỷ lệ agent kết luận “không có” khi coverage partial.
- **Ambiguity preservation:** candidate hợp lệ có bị hệ thống tự loại?
- **Serialization loss:** quan hệ/guard/provenance nào bị mất khi chuyển graph sang context?
- **Expansion efficiency:** số tool calls/token để đạt evidence sufficiency.

### 11.4 Metrics downstream

- localization/answer/patch correctness;
- build/test/static analysis success;
- regression và invariant preservation;
- number of unnecessary edits;
- time/cost/token/tool calls;
- evidence citation accuracy;
- human review acceptance;
- unsafe action/false certainty rate.

[Code Graph Model, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/178ae4ba29022eb7bf509c2e27bc8ab8-Paper-Conference.pdf) cho thấy nhiều output có thể executable nhưng vẫn không giải quyết issue; vì vậy “compiles” không phải final correctness.

### 11.5 Metrics vận hành và governance

- indexing/update latency p50/p95/p99;
- invalidation fan-out và stale-edge rate;
- storage/edges per LOC theo layer;
- query timeout/truncation/high-degree hub rate;
- provenance completeness/signature verification;
- access-control leak test;
- poisoning mutation detection;
- reproducibility theo extractor/model/config version;
- restore/audit của graph snapshot.

### 11.6 Benchmark fixture bắt buộc

Corpus nội bộ phải chứa các case cố ý khó:

- overload, generics, mixin/trait, inheritance diamond;
- function pointer/closure/callback/dynamic dispatch;
- reflection/eval/plugin/dependency injection;
- macro/template/desugaring/generated code;
- conditional compilation và multi-target build;
- feature flag theo tenant/region/time;
- dynamic SQL, ORM, migration, trigger;
- exception/finally/resource lifecycle;
- coroutine/thread/lock/atomic/message ordering/race;
- HTTP/RPC/Kafka/webhook và retry/idempotency;
- UI state/effect/navigation;
- multiple valid revisions, rename/move/split/merge;
- stale documentation và conflicting architecture claim;
- partial traces, missing instrumentation, flaky tests;
- graph poisoning, ACL boundary và malicious LLM claim.

Mỗi fixture cần gold facts theo context, không chỉ một gold patch location.

### 11.7 Acceptance gate cho production

Một layer chỉ được đánh dấu **available** khi:

1. schema và semantics được version hóa;
2. extractor capability/coverage được công bố;
3. accuracy có benchmark representative;
4. evidence/provenance có thể truy ngược;
5. incremental invalidation có test;
6. ACL/privacy/retention được áp dụng;
7. query view có budget/truncation;
8. fallback và unknown behavior rõ ràng.

---

## 12. Anti-patterns cần tránh

1. **AST = meaning.** AST không giải quyết binding, dynamic behavior, build và intent.
2. **One timeless graph.** Merge facts từ nhiều revision/build/config tạo một phần mềm không bao giờ tồn tại.
3. **Name-based identity.** Simple name/path không đủ cho overload, scope, rename và content reuse.
4. **Binary edge cho relation n-ary.** Caller→callee làm mất call site, guard, dispatch, build và evidence.
5. **MAY edge được trình bày như fact chắc chắn.**
6. **Runtime observation được coi là exhaustive.**
7. **No edge = no dependency.** Sai khi reflection/coverage/query budget partial.
8. **Spec, code và runtime bị merge thành một node “API truth”.**
9. **Comment/README/ADR được ingest như compiler fact.**
10. **LLM summary overwrite source-derived relation.**
11. **Vector similarity được dùng thay symbol binding/data-flow.**
12. **Full graph neighborhood bị flatten vào prompt.**
13. **Mọi AST/CFG/trace event được nhồi vào một graph DB.**
14. **Generated code không có origin/source map.**
15. **Feature flag/config/environment bị coi là metadata phụ.**
16. **Dependency chỉ lấy từ manifest, không lấy resolved build/artifact.**
17. **Coverage được diễn giải thành correctness.**
18. **Architecture tự động cluster rồi gọi là ground truth.**
19. **Stable ID giả qua revision nhưng không có continuity evidence.**
20. **Agent có quyền ghi canonical fact trực tiếp.**
21. **Graph query không có revision/RBAC/budget/truncation flag.**
22. **Secret value hoặc PII runtime được ingest không kiểm soát.**

---

## 13. Các vấn đề nghiên cứu còn mở

### 13.1 “Universal representation” thực ra nên là universal evidence contract

Không thể có một schema chi tiết giống nhau cho mọi ngôn ngữ/framework. Câu hỏi nghiên cứu tốt hơn:

- tập primitive cross-language nhỏ nhất là gì;
- cách giữ lossless link về language-specific facts;
- cách version schema và derived view;
- cách chứng minh adapter không làm mất semantics quan trọng.

### 13.2 Configuration-space semantics

Một repo có thể có hàng triệu build/config/flag combinations. Cần:

- symbolic condition graph;
- representative context selection;
- lazy materialization;
- equivalence classes của variants;
- đo coverage của production contexts.

### 13.3 Static–dynamic fusion không làm mất modality

Cần thuật toán kết hợp static candidate và runtime observations để:

- tăng ranking/precision;
- phát hiện missing static model/framework adapter;
- không xóa unobserved nhưng possible edge;
- định lượng instrumentation/sampling bias.

### 13.4 Semantic change và graph diff

Text diff không đủ. Cần nhận ra:

- behavior-preserving refactor;
- changed guard/data dependency/effect;
- public/API/schema/invariant break;
- move/rename/split/merge;
- build/config-specific change.

### 13.5 Architecture/domain grounding

Cần benchmark mapping requirement/capability/rule → code/test/runtime, đo:

- support/contradiction;
- human agreement;
- drift theo revision;
- LLM claim calibration;
- task usefulness mà không biến inference thành truth.

### 13.6 Agent–graph interface

Câu hỏi mở:

- task view nào tối ưu cho từng repair/generation/security task;
- khi nào traversal, semantic retrieval, Datalog/CPG hoặc runtime query tốt hơn;
- evidence sufficiency được dừng thế nào;
- graph serialization nào giữ topology mà không vượt context;
- agent có nhận biết coverage gap và hỏi/validate đúng lúc không.

### 13.7 Security và epistemic integrity

Ngoài ACL còn cần:

- signed immutable ingestion log;
- extractor/model supply-chain attestation;
- claim/fact namespace separation;
- multi-source conflict detection;
- anomalous graph delta detection;
- adversarial query/result testing;
- independent source/build/runtime verification cho high-impact action.

---

## 14. Khuyến nghị kiến trúc cuối cùng

### 14.1 Định nghĩa sản phẩm nên dùng

**Code Knowledge Graph là một mạng contextual assertions có version và provenance, liên kết source artifacts với language semantics, build/configuration, contracts, data, runtime observations, tests, architecture/domain intent và lịch sử thay đổi; nó cung cấp task-specific evidence views cho con người và agents.**

Định nghĩa này rộng hơn AST/call graph nhưng vẫn kỷ luật hơn việc gọi mọi metadata “knowledge”.

### 14.2 Core bắt buộc

Nếu chỉ chọn mười năng lực để xây trước:

1. immutable revision/workspace snapshot;
2. content/file occurrence/source anchor;
3. symbol–occurrence–binding–type;
4. reified call sites và may/must target;
5. build variant/artifact/dependency identity;
6. test discovery và observed coverage;
7. contextual assertion + provenance;
8. capability/unknown/negative-knowledge contract;
9. typed agent views + evidence paths;
10. patch overlay + build/test/graph-diff closed loop.

### 14.3 Điều tạo khác biệt dài hạn

Moat không nằm ở số edge lớn nhất. Nó nằm ở:

- **semantic fidelity** qua language/build/framework;
- **context correctness** qua revision/config/runtime;
- **evidence integrity** và honest uncertainty;
- **incremental freshness**;
- **task views** giúp agent lý giải với ít context;
- **closed-loop validation** nối graph trở lại phần mềm thật.

### 14.4 Câu trả lời ngắn cho câu hỏi “graph nào làm LLM thực sự hiểu phần mềm?”

Không phải một graph duy nhất, mà là:

1. **semantic spine** xác định code là gì;
2. **behavior/dependence layers** xác định code có thể làm gì;
3. **build/config/contracts/data/deployment layers** xác định chương trình nào đang tồn tại;
4. **runtime/test evidence** xác định điều gì đã xảy ra và được kiểm chứng;
5. **architecture/domain/evolution layers** xác định vì sao nó tồn tại và thay đổi;
6. **provenance/modality/capability** cho LLM biết mức độ tin cậy;
7. **task-specific views** biến mạng tri thức đó thành context có thể reasoning.

---

## 15. Nguồn chính và vai trò bằng chứng

### 15.1 Nền tảng lý thuyết và program representation

| Nguồn | Loại | Vai trò trong báo cáo |
|---|---|---|
| [Rice — Classes of Recursively Enumerable Sets and Their Decision Problems](https://www.ams.org/journals/tran/1953-074-02/S0002-9947-1953-0053041-6/S0002-9947-1953-0053041-6.pdf), 1953 | Paper nền tảng | Giới hạn decidability; không thể tuyên bố complete behavior semantics. |
| [Cousot & Cousot — Abstract Interpretation](https://dl.acm.org/doi/10.1145/512950.512973), POPL 1977 | Paper nền tảng | Static analysis là approximation có semantics. |
| [Ferrante, Ottenstein & Warren — Program Dependence Graph](https://dl.acm.org/doi/10.1145/24039.24041), TOPLAS 1987 | Journal paper | Control/data dependence. |
| [Horwitz, Reps & Binkley — System Dependence Graph](https://dl.acm.org/doi/10.1145/77606.77608), TOPLAS 1990 | Journal paper | Interprocedural slicing. |
| [Cytron et al. — Static Single Assignment Form](https://dl.acm.org/doi/10.1145/115372.115320), TOPLAS 1991 | Journal paper | Value/version/def-use representation. |
| [Hind — Pointer Analysis: Haven’t We Solved This Problem Yet?](https://dl.acm.org/doi/10.1145/379605.379665), PASTE 2001 | Conference paper | Precision–efficiency trade-off của points-to analysis. |
| [Yamaguchi et al. — Modeling and Discovering Vulnerabilities with Code Property Graphs](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf), IEEE S&P 2014 | Top-tier paper | Hợp nhất AST/CFG/PDG và graph query cho security. |
| [Lamport — Time, Clocks, and the Ordering of Events](https://dl.acm.org/doi/10.1145/359545.359563), CACM 1978 | Journal paper | Happened-before và partial order trong distributed execution. |
| [Murphy, Notkin & Sullivan — Software Reflexion Models](https://dl.acm.org/doi/10.1145/222132.222136), FSE 1995 | Conference paper | Intended-vs-implemented architecture mapping/divergence. |
| [Kruchten — 4+1 View Model](https://www.cs.ubc.ca/~gregor/teaching/papers/4%2B1view-architecture.pdf), IEEE Software 1995 | Journal article | Nhiều architecture views theo concern. |
| [Dapper](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/), 2010 | Production research paper | Runtime distributed tracing. |

### 15.2 Metamodel, indexer và official technical specifications

| Nguồn | Nội dung được dùng |
|---|---|
| [OMG KDM 1.4 About](https://www.omg.org/spec/KDM/1.4/About-KDM) và [spec PDF](https://www.omg.org/spec/KDM/1.4/PDF) | Bốn layer, program/runtime/abstraction packages, build-dependent code assembly. |
| [Tree-sitter](https://tree-sitter.github.io/) | Incremental concrete syntax tree và error recovery. |
| [Kythe schema overview](https://kythe.io/docs/schema-overview.html) và [call graph](https://kythe.io/docs/schema/callgraph.html) | Anchor/semantic node và call-site representation. |
| [SCIP protocol](https://github.com/scip-code/scip/blob/main/scip.proto) | Occurrence, SymbolInformation, relationship, enclosing range. |
| [Glean](https://glean.software/), [derived predicates](https://glean.software/docs/derived/) và [Meta engineering report](https://engineering.fb.com/2024/12/19/developer-tools/glean-open-source-code-indexing/) | Typed facts, language-specific/common schemas, revisions, derived views, incremental indexing. |
| [Joern CPG specification](https://cpg.joern.io/) | AST/CFG/PDG layers, derived edges, findings/evidence. |
| [CodeQL JavaScript library](https://codeql.github.com/docs/codeql-language-guides/codeql-library-for-javascript/) | Textual→lexical→syntactic→binding→control/data/call/framework levels. |
| [LLVM MemorySSA](https://llvm.org/docs/MemorySSA.html), [Alias Analysis](https://llvm.org/docs/AliasAnalysis.html), [Language Reference](https://llvm.org/docs/LangRef.html) | Memory def-use, aliasing, IR semantics/undefined behavior. |
| [C++ draft memory model](https://eel.is/c%2B%2Bdraft/intro.races) | Concurrency, happens-before, race/undefined behavior. |
| [Bazel query](https://bazel.build/query/language), [cquery](https://bazel.build/query/cquery), [aquery](https://bazel.build/query/aquery) | Abstract/configured/action build graphs. |
| [SPDX 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/) | Package/file/snippet/build/security/licensing relationships và evidence. |
| [CycloneDX specification overview](https://cyclonedx.org/specification/overview/) | Component/service/dependency/vulnerability/VEX supply-chain facets. |
| [OpenAPI 3.2](https://spec.openapis.org/oas/v3.2.0.html) | HTTP API operations/schemas/security contract. |
| [AsyncAPI 3.1](https://www.asyncapi.com/docs/reference/specification/latest) | Channels, message operations và protocol bindings. |
| [Arazzo 1.1](https://spec.openapis.org/arazzo/latest.html) | Call sequence/dependency/workflow/outcome. |
| [OpenFeature evaluation context](https://openfeature.dev/specification/sections/evaluation-context/) | Context-dependent feature flag semantics. |
| [OpenLineage object model](https://openlineage.io/docs/spec/object-model/) | Job/run/dataset và static/runtime lineage. |
| [OpenTelemetry spec](https://opentelemetry.io/docs/specs/otel/), [semantic conventions](https://opentelemetry.io/docs/specs/semconv/) và [code attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/code/) | Span/event/link, runtime semantics, source correlation. |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | Entity/activity/agent provenance và specialization. |
| [Software Heritage data model](https://docs.softwareheritage.org/devel/swh-model/data-model.html) và [SWHID](https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html) | Merkle DAG, intrinsic identity, context và fragment qualifiers. |
| [ISO/IEC/IEEE 42010:2022 overview](https://www.iso.org/standard/74393.html) | Stakeholder/concern/viewpoint/view cho architecture description. |
| [C4 diagrams](https://c4model.com/diagrams) | System/container/component/code zoom và task-specific views. |
| [OMG DMN](https://www.omg.org/spec/DMN/1.5/About-DMN) | Machine-readable decision/business-rule model. |

### 15.3 Nghiên cứu Agent/LLM và Code Graph 2025–2026

| Nguồn | Venue/trạng thái | Điều được dùng trong thiết kế |
|---|---|---|
| [RepoGraph](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf) | ICLR 2025 | Lightweight graph như external context; retrieval gain và giới hạn downstream reasoning. |
| [CodexGraph](https://aclanthology.org/2025.naacl-long.7/) | NAACL 2025 long | Graph database tool-use; missing/deep/invalid query và privacy/scale lessons. |
| [LocAgent](https://aclanthology.org/2025.acl-long.426/) | ACL 2025 long | Typed multi-hop graph navigation cho code localization. |
| [Code Graph Model](https://proceedings.neurips.cc/paper_files/paper/2025/file/178ae4ba29022eb7bf509c2e27bc8ab8-Paper-Conference.pdf) | NeurIPS 2025 | Graph-native model/context; executable output vẫn có thể không giải issue. |
| [RepoDistill](https://aclanthology.org/2026.findings-acl.217/) | Findings ACL 2026 | Graph retrieval vẫn cần context budgeting/compression; retrieval false negative không phục hồi được. |
| [RPG-Encoder](https://arxiv.org/abs/2602.02084) | 2026 preprint/venue claim cần đối chiếu proceedings | Incremental repository representation và code↔planning topology. |
| [Oracle Poisoning](https://arxiv.org/abs/2605.09822) | 2026 preprint | Threat model cho integrity/provenance/read-only/cross-verification của graph oracle. |

### 15.4 Cách đọc bằng chứng

- Các standard/official docs xác định semantics của format/protocol, không tự chứng minh một implementation cụ thể đúng.
- Các foundational papers cung cấp formalism; chi phí/coverage trong hệ thống hiện đại vẫn phải benchmark.
- RepoGraph/CodexGraph/LocAgent/Code Graph Model/RepoDistill là evidence mạnh về agent use, nhưng schema của chúng chủ yếu task-specific.
- RPG-Encoder và Oracle Poisoning còn mới; dùng như hướng thiết kế/threat evidence, cần replication độc lập.
- Những phần ghi “đề xuất”, “nên” hoặc “thiết kế” là synthesis của báo cáo, không phải claim nguyên văn từ một nguồn duy nhất.

---

## 16. Kết luận

Muốn Agent/LLM “thực sự hiểu” phần mềm qua graph, cần từ bỏ hai cực:

- graph nhẹ chỉ phục vụ navigation nhưng được gọi là complete knowledge;
- ontology khổng lồ cố materialize mọi thứ nhưng không giữ context/evidence và không thể dùng trong token budget.

Hướng cân bằng là **versioned, contextual, evidence-backed multilayer graph**:

- deterministic semantic facts làm xương sống;
- static approximations và runtime observations giữ modality riêng;
- build/config/environment làm context;
- contracts/data/tests/architecture/evolution tạo whole-system meaning;
- human/LLM claims có provenance và không overwrite facts;
- agent truy cập qua task view, typed tools và closed-loop validation.

Graph như vậy không “biết mọi execution”. Nó làm điều hữu ích hơn: cho agent một mô hình thống nhất, truy vết được và trung thực về điều đã biết, điều có thể xảy ra, điều đã quan sát, điều được kỳ vọng và điều vẫn chưa biết.
