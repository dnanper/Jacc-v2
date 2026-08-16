# Cơ sở lý thuyết và mô hình đồ thị hóa tri thức để hiểu một software/codebase

## 1. Phạm vi và luận điểm chính

Mục tiêu của tài liệu này là trả lời hai câu hỏi:

1. **Muốn hiểu đầy đủ một sản phẩm phần mềm thì cần hiểu những khía cạnh nào?**
2. **Có thể tổ chức thông tin từ source code, tài liệu, kiểm thử, telemetry, lịch sử phát triển và hạ tầng thành một đồ thị tri thức như thế nào để trả lời các câu hỏi đó?**

Điểm xuất phát không phải là graph. Điểm xuất phát là lý thuyết về **architecture views, viewpoints, stakeholder concerns và quality properties**. Graph chỉ là một cơ chế biểu diễn các thực thể, quan hệ và bằng chứng được rút ra từ những nguồn thông tin khác nhau.

Cũng cần làm rõ ngay từ đầu:

> Bộ “8 câu hỏi” trong tài liệu này là một **checklist được suy diễn có kiểm soát**, không phải danh sách được trích nguyên văn từ một tiêu chuẩn duy nhất.

Nền tảng trực tiếp nhất của checklist là bảy viewpoint trong sách *Software Systems Architecture* của Rozanski và Woods, kết hợp với khái niệm architectural perspectives của cùng tác giả. Khung này được đặt trong nền tảng khái niệm của ISO/IEC/IEEE 42010 và được đối chiếu với *Views and Beyond* của Software Engineering Institute (SEI) và mô hình 4+1 của Kruchten.[1][2][3][4][5]

---

## 2. Cơ sở lý thuyết của tám câu hỏi

### 2.1. ISO/IEC/IEEE 42010: stakeholder, concern, view và viewpoint

ISO/IEC/IEEE 42010 là tiêu chuẩn quốc tế về **architecture description**. Tiêu chuẩn này không quy định mọi hệ thống phải sử dụng một danh sách view cố định. Thay vào đó, nó cung cấp nền tảng khái niệm:

- **Stakeholder**: cá nhân, nhóm hoặc tổ chức có mối quan tâm đối với hệ thống.
- **Concern**: điều quan trọng đối với stakeholder, chẳng hạn chức năng, bảo mật, dữ liệu, vận hành hoặc khả năng thay đổi.
- **Viewpoint**: quy ước xác định cách xây dựng một loại architecture view để giải quyết một nhóm concern.
- **View**: biểu diễn cụ thể của kiến trúc, được xây dựng theo một viewpoint.

Ý nghĩa nền tảng là: **không có một biểu diễn đơn lẻ đủ để phục vụ mọi stakeholder và mọi concern**.[1]

### 2.2. Rozanski và Woods: bảy viewpoint

Phiên bản thứ hai của *Software Systems Architecture* trình bày bảy viewpoint quan trọng cho kiến trúc hệ thống thông tin:[2]

1. **Context**
2. **Functional**
3. **Information**
4. **Concurrency**
5. **Development**
6. **Deployment**
7. **Operational**

Trong đó, sáu viewpoint từ Functional đến Operational đã được trình bày trong catalogue ban đầu; Context được bổ sung và chuẩn hóa rõ hơn trong phiên bản thứ hai.[2][3]

| Viewpoint | Nội dung cần hiểu |
|---|---|
| **Context** | Ranh giới hệ thống; con người, hệ thống và thực thể bên ngoài mà hệ thống tương tác hoặc phụ thuộc vào |
| **Functional** | Các phần tử chức năng lúc runtime, trách nhiệm, interface và tương tác chính |
| **Information** | Cách thông tin được cấu trúc, lưu trữ, thao tác, quản lý và phân phối |
| **Concurrency** | Process, thread, đơn vị thực thi đồng thời, synchronization và inter-process communication |
| **Development** | Cấu trúc hỗ trợ việc xây dựng, kiểm thử, bảo trì và mở rộng phần mềm |
| **Deployment** | Môi trường runtime và ánh xạ các software element lên node, network, storage và nền tảng kỹ thuật |
| **Operational** | Cách hệ thống được cài đặt, quản trị, giám sát, hỗ trợ và phục hồi trong production |

Rozanski và Woods nhấn mạnh rằng các view là **riêng biệt nhưng liên quan**, và không phải hệ thống nào cũng cần cùng một tập view hoặc cùng mức chi tiết.[2][3]

### 2.3. Architectural perspectives và chất lượng

Các thuộc tính như security, performance, availability hay evolution không được xem là một cấu trúc độc lập giống Functional hoặc Deployment. Chúng là **cross-cutting quality properties** tác động lên nhiều view.

Rozanski và Woods gọi cơ chế phân tích này là **architectural perspective**. Catalogue của họ gồm những perspective như:

- Security
- Performance and Scalability
- Availability and Resilience
- Evolution
- Regulation
- Usability
- Development Resource
- Internationalization[2]

Để chuẩn hóa câu hỏi về chất lượng sản phẩm, có thể đối chiếu thêm ISO/IEC 25010:2023. Tiêu chuẩn này định nghĩa một product quality model gồm các characteristic và sub-characteristic dùng để đặc tả, đo lường và đánh giá chất lượng sản phẩm ICT và phần mềm.[6]

### 2.4. Từ bảy viewpoint đến tám câu hỏi

Từ các nguồn trên, có thể tạo checklist sau:

| Câu hỏi suy diễn | Cơ sở trực tiếp | Lưu ý |
|---|---|---|
| **1. Why does it exist and what is its context?** | Context, stakeholder concerns, requirements và design rationale | “Why” rộng hơn riêng Context; cần goal, requirement và rationale |
| **2. What does it do?** | Functional viewpoint | Chức năng, responsibility, interface và interaction |
| **3. What information exists and how is it handled?** | Information viewpoint | Data structure, ownership, flow, storage và transformation |
| **4. How does it execute?** | Concurrency viewpoint | Process, thread, async flow, synchronization; runtime thực tế cần telemetry |
| **5. How is the code organized and developed?** | Development viewpoint | Repository, module, dependency, build, test và maintenance structure |
| **6. Where does it run?** | Deployment viewpoint | Software-to-runtime mapping, compute, network, storage và environment |
| **7. How is it operated?** | Operational viewpoint | Configuration, monitoring, alerting, support, backup và recovery |
| **8. How well does it satisfy its quality goals?** | Architectural perspectives và ISO/IEC 25010 | Phải dựa trên requirement và evidence đo được |

Cách diễn đạt này là một **synthesis checklist**: tên và phạm vi của các viewpoint đến từ Rozanski–Woods; nguyên tắc chọn view theo concern đến từ ISO/IEC/IEEE 42010; câu hỏi về chất lượng được củng cố bằng architectural perspectives và ISO/IEC 25010.[1][2][6]

---

## 3. Đánh giá độ chuẩn xác, phổ biến và hợp lý

### 3.1. Mức độ chuẩn hóa

- **ISO/IEC/IEEE 42010** là tiêu chuẩn quốc tế, cung cấp nền tảng chính thống cho việc mô tả kiến trúc bằng stakeholder, concern, view và viewpoint.[1]
- **Rozanski và Woods** là một catalogue thực hành, không phải tiêu chuẩn bắt buộc. Tuy nhiên, sách được xuất bản bởi Addison-Wesley, được xây dựng từ thực tiễn kiến trúc hệ thống thông tin và phiên bản thứ hai được cập nhật để phù hợp với ISO 42010.[2]
- **SEI Views and Beyond** là phương pháp và sách kinh điển của Software Engineering Institute thuộc Carnegie Mellon University. SEI định nghĩa view như một tập system element và các relation giữa chúng, đồng thời nhấn mạnh cần tài liệu hóa cả thông tin xuyên view và design rationale.[4]
- **Kruchten 4+1** là công trình kinh điển đăng trên *IEEE Software*, thiết lập rộng rãi nguyên tắc mô tả kiến trúc bằng nhiều concurrent view cho các stakeholder khác nhau.[5]

Do đó, **nguyên tắc multi-view là nền tảng phổ biến và có độ tin cậy cao**. Tuy nhiên, danh sách bảy viewpoint của Rozanski–Woods là một catalogue cụ thể dành cho information systems, không phải “định luật” rằng mọi software bắt buộc có đúng bảy view.

### 3.2. Tính hợp lý

Khung này hợp lý vì nó tách các concern vốn dễ bị trộn lẫn:

- Cấu trúc source code không đồng nghĩa với chức năng nghiệp vụ.
- Static call graph không đồng nghĩa với execution thực tế.
- Dockerfile hoặc Kubernetes manifest không đồng nghĩa với trạng thái deployment đang chạy.
- Test case không đồng nghĩa với một lần test đã pass.
- Có code xử lý retry không đồng nghĩa hệ thống đạt reliability target.

Rozanski–Woods và SEI đều cảnh báo rằng một mô hình duy nhất chứa mọi thông tin sẽ khó hiểu, khó duy trì và dễ không nhất quán.[3][4]

### 3.3. Giới hạn cần tuyên bố

1. **Tám câu hỏi không phải nguyên văn từ sách hay tiêu chuẩn.** Chúng là checklist được suy ra từ các viewpoint và perspective.
2. **“Why does it exist?” không được giải quyết chỉ bằng Context viewpoint.** Nó còn cần business goal, requirement, stakeholder concern và design rationale.
3. **Các viewpoint là architecture-level.** Chúng không tự định nghĩa chi tiết AST, variable, control dependence hoặc data dependence.
4. **Không phải mọi dự án cần mức chi tiết như nhau.** Một thư viện nhỏ có thể không cần Operational hoặc Deployment view phức tạp.
5. **Graph không được bắt buộc bởi lý thuyết.** Lý thuyết chỉ yêu cầu các view biểu diễn system element, relation và concern. Graph là lựa chọn triển khai phù hợp cho việc tích hợp và truy vấn xuyên nguồn.

---

## 4. Từ cơ sở lý thuyết đến biểu diễn codebase bằng graph

### 4.1. Vì sao graph là một lựa chọn phù hợp?

SEI mô tả architecture view như một tập **system elements và relations**.[4] Đây là cấu trúc tự nhiên của graph:

```text
Node     = system element, concept, artifact, event hoặc evidence
Edge     = relation giữa các element
Property = metadata, thời gian, môi trường, nguồn và độ tin cậy
```

Tuy nhiên, mục tiêu không phải tạo một sơ đồ khổng lồ. Cách đúng là xây dựng **một knowledge base thống nhất**, rồi tạo các **projection/view truy vấn** khác nhau cho từng concern.

Ví dụ, cùng một method có thể xuất hiện trong nhiều projection:

```text
Development: Class --HAS_METHOD--> Method
Functional:  Feature --IMPLEMENTED_BY--> Method
Information: Method --READS--> DomainEntity
Concurrency: Method --PUBLISHES--> Event
Deployment:  Method --PART_OF--> Service --DEPLOYED_AS--> Pod
Operational: Method --OBSERVED_IN--> Span
Evolution:   Method --CHANGED_BY--> Commit
```

### 4.2. OMG KDM làm nền cho vocabulary phần mềm

OMG Knowledge Discovery Metamodel (KDM) là một đặc tả chính thức cho việc biểu diễn phần mềm hiện hữu, các element, association và operational environment của nó. KDM cung cấp các package machine-readable như Source, Code, Action, Data, Event, Build, Platform, Structure và Conceptual.[7]

KDM không bắt buộc phải được triển khai nguyên trạng, nhưng nó cung cấp một cơ sở đáng tin cậy để tránh tự phát minh toàn bộ vocabulary. Một code knowledge graph có thể:

- kế thừa hoặc ánh xạ các node/edge cốt lõi sang KDM;
- mở rộng thêm node cho requirement, test result, telemetry và versioning;
- ghi rõ phần nào là chuẩn, phần nào là extension của nghiên cứu.

---

## 5. Các nguồn tài nguyên cần đồ thị hóa

Một sản phẩm phần mềm có nhiều nguồn tri thức. Mỗi nguồn cung cấp một loại bằng chứng khác nhau.

### 5.1. Documents: ý định, ngữ cảnh và rationale

Các tài liệu quan trọng gồm:

- README và product overview
- Requirement, user story và acceptance criterion
- Use case và business rule
- Architecture document và diagram
- API specification
- ADR
- Data dictionary
- Developer guide
- Deployment guide
- Runbook, SLO và operational procedure
- Security hoặc performance requirement

Node đề xuất:

```text
Document, DocumentSection
Stakeholder, Goal, Requirement
UseCase, Feature, BusinessRule
ArchitectureDecision
ExternalSystem
QualityRequirement, SLO
Runbook, OperationalProcedure
```

Edge đề xuất:

```text
HAS_GOAL
REQUIRES
HAS_USE_CASE
IMPLEMENTS
SATISFIES
CONSTRAINED_BY
DECIDED_BY
INTERACTS_WITH
DOCUMENTED_BY
EXTRACTED_FROM
```

Ví dụ:

```text
Goal: Reduce refund handling time
  --REFINED_AS--> Requirement: Automatic refund
  --REALIZED_BY--> Feature: Refund Order
  --IMPLEMENTED_BY--> PaymentService.refund
```

**Đóng góp:** documents là nguồn chính cho Context, goal, requirement, business intent, design rationale và quality target — những thông tin không thể suy ra chắc chắn chỉ từ syntax của code.

---

### 5.2. Source code: implementation tĩnh

Node có thể gồm:

```text
Repository, Directory, File
Package, Module, Component, Service
Class, Interface, Type
Function, Method, Constructor
Parameter, Variable, Field
Statement, Expression
APIEndpoint, EventHandler, Job
DomainEntity, DTO, Schema, Table
```

Edge có thể gồm:

```text
CONTAINS, DECLARES
IMPORTS, DEPENDS_ON
INHERITS, IMPLEMENTS_INTERFACE
CALLS, ACCESSES
READS, WRITES, TRANSFORMS
EXPOSES_ENDPOINT
PUBLISHES, SUBSCRIBES
CONTROL_DEPENDS_ON
DATA_DEPENDS_ON
```

**Đóng góp:**

- Development: tổ chức repository, module, file và dependency.
- Functional: component, responsibility, interface và call relation.
- Information: data type, schema, read/write và transformation.
- Concurrency: async function, event, queue, lock hoặc thread API ở mức tĩnh.

Source code chủ yếu thể hiện **implemented structure và possible behaviour**, không chứng minh chắc chắn hành vi nào đã xảy ra tại runtime.

---

### 5.3. Tests: hành vi mong đợi và phạm vi đã kiểm tra

#### Test nằm trong source repository

Unit test, integration test và E2E test vẫn là source code, nhưng cần được gán semantic role riêng:

```text
TestSuite
TestCase
TestFixture
TestStep
ExpectedOutcome
```

```text
TestCase --TESTS--> Method
TestCase --VERIFIES--> BusinessRule
TestCase --COVERS--> Feature
TestCase --USES_FIXTURE--> TestFixture
```

Nếu chỉ biểu diễn test như một `Method`, graph biết cấu trúc nhưng không biết nó xác minh requirement hoặc behaviour nào.

#### Test nằm ngoài repository

Manual test, Postman collection, Selenium suite ở repository khác hoặc test case trong test-management system vẫn có thể được mô hình hóa:

```text
ExternalTestArtifact
  --DEFINES--> TestCase
TestCase
  --VERIFIES--> APIEndpoint
  --COVERS--> Requirement
```

ISO/IEC/IEEE 29119-3 định nghĩa template và ví dụ cho test documentation được tạo ra trong test process, bao gồm actual result và test result. Điều này củng cố việc phân biệt **test definition** với **test execution result**.[8]

---

### 5.4. Test output: bằng chứng verification

Cần phân biệt:

```text
TestCase   = định nghĩa điều cần kiểm tra
TestRun    = một lần chạy trong commit/environment cụ thể
TestResult = kết quả của một TestCase trong TestRun
Measurement = coverage, duration hoặc resource consumption
```

Ví dụ:

```text
TestCase --EXECUTED_IN--> TestRun
TestRun --TESTED_COMMIT--> Commit
TestRun --RAN_IN--> Environment
TestResult --RESULT_OF--> TestCase
TestResult --STATUS--> Passed
TestResult --COVERS--> PaymentService.refund
```

Node bổ sung:

```text
CoverageMeasurement
PerformanceTestResult
SecurityScanResult
BuildRun
PipelineRun
```

**Đóng góp:** test output tạo evidence cho câu hỏi “implementation có thỏa mãn behaviour hoặc requirement đã định nghĩa hay không?”. Nó không chứng minh toàn bộ production behaviour, nhưng mạnh hơn việc chỉ biết test code tồn tại.

---

### 5.5. Traces, logs và metrics: runtime evidence

OpenTelemetry chuẩn hóa ba loại signal chính:

- **Trace**: đường đi của request qua ứng dụng.
- **Metric**: phép đo được thu thập tại runtime.
- **Log**: bản ghi của một event.[9]

Node đề xuất:

```text
Trace, Span
LogEvent
MetricSeries, MetricObservation
RuntimeResource
ServiceInstance
DeploymentEnvironment
```

Edge đề xuất:

```text
Span --CHILD_OF--> Span
Span --EXECUTED_BY--> ServiceInstance
Span --OBSERVES--> APIEndpoint
Span --CALLS--> ExternalService
LogEvent --EMITTED_BY--> ServiceInstance
LogEvent --BELONGS_TO--> Span
MetricObservation --MEASURES--> Service
RuntimeResource --INSTANCE_OF--> Deployment
```

Ví dụ:

```text
Trace: refund-request
  └─ Span: POST /refund
       ├─ CHILD_SPAN: PaymentService
       ├─ CHILD_SPAN: PaymentGateway
       └─ CHILD_SPAN: INSERT refund
```

**Đóng góp:**

- Concurrency: flow thực tế, parallel span và async boundary.
- Information: database operation hoặc message thực sự được truy cập.
- Operational: lỗi, latency, throughput và resource usage.
- Quality: evidence cho performance, availability và reliability.

Không nên mặc định một span ánh xạ chính xác đến từng method. Ánh xạ này chỉ đáng tin khi instrumentation, symbol metadata hoặc source mapping cung cấp đủ bằng chứng.

Do telemetry có khối lượng lớn, knowledge graph thường nên lưu:

- cấu trúc trace quan trọng;
- aggregate theo service, endpoint hoặc time window;
- anomaly hoặc representative trace;
- liên kết đến kho telemetry gốc;

thay vì đưa mọi log line và mọi metric sample vào graph lâu dài.

---

### 5.6. Evolution: thay đổi của phần mềm theo thời gian

Git lưu lịch sử bằng object database gồm blob, tree và commit; mỗi commit tham chiếu một tree và các parent commit trước nó.[10]

Node đề xuất:

```text
Commit, Branch, Tag
ChangeSet, ChangeEvent
Issue, PullRequest
CodeEntityVersion
Release
```

Edge đề xuất:

```text
Commit --PARENT_OF--> Commit
Commit --MODIFIES--> CodeEntity
Commit --ADDS--> CodeEntity
Commit --DELETES--> CodeEntity
Commit --IMPLEMENTS--> Issue
CodeEntityVersion --NEXT_VERSION--> CodeEntityVersion
Release --CONTAINS_COMMIT--> Commit
```

#### Mô hình khuyến nghị

Không nên copy toàn bộ code graph cho mọi commit. Nên dùng:

```text
StableEntity
+ ChangeEvent
+ temporal validity
+ EntityVersion chỉ khi thực thể thay đổi
```

Ví dụ:

```text
PaymentService.refund
  <-VERSION_OF- refund@commitA
  <-VERSION_OF- refund@commitB

refund@commitA --NEXT_VERSION--> refund@commitB
commitB --MODIFIES--> PaymentService.refund
```

Các property cần thiết:

```text
valid_from
valid_to
commit_hash
branch
change_type
source_location
```

Snapshot của một release hoặc commit có thể được dựng lại từ stable entity, version và change event. Full snapshot graph chỉ nên dùng cho các mốc quan trọng nếu có nhu cầu truy vấn nhanh hoặc audit.

**Đóng góp:** evolution hỗ trợ đánh giá khả năng thay đổi, truy vết bug/requirement đến code, ownership, co-change và lý do kiến trúc trở thành trạng thái hiện tại. Trong Rozanski–Woods, Evolution là một quality perspective xuyên nhiều view, không chỉ là một view tách biệt.[2]

---

### 5.7. Infrastructure và DevOps assets

Infrastructure là phần cần thiết của Deployment và Operational viewpoints. Nguồn có thể gồm:

- Dockerfile và Docker Compose
- Kubernetes manifest và Helm chart
- Terraform
- CI/CD pipeline
- Cloud configuration
- Runtime inventory từ Kubernetes hoặc cloud API

Dockerfile chứa instruction dùng để xây container image từ source và dependency.[11] Terraform là ngôn ngữ khai báo các infrastructure resource và dependency giữa chúng.[12] Kubernetes object biểu diễn desired state; trường `status` phản ánh current state được control plane cập nhật.[13]

Node đề xuất:

```text
BuildArtifact
ContainerImage, ImageRegistry
Pipeline, Build
Environment
Cluster, Namespace
Deployment, StatefulSet, Pod
Host, ComputeNode
Network, Service, Ingress
Database, Queue, Cache, Volume
Config, SecretReference
CloudResource
```

Edge đề xuất:

```text
Module --BUILT_AS--> BuildArtifact
BuildArtifact --PACKAGED_IN--> ContainerImage
ContainerImage --DEPLOYED_BY--> Deployment
Deployment --CREATES--> Pod
Pod --RUNS_ON--> ComputeNode
Service --EXPOSES--> Pod
Pod --CONNECTS_TO--> Database
Pod --CONFIGURED_BY--> Config
TerraformResource --DEPENDS_ON--> TerraformResource
Pipeline --DEPLOYS_TO--> Environment
```

Cần phân biệt hai loại bằng chứng:

```text
Declared infrastructure
  = Dockerfile, Kubernetes spec, Terraform và pipeline

Observed infrastructure
  = Kubernetes status, cloud inventory và runtime resource
```

Ví dụ:

```text
KubernetesSpec --DECLARES--> Deployment
Deployment --OBSERVED_AS--> RunningReplicaSet
```

Việc tách desired state và observed state giúp phát hiện drift, cấu hình chưa được triển khai hoặc deployment thực tế khác tài liệu.

**Đóng góp:** infrastructure trả lời “software được build thành gì, chạy ở đâu, phụ thuộc hạ tầng nào và được cấu hình/triển khai như thế nào?”.

---

## 6. Mô hình bằng chứng tích hợp

Đây là **đề xuất tổng hợp của tài liệu**, không phải taxonomy nguyên văn từ một tiêu chuẩn. Nó được suy ra từ sự khác biệt giữa architecture description, source code, test documentation, runtime telemetry, version control và infrastructure desired/observed state.

Graph nên phân biệt năm loại evidence:

| Evidence kind | Ý nghĩa | Nguồn chính |
|---|---|---|
| **DECLARED** | Hệ thống được yêu cầu hoặc thiết kế như thế nào | Requirement, docs, ADR, IaC spec |
| **IMPLEMENTED** | Code và configuration thực sự chứa gì | Source code, build file, config |
| **VERIFIED** | Điều gì đã được test hoặc kiểm tra | Test result, coverage, scan result |
| **OBSERVED** | Điều gì đã xảy ra trong runtime | Trace, log, metric, runtime inventory |
| **HISTORICAL** | Thông tin thay đổi qua thời gian | Git, issue, pull request, release |

Mỗi node hoặc edge mang assertion quan trọng nên có provenance:

```text
source_artifact
source_location
commit_hash
timestamp
environment
evidence_kind
extraction_method
extractor_version
confidence
valid_from
valid_to
```

Ví dụ, không nên lưu một edge duy nhất:

```text
PaymentService --CALLS--> PaymentGateway
```

mà không biết nguồn. Có thể tồn tại ba assertion:

```text
StaticCallAssertion:
  evidence_kind = IMPLEMENTED
  source = PaymentService.java:42

DocumentedInteraction:
  evidence_kind = DECLARED
  source = architecture.md#refund-flow

ObservedCall:
  evidence_kind = OBSERVED
  source = trace_id: abc
  environment = production
```

Các assertion có thể củng cố hoặc mâu thuẫn với nhau. Graph phải lưu mâu thuẫn thay vì tự động hợp nhất thành một “sự thật” không có provenance.

---

## 7. Đóng góp của từng nguồn vào tám câu hỏi

| Câu hỏi | Thông tin đồ thị cần có | Nguồn chính | Nguồn kiểm chứng/bổ sung |
|---|---|---|---|
| **1. Why does it exist and what is its context?** | Stakeholder, goal, requirement, use case, external system, business rule, rationale | Requirements, product docs, ADR | Issue, commit, code implementation |
| **2. What does it do?** | Feature, responsibility, component, API, interaction, implementation link | Architecture/API docs, source code | Test case, runtime trace |
| **3. What information exists and how is it handled?** | Entity, schema, table, message, ownership, read/write, transformation, lineage | Source code, schema, data docs | Database spans, logs, runtime observation |
| **4. How does it execute?** | Call/control flow, process, thread, task, event, queue, synchronization | Source code và configuration | Trace, span, runtime event |
| **5. How is the code organized and developed?** | Repository, module, file, class, method, dependency, test, build | Source repository | CI/CD result, ownership và Git history |
| **6. Where does it run?** | Artifact, image, deployment, pod, node, network, storage, environment | Docker/K8s/Terraform/pipeline | Cluster/cloud inventory, telemetry resource |
| **7. How is it operated?** | Config, health check, monitor, alert, runbook, backup, recovery, support procedure | Operational docs và configuration | Logs, metrics, incidents, runtime status |
| **8. How well does it satisfy its quality goals?** | Quality requirement, SLO, test result, metric, failure evidence, trend | Requirement/SLO và quality model | Test output, telemetry, incident/history |

### 7.1. Ví dụ đường truy vấn

#### Câu hỏi 1: Tại sao method này tồn tại?

```text
Method: refund
<-IMPLEMENTED_BY- Feature: Refund Order
<-REALIZES- Requirement: Allow eligible customers to refund
<-SUPPORTS- Goal: Reduce manual refund processing
<-REQUESTED_BY- Stakeholder: Customer Support
```

#### Câu hỏi 4: Nó thực thi như thế nào?

```text
APIEndpoint: POST /refund
--HANDLED_BY--> PaymentController.refund
--CALLS--> PaymentService.refund
--PUBLISHES--> RefundRequested
--CONSUMED_BY--> RefundWorker
```

Sau đó kiểm chứng:

```text
Trace
--OBSERVES--> POST /refund
--CONTAINS_SPAN--> payment-service
--CONTAINS_SPAN--> payment-gateway
```

#### Câu hỏi 6: Nó chạy ở đâu?

```text
PaymentService
--PART_OF--> payment-module
--BUILT_AS--> payment.jar
--PACKAGED_IN--> payment-service:1.4
--DEPLOYED_BY--> payment-deployment
--CREATES--> payment-pod
--RUNS_ON--> cluster-node
--IN_ENVIRONMENT--> production
```

#### Câu hỏi 8: Nó hoạt động tốt đến đâu?

```text
QualityRequirement: refund p95 < 300 ms
--MEASURED_BY--> Metric: refund_latency_p95
--OBSERVED_VALUE--> 240 ms

BusinessRule: closed orders cannot be refunded
--VERIFIED_BY--> TestCase
--RESULT_IN--> Passed TestResult
```

---

## 8. Một ví dụ tích hợp ngắn

Giả sử sản phẩm có chức năng hoàn tiền:

```java
class PaymentService {
    RefundResult refund(Order order) {
        gateway.refund(order.paymentId());
        repository.save(new Refund(order.id()));
        return RefundResult.success();
    }
}
```

Graph tối thiểu từ source:

```text
PaymentService --HAS_METHOD--> refund
refund --CALLS--> PaymentGateway.refund
refund --READS--> Order
refund --CREATES--> Refund
refund --WRITES--> RefundRepository
```

Graph từ docs:

```text
Requirement: Refund eligible order
--IMPLEMENTED_BY--> refund

BusinessRule: Closed order cannot be refunded
--VERIFIED_BY--> refund_closed_order_test

ArchitectureDecision: Use asynchronous settlement
--AFFECTS--> RefundRequestedEvent
```

Graph từ test và test result:

```text
refund_closed_order_test
--TESTS--> refund
--EXECUTED_IN--> ci-run-102
--HAS_RESULT--> Passed
--TESTED_COMMIT--> abc123
```

Graph từ runtime:

```text
trace-789
--OBSERVES--> POST /refund
--CONTAINS_SPAN--> PaymentService
--CONTAINS_SPAN--> PaymentGateway
--RAN_IN--> production
```

Graph từ infrastructure:

```text
payment-module
--PACKAGED_IN--> payment-service:1.4
--DEPLOYED_BY--> payment-deployment
--CREATES--> payment-pod
--CONNECTS_TO--> payment-db
```

Graph từ evolution:

```text
commit-abc123
--MODIFIES--> PaymentService.refund
--IMPLEMENTS--> issue-456
```

Nhờ các liên kết này, một code entity không còn chỉ là node cú pháp; nó được đặt trong chuỗi:

```text
Goal
→ Requirement
→ Feature
→ Code
→ Test
→ Runtime observation
→ Deployment
→ Evolution
```

---

## 9. Nguyên tắc để graph đúng và đủ

### 9.1. “Đủ” phải được định nghĩa theo concern

Không có graph nào tuyệt đối đầy đủ. Graph được xem là đủ khi:

- các stakeholder và concern mục tiêu đã được xác định;
- mỗi câu hỏi cần thiết có ít nhất một nguồn evidence;
- các path quan trọng có provenance;
- coverage gap được biểu diễn rõ thay vì che giấu.

### 9.2. Không trộn expected và actual

Phải tách:

```text
Documented behaviour
Static possible behaviour
Tested behaviour
Observed behaviour
```

Một interaction có trong architecture document nhưng không có trong code là mismatch. Một lời gọi có trong code nhưng chưa từng xuất hiện trong trace có thể do sampling, dead code hoặc flow chưa được kích hoạt; không được tự động kết luận.

### 9.3. Không xem inference là fact

Thông tin suy ra bằng LLM, naming convention hoặc community detection cần có:

```text
extraction_method = inferred
confidence = ...
supporting_evidence = ...
```

Thông tin từ parser, compiler index, manifest hoặc telemetry có provenance trực tiếp nên được phân biệt với inference.

### 9.4. Duy trì consistency xuyên view

Cùng một logical entity cần stable identity để liên kết qua source, docs, runtime và version. Tuy nhiên, không nên ép các entity khác granularity thành một node:

- `PaymentService` trong source có thể ánh xạ tới một runtime service, nhưng không mặc định là cùng thực thể.
- `Function` không mặc định tương ứng một `Span`.
- `Feature` không mặc định tương ứng một module.

Cần edge ánh xạ có provenance như:

```text
REALIZED_BY
PART_OF_RUNTIME_COMPONENT
OBSERVED_AS
DEPLOYED_AS
```

### 9.5. Sử dụng projection thay vì một graph visualization duy nhất

Knowledge graph có thể tích hợp mọi nguồn, nhưng giao diện nên tạo projection riêng:

- feature-to-code view;
- data lineage view;
- static execution view;
- runtime trace view;
- deployment view;
- test coverage view;
- evolution view.

Điều này tuân theo nguyên tắc multi-view: một nguồn tri thức thống nhất nhưng nhiều cách quan sát theo concern.[1][3][4]

---

## 10. Kết luận

Cơ sở lý thuyết đáng tin cậy nhất cho mục tiêu hiểu một software/codebase là:

1. **ISO/IEC/IEEE 42010** cung cấp nguyên tắc stakeholder–concern–view–viewpoint.
2. **Rozanski và Woods** cung cấp catalogue Context, Functional, Information, Concurrency, Development, Deployment và Operational, cùng các quality perspective xuyên view.
3. **SEI Views and Beyond** củng cố quan điểm rằng kiến trúc gồm nhiều tập system element và relation, cùng thông tin xuyên view và design rationale.
4. **Kruchten 4+1** là nền tảng kinh điển của cách mô tả kiến trúc bằng nhiều concurrent view.
5. **ISO/IEC 25010** cung cấp quality model để làm rõ câu hỏi “How well?”.
6. **OMG KDM** cung cấp vocabulary chuẩn hóa cho source, code, action, data, build, platform và các software asset hiện hữu.
7. **ISO/IEC/IEEE 29119, OpenTelemetry, Git, Docker, Kubernetes và Terraform** cung cấp nền tảng cho test evidence, runtime evidence, evolution và infrastructure.

Từ các cơ sở đó, graph nên được xem là một **evidence-backed, multi-view knowledge model**:

```text
Docs          → declared intent and design
Source code   → implemented structure and possible behaviour
Tests         → expected and verified behaviour
Telemetry     → observed runtime behaviour
Infrastructure→ declared and observed deployment
Git history   → temporal evolution
```

Mục tiêu cuối cùng không phải “đưa mọi thứ vào graph”, mà là tạo được các đường truy vấn có provenance để trả lời tám concern quan trọng, đồng thời cho biết câu trả lời đến từ **thiết kế, implementation, verification, observation hay lịch sử**.

---

## Tài liệu tham khảo

[1] ISO/IEC/IEEE 42010:2022, *Software, systems and enterprise — Architecture description*.

[2] N. Rozanski and E. Woods, *Software Systems Architecture: Working with Stakeholders Using Viewpoints and Perspectives*, 2nd ed., Addison-Wesley Professional, 2011.

[3] N. Rozanski and E. Woods, “Applying Viewpoints and Views to Software Architecture,” Viewpoints and Perspectives white paper.

[4] P. Clements, F. Bachmann, L. Bass, D. Garlan, J. Ivers, R. Little, P. Merson, R. Nord, and J. Stafford, *Documenting Software Architectures: Views and Beyond*, 2nd ed., Addison-Wesley Professional, 2010.

[5] P. Kruchten, “Architectural Blueprints—The ‘4+1’ View Model of Software Architecture,” *IEEE Software*, vol. 12, no. 6, pp. 42–50, 1995.

[6] ISO/IEC 25010:2023, *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — Product quality model*.

[7] Object Management Group, *Knowledge Discovery Metamodel (KDM), Version 1.4*, 2016.

[8] ISO/IEC/IEEE 29119-3:2021, *Software and systems engineering — Software testing — Part 3: Test documentation*.

[9] OpenTelemetry, *Concepts and Specification: Traces, Metrics, Logs and Resources*.

[10] Git Project, *Git Documentation and Pro Git: Git Objects*.

[11] Docker, *Dockerfile Overview and Reference*.

[12] HashiCorp, *Terraform Language Documentation*.

[13] Kubernetes, *Kubernetes Objects: Spec, Status and Desired State*.
