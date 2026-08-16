# Code Knowledge Graph — Nguồn gốc có ảnh hưởng thiết kế & Cách thiết kế

**Tài liệu rút gọn**, dẫn xuất từ báo cáo nền tảng `code-kg-research.md`.
Phạm vi: chỉ giữ những nguồn gốc **trực tiếp quyết định một lựa chọn thiết kế cụ thể**, và trình bày thiết kế suy ra từ chúng.

**Đã loại bỏ khỏi tài liệu này** (vẫn còn trong báo cáo đầy đủ): khảo sát so sánh framework, bảng đánh giá độ phổ biến, research gaps, các nguồn chỉ có giá trị bối cảnh (Kruchten 4+1, Maalej, Dagstuhl MM, C4, ISO 25010 chi tiết).

**Nhãn nguồn gốc:** **[ĐN]** nguồn định nghĩa trực tiếp · **[DG]** diễn giải của tôi · **[TH]** tổng hợp nhiều nguồn · **[ĐX]** đề xuất mới, chưa có nguồn hậu thuẫn.

---

## Phần I — Các nguồn gốc có ảnh hưởng thiết kế trực tiếp

Mỗi mục dưới đây gồm: *nguồn* → *điều nguồn nói* → *hệ quả thiết kế bắt buộc*.

### I.1 Nhóm quyết định **truy vấn nào graph phải phục vụ**

#### Sillito, Murphy & De Volder (FSE 2006 / TSE 2008) — nguồn quan trọng nhất

**[ĐN]** Catalogue 44 loại câu hỏi lập trình viên hỏi khi làm change task, thu được qua hai nghiên cứu định tính (9 người mới trên ArgoUML ~60 KLOC; 16 lập trình viên công nghiệp trên code họ quen). Điểm then chốt: **các tác giả phân nhóm câu hỏi dựa trên đặc tính của subgraph cần duyệt để trả lời**, coi codebase là đồ thị thực thể (method, field) và quan hệ (reference, call).

| Nhóm | Số câu | Hình dạng subgraph |
|---|---|---|
| 1. Finding initial focus points | 5 | Tìm **một node** |
| 2. Building on those points | 15 | Node + **láng giềng bậc 1** |
| 3. Understanding a subgraph | 13 | **Subgraph liên thông** |
| 4. Questions over groups of subgraphs | 11 | **Quan hệ giữa các subgraph** |

**[ĐN]** Các tác giả cũng ghi nhận: câu hỏi của lập trình viên **ánh xạ không khớp** với câu hỏi mà tool trả lời được; người dùng phải ghép thủ công kết quả nhiều tool, kết quả thường nhiễu. Ví dụ cụ thể trong bài: muốn biết "kiểu nào có `MEvent` làm field", phải dùng reference search, nhận 102 kết quả, và bỏ cuộc.

> **Hệ quả thiết kế [DG, Cao]**
> 1. Graph phải hỗ trợ **bốn lớp truy vấn** phân biệt theo phạm vi duyệt, không phải một API phẳng. Xem §II.9.
> 2. Nhóm 4 (quan hệ giữa các subgraph) là nhóm **hiện chưa tool nào phục vụ tốt** — đây là nơi KG hợp nhất tạo giá trị so với tập tool rời rạc.
> 3. **44 câu hỏi này là bộ nghiệm thu.** Mỗi node type và edge type phải được biện minh bằng ít nhất một câu hỏi nó cần thiết để trả lời. Không phục vụ truy vấn nào → loại.

#### LaToza & Myers (PLATEAU 2010; ICSE 2010)

**[ĐN]** 179 lập trình viên → 371 câu hỏi → 21 nhóm, 94 câu hỏi phân biệt. **Nhóm được báo cáo nhiều nhất liên quan tới intent và rationale**: code này làm gì, nó *định* làm gì, và *tại sao* làm theo cách này. Công trình song song: 460 lập trình viên báo cáo hỏi câu hỏi kiểu reachability **hơn 9 lần/ngày**.

> **Hệ quả thiết kế [DG, Cao]**
> 1. Tầng **INTENT là bắt buộc**, không phải tùy chọn. Nhóm câu hỏi phổ biến nhất **không trích xuất được từ source code**; nó chỉ tồn tại trong ADR, commit message, PR discussion, issue.
> 2. Reachability là truy vấn tần suất cao → cần index đường đi, không chỉ index cạnh.

#### Letovsky (1987)

**[ĐN]** Năm loại conjecture: *why*, *how*, *what*, *whether*, và **discrepancy** — chất vấn về mâu thuẫn quan sát được.

> **Hệ quả thiết kế [DG, Cao]** Xử lý mâu thuẫn là **một phần của comprehension**, không phải tính năng phụ. Graph phải **hiển thị** mâu thuẫn thay vì âm thầm chọn một bên. Kéo theo: cần node `Discrepancy` first-class (§II.5).

---

### I.2 Nhóm quyết định **có những lớp node nào**

#### SEI — *Documenting Software Architectures: Views and Beyond* (Clements et al.)

**[ĐN]** Đơn vị cơ bản là **viewtype**. Có **ba viewtype**, mỗi cái chứa loại phần tử khác nhau về bản chất:
- **Module viewtype** — đơn vị *implementation*. Styles: decomposition, uses, generalization, layers.
- **Component-and-Connector** — phần tử *runtime* và tương tác. Styles: client-server, pipe-and-filter, publish-subscribe, shared-data, peer-to-peer.
- **Allocation viewtype** — ánh xạ sang môi trường phi-phần-mềm. Styles: deployment, install, work assignment.

> **Hệ quả thiết kế [DG, Cao] — phân biệt quan trọng nhất trong toàn bộ tài liệu.**
> `Module` ≠ `Component` ≠ `Deployment` là **ba lớp node khác nhau**, do chính tác giả gốc tách bạch. Việc gộp chúng vì trùng tên trong repo là lỗi mô hình hoá có thể chỉ đích danh nguồn. Xem §II.8.

#### OMG KDM = ISO/IEC 19506:2012 — baseline schema

**[ĐN]** Metamodel biểu diễn **tài sản phần mềm hiện hữu, các liên kết giữa chúng, và môi trường vận hành của chúng**. Bốn tầng:

| Tầng | Packages | Nội dung |
|---|---|---|
| Infrastructure | Core, kdm, **Source** | Inventory artifact; **truy nguyên đầy đủ ngược về source code**; cơ chế mở rộng |
| Program Elements | Code, Action | Datatype, procedure, class, method, variable; control/data flow mức statement |
| Runtime Resource | Platform, UI, Event, Data | Môi trường vận hành; giao diện; sự kiện/chuyển trạng thái; dữ liệu bền vững |
| Abstractions | Conceptual, Structure, Build | Business rule (căn chỉnh SBVR); subsystem/layer/component; góc nhìn build |

**[ĐN]** Khái niệm trung tâm: **container** — thực thể sở hữu thực thể khác, cho phép biểu diễn ở nhiều mức hạt. Hỗ trợ **phân tích tăng dần** qua biến đổi KDM→KDM. Có cơ chế extension family/stereotype.

> **Hệ quả thiết kế [DG, Cao]**
> 1. Dùng KDM làm **baseline để mở rộng**, không thiết kế lại từ đầu. Bốn tầng của nó ánh xạ gần trực tiếp sang tầng CODE, INFRA và một phần INTENT trong §II.2.
> 2. **Package `Source` đã chuẩn hoá sẵn provenance mức tối thiểu** (truy nguyên về vị trí source). Không phát minh lại — mở rộng nó.
> 3. **Bốn thứ KDM thiếu** và phải tự thiết kế: test execution, telemetry runtime, IaC khai báo, lịch sử tiến hoá. (Dễ hiểu: KDM 1.0 ra 2007, trước Kubernetes 2014 và OpenTelemetry 2019.)

#### FAMIX (Demeyer, Tichelaar & Ducasse)

**[ĐN]** Metamodel độc lập ngôn ngữ cho code OO: Class, Method, Attribute, Invocation, Inheritance. **Trade-off được chính tác giả nêu:** mọi code metamodel là đánh đổi giữa **quá thô** (vô dụng cho nhiều bài toán) và **quá mịn** (mất tính độc lập ngôn ngữ).

> **Hệ quả thiết kế [DG, Cao]** Đây là căn cứ có nguồn để chọn **Function/Method làm đơn vị nguyên tử** của KG và **loại Statement/Expression** khỏi graph mặc định. Xem §II.3.

#### Chikofsky & Cross (IEEE Software 1990)

**[ĐN]** *Redocumentation* = khôi phục tài liệu ở **cùng mức trừu tượng**. *Design recovery* = tái tạo **toàn bộ thông tin cần để một người hiểu đầy đủ** chương trình — bao gồm **thông tin ngoài code**: domain knowledge, kinh nghiệm, thông tin bên ngoài.

> **Hệ quả thiết kế [DG, Cao]** Chính các tác giả đã ghi nhận từ 1990 rằng hiểu đầy đủ **đòi hỏi thông tin không nằm trong source code**. Đây là chỗ dựa lịch sử cho kiến trúc đa nguồn — KG chỉ có tầng code là redocumentation, không phải design recovery.

#### Diehl (2007)

**[ĐN]** Software visualization bao gồm biểu diễn **cấu trúc, sự thực thi, và sự tiến hoá**.

> **Hệ quả thiết kế [DG, Trung bình]** Bộ ba trực giao ngắn gọn nhất trong tài liệu kinh điển, và là nguồn *gốc* duy nhất đặt evolution **ngang hàng** với structure và behaviour. Mượn làm ba chiều chính của graph. **Lưu ý trung thực: đây là phân loại cho *visualization*, không phải cho knowledge representation — việc mượn là diễn giải của tôi, không phải điều Diehl phát biểu.**

---

### I.3 Nhóm quyết định **cạnh nào tin được**

#### Soundiness Manifesto (Livshits et al., CACM 2/2015)

**[ĐN]** Trên thực tế hầu như mọi phân tích tĩnh whole-program có tính chính xác và khả mở đều **không sound**. Chuẩn thực hành: over-approximate hầu hết đặc trưng ngôn ngữ, nhưng **cố ý under-approximate một tập con mà giới chuyên môn đều biết** — điển hình **Java reflection** và **`eval` trong JavaScript**. Một phân tích thực dụng có thể giả vờ `eval` không làm gì, trừ khi phân giải được tham số chuỗi lúc biên dịch. Tên gọi cho loại phân tích này: **soundy**.

> **Hệ quả thiết kế [DG, Cao]**
> 1. Cạnh `CALLS` **vừa thiếu vừa thừa** cùng lúc. **Bắt buộc** gắn `confidence`, `extraction_method`, `extractor_version`.
> 2. **Vắng mặt cạnh không phải bằng chứng phủ định.** Cần phân biệt *"không có cạnh"* với *"đã kiểm tra và xác nhận không có cạnh"*.

#### Biggerstaff, Mitbander & Webster (CACM 1994)

**[ĐN]** Bài toán khám phá khái niệm hướng-con-người và gán vào đối tác hướng-cài-đặt là **concept assignment problem**; lời giải **đòi hỏi thành phần suy luận hợp lý (plausible reasoning) mạnh** — về bản chất không phải bài toán suy diễn tất định.

> **Hệ quả thiết kế [DG, Cao]** Cạnh `Feature → Code` (`REALIZES`) **không bao giờ được coi là fact**. LLM năm 2026 làm concept assignment tốt hơn DESIRE 1994 rất nhiều, nhưng **bản chất bài toán không đổi**: vẫn là plausible reasoning, không phải extraction. Kéo theo yêu cầu về `evidence_type = inferred` (§II.5).

#### Gotel & Finkelstein (ICRE 1994)

**[ĐN]** Phân biệt **pre-RS traceability** (từ nguồn gốc nhu cầu → đặc tả) và **post-RS traceability** (đặc tả → thiết kế/code/test). Dựa trên nghiên cứu với hơn 100 người hành nghề: **phần lớn vấn đề bị quy cho "traceability kém" thực ra thuộc pre-RS**, và các tác giả nêu rõ vì sao **một giải pháp bao trùm là khó xảy ra**.

> **Hệ quả thiết kế [DG, Cao] — đây là tuyên bố phạm vi, không phải tính năng.** KG chỉ giải quyết được post-RS. "Tại sao yêu cầu này tồn tại", "ai đề xuất", "đánh đổi nào đã bị loại" thuộc pre-RS và **về cấu trúc không trích xuất được từ repository**. Phải nói thẳng điều này trong thiết kế thay vì hứa hẹn.

#### Git — hành vi rename

**[ĐN]** **Git không lưu tường minh thao tác rename.** Rename được phát hiện dựa trên **độ tương đồng nội dung** khi sinh diff; ngưỡng similarity index mặc định **50%**, cấu hình qua `-M`/`--find-renames`. `git mv` chỉ là shortcut cho `git rm` + `git add`. `git log --follow` **đứt** khi khác biệt vượt ngưỡng, và mặc định **không kiểm tra merge commit**.

> **Hệ quả thiết kế [DG, Cao]** Cạnh `RENAMED_TO` **luôn** mang `confidence` + `analysis_config` ghi rõ ngưỡng. Ở mức entity (function, class) còn tệ hơn mức file vì phải AST diff + matching, không có công cụ chuẩn. **"Theo dấu lịch sử một hàm" — truy vấn hấp dẫn nhất của code KG — về bản chất là ước lượng, không phải truy hồi.**

---

### I.4 Nhóm quyết định **cách mô hình hoá desired vs observed**

#### Kubernetes API Conventions (SIG Architecture)

**[ĐN]** API phân biệt **đặc tả trạng thái mong muốn** (`spec`) với **trạng thái tại thời điểm hiện tại** (`status`). **Conditions** truyền đạt tường minh thuộc tính người dùng quan tâm, thay vì bắt suy ra từ quan sát khác; ý nghĩa condition một khi định nghĩa **trở thành một phần của API**. Với condition đã biết, **vắng mặt trạng thái phải diễn giải là `Unknown`**, thường cho biết reconciliation chưa xong *hoặc trạng thái chưa quan sát được*. Trường `observedGeneration` phân biệt "đang trong quá trình" với "đã ổn định". Nguyên tắc thiết kế: status phải **tái dựng được 100% bằng quan sát**.

> **Hệ quả thiết kế [DG, Cao]** Kubernetes **đã chuẩn hoá sẵn** đúng bài toán này. **Mượn nguyên ngữ nghĩa** thay vì phát minh lại — bao gồm cả giá trị thứ ba `Unknown`, thứ mà hầu hết mô hình bỏ sót.

#### Terraform (HashiCorp)

**[ĐN]** **Mục đích chính của state là lưu các *binding* giữa object trong hệ thống từ xa và resource instance khai báo trong configuration.** Trước mọi thao tác, Terraform **refresh** để cập nhật state theo hạ tầng thực. **Drift** = trạng thái thực khác trạng thái định nghĩa trong configuration.

> **Hệ quả thiết kế [DG, Cao]** Terraform có **ba** mức phân biệt, không phải hai: **configuration** (khai báo) / **state file** (bản ghi binding, có thể cũ) / **hạ tầng thực** (quan sát). Vì vậy thuộc tính `state_kind` phải có **ba** giá trị `{desired, recorded, observed}` để bao được cả Terraform lẫn Kubernetes.

#### OpenTelemetry Specification

**[ĐN]** Signals: **traces, metrics, logs** (+ profiles). **Resource** = tập thuộc tính cố định mô tả nguồn phát telemetry, có Resource Semantic Conventions riêng. Log record mang **trace context fields** cho phép nối log ↔ trace. **Semantic Conventions** quy định span name/kind, metric instrument/unit, tên & ý nghĩa attribute.

**[ĐN — chi tiết quyết định mô hình]** Trong pattern **scatter/gather**, span cuối được **link** tới nhiều thao tác nó tổng hợp; OTel **khuyến nghị KHÔNG đặt parent**, vì trường parent về mặt ngữ nghĩa biểu diễn quan hệ **cha đơn**.

> **Hệ quả thiết kế [DG, Cao]** **Trace không phải cây** — nó là DAG với **hai loại cạnh phân biệt**: `PARENT_OF` và `LINKS_TO`. Gộp chúng là sai đặc tả.

---

### I.5 Nhóm quyết định **cách mô hình hoá thời gian và provenance**

#### Hismo — Gîrba & Ducasse (JSME 18:207–236, 2006)

**[ĐN]** History được mô hình hoá như **thực thể tường minh**; một *history* là **một dãy các version**. Hismo **thêm một tầng thời gian lên trên thông tin cấu trúc**, cung cấp hạ tầng chung để **kết hợp phân tích tiến hoá với phân tích cấu trúc**. Các tác giả nhấn mạnh: cách tiếp cận trước đó **không dựa trên metamodel tường minh**, khiến kết quả khó tái dùng và so sánh.

> **Hệ quả thiết kế [DG, Cao]** Thời gian là **một tầng chồng lên** cấu trúc, không phải thuộc tính rời rạc gắn vào node. Kéo theo: `CodeEntity` (danh tính ổn định) tách khỏi `CodeEntityVersion` (trạng thái tại thời điểm).

#### Software Heritage — Di Cosmo & Zacchiroli; Pietri et al. (MSR 2019)

**[ĐN]** Mô hình dữ liệu là **một Merkle DAG duy nhất**, **năm tầng logic**: **Content (blob) → Directory → Revision (commit) → Release → Snapshot** (toàn bộ trạng thái các branch của một repository). Cạnh nảy sinh tự nhiên: directory entry → directory/content; revision → directory và revision trước; release → revision; snapshot → revision và release.

**[ĐN]** Hash mật mã bền vững làm định danh node → **deduplication toàn cục**: mỗi blob lưu đúng một lần bất kể bao nhiêu directory trỏ tới; mỗi commit lưu một lần bất kể bao nhiêu repository chứa nó. Ngoài DAG, lưu **crawling information**: ánh xạ ba chiều **origin (URL) ↔ visit timestamp ↔ snapshot object** trong log append-only.

> **Hệ quả thiết kế [DG, Cao]** Bằng chứng vận hành ở quy mô ~tỉ node rằng **content-addressed + structural sharing** giải quyết được bài toán lưu lịch sử. Đồng thời là mẫu tốt cho việc tách *cái được quan sát* (visit, timestamp) khỏi *cái được lưu* (snapshot).

#### W3C PROV-O (W3C Recommendation, 30/04/2013)

**[ĐN]** Ba lớp chính: **Entity** (thứ có khía cạnh cố định), **Activity** (thứ tác động lên hoặc sinh ra entity theo thời gian), **Agent** (thứ chịu trách nhiệm). Nối qua `wasGeneratedBy`, `used`, `wasAssociatedWith`, `wasDerivedFrom`, `wasAttributedTo`, `wasRevisionOf`, `actedOnBehalfOf`. Conform OWL-RL.

> **Hệ quả thiết kế [DG, Cao]** Dùng vocabulary đã là W3C Recommendation và **suy luận tự động được**, thay vì tự phát minh. Ánh xạ ở §II.5.

---

### I.6 Nguồn có ảnh hưởng thiết kế **hạn chế** (giữ một dòng)

| Nguồn | Điều duy nhất ảnh hưởng thiết kế |
|---|---|
| **ISO/IEC/IEEE 42010:2022** | Khái niệm **correspondence rule** → cơ sở chuẩn cho ràng buộc nhất quán liên tầng (§II.8). Ngoài ra: tiêu chuẩn **cố ý không quy định tập view cố định** → biện minh cho việc không giả định trước schema. |
| **Rozanski & Woods** | **Operational viewpoint** (cài đặt, migration, quản trị, hỗ trợ) — bộ viewpoint kinh điển duy nhất chạm tới vận hành → biện minh tầng INFRA. |
| **von Mayrhauser & Vans (1995)** | Lập trình viên **chuyển đổi thường xuyên** giữa top-down và bottom-up → graph phải **duyệt hai chiều** intent↔code, cần index ngược cho `REALIZES`. |
| **Code Property Graph (Yamaguchi 2014)** | Hợp nhất AST+CFG+PDG **trên node statement/predicate chung**. **Cảnh báo của chính tác giả: schema để mở, các cài đặt khác nhau đáng kể** → trích ở mức *nguyên lý*, không phải chuẩn. |
| **ISO/IEC 25010:2023** | Chỉ dùng làm **từ vựng** cho node `QualityRequirement`. Không dùng làm taxonomy comprehension. |
| **SPDX (ISO/IEC 5962:2021) / CycloneDX (ECMA-424) / SLSA** | Nguồn chuẩn cho `DEPENDS_ON` mức package và provenance có chữ ký cho `BuildArtifact`. |

---

## Phần II — Thiết kế đồ thị

### II.1 Sáu nguyên tắc thiết kế, mỗi nguyên tắc có nguồn

| # | Nguyên tắc | Suy ra từ |
|---|---|---|
| **P1** | **Question-driven.** Mỗi node/edge type phải được biện minh bằng ≥1 câu hỏi trong catalogue Sillito/LaToza. Không phục vụ truy vấn nào → loại. | Sillito et al. (phân loại theo subgraph); FAMIX (trade-off hạt) |
| **P2** | **Đơn vị nguyên tử là Function/Method.** Statement/Expression không vào graph mặc định. | FAMIX (trade-off do chính tác giả nêu) |
| **P3** | **Không gộp thực thể khác bản chất dù trùng tên.** | SEI Views & Beyond (Module/C&C/Allocation) |
| **P4** | **Mọi assertion mang bằng chứng.** `evidence_type` + `extraction_method` + `confidence` nằm trên **instance**, không trên định nghĩa loại. | Soundiness Manifesto; Biggerstaff |
| **P5** | **Vắng mặt ≠ phủ định.** Phân biệt "không có dữ liệu" / "đã kiểm tra và không có" / "chưa biết". | Soundiness; K8s (`Unknown`) |
| **P6** | **Mâu thuẫn là dữ liệu, không phải lỗi.** Hiển thị, không âm thầm chọn bên. | Letovsky (discrepancy conjecture) |

### II.2 Kiến trúc tầng

```
╔═══════════════════════════════════════════════════════════════╗
║  PROVENANCE — cắt ngang mọi tầng, căn chỉnh PROV-O            ║
╚═══════════════════════════════════════════════════════════════╝
        ↑           ↑           ↑           ↑            ↑
  ┌──────────┐ ┌─────────┐ ┌────────┐ ┌─────────┐ ┌────────────┐
  │  INTENT  │→│  CODE   │→│  TEST  │ │ RUNTIME │ │   INFRA    │
  │ declared │ │implem't'd│ │verified│ │observed │ │ desired /  │
  │          │ │          │ │        │ │         │ │ recorded / │
  │          │ │          │ │        │ │         │ │ observed   │
  └──────────┘ └─────────┘ └────────┘ └─────────┘ └────────────┘
        ↕           ↕           ↕           ↕            ↕
  ╔═══════════════════════════════════════════════════════════════╗
  ║  EVOLUTION — tầng thời gian chồng lên cấu trúc (Hismo)        ║
  ╚═══════════════════════════════════════════════════════════════╝
```

**Nguồn của việc chia tầng:** CODE/RUNTIME/EVOLUTION ↔ bộ ba structure–behaviour–evolution của Diehl **[DG]**; INTENT ↔ architecture description + requirements **[DG]**; INFRA ↔ Allocation viewtype (SEI) + Platform package (KDM) **[DG]**; EVOLUTION như *tầng chồng* ↔ Hismo **[DG]**; TEST **[ĐX]** — **không có tiền lệ trong nhóm framework kinh điển**.

> **Ghi chú trung thực:** trong toàn bộ nhóm kinh điển đã khảo sát, gần như không framework nào coi "trạng thái kiểm chứng" là một khía cạnh của việc hiểu hệ thống. Sillito chỉ có duy nhất Q41 chạm tới tính đúng đắn. Tầng TEST là đề xuất, không phải kế thừa.

### II.3 Danh mục node và quyết định

#### CODE

| Node | Quyết định | Căn cứ |
|---|---|---|
| Repository, Directory, File | Giữ | Neo cho `source_location` (KDM Source package) |
| Package, **Module** | Giữ | SEI Module viewtype; Sillito Q5, Q7 |
| **Component**, Service | Giữ — **KHÔNG gộp với Module** | SEI C&C viewtype |
| **Class, Interface, Function, Method** | **Giữ — đơn vị nguyên tử** | Sillito Q6–Q18 tập trung ở mức này; FAMIX core |
| Field, Parameter | Giữ | Sillito Q10, Q15, Q18 |
| Variable (cục bộ) | Có điều kiện — chỉ khi cần data-flow query | Bùng nổ số lượng |
| **Statement, Expression** | **LOẠI khỏi graph mặc định** | Xem lập luận dưới |
| APIEndpoint, EventHandler, Job | Giữ | Điểm vào; cầu nối sang RUNTIME |
| Entity, DTO, Schema, Table | Giữ | KDM Data package; Sillito Q26, Q27, Q33 |

**Lập luận loại Statement/Expression [ĐX, Trung bình]**

- *Ủng hộ giữ:* CPG đặt CFG/PDG edge trên node AST của statement và predicate; không có chúng thì không có data/control dependence. Sillito Q28–Q33 cần chúng.
- *Ủng hộ loại:* (a) FAMIX nêu rõ trade-off quá mịn/quá thô; (b) repo 1M dòng sinh ~10⁷ statement node, khiến truy vấn xuyên tầng bất khả thi; (c) tầng statement **thay đổi ở gần như mọi commit** → nổ tung tầng EVOLUTION.
- **Dung hoà — kiến trúc hai kho:**
  - **Kho 1 = Knowledge Graph.** Đơn vị nguyên tử Function/Method. Lưu quan hệ xuyên tầng + lịch sử. Bền vững.
  - **Kho 2 = CPG store** (Joern / CodeQL / tree-sitter index). Tính **theo yêu cầu** cho một commit cụ thể. Không lưu lâu dài.
  - **Cầu nối:** `source_location = (repo, commit_sha, path, byte_start, byte_end)`.
  - Giữ khả năng trả lời Sillito Q28–Q33 mà không vật chất hoá tầng statement.
  - **Chưa được kiểm chứng thực nghiệm — độ tin cậy Thấp, cần đo.**

#### INTENT

`Stakeholder`, `Goal`, `Requirement`, `UseCase`, `Feature`, `BusinessRule`, `ArchitectureDecision`, `QualityRequirement`, `ExternalSystem`, `Document`, `DocumentSection` — giữ toàn bộ.

- `ArchitectureDecision` phục vụ **nhóm câu hỏi phổ biến nhất** theo LaToza & Myers.
- `BusinessRule` ↔ KDM Conceptual package (căn chỉnh SBVR).
- `Document`/`DocumentSection` giữ **để làm neo bằng chứng** cho `EXTRACTED_FROM`, không phải để lưu nội dung.

#### TEST

`TestSuite`, `TestCase`, `TestFixture`, `ExpectedOutcome`, `TestRun`, `TestResult`, `CoverageMeasurement`, `BenchmarkResult`, `SecurityScanResult`.

> **Ràng buộc bắt buộc [ĐX]:** `TestCase` (định nghĩa, declared) và `TestRun`/`TestResult` (thực thi, verified) là **hai node khác nhau**. Song song hoàn hảo với `spec`/`status` của Kubernetes.
> **Một `TestCase` không có `TestRun` nào là trạng thái hợp lệ và có ý nghĩa** — nó trả lời trực tiếp "test này đã từng chạy chưa":
> ```cypher
> MATCH (t:TestCase) WHERE NOT (t)-[:EXECUTED_AS]->(:TestRun) RETURN t
> ```

#### RUNTIME

| Node | Quyết định | Căn cứ |
|---|---|---|
| `Trace`, `Span` | Giữ | OTel |
| `LogEvent` | Giữ **chỉ template + tham chiếu** | Khối lượng. Lưu `LogTemplate` trong graph, raw log ở kho khác |
| `MetricSeries` | Giữ (định danh: name + attribute set) | OTel |
| `MetricObservation` | **KHÔNG lưu trong graph** | Chuỗi thời gian thuộc TSDB. Graph trỏ tới TSDB |
| `ServiceInstance`, `RuntimeResource`, `Environment` | Giữ | OTel Resource semantic conventions |

#### INFRA

`BuildArtifact`, `ContainerImage`, `Pipeline`, `Cluster`, `Namespace`, `Deployment`, `Pod`, `Host`, `Network`, `Database`, `Queue`, `Cache`, `Config`, `CloudResource`.

> **Ràng buộc bắt buộc [ĐX]:** mỗi node hạ tầng mang `state_kind ∈ {desired, recorded, observed}`. **Ba** giá trị — vì Terraform có ba mức (config/state/thực tế) trong khi K8s có hai (spec/status).

#### EVOLUTION

`Commit`, `Branch`, `Tag`, `PullRequest`, `Issue`, `Release`, `ChangeEvent`, `Snapshot`, `CodeEntityVersion` (chỉ cho entity thực sự thay đổi — §II.6).

### II.4 Danh mục cạnh — phân loại theo **phương pháp trích xuất**

Đây là phân loại quan trọng nhất: nó quyết định cạnh nào tin được.

#### Nhóm 1 — Tất định (parser / compiler)
> Có thể coi là fact **trong phạm vi một commit cụ thể**.

`CONTAINS`, `DECLARES`, `IMPORTS` (tĩnh), `INHERITS`, `IMPLEMENTS`, `HAS_COLUMN`, `FOREIGN_KEY`

#### Nhóm 2 — Soundy (static analysis)
> **Vừa thiếu vừa thừa.** Bắt buộc `confidence` + `extractor` + `extractor_version`.

| Cạnh | Suy giảm khi |
|---|---|
| `CALLS` | reflection, DI container, dynamic dispatch, callback, `eval` |
| `READS` / `WRITES` | ORM lazy loading, raw SQL ghép chuỗi, stored procedure |
| `IMPORTS` (động) | import theo tên tính lúc chạy |
| control/data dependence | như trên |

#### Nhóm 3 — Cần runtime instrumentation
> Chính xác cho *cái đã quan sát*; **im lặng về cái chưa quan sát**. Bắt buộc `observation_window` + `sampling_rate`.

`COVERS` ← **cạnh đáng tin nhất nối test↔code**
`OBSERVED_IN`, `RUNS_ON`, `MAPS_TO_CODE`, `PARENT_OF`, `LINKS_TO`, `PUBLISHES`/`CONSUMES` (topic động)

#### Nhóm 4 — Heuristic hoặc LLM
> **Không bao giờ là fact.** Bắt buộc `evidence_type=inferred`.

| Cạnh | Giới hạn gốc |
|---|---|
| `REALIZES` (Feature→Code) | Concept assignment problem (Biggerstaff) |
| `RENAMED_TO` | Git không lưu rename; ngưỡng ~50% |
| `TRANSFORMS`, `DECIDED_BY` | Không có ground truth |
| `DOCUMENTED_BY` (suy luận) | Docstring parsing thì cao; LLM matching thì thấp |

#### Nhóm 5 — Cần tài liệu bên ngoài
> Không tồn tại trong repository — pre-RS traceability (Gotel & Finkelstein).

`SATISFIES`, `CONSTRAINED_BY`, `Stakeholder`–`Goal`

#### Nhóm 6 — Metadata hệ thống (tất định)

`EXTRACTED_FROM`, `BUILT_AS` (CI metadata / SLSA), `PACKAGED_IN` (OCI + SBOM), `EXECUTED_IN`

#### Cạnh cần tách bạch — hay bị gộp nhầm

| Cặp cạnh | Vì sao phải tách | Nguồn |
|---|---|---|
| `PARENT_OF` vs `LINKS_TO` | OTel khuyến nghị **không** đặt parent trong scatter/gather; trường parent biểu diễn quan hệ cha **đơn** | OTel spec |
| `DEPLOYED_AS` vs `RUNS_ON` | Cái đầu là **desired** (manifest), cái sau là **observed** (cluster API). Nối bằng `RECONCILES_TO` | K8s API conventions |
| `TESTS` vs `COVERS` | `TESTS` suy từ import/mock (trung bình); `COVERS` từ instrumentation (cao) | [ĐX] |

### II.5 Mô hình assertion & provenance

#### Hai chiều trực giao — sửa lỗi của taxonomy 5 mức

**Tuyên bố rõ: taxonomy DECLARED/IMPLEMENTED/VERIFIED/OBSERVED/HISTORICAL không có nguồn gốc — không tiêu chuẩn nào định nghĩa năm mức này. Đó là synthesis. [TH]**

Vấn đề của nó: **HISTORICAL không cùng chiều với bốn mức kia** — bốn mức đầu là *loại bằng chứng*, HISTORICAL là *trục thời gian*. Trộn vào một enum là lỗi mô hình hoá.

> **Sửa [ĐX]:** tách thành hai chiều độc lập.
> ```
> evidence_type ∈ {declared, implemented, verified, observed, inferred}
> temporal      = (valid_from, valid_to) + (recorded_at, recorded_until)
> ```
> Thêm `inferred` — mức còn thiếu và quan trọng nhất trong bối cảnh LLM.

Tiền lệ độc lập cho từng mức:

| Mức | Tiền lệ có nguồn |
|---|---|
| `declared` | ISO 42010 (AD ≠ architecture); K8s `spec`; Terraform config |
| `implemented` | KDM Program Elements; FAMIX core |
| `verified` | **Không có tiền lệ kinh điển** — gần nhất là ISO/IEC/IEEE 29119 + coverage **[ĐX]** |
| `observed` | K8s `status` ("tái dựng được 100% bằng quan sát"); OTel signals |
| `inferred` | Biggerstaff (plausible reasoning) **[ĐX cho việc nâng thành mức riêng]** |

#### Ánh xạ PROV-O

| Code KG | PROV-O |
|---|---|
| Assertion (node/edge) | `prov:Entity` |
| Lần chạy extractor | `prov:Activity` |
| Parser / analyzer / LLM / instrumentation agent | `prov:SoftwareAgent` |
| Source artifact được đọc | `prov:Entity` + `prov:used` |
| Người xác nhận / sửa | `prov:Person` + `prov:wasAttributedTo` |
| Assertion phái sinh | `prov:wasDerivedFrom` |

#### Schema metadata

```yaml
assertion:
  # Truy nguyên nguồn — mở rộng KDM Source package
  source_artifact:      # URI
  source_location:      # {path, line_start, line_end, byte_start, byte_end}
  commit_hash:          # SHA — neo bất biến

  # Bằng chứng
  evidence_type:        # declared | implemented | verified | observed | inferred
  extraction_method:    # parser | type_resolver | static_analysis |
                        # runtime_instrumentation | test_report |
                        # config_parse | heuristic | llm | human
  extractor:            # → prov:SoftwareAgent
  extractor_version:    # BẮT BUỘC — kết quả static analysis phụ thuộc version
  analysis_config:      # vd: ngưỡng -M cho rename detection
  confidence:           # [0,1] — bắt buộc với nhóm 2, 4
  human_confirmed:      # bool — cho phép nâng cấp inferred → declared

  # Thời gian — BITEMPORAL
  valid_from: / valid_to:          # đúng trong thế giới khi nào
  recorded_at: / recorded_until:   # hệ thống tin điều đó khi nào

  # Bối cảnh
  environment:          # dev | staging | prod | <cluster-id> | null
  observation_window:   # với assertion observed
  sampling_rate:        # với telemetry — BẮT BUỘC
```

**Vì sao bitemporal, không phải một trục [ĐX, Trung bình]** — hai câu hỏi khác nhau, đều phải trả lời được:
- *"Ngày 15/03 hệ thống thực sự thế nào?"* → **valid time**
- *"Ngày 15/03 chúng ta **tin rằng** hệ thống thế nào?"* → **transaction time**

Câu thứ hai không phải học thuật suông: đó là câu hỏi bắt buộc khi điều tra sự cố ("lúc đó ta biết gì?") và khi đánh giá độ tin cậy của chính graph.

**Vì sao `sampling_rate` là bắt buộc [ĐX]** — không có nó, câu "không có span nào cho hàm này" **vô nghĩa**. Với sampling 1%, việc không thấy span cho hàm chạy 50 lần/ngày là hoàn toàn bình thường.

#### Cơ chế biểu diễn — lai

| Loại cạnh | Cơ chế | Lý do |
|---|---|---|
| Nội tầng, nguồn tất định (`CONTAINS`, `DECLARES`) | **Edge properties** | Gọn, nhanh, mâu thuẫn hiếm |
| **Liên tầng**, hoặc `evidence_type ∈ {inferred, observed}` | **Reify thành `Assertion` node** | Đây chính là nhóm có thể mâu thuẫn và cần lập luận *về* chúng |

Đánh đổi kích thước chấp nhận được vì nhóm thứ hai ít hơn nhiều so với cạnh cấu trúc. **[ĐX, Thấp — cần thực nghiệm.]** Nếu ưu tiên tính chuẩn hơn hiệu năng: dùng named graphs / RDF-star, hợp tự nhiên với PROV-O.

#### Xử lý năm tình huống mâu thuẫn

| Tình huống | Chẩn đoán | Xử lý |
|---|---|---|
| **Docs ≠ code** | Hai assertion khác `evidence_type` cùng chủ thể | Giữ **cả hai** + node `Discrepancy`. **Không tự động ưu tiên code** — nếu doc là spec đã ký thì code mới sai. Ưu tiên là quyết định người dùng, không phải schema |
| **Có `CALLS` tĩnh, trace không thấy** | **Không phải mâu thuẫn.** Static = *possible*, trace = *observed* | Không tạo `Discrepancy`. Thêm `observed_count=0` + `observation_window` + `sampling_rate`. Chỉ nâng thành cảnh báo "dead code khả nghi" khi coverage đầy đủ **và** sampling 100% **và** cửa sổ đủ dài — và ghi rõ là **dấu hiệu, không phải kết luận** |
| **Test tồn tại, chưa từng chạy** | **Trạng thái hợp lệ, có giá trị** | `TestCase` không có cạnh tới `TestRun`. Chính là lý do tách hai node |
| **K8s desired ≠ thực tế** | Drift | Hai node `state_kind=desired` / `observed`, nối `RECONCILES_TO` mang `drift_detected`, `observedGeneration`, `conditions` — **kể cả `Unknown` khi condition vắng mặt**. Terraform thêm mức `recorded` |
| **LLM suy luận không có bằng chứng trực tiếp** | `evidence_type=inferred` | Bắt buộc: `extraction_method=llm`, model + version, `confidence`, và `prov:used` trỏ **chính xác** các artifact đưa vào prompt. **Assertion inferred không được dùng làm tiền đề cho assertion inferred khác** nếu không đánh dấu suy giảm confidence — nếu không sẽ có hallucination chồng chất |

### II.6 Mô hình evolution

#### So sánh bốn phương án

| Tiêu chí | P1: Copy graph mỗi commit | P2: Stable + ChangeEvent | P3: Version node | **P4: Lai (khuyến nghị)** |
|---|---|---|---|---|
| Storage | **Rất tệ** — O(commits × entities) | **Tốt nhất** | Tốt | Tốt |
| Query hiện tại | Tốt | **Tốt nhất** | Trung bình | Tốt |
| Query lịch sử | Tốt | **Yếu** — phải replay | **Tốt nhất** | Tốt |
| Snapshot reconstruction | Tầm thường | **Đắt** | Trung bình | **Tốt** |
| Rename/refactoring | **Rất tệ** — mất danh tính | Tốt nếu ChangeEvent ghi được | Tốt nếu có `NEXT_VERSION` | Tốt (vẫn phụ thuộc heuristic) |
| Branching & merge | Tệ | Trung bình | Trung bình | **Tốt** — DAG commit tự nhiên |
| Đã kiểm chứng quy mô lớn? | Không | Hismo (có công bố) | CSDL thời gian | **Software Heritage, ~tỉ node** |

#### Phương án P4 [ĐX, Trung bình]

```
CodeEntity  (danh tính ổn định, UUID)
    │ current_version →
    ├─ CodeEntityVersion  (CHỈ tạo khi nội dung thay đổi)
    │      ├─ content_hash          ← content-addressed → dedup tự nhiên
    │      ├─ introduced_in_commit
    │      ├─ NEXT_VERSION →
    │      └─ giữ toàn bộ cạnh cấu trúc tại version đó
    │
    └─ ChangeEvent  (Commit → CodeEntity)
           ├─ kind: ADD | MODIFY | DELETE | RENAME | MOVE
           └─ confidence   ← BẮT BUỘC với RENAME/MOVE

Snapshot (mỗi commit) → trỏ trực tiếp tập CodeEntityVersion "sống"
```

**Lý do:**
1. Version chỉ cho entity thay đổi → chi phí tiệm cận P2 (một commit điển hình chạm rất ít entity).
2. `content_hash` → hai version giống hệt (vd file bị revert) tự dedup — cơ chế Software Heritage.
3. `Snapshot` → giải điểm yếu chính của P2 (reconstruction đắt) mà không copy graph. Đây là cách SWH giải: `revision → directory → content`, dedup từng tầng.
4. `ChangeEvent` giữ lại vì nó ghi **semantics của thay đổi** (rename, move, refactor) — thứ version diff thuần tuý không diễn đạt được.

#### Cảnh báo bắt buộc về rename

- Cạnh `RENAMED_TO` **luôn** mang `confidence`, `extraction_method=heuristic`, `analysis_config` ghi rõ ngưỡng.
- Ở mức entity còn tệ hơn mức file: cần AST diff + matching, **không có công cụ chuẩn**.
- Refactoring đổi cả tên lẫn nội dung (vd Extract Method) **cắt đứt** chuỗi `NEXT_VERSION` ở **mọi** phương án. Không có lời giải hoàn hảo.
- Nói thẳng trong tài liệu: "theo dấu lịch sử một hàm" là **ước lượng**, không phải truy hồi.

#### Multi-repository [ĐX, Thấp]

- `CodeEntity` cần định danh **toàn cục**: băm `(repo_origin_url, path, qualified_name)`, hoặc theo lược đồ kiểu **SWHID** (định danh nội tại bằng hash mật mã + qualifier `origin`, `visit`, `anchor`, `path`).
- Quan hệ liên repo **không trích được bằng static analysis nội repo**. Nguồn đáng tin duy nhất: **distributed trace** (OTel) và **API contract** (OpenAPI/protobuf). → Lập luận mạnh cho việc **bắt buộc có tầng RUNTIME** trong hệ đa repo.
- **Thời gian không đồng bộ giữa repo** — commit ở A và B không có thứ tự toàn phần. Dùng timestamp thực + release/deployment làm mốc, **không** dùng commit order.

### II.7 Mô hình infrastructure

Ba quy tắc **[ĐX]**:

1. **Mỗi tài nguyên có ≥2 đại diện** — `desired` (manifest/config) và `observed` (cluster/cloud API); Terraform thêm `recorded` (state file). Không gộp.
2. **Node `observed` bắt buộc có `valid_from`/`valid_to`.** Một Pod tồn tại 3 phút; biểu diễn nó không có khoảng hiệu lực là sai.
3. **`DEPLOYED_AS` (desired) và `RUNS_ON` (observed) là hai cạnh khác nhau.** Nối bằng `RECONCILES_TO` mang `observedGeneration` + `conditions` theo đúng ngữ nghĩa Kubernetes — bao gồm việc vắng mặt condition được diễn giải là `Unknown`, **không phải** `False`.

### II.8 Bảy phân biệt không được gộp

| # | Phân biệt | Nguồn |
|---|---|---|
| 1 | Static **possible** behaviour ≠ observed **actual** behaviour | Soundiness Manifesto; OTel sampling |
| 2 | Test **definition** ≠ test **execution result** | [ĐX] — song song `spec`/`status` |
| 3 | **Declared** infrastructure ≠ **observed** infrastructure (≠ **recorded**) | K8s API conventions; Terraform |
| 4 | **Code entity** ≠ **runtime component** | SEI: Module viewtype ≠ C&C viewtype |
| 5 | **Function** ≠ **trace span** (0, 1, hay N span cho một function) | OTel data model |
| 6 | **Feature** ≠ **module** (feature thường crosscutting) | Biggerstaff — concept assignment |
| 7 | **Documentation claim** ≠ **verified fact** | Chikofsky & Cross: redocumentation ≠ design recovery |

> **Cám dỗ lớn nhất là gộp theo tên.** Trong một repo microservice điển hình có: thư mục `payment-service/` (code entity), một `Deployment` tên `payment-service` (declared infra), một `ServiceInstance` phát telemetry với `service.name=payment-service` (observed runtime), và một "Payment" feature trong tài liệu (intent).
> **Bốn thực thể khác nhau, cùng một chuỗi ký tự.** Bốn node nối bằng cạnh có confidence — không phải một node. Đây là lỗi phần lớn công cụ code-graph thương mại mắc phải.

**Cơ chế thực thi [DG]:** dùng khái niệm **correspondence rule** của ISO/IEC/IEEE 42010 làm ràng buộc nhất quán liên tầng, thay vì tự phát minh. Mỗi cặp thực thể "trùng tên khác tầng" phải có một correspondence tường minh mang confidence.

### II.9 Bốn lớp truy vấn — ánh xạ trực tiếp từ Sillito

Đây là **giao diện thiết kế** của graph. Mỗi lớp cần chiến lược index khác nhau.

| Lớp | Sillito | Hình dạng | Ví dụ | Yêu cầu index |
|---|---|---|---|---|
| **L1 — Định vị** | Nhóm 1 (5 câu) | Tìm 1 node | "Kiểu nào biểu diễn khái niệm domain này?" | Full-text + vector trên `name`, `docstring`, `Feature`; cần `REALIZES` **hai chiều** |
| **L2 — Láng giềng** | Nhóm 2 (15 câu) | Node + bậc 1 | "Method này được gọi ở đâu?" | Adjacency index chuẩn; cần index **ngược** cho `CALLS`, `IMPORTS`, `TESTS` |
| **L3 — Subgraph** | Nhóm 3 (13 câu) | Subgraph liên thông | "Feature này cài đặt thế nào?", "Điều khiển đi từ A tới B ra sao?" | Path query có giới hạn độ sâu; **đây là nơi cần CPG store theo yêu cầu** |
| **L4 — Liên subgraph** | Nhóm 4 (11 câu) | Quan hệ giữa các subgraph | "Tổng tác động của thay đổi này?", "Ánh xạ UI types ↔ model types?" | Truy vấn **xuyên tầng** + xuyên thời gian. **Đây là nơi KG hợp nhất tạo giá trị** — hiện chưa tool nào phục vụ tốt |

> **[DG, Cao]** Sillito et al. ghi nhận rằng tool hiện có chủ yếu phục vụ L1–L2, và người dùng phải **ghép thủ công** kết quả nhiều tool cho L3–L4. Nếu KG chỉ làm tốt L1–L2 thì nó không hơn gì một IDE index. **Giá trị của thiết kế này nằm ở L4** — và L4 chính là lớp đòi hỏi tầng INTENT, TEST, RUNTIME, EVOLUTION cùng có mặt.

---

## Phần III — Trình tự triển khai đề xuất

**[ĐX, Trung bình]** Thứ tự này tối đa hoá giá trị sớm, đồng thời tránh phải làm lại nền tảng.

| Giai đoạn | Xây gì | Mở khoá lớp truy vấn | Rủi ro nếu làm sai thứ tự |
|---|---|---|---|
| **0. Provenance trước tiên** | Schema `assertion` + bitemporal + `evidence_type` | — | **Bổ sung provenance sau là viết lại toàn bộ.** Đây là lý do nó đứng đầu |
| **1. CODE + EVOLUTION** | Function-level graph + `CodeEntityVersion` + `Snapshot` | L1, L2 | Nếu làm CODE mà chưa có mô hình version, khi thêm lịch sử phải reload toàn bộ |
| **2. TEST** | `TestCase`/`TestRun` tách bạch + `COVERS` từ coverage | L2, một phần L3 | `COVERS` là cạnh đáng tin nhất nối test↔code — có nó sớm thì `TESTS` heuristic bớt quan trọng |
| **3. INFRA** | `state_kind` ba giá trị + `RECONCILES_TO` | L3 | — |
| **4. RUNTIME** | Trace/Span (`PARENT_OF` ≠ `LINKS_TO`) + `MAPS_TO_CODE` | L3, mở đường L4 | Bắt buộc trước khi làm multi-repo |
| **5. INTENT** | ADR, Requirement, Feature + `REALIZES` (inferred) | **L4** | Làm cuối vì đây là tầng phụ thuộc LLM nhiều nhất và có confidence thấp nhất — cần các tầng khác làm bằng chứng đối chiếu |
| **6. Discrepancy** | Phát hiện & hiển thị mâu thuẫn liên tầng | L4 | Chỉ có nghĩa khi đã có ≥2 tầng bằng chứng |

**Nghiệm thu từng giai đoạn:** dùng tập con tương ứng trong 44 câu hỏi Sillito làm test case. Đo **tỉ lệ câu hỏi trả lời được** + precision/recall trên codebase thật.

---

## Bảng tra cứu một trang: nguồn → hệ quả thiết kế

| Nguồn | Điều nguồn nói | Hệ quả thiết kế |
|---|---|---|
| **Sillito et al. 2006/2008** | 44 câu hỏi, phân nhóm theo **đặc tính subgraph** | Bốn lớp truy vấn L1–L4; bộ nghiệm thu cho mọi node/edge type |
| **Sillito et al.** | Câu hỏi người dùng ≠ câu hỏi tool trả lời được | Giá trị KG nằm ở **L4**, không phải L1–L2 |
| **LaToza & Myers 2010** | Nhóm phổ biến nhất = **intent & rationale** | Tầng **INTENT bắt buộc**; `ArchitectureDecision` là node hạng nhất |
| **Letovsky 1987** | **Discrepancy conjecture** là hoạt động comprehension | Node `Discrepancy` first-class; không âm thầm chọn bên |
| **von Mayrhauser & Vans 1995** | Lập trình viên **switching** top-down ↔ bottom-up | `REALIZES` cần index **hai chiều** |
| **SEI Views & Beyond** | Ba viewtype: Module / C&C / Allocation | `Module` ≠ `Component` ≠ `Deployment` — ba lớp node |
| **KDM / ISO 19506** | 4 tầng; package **Source** = truy nguyên về source code | Baseline schema; provenance mức tối thiểu đã chuẩn hoá → mở rộng, đừng phát minh lại |
| **KDM** | Không có test/telemetry/IaC/history | Bốn tầng phải tự thiết kế; định vị đóng góp |
| **FAMIX** | Trade-off **quá mịn ↔ quá thô** (tác giả tự nêu) | **Function là đơn vị nguyên tử**; loại Statement/Expression |
| **CPG (Yamaguchi)** | Hợp nhất trên node statement chung; **schema để mở** | Kiến trúc **hai kho**; trích CPG ở mức nguyên lý, không phải chuẩn |
| **Chikofsky & Cross 1990** | Design recovery cần **thông tin ngoài code** | Kiến trúc đa nguồn; code-only KG = redocumentation |
| **Diehl 2007** | structure / behaviour / evolution | Ba chiều chính (ghi rõ: là **mượn** từ visualization) |
| **Soundiness 2015** | Static analysis **cố ý** unsound với reflection/`eval` | `confidence` bắt buộc trên `CALLS`; vắng mặt ≠ phủ định |
| **Biggerstaff 1994** | Concept assignment = **plausible reasoning** | `REALIZES` không bao giờ là fact → cần `evidence_type=inferred` |
| **Gotel & Finkelstein 1994** | pre-RS ≠ post-RS; pre-RS là phần khó nhất | **Tuyên bố phạm vi**: KG chỉ giải post-RS |
| **K8s API conventions** | `spec` / `status`; vắng condition = **`Unknown`**; `observedGeneration` | Mượn nguyên ngữ nghĩa desired/observed/**unknown** |
| **Terraform** | config / **state (binding)** / thực tế | `state_kind` có **ba** giá trị, không phải hai |
| **OTel** | scatter/gather dùng **span links**, **không** đặt parent | Trace là **DAG**; `PARENT_OF` ≠ `LINKS_TO` |
| **OTel** | Resource + Semantic Conventions | `ServiceInstance`, `Environment`; `sampling_rate` bắt buộc |
| **Hismo 2006** | History = **dãy version**; **tầng thời gian chồng lên cấu trúc** | Tách `CodeEntity` (danh tính) ↔ `CodeEntityVersion` (trạng thái) |
| **Software Heritage** | Merkle DAG 5 tầng; **dedup toàn cục**; origin↔visit↔snapshot | `content_hash` + `Snapshot` node; mẫu tách quan sát khỏi lưu trữ |
| **Git** | **Không lưu rename**; ngưỡng similarity 50% | `RENAMED_TO` luôn có `confidence` + `analysis_config` |
| **PROV-O (W3C Rec)** | Entity / Activity / Agent | Vocabulary provenance chuẩn, suy luận được — đừng tự phát minh |
| **ISO 42010** | **Correspondence rule** | Cơ chế chuẩn cho ràng buộc nhất quán liên tầng |
| **ISO 25010:2023** | 9 đặc tính chất lượng | Chỉ dùng làm **từ vựng** cho `QualityRequirement` |

---

## Ba điều phải nói thẳng trong mọi trình bày về thiết kế này

1. **Taxonomy bằng chứng là synthesis, không phải chuẩn.** Không nguồn nào định nghĩa năm mức; mỗi mức có tiền lệ độc lập nhưng tổ hợp là của tôi. Và nó nên là **hai chiều trực giao**, không phải một enum.
2. **Phần lớn các cạnh thú vị nhất không phải fact.** `REALIZES`, `DECIDED_BY`, `RENAMED_TO`, và cả `CALLS` trong ngôn ngữ động — tất cả đều là ước lượng. **Một code KG trung thực trông sẽ kém ấn tượng hơn một code KG không trung thực**, vì nó hiển thị confidence thay vì cạnh sạch sẽ. Đó là cái giá phải trả.
3. **Vắng mặt không bao giờ là bằng chứng phủ định.** Không có span, không có cạnh `CALLS`, không có test — không cái nào chứng minh điều tương ứng không tồn tại. Kubernetes đã chuẩn hoá sẵn `Unknown` cho đúng vấn đề này; code KG nên mượn.

---

*Tài liệu đầy đủ kèm khảo sát so sánh, đánh giá nguồn, research gaps và danh mục tài liệu tham khảo đầy đủ: `code-kg-research.md`.*
