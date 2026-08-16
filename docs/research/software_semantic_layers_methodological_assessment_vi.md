# Đánh giá phương pháp luận về các tầng ngữ nghĩa của phần mềm

> **Câu hỏi:** Một sản phẩm phần mềm hoặc một kho mã nguồn có thể được bóc tách
> thành những tầng ngữ nghĩa nào? Danh sách 10 tầng đề xuất có đúng không?
>
> **Ngày nghiên cứu:** 04-08-2026. Phạm vi nguồn gồm tiêu chuẩn chính thức,
> đặc tả kỹ thuật chính thức và công trình nền tảng. Taxonomy cuối cùng là phần
> tổng hợp của báo cáo, không phải taxonomy được một tiêu chuẩn duy nhất quy định.

## 1. Kết luận ngắn

Danh sách đề xuất **đúng về hướng và có độ phủ khá cao**, nhưng **không phải một
hierarchy tuyến tính gồm 10 tầng ngữ nghĩa đồng loại**.

Ba loại khái niệm đang bị trộn vào cùng một trục:

1. **Các mặt cấu thành phần mềm:** source, entity, structure, control, data,
   interface, workflow.
2. **Các phương thức tạo tri thức về phần mềm:** phân tích tĩnh, quan sát runtime,
   kiểm thử, chứng minh, review.
3. **Các chiều bối cảnh:** revision, build, configuration, environment,
   deployment, thời gian, ownership và intent.

Điểm thiếu quan trọng nhất là **realization context**: dependency, build variant,
compiler/linker option, configuration, feature flag, platform và deployment.
Cùng một source revision có thể tạo artifact và hành vi khác nhau dưới các context
này. KDM dành riêng các package cho Build, Platform, Event và Data; OpenFeature
cũng mô tả flag evaluation là hàm của evaluation context
([OMG KDM 1.4](https://www.omg.org/spec/KDM/1.4/PDF),
[OpenFeature Evaluation Context](https://openfeature.dev/specification/sections/evaluation-context/)).

Khuyến nghị thực tế là dùng:

- **9 semantic planes** để nói phần mềm *là gì và làm gì*;
- **4 cross-cutting axes** để nói fact đó đúng ở revision/context nào, được biết
  bằng cách nào, đáng tin đến đâu và thay đổi ra sao.

Không có số tầng “đúng tuyệt đối”. ISO/IEC/IEEE 42010 yêu cầu architecture
description được tổ chức theo concern, viewpoint và model kind; mô hình 4+1 cũng
dùng nhiều view đồng thời cho các stakeholder khác nhau. Vì vậy taxonomy tốt phải
được đánh giá theo **coverage, separation of concerns, traceability và fitness for
purpose**, không theo số tầng
([ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html),
[Kruchten, 1995](https://www.cs.ubc.ca/~gregor/teaching/papers/4%2B1view-architecture.pdf)).

## 2. Đánh giá từng mục trong danh sách đề xuất

| Mục đề xuất | Nhận xét | Điều chỉnh nên làm |
|---|---|---|
| 1. Source form | Đúng nhưng còn hẹp. Text/token/CST/AST không đủ định danh đối tượng đang nói tới. | Thêm repository, revision, content identity, path occurrence, generated/macro mapping và source anchor. |
| 2. Program entities | Đúng và cần tách khỏi syntax. Identifier occurrence không đồng nhất với symbol. | Gọi là **entities, binding, scope and types**; giữ declaration, definition, reference, overload và type relation. SCIP chính thức tách `Occurrence` khỏi `SymbolInformation` ([SCIP](https://github.com/scip-code/scip/blob/main/scip.proto)). |
| 3. Static structure | Đúng. Bao gồm containment, import, inheritance, implementation, reference và call candidates. | Ghi rõ static call/dispatch thường là **may-call**, không phải sự kiện đã xảy ra. Static structure cũng không bao phủ control/data dependence. |
| 4. Control semantics | Đúng nhưng thiếu concurrency. | Bao gồm CFG, branch, exception, lifecycle/state transition, task/thread, synchronization và causality. Lamport cho thấy distributed events tạo partial order thay vì một trình tự toàn cục đơn giản ([Lamport, 1978](https://doi.org/10.1145/359545.359563)). |
| 5. Data and state semantics | Đúng nhưng đang gộp nhiều cấp. | Bao gồm value/def-use, memory/alias, object state, transaction, persistent schema và lineage; có thể tách persistence khi hệ thống data-heavy. PDG hợp nhất control dependence và data dependence nhưng không thay thế mô hình persistence toàn hệ thống ([Ferrante, Ottenstein & Warren, 1987](https://doi.org/10.1145/24039.24041)). |
| 6. Contracts, effects and workflows | Có ba khái niệm hợp lệ nhưng không đồng cấp. | **Effects** gắn với operational/data semantics; **contracts** là expected behavior tại boundary; **workflow** là composition nhiều operation theo thời gian. OpenAPI mô tả operation/interface, còn Arazzo mô tả step, dependency, success/failure của workflow ([OpenAPI](https://spec.openapis.org/oas/latest.html), [Arazzo](https://spec.openapis.org/arazzo/latest.html)). |
| 7. Observed runtime | Rất cần, nhưng là một observational view chứ không phải tầng “cao hơn” static semantics. | Scope mỗi observation bằng artifact/revision, configuration, environment, workload, time và sampling. Trace chỉ chứng minh **đã quan sát thấy trong run này**. OpenTelemetry định nghĩa trace từ span, event, link, resource và context ([OpenTelemetry](https://opentelemetry.io/docs/specs/otel/overview/)). |
| 8. Verification evidence | Cần cho engineering, nhưng là **evidence plane** áp vào mọi claim, không phải semantics của chương trình. | Tách test, assertion, proof, review, coverage, static finding, benchmark và run result; luôn liên kết target, oracle, environment và outcome. NIST phân biệt review/analyze human-readable code và test executable code để kiểm tra compliance ([NIST SP 800-218](https://doi.org/10.6028/NIST.SP.800-218)). |
| 9. Domain and intent | Đúng và không thể suy ra đáng tin chỉ từ code. | Tách requirement, business rule, architectural decision, stakeholder concern và mapping xuống implementation/evidence. ISO 29148 quy định requirement processes và information items suốt vòng đời; ISO 42010 tách architecture khỏi architecture description ([ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html), [ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html)). |
| 10. Evolution and organization | Quan trọng, nhưng là hai chiều khác nhau và đều cross-cutting. | Evolution gồm revision/change/release/migration; organization gồm author/owner/team/process/decision authority. Dùng provenance để liên kết entity, activity và agent thay vì xem organization như nghĩa nội tại của code ([W3C PROV-O](https://www.w3.org/TR/prov-o/)). |

### Phán quyết

- **Giữ nguyên được:** 2, 3, 4, 5, 9 sau khi làm rõ phạm vi.
- **Cần mở rộng:** 1 và 4.
- **Cần tách lại:** 6 và 10.
- **Nên đổi từ layer sang evidence/view:** 7 và 8.
- **Cần bổ sung:** build/dependency/configuration/platform/deployment; interface và
  protocol nên hiện rõ hơn; quality attributes là concern xuyên suốt.

## 3. Taxonomy đề xuất

### 3.1 Chín semantic planes

Các plane dưới đây có quan hệ phụ thuộc, nhưng **không tạo thành một total order**.
Một truy vấn có thể đi ngang qua nhiều plane.

| Plane | Câu hỏi trung tâm | Nội dung tiêu biểu |
|---|---|---|
| P1. Artifact, identity and source form | Đang nói về nội dung nào, tại revision/path nào, được biểu diễn ra sao? | repository, revision, artifact, file occurrence, content hash, text, token, comment, CST/AST, source/generated mapping |
| P2. Entities, binding and types | Tên này trỏ tới thực thể nào và có kiểu/phạm vi gì? | symbol, declaration, definition, occurrence, scope, signature, type, generic, overload |
| P3. Static topology | Các thực thể liên hệ cấu trúc thế nào? | containment, import, reference, dependency, inheritance, override, implementation, possible call/dispatch |
| P4. Operational, control and concurrency semantics | Execution có thể tiến triển và tương tác theo thứ tự nào? | action, basic block, branch, exception, state machine, task/thread, synchronization, happens-before |
| P5. Value, data, memory and persistent state | Giá trị và trạng thái được tạo, truyền, biến đổi và lưu ở đâu? | def-use, SSA, alias/points-to, taint, object state, schema, query, transaction, dataset lineage |
| P6. Interfaces, protocols and contracts | Hệ thống hứa gì tại boundary và trao đổi theo protocol nào? | API/RPC operation, event/message schema, pre/postcondition, invariant, permission, error contract |
| P7. Interaction and workflows | Nhiều operation được ghép thành outcome người dùng/hệ thống thế nào? | route/UI action, use case, scenario, orchestration, saga, business process, success/failure path |
| P8. Realization and operational context | Source trở thành hệ thống chạy cụ thể bằng cách nào? | dependency/package, build target/action, generated artifact, compiler option, config/flag, secret/policy, platform, deployment topology |
| P9. Architecture, domain and intent | Tại sao hệ thống tồn tại, trách nhiệm/boundary nào được mong đợi? | stakeholder need, requirement, quality attribute, domain concept/rule, component, viewpoint, ADR, rationale |

Taxonomy này tương thích về coverage với KDM mà không sao chép KDM nguyên khối.
KDM tổ chức tri thức thành Infrastructure, Program Elements, Runtime Resources và
Abstractions, với các package Source, Code, Action, Platform, UI, Event, Data,
Structure, Conceptual và Build
([OMG KDM 1.4](https://www.omg.org/spec/KDM/1.4/PDF)). Nó cũng phù hợp với nguyên
tắc nhiều view theo concern của ISO 42010, thay vì ép mọi artifact vào một cây
abstraction duy nhất.

### 3.2 Bốn cross-cutting axes

| Axis | Phải ghi gì? | Vì sao không nên là một semantic layer? |
|---|---|---|
| A1. Version and validity context | repository, revision, build variant, config, environment, workload, time interval | Một fact có thể đúng ở một context nhưng sai ở context khác; axis này scope mọi plane. |
| A2. Epistemic status and modality | declared, inferred, may, must, observed, claimed, refuted, unknown; confidence/coverage | Nó mô tả **ta biết fact bằng cách nào**, không mô tả phần mềm tự thân. |
| A3. Evidence and assurance | source span, analyzer run, trace, log, test result, proof, review, benchmark, attestation | Cùng một loại evidence có thể hỗ trợ hoặc bác bỏ claim ở bất kỳ plane nào. |
| A4. Evolution, provenance and organization | commit/change set, derivation, author/agent, owner/team, issue/decision/release | Đây là chiều thời gian và nguồn gốc của mọi artifact/fact. PROV-O cũng mô hình provenance bằng Entity–Activity–Agent xuyên miền. |

Observed runtime vì vậy nên được mô hình như **observation records/evidence** ánh
xạ vào P4–P8, không được ghi đè static facts. Ví dụ:

- `MAY_CALL(A, B)` từ static analysis;
- `OBSERVED_CALL(A, B, trace=T, config=C, workload=W)` từ telemetry;
- không quan sát thấy call trong trace `T` không chứng minh call đó bất khả thi.

Google Dapper dùng sampling để kiểm soát overhead; bản thân nhóm tác giả nhấn mạnh
trace được thu từ một hạ tầng quan sát production cụ thể. Điều này củng cố việc
không suy rộng một trace thành universal semantics
([Dapper, 2010](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)).

## 4. Cơ sở lý thuyết và phương pháp luận

### 4.1 Formal semantics: “nghĩa” không chỉ là cấu trúc

Ba họ semantics cổ điển trả lời các câu hỏi khác nhau:

- operational semantics mô tả bước chuyển execution;
- denotational semantics ánh xạ chương trình sang đối tượng toán học;
- axiomatic semantics mô tả các thuộc tính có thể chứng minh bằng assertion.

Hoare đặt nền cho việc chứng minh thuộc tính chương trình bằng axioms và inference
rules, cho thấy contract/assertion không đồng nhất với trace thực thi
([Hoare, 1969](https://doi.org/10.1145/363235.363259)). Vì vậy “control
semantics”, “contracts” và “observed runtime” là các view bổ sung nhau, không phải
ba mức thay thế nhau.

Không taxonomy hữu hạn nào khiến mọi thuộc tính semantic trở nên quyết định được.
Rice chứng minh giới hạn tổng quát cho các thuộc tính không tầm thường của hàm do
chương trình tính; abstract interpretation cung cấp cách tính safe approximation,
không xóa giới hạn đó
([Rice, 1953](https://www.ams.org/journals/tran/1953-074-02/S0002-9947-1953-0053041-6/S0002-9947-1953-0053041-6.pdf),
[Cousot & Cousot, 1977](https://doi.org/10.1145/512950.512973)). Do đó một mô hình
nghiêm túc phải biểu diễn cả uncertainty, approximation và coverage.

### 4.2 Program representation: AST không phải toàn bộ semantics

PDG biểu diễn đồng thời control dependence và data dependence; SSA biểu diễn mỗi
definition của biến như một version riêng. Đây là bằng chứng nền tảng cho việc tách
P3, P4 và P5 thay vì đặt toàn bộ quan hệ vào “static structure”
([Ferrante, Ottenstein & Warren, 1987](https://doi.org/10.1145/24039.24041),
[Cytron et al., 1991](https://doi.org/10.1145/115372.115320)).

Trong tooling hiện đại, SCIP tách source occurrence khỏi symbol information; Kythe
dùng anchor tại source span để nối reference/call site tới semantic node. Hai mô
hình cùng chỉ ra rằng “text occurrence”, “semantic entity” và “relation” không nên
bị đồng nhất
([SCIP protocol](https://github.com/scip-code/scip/blob/main/scip.proto),
[Kythe schema overview](https://kythe.io/docs/schema-overview.html)).

### 4.3 Software description là multi-view và concern-driven

ISO 42010 phân biệt entity-of-interest với architecture description, và tổ chức
mô tả qua stakeholder concern, viewpoint, view và model kind. Kruchten cũng dùng
logical, process, development, physical views cộng scenarios. Cả hai chống lại ý
tưởng rằng chỉ có một phân rã đúng cho mọi stakeholder
([ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html),
[Kruchten, 1995](https://www.cs.ubc.ca/~gregor/teaching/papers/4%2B1view-architecture.pdf)).

Hệ quả: taxonomy nên có một **semantic spine ổn định**, sau đó tạo projection cho
debugging, impact analysis, security, onboarding, audit hoặc product reasoning.
Không nên materialize mọi plane ở cùng độ chi tiết cho mọi use case.

### 4.4 Product lifecycle không đồng nhất với product semantics

ISO/IEC/IEEE 12207:2026 bao phủ acquisition, supply, development, operation,
maintenance và disposal; các process có thể áp dụng đồng thời, lặp và đệ quy. Đây
là cơ sở để xem development/evolution/organization là lifecycle context, không
phải “tầng cuối” của code
([ISO/IEC/IEEE 12207:2026](https://www.iso.org/standard/90219.html)).

Tương tự, SWEBOK v4 tổ chức body of knowledge thành requirements, architecture,
design, construction, testing, operations, maintenance, configuration management,
process, models/methods, quality, security và các vùng khác. Đó là bản đồ discipline
và activities, không phải semantic hierarchy của một artifact
([SWEBOK v4](https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf)).

### 4.5 Quality và security là concern xuyên suốt

ISO/IEC 25010:2023 định nghĩa product quality model gồm các characteristic và
subcharacteristic để specification, measurement và evaluation. Quality attribute
không chỉ nằm trong test evidence: nó bắt đầu từ requirement/intent, ảnh hưởng
design và realization, rồi được đo bằng evidence
([ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html)).

Tương tự, NIST SSDF đưa secure development practices vào SDLC thay vì tạo một
“security layer” độc lập. Vì vậy security, privacy, safety, reliability,
performance, accessibility và compliance nên là **concern/tag/query projection
xuyên P1–P9**, với requirement và evidence riêng.

## 5. Các insight có thể dùng làm tiêu chí thiết kế

### 5.1 “Layer” nên được dùng theo hai nghĩa khác nhau

- **Semantic plane:** nhóm fact cùng loại về đối tượng phần mềm.
- **Projection/view:** lát cắt được chọn cho một stakeholder hoặc task.

Nếu không phân biệt hai nghĩa này, graph/schema dễ biến runtime trace, test report,
commit và business concept thành các node ngang hàng nhưng không có quy tắc về
authority hay validity.

### 5.2 Tách object-level fact khỏi evidence-level claim

`Function F calls G` không đủ. Ít nhất phải biết:

- call site/source revision nào;
- relation là language-resolved, static approximation hay runtime observation;
- build/config/environment nào;
- extractor/run nào tạo fact;
- evidence và coverage ra sao.

W3C PROV-O cung cấp vocabulary Entity–Activity–Agent và derivation/generation/use
phù hợp để provenance hóa claim mà không nhét lịch sử vào bản thân semantic edge
([W3C PROV-O](https://www.w3.org/TR/prov-o/)).

### 5.3 Static possibility, specified expectation và observed actuality phải tách

Ba câu sau không tương đương:

1. `A` **có thể** gọi `B` theo static analysis;
2. contract nói `A` **phải** gọi `B` khi điều kiện `C`;
3. trace cho thấy `A` **đã** gọi `B` trong workload `W`.

Một evidence model tốt giữ cả ba, kể cả khi chúng mâu thuẫn. Mâu thuẫn thường là
insight quan trọng: dead path, missing instrumentation, config drift, contract
violation hoặc architecture erosion.

### 5.4 Build/config/environment là một phần của meaning-in-context

Source text không quyết định một mình deployed behavior. Macro, conditional
compilation, dependency resolution, generated code, feature flag, tenant/user,
platform và deployment đều có thể đổi reachable behavior. OpenFeature chỉ rõ
evaluation context có thể chứa end-user, application, host và ambient data dùng
cho targeting; KDM dành Build và Platform packages riêng
([OpenFeature](https://openfeature.dev/specification/sections/evaluation-context/),
[OMG KDM](https://www.omg.org/spec/KDM/1.4/PDF)).

Vì vậy công thức làm việc hợp lý là:

> **Behavior claim = source + language semantics + dependencies + build + config
> + environment + input/state + schedule + workload + revision.**

### 5.5 Workflow không phải call graph phóng to

Call graph nói implementation relation; workflow nói sequence/dependency/outcome
ở boundary nghiệp vụ hoặc hệ thống. Arazzo biểu diễn workflow step có operation,
dependency, success criteria, on-success và on-failure. Vì vậy workflow cần map
xuống calls/events/data/runtime evidence, nhưng không nên bị suy ra mặc định chỉ từ
call graph
([Arazzo 1.1](https://spec.openapis.org/arazzo/latest.html)).

### 5.6 “Complete representation” phải đổi thành “explicit coverage”

Mục tiêu khả thi không phải biểu diễn mọi execution và mọi intent, mà là:

- có chỗ cho mỗi plane quan trọng;
- mỗi fact có revision/context và authority;
- phân biệt must/may/observed/claimed/unknown;
- báo rõ extractor capability, coverage và blind spots;
- tạo được evidence path từ requirement/claim xuống artifact hoặc observation.

## 6. Cách dùng taxonomy theo phạm vi

### Nếu chỉ phân tích một source repository

Ưu tiên P1–P5, một phần P6, rồi thêm A1–A3. Không nên giả vờ có domain intent,
runtime truth hay deployment topology nếu repo không chứa evidence tương ứng.

### Nếu mô tả một software product hoàn chỉnh

Cần đủ P1–P9 và A1–A4. Ngoài source repository còn phải ingest artifact từ build,
package/dependency, config/flag, API/schema, database/migration, IaC/deployment,
telemetry, test/assurance, requirement/ADR và VCS/issue tracker.

### Nếu thiết kế Code Knowledge Graph cho agent

Không cần biến mọi token, CFG block, span hoặc test event thành graph node. Nên giữ
semantic identity và cross-plane roots trong graph; dữ liệu high-cardinality hoặc
temporal có thể nằm ở typed fact store/artifact store và được project theo task.
Điều bắt buộc là join được bằng stable identity, revision/context và provenance.

## 7. Taxonomy rút gọn nếu buộc phải giữ đúng 10 mục

Nếu yêu cầu trình bày đúng 10 dòng, có thể dùng bản sửa tối thiểu sau:

1. Artifact identity and source form
2. Program entities, binding and types
3. Static structure and dependency topology
4. Control, state-machine and concurrency semantics
5. Value, data, memory and persistence semantics
6. Interfaces, protocols, contracts and effects
7. Interactions and workflows
8. Build, configuration, platform and deployment context
9. Architecture, domain, requirements and quality intent
10. Runtime, verification and evolution **evidence views**

Tuy nhiên mục 10 vẫn là phép nén để trình bày. Trong data model nghiêm túc, runtime
observation, verification evidence, evolution/provenance và organization nên là
các axis/fact families riêng như mục 3.2.

## 8. Kết luận

Danh sách ban đầu là một **coverage checklist tốt**, không phải một ontology hoặc
semantic hierarchy đã hoàn chỉnh. Điều chỉnh quan trọng nhất không phải thêm thật
nhiều layer, mà là đổi mô hình tư duy:

- từ một tháp tuyến tính sang nhiều semantic planes có liên kết;
- từ fact vô điều kiện sang fact được scope bởi revision/build/config/environment;
- từ việc trộn static, expected và observed sang giữ modality riêng;
- từ “verification/runtime/history là nghĩa của code” sang “chúng là evidence và
  provenance về các claim”;
- từ source-only sang software-system, nhưng chỉ mở rộng khi có artifact thật.

Với mục tiêu mô tả khách quan một sản phẩm phần mềm, mô hình **9 planes + 4 axes**
phía trên có cơ sở vững hơn danh sách 10 tầng tuyến tính: nó khớp với formal
semantics, program analysis, KDM, architecture description, requirements/V&V,
observability và lifecycle standards, đồng thời vẫn đủ gọn để triển khai theo từng
use case.
