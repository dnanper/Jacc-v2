# Cơ sở lý thuyết cho Code Knowledge Graph: Từ software understanding đến mô hình biểu diễn có bằng chứng

**Báo cáo nghiên cứu nền tảng**
Ngày: 07/08/2026
Phạm vi: khảo sát lý thuyết kinh điển → checklist comprehension → vai trò artifact → mô hình graph được suy diễn

---

## Quy ước ký hiệu trong báo cáo

Mỗi luận điểm quan trọng được gắn nhãn nguồn gốc:

| Nhãn     | Ý nghĩa                                                                     |
| -------- | --------------------------------------------------------------------------- |
| **[ĐN]** | Được **định nghĩa trực tiếp** bởi nguồn gốc (tiêu chuẩn hoặc tác giả)       |
| **[DG]** | **Diễn giải** của tôi về nguồn gốc — nguồn không nói y như vậy              |
| **[TH]** | **Tổng hợp (synthesis)** từ nhiều nguồn — không nguồn nào phát biểu toàn bộ |
| **[ĐX]** | **Đề xuất mới** của nghiên cứu này — chưa có nguồn hậu thuẫn                |

Mức độ chắc chắn: **Cao** (tiêu chuẩn/paper nói rõ) · **Trung bình** (suy ra hợp lý, có thể tranh luận) · **Thấp** (giả thuyết cần kiểm chứng thực nghiệm).

---

## 1. Executive summary

**Kết luận trung tâm: không tồn tại một framework kinh điển đơn lẻ nào định nghĩa "hiểu đầy đủ một hệ thống phần mềm".** Có ít nhất **sáu dòng lý thuyết độc lập**, ra đời từ những cộng đồng khác nhau, với **mục tiêu khác nhau**, và các tác giả gốc chưa từng hợp nhất chúng. Bất kỳ nỗ lực nào tạo ra "một taxonomy chuẩn" bằng cách trộn chúng lại đều là synthesis của người viết, không phải cơ sở lý thuyết đã được công nhận. **[TH, Cao]**

Sáu dòng đó là:

1. **Architecture description** — ISO/IEC/IEEE 42010, Kruchten 4+1, SEI Views & Beyond, Rozanski & Woods. Trả lời: _cần mô tả những cấu trúc nào, cho ai?_
2. **Program comprehension (nhận thức)** — Brooks, Pennington, Letovsky, von Mayrhauser & Vans, Sillito et al., LaToza & Myers. Trả lời: _con người thực sự hỏi gì khi đọc code?_
3. **Program representation / reverse engineering** — Chikofsky & Cross, PDG/SDG, FAMIX, Code Property Graph, OMG KDM (ISO/IEC 19506). Trả lời: _biểu diễn code thành cấu trúc dữ liệu như thế nào?_
4. **Traceability** — Gotel & Finkelstein, Ramesh & Jarke. Trả lời: _nối intent với implementation ra sao, và tại sao nó khó?_
5. **Software visualization** — Diehl (structure / behaviour / evolution). Trả lời: _có mấy chiều trực giao cần trình bày?_
6. **Software quality** — ISO/IEC 25010. Trả lời: _cần lập luận về những thuộc tính chất lượng nào?_ (**Đây KHÔNG phải mô hình comprehension** — dùng nhầm nó làm taxonomy hiểu biết là lỗi phổ biến.)

**Phát hiện quan trọng nhất cho luận văn:** artifact gần nhất với "một schema graph chuẩn quốc tế cho phần mềm hiện hữu" là **OMG KDM = ISO/IEC 19506:2012** — nó biểu diễn source code, giao diện, dữ liệu bền vững, môi trường vận hành, cấu trúc kiến trúc và build trong **một metamodel duy nhất, 4 tầng**. Nhưng KDM được thiết kế cho _legacy modernization_ và **không** bao phủ: kết quả thực thi test, telemetry runtime (trace/metric/log), Infrastructure-as-Code, và lịch sử tiến hoá. Đây chính là khoảng trống mà một Code Knowledge Graph hiện đại phải lấp — và là chỗ đứng học thuật hợp lệ cho một luận văn. **[TH, Cao]**

**Về phương pháp thiết kế graph:** báo cáo này khuyến nghị thiết kế **question-driven** thay vì schema-driven. Lý do có nguồn: Sillito, Murphy & De Volder (2006/2008) đã phân loại 44 loại câu hỏi lập trình viên thực sự hỏi, và **họ phân loại chúng dựa trên đặc tính của subgraph cần duyệt để trả lời** — tức là chính các tác giả gốc đã coi codebase như một đồ thị thực thể–quan hệ và phân tầng câu hỏi theo phạm vi subgraph. Đây là cầu nối trực tiếp nhất từ lý thuyết comprehension sang thiết kế graph mà tôi tìm được trong tài liệu. **[ĐN cho việc phân loại; DG cho việc dùng nó làm requirement thiết kế, Cao]**

**Về evidence taxonomy (DECLARED / IMPLEMENTED / VERIFIED / OBSERVED / HISTORICAL):** đây **không phải taxonomy có sẵn**. Không tiêu chuẩn nào định nghĩa năm mức này. Đó là **synthesis** của tôi. Tuy nhiên nó _có thể bảo vệ được_ vì mỗi mức tương ứng một phân biệt đã được chuẩn hoá độc lập ở nơi khác (chi tiết §8). Luận văn phải trình bày nó đúng như vậy. **[TH, Trung bình]**

**Khuyến nghị evolution modeling:** phương án lai — _stable logical entity + version node chỉ cho thực thể thay đổi + ChangeEvent + snapshot content-addressed kiểu Merkle DAG_. Cảnh báo bắt buộc: **Git không lưu thông tin rename**; mọi cạnh `RENAMED_TO` đều là suy luận heuristic dựa trên ngưỡng tương đồng, mặc định 50%. Không được biểu diễn nó như fact. **[ĐN cho hành vi Git; ĐX cho phương án lai, Cao/Thấp]**

---

## 2. Research question

Ba câu hỏi được trả lời tuần tự, không giả định trước schema:

> **RQ1.** Theo các lý thuyết kinh điển và được sử dụng rộng rãi, cần hiểu những khía cạnh nào để có được sự hiểu biết đầy đủ về một hệ thống phần mềm hoặc codebase?

> **RQ2.** Những khía cạnh đó có thể được chuyển thành các câu hỏi comprehension cụ thể như thế nào?

> **RQ3.** Các tài nguyên của một sản phẩm phần mềm cần được biểu diễn và liên kết ra sao để trả lời các câu hỏi đó?

**Giả định phương pháp luận được tuyên bố rõ:** báo cáo **không** giả định phần mềm gồm đúng N layer hay N view. ISO/IEC/IEEE 42010 — tiêu chuẩn quốc tế duy nhất về architecture description — **cố ý không quy định một tập view cố định**; nó chỉ quy định _yêu cầu về cấu trúc_ của một architecture description, và nói rõ rằng nó không đặc tả process, phương pháp, model, notation hay tool nào. Do đó bất kỳ ai tuyên bố "kiến trúc gồm đúng 4 view" đều đang trích một _framework cụ thể_ (ví dụ Kruchten), không trích tiêu chuẩn. **[ĐN, Cao]**

---

## 3. Các lý thuyết kinh điển (Phần A)

### 3.1 Nhóm A — Architecture description

#### 3.1.1 ISO/IEC/IEEE 42010

- **Trạng thái:** International Standard. Ấn bản hiện hành **ISO/IEC/IEEE 42010:2022**, "Software, systems and enterprise — Architecture description" (Edition 2, 11/2022). Thay thế 42010:2011, vốn thay thế IEEE 1471:2000. Bản 42010:2011 hiện ở trạng thái _Inactive-Reserved_ tại IEEE.
- **Nội dung được định nghĩa:** tiêu chuẩn quy định yêu cầu cho **architecture description (AD)**, **architecture description framework (ADF)**, **architecture description language (ADL)**, **architecture viewpoint** và **model kind**. Nó phân biệt nghiêm ngặt _architecture_ (bản chất của thực thể) với _architecture description_ (sản phẩm công việc mô tả kiến trúc đó). **[ĐN, Cao]**
- **Khái niệm cốt lõi hữu ích cho graph:** _Entity of Interest_, _stakeholder_, _concern_, _architecture viewpoint_ (quy ước để dựng một view), _architecture view_, _model kind_, _correspondence rule_ (đảm bảo nhất quán giữa các view), _architecture decision_ và _rationale_.
- **Giới hạn khi làm nền lý thuyết cho code understanding:** 42010 nói về _mô tả_ kiến trúc, không nói về _code_. Nó không có khái niệm function, call graph, test, hay telemetry. Nó cũng không đặc tả định dạng lưu trữ. Dùng 42010 làm khung tổ chức viewpoint thì hợp lệ; dùng nó làm metamodel cho codebase thì sai phạm vi. **[DG, Cao]**
- **Giá trị lớn nhất cho luận văn:** khái niệm **correspondence rule** — đây là cơ sở chuẩn để nói "các layer trong graph phải có ràng buộc nhất quán chéo", thay vì tự phát minh.

#### 3.1.2 Kruchten 4+1 View Model (1995)

- Bài báo IEEE Software 12(6):42–50, DOI `10.1109/52.469759`.
- **[ĐN]** Tổ chức mô tả kiến trúc bằng **năm view đồng thời**: _logical_ (object model của thiết kế), _process_ (concurrency và đồng bộ), _development_, _physical_, cộng _scenarios_ dùng để minh hoạ và kiểm chứng bốn view kia.
- **Mức độ phổ biến:** rất cao (2000+ trích dẫn); là view model được trích nhiều nhất trong ngành.
- **Hạn chế:** ra đời 1995, giả định phát triển tập trung, đơn hệ. Không có view nào cho dữ liệu bền vững, cho vận hành, cho quan sát runtime, hay cho tiến hoá. Kruchten cũng ghi nhận có thể thay logical view bằng ER diagram cho hệ thống data-driven — tức chính tác giả cũng coi tập view là _có thể thay thế_, không cố định. **[ĐN, Cao]**

#### 3.1.3 SEI — _Documenting Software Architectures: Views and Beyond_ (Clements et al.)

- **[ĐN]** Đơn vị cơ bản của tài liệu kiến trúc là **viewtype** — đặc tả loại thông tin cần cung cấp trong một view. Có **ba viewtype cơ bản**:
  - **Module viewtype** — đơn vị _implementation_. Styles: decomposition, uses, generalization, layers.
  - **Component-and-Connector (C&C) viewtype** — các phần tử _runtime_ và tương tác. Styles: client-server, pipe-and-filter, publish-subscribe, shared-data, peer-to-peer, communicating-processes.
  - **Allocation viewtype** — ánh xạ phần mềm sang môi trường phi-phần-mềm. Styles: deployment, install, work assignment.
- **Đây là phân biệt quan trọng nhất trong toàn bộ báo cáo cho việc thiết kế graph.** Module ≠ Component ≠ Deployment node là ba loại thực thể khác nhau về bản chất, được chính tác giả gốc tách bạch. Việc nhiều công cụ code-graph hiện nay gộp chúng lại (vì cùng tên "service") là một lỗi mô hình hoá có thể chỉ đích danh nguồn gốc. **[ĐN cho phân biệt; DG cho việc gọi đó là lỗi, Cao]**
- Ấn bản 2 (Addison-Wesley, 2011, SEI Series in Software Engineering).

#### 3.1.4 Rozanski & Woods — Viewpoints and Perspectives

- **[ĐN]** Catalogue **7 viewpoint** (ấn bản 2): _Context, Functional, Information, Concurrency, Development, Deployment, Operational_ — và một catalogue riêng các **perspective** cắt ngang: Security, Performance & Scalability, Availability & Resilience, Evolution, Location, Development Resource, Internationalization, Regulation, Usability, Accessibility.
- Các tác giả tự mô tả bộ viewpoint của mình là **mở rộng và tinh chỉnh bộ 4+1 của Kruchten**: đổi tên Logical/Process/Physical, và **bổ sung Information và Operational**. Ấn bản 2 thêm Context viewpoint và được cập nhật để tương thích thuật ngữ ISO 42010.
- **Giá trị:** đây là bộ viewpoint duy nhất trong nhóm kinh điển có **Operational viewpoint** (cài đặt, migration, quản trị, hỗ trợ) — tức là dòng lý thuyết kiến trúc _có_ chạm tới vận hành, chỉ là ở mức tài liệu chứ không phải telemetry. **[ĐN, Cao]**
- **Trạng thái:** sách chuyên ngành được dùng rộng rãi, **không phải tiêu chuẩn**. ISBN 0321112296 (ấn bản 1) / 032171833X (ấn bản 2).

#### 3.1.5 Ghi chú về C4 model

C4 (Simon Brown) rất phổ biến trong công nghiệp nhưng **không phải tiêu chuẩn, không qua peer review, không có metamodel hình thức được công bố qua kênh học thuật**. Có thể trích như _industry practice_, **không nên** dùng làm cơ sở lý thuyết của luận văn. **[DG, Cao]**

---

### 3.2 Nhóm B — Program comprehension (mô hình nhận thức)

Đây là dòng lý thuyết trả lời câu hỏi _con người xây dựng hiểu biết như thế nào_, và do đó xác định **truy vấn nào graph phải phục vụ**.

#### 3.2.1 Các mô hình nhận thức nền tảng

von Mayrhauser & Vans (IEEE _Computer_ 28(8):44–55, 1995) khảo sát và so sánh **sáu mô hình** comprehension:

| Mô hình                         | Tác giả                          | Ý tưởng cốt lõi                                               |
| ------------------------------- | -------------------------------- | ------------------------------------------------------------- |
| Bottom-up                       | Shneiderman & Mayer (1979)       | Gom nhóm (chunking) từ statement lên trừu tượng cao           |
| Top-down                        | Brooks (1983)                    | Giả thuyết về domain → xác nhận qua _beacon_ trong code       |
| Programming plans               | Soloway & Ehrlich (1984)         | Kế hoạch lập trình + "rules of discourse"                     |
| Program model / Situation model | Pennington (1987)                | Hai biểu diễn tinh thần: luồng điều khiển vs ngữ nghĩa domain |
| Knowledge-based / inquiry       | Letovsky (1986/1987)             | _Inquiry episode_: hỏi → phỏng đoán → tìm kiếm xác minh       |
| **Integrated Metamodel**        | **von Mayrhauser & Vans (1995)** | Tích hợp cả bốn cái trên                                      |

**[ĐN]** Integrated Metamodel gồm **bốn thành phần**: top-down model (dựa Soloway & Ehrlich), program model và situation model (dựa Pennington), cùng **knowledge base** — nơi chứa thông tin để xây dựng và **chuyển đổi qua lại** giữa các process model. Quan sát thực nghiệm nền tảng: lập trình viên **chuyển đổi thường xuyên** giữa các chế độ, không đi tuyến tính. **[ĐN, Cao]**

**Hệ quả trực tiếp cho thiết kế graph [DG, Trung bình]:** vì con người chuyển đổi liên tục giữa top-down (domain → code) và bottom-up (code → trừu tượng), graph phải **duyệt được hai chiều** giữa tầng intent và tầng code, chứ không chỉ một chiều. Đây là lập luận lý thuyết cho việc cần cạnh `REALIZES` hai chiều với chỉ mục ngược.

Letovsky ghi nhận **năm loại phỏng đoán (conjecture)**: _why_ (vai trò của một đoạn code), _how_ (cách đạt được mục tiêu), _what_ (biến/hàm là gì), _whether_ (một routine có phục vụ mục đích nào đó không), và _discrepancy_ (nghi vấn về mâu thuẫn quan sát được). **[ĐN, Cao]** — Loại _discrepancy_ đặc biệt đáng chú ý: nó là bằng chứng kinh điển cho thấy **xử lý mâu thuẫn là một phần của comprehension**, không phải một tính năng phụ. Đây là cơ sở lý thuyết mạnh cho việc graph phải mô hình hoá mâu thuẫn thay vì im lặng chọn một bên.

#### 3.2.2 Catalogue câu hỏi thực nghiệm — nguồn quan trọng nhất cho RQ2

**Sillito, Murphy & De Volder** — "Questions Programmers Ask During Software Evolution Tasks", FSE-14 (2006), DOI `10.1145/1181775.1181779`; bản mở rộng IEEE TSE 34(4):434–451 (2008).

- **Phương pháp:** hai nghiên cứu định tính, grounded theory. Nghiên cứu 1: 9 sinh viên cao học, làm việc theo cặp, 12 phiên, task thật từ issue tracker của ArgoUML (~60 KLOC). Nghiên cứu 2: 16 lập trình viên công nghiệp, code họ đã quen, 15 phiên, nhiều ngôn ngữ và tool.
- **[ĐN] Kết quả: catalogue 44 loại câu hỏi, chia 4 nhóm.** Điều then chốt: **các tác giả phân nhóm dựa trên đặc tính của subgraph cần xét để trả lời** — họ coi codebase là đồ thị thực thể (method, field) và quan hệ (reference, call):

| Nhóm                                  | Số câu hỏi | Bản chất subgraph                 | Ví dụ                                                                                   |
| ------------------------------------- | ---------- | --------------------------------- | --------------------------------------------------------------------------------------- |
| 1. Finding initial focus points       | 5          | Tìm **một node** khởi đầu         | "Kiểu nào biểu diễn khái niệm domain / phần tử UI này?"                                 |
| 2. Building on those points           | 15         | Node + **các node kề trực tiếp**  | "Method này được gọi ở đâu?", "Kiểu này nằm ở đâu trong cây phân cấp?"                  |
| 3. Understanding a subgraph           | 13         | **Nhiều node + quan hệ cùng lúc** | "Feature này được cài đặt thế nào?", "Điều khiển đi từ đây tới đây bằng cách nào?"      |
| 4. Questions over groups of subgraphs | 11         | **Quan hệ giữa các subgraph**     | "Tổng tác động của thay đổi này là gì?", "Ánh xạ giữa các kiểu UI và kiểu model là gì?" |

- **Quan sát bổ sung có giá trị thiết kế [ĐN]:** các tác giả ghi nhận câu hỏi của lập trình viên **ánh xạ không khớp** với câu hỏi mà tool trả lời được; người dùng phải ghép thủ công kết quả từ nhiều tool, và kết quả thường nhiễu (false positive so với ý định thật). Ví dụ cụ thể trong bài: người tham gia muốn biết "kiểu nào có MEvent làm field", phải dùng reference search, nhận 102 kết quả, và bỏ cuộc.
- **Đây là bằng chứng thực nghiệm gốc cho luận điểm rằng một KG hợp nhất có giá trị hơn tập tool rời rạc.** **[DG, Cao]**

**LaToza & Myers** — "Hard-to-Answer Questions about Code", PLATEAU '10, DOI `10.1145/1937117.1937125`.

- **[ĐN]** Khảo sát 179 lập trình viên chuyên nghiệp → 371 câu hỏi → gom thành **21 nhóm, 94 câu hỏi phân biệt**. Nhóm được báo cáo nhiều nhất liên quan tới **intent và rationale**: code này làm gì, nó _định_ làm gì, và _tại sao_ nó được làm theo cách này.
- Công trình liên quan: LaToza & Myers, "Developers Ask Reachability Questions", ICSE 2010, DOI `10.1145/1806799.1806829` — 460 lập trình viên báo cáo hỏi các câu hỏi kiểu reachability **hơn 9 lần mỗi ngày**.
- **Ý nghĩa nghiêm trọng cho thiết kế graph [DG, Cao]:** nhóm câu hỏi _phổ biến nhất_ (intent/rationale) **không thể trích xuất được từ source code**. Nó chỉ tồn tại trong ADR, commit message, PR discussion, issue — hoặc không tồn tại ở đâu cả. Một code KG chỉ có tầng code sẽ bỏ lỡ đúng loại câu hỏi khó nhất.

#### 3.2.3 Nghiên cứu thực hành

**Maalej, Tiarks, Roehm & Koschke** — "On the Comprehension of Program Comprehension", ACM TOSEM 23(4), Article 31, 2014, DOI `10.1145/2622669`.

- **[ĐN]** Quan sát 28 lập trình viên chuyên nghiệp + khảo sát 1477 người. Kết luận: lập trình viên theo **chiến lược comprehension thực dụng, phụ thuộc ngữ cảnh**; công cụ comprehension chuyên dụng **không được dùng** — nhiều người thậm chí không biết IDE của họ có chức năng đó.
- Công trình liên quan (Roehm et al., ICSE 2012): lập trình viên thường đặt mình vào vai người dùng cuối bằng cách khảo sát giao diện, và **ưu tiên giao tiếp trực tiếp hơn tài liệu**.
- **[DG, Trung bình]** Đây là cảnh báo thực nghiệm cho luận văn: một KG "đúng lý thuyết" nhưng đòi hỏi học một ngôn ngữ truy vấn mới sẽ không được dùng. Điều này ủng hộ hướng KG-làm-backend-cho-LLM hơn là KG-làm-tool-cho-người.

#### 3.2.4 Giới hạn lý thuyết: Concept Assignment Problem

**Biggerstaff, Mitbander & Webster** — "Program Understanding and the Concept Assignment Problem", CACM 37(5):72–82, 1994, DOI `10.1145/175290.175300` (bản hội nghị ICSE '93).

- **[ĐN]** Bài toán khám phá các khái niệm hướng-con-người và gán chúng vào các đối tác hướng-cài-đặt trong một chương trình là **concept assignment problem**. Các tác giả lập luận rằng lời giải **đòi hỏi thành phần suy luận hợp lý mạnh (plausible reasoning)** — tức về bản chất không phải bài toán suy diễn tất định.
- **Đây là nguồn gốc lý thuyết chính xác để giải thích tại sao cạnh `Feature → Code` không bao giờ có thể được coi là fact.** LLM ngày nay làm concept assignment tốt hơn DESIRE năm 1994, nhưng **bản chất bài toán không đổi**: nó vẫn là plausible reasoning, không phải extraction. **[ĐN cho bài toán; DG cho hệ quả LLM, Cao]**

---

### 3.3 Nhóm C — Program representation & reverse engineering

#### 3.3.1 Chikofsky & Cross (1990) — taxonomy nền tảng

IEEE Software 7(1):13–17, DOI `10.1109/52.43044`. **[ĐN]** Định nghĩa và liên hệ **sáu thuật ngữ**: forward engineering, reverse engineering, redocumentation, design recovery, restructuring, reengineering. Mục tiêu tuyên bố của các tác giả là _hợp lý hoá thuật ngữ đang dùng_, không tạo thuật ngữ mới.

Hai phân biệt cần giữ nguyên trong luận văn:

- **Redocumentation** = khôi phục tài liệu đã mất hoặc chưa từng có, ở **cùng mức trừu tượng**.
- **Design recovery** = tái tạo _toàn bộ thông tin cần thiết để một người hiểu đầy đủ_ chương trình — bao gồm **thông tin ngoài code**: domain knowledge, kinh nghiệm, thông tin bên ngoài.

**[DG, Cao]** Nói cách khác: chính Chikofsky & Cross đã ghi nhận từ 1990 rằng **hiểu đầy đủ một hệ thống đòi hỏi thông tin không nằm trong source code**. Đây là chỗ dựa lịch sử tốt nhất cho lập luận rằng code KG phải đa nguồn.

#### 3.3.2 Các biểu diễn chương trình kinh điển

| Biểu diễn                | Nguồn gốc                            | Nội dung                        |
| ------------------------ | ------------------------------------ | ------------------------------- |
| AST                      | Lý thuyết compiler                   | Cấu trúc cú pháp                |
| Control Flow Graph       | Allen (1970)                         | Thứ tự thực thi có thể          |
| Program Dependence Graph | Ferrante, Ottenstein & Warren (1987) | Phụ thuộc dữ liệu + điều khiển  |
| System Dependence Graph  | Horwitz, Reps & Binkley (1990)       | PDG liên thủ tục                |
| Program slicing          | Weiser (1984)                        | Tập câu lệnh ảnh hưởng một điểm |
| Call graph               | —                                    | Quan hệ gọi giữa thủ tục        |

#### 3.3.3 Code Property Graph (CPG)

Yamaguchi, Golde, Arp & Rieck — "Modeling and Discovering Vulnerabilities with Code Property Graphs", IEEE S&P 2014.

- **[ĐN]** Hợp nhất **AST + CFG + PDG** thành một **multigraph có hướng** duy nhất. Cái then chốt cho phép hợp nhất: **statement và predicate có node trong cả ba subgraph**, nên có thể chia sẻ node.
- **[ĐN — cảnh báo quan trọng từ chính tác giả]** Fabian Yamaguchi ghi nhận rằng định nghĩa CPG **rất phóng khoáng**: nó chỉ yêu cầu một số cấu trúc phải được hợp nhất, còn **schema graph để mở**. Hệ quả: **các cài đặt CPG cụ thể khác nhau đáng kể**.
- **[DG, Cao]** Vì vậy: **không thể trích "Code Property Graph" như một schema chuẩn.** Nó là một _ý tưởng kiến trúc_ (hợp nhất nhiều IR trên node chung), không phải một đặc tả. Luận văn nên trích nó ở mức nguyên lý.

#### 3.3.4 FAMIX & Dagstuhl Middle Metamodel

- **FAMIX** (Demeyer, Tichelaar & Ducasse; FAMIX 2.1 tech report, Univ. of Bern, 2001; MSE/FAMIX 3.0, 2011). **[ĐN]** Metamodel **độc lập ngôn ngữ** cho mã nguồn hướng đối tượng: Class, Method, Attribute, Invocation, Inheritance. FAMIX 3.0 là một _họ_ metamodel với các biến thể cho static, dynamic và history. Nền tảng của môi trường Moose.
- **[ĐN — trade-off được chính tác giả nêu]** Bất kỳ code metamodel nào cũng là **đánh đổi giữa quá thô (vô dụng cho nhiều bài toán) và quá mịn (mất tính độc lập ngôn ngữ)**. Đây là căn cứ trực tiếp cho quyết định thiết kế ở §7 về việc có nên đưa Statement/Expression vào graph hay không.
- **Dagstuhl Middle Metamodel** — Lethbridge, Tichelaar & Plödereder, ENTCS 94:7–18 (2004): "A schema for reverse engineering". Nỗ lực tạo schema trung gian chung cho công cụ reverse engineering.

#### 3.3.5 OMG KDM = ISO/IEC 19506:2012 — nguồn quan trọng nhất cho RQ3

- **Trạng thái:** đặc tả OMG, được ISO chấp nhận qua fast-track thành **ISO/IEC 19506:2012**, "Information technology — OMG Architecture-Driven Modernization (ADM) — Knowledge Discovery Meta-Model (KDM)". Được ISO **rà soát và xác nhận còn hiệu lực năm 2025**. Đặc tả OMG: `https://www.omg.org/spec/KDM/`.
- **[ĐN] Phạm vi:** định nghĩa metamodel biểu diễn **tài sản phần mềm hiện hữu, các liên kết giữa chúng, và môi trường vận hành của chúng**. Dùng MOF + XMI. Có sự tương thích giữa KDM Core và RDF.
- **[ĐN] Bốn tầng, và nội dung từng tầng:**

| Tầng                 | Packages                     | Nội dung                                                                                                                                                     |
| -------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Infrastructure**   | Core, kdm, **Source**        | Core patterns; inventory model của artifact; **truy nguyên đầy đủ ngược về source code**; cơ chế mở rộng                                                     |
| **Program Elements** | Code, Action                 | Code: datatype, procedure, class, method, variable (datatype căn chỉnh theo ISO/IEC 11404). Action: hành vi mức thấp, control- và data-flow giữa statement   |
| **Runtime Resource** | Platform, UI, Event, Data    | Môi trường vận hành (OS, middleware, control flow do platform quyết định); giao diện người dùng; sự kiện & chuyển trạng thái; dữ liệu bền vững (file, RDBMS) |
| **Abstractions**     | Conceptual, Structure, Build | Tri thức nghiệp vụ & business rule (căn chỉnh theo OMG SBVR); tổ chức logic thành subsystem/layer/component; **góc nhìn engineering (build)**                |

- **[ĐN] Khái niệm cốt lõi:** _container_ — một thực thể sở hữu các thực thể khác, cho phép biểu diễn hệ thống ở nhiều mức hạt. Có **micro-KDM** làm nền ngữ nghĩa chính xác cho hành vi (tương tự một virtual machine cho KDM). KDM hỗ trợ **phân tích tăng dần**: biểu diễn ban đầu được phân tích, tri thức mới được trích xuất và hiện thực hoá qua **biến đổi KDM→KDM**.
- **Đánh giá cho luận văn [DG, Cao]:**
  - **Điểm mạnh vượt trội:** đây là **artifact duy nhất ở cấp ISO** bao phủ đồng thời code, dữ liệu, UI, môi trường vận hành, cấu trúc kiến trúc, business rule và build — trong một metamodel. Package `Source` cung cấp sẵn cơ chế truy nguyên về vị trí source, tức là **provenance ở mức tối thiểu đã được chuẩn hoá**. Cơ chế extension family/stereotype đã được chứng minh là mở rộng được cho domain mới (ví dụ nghiên cứu mở rộng KDM cho quantum software).
  - **Khoảng trống rõ ràng:** KDM **không có** khái niệm nào cho (a) test case, test run, test result; (b) telemetry runtime — trace, span, metric series, log event; (c) Infrastructure-as-Code khai báo (Terraform, Helm, K8s manifest); (d) lịch sử tiến hoá (commit, PR, release). Điều này dễ hiểu về mặt lịch sử — KDM 1.0 ra 2007, trước Kubernetes (2014), OpenTelemetry (2019), và trước khi IaC phổ biến.
  - **Kết luận:** KDM là **baseline lý thuyết tốt nhất để mở rộng**, không phải để thay thế. Định vị luận văn là "mở rộng KDM về phía verified/observed/historical knowledge" mạnh hơn nhiều so với "đề xuất một schema mới".

#### 3.3.6 Giới hạn nhận thức luận: Soundiness

Livshits et al., "In Defense of Soundiness: A Manifesto", CACM (2/2015).

- **[ĐN]** Trên thực tế, hầu như mọi phân tích tĩnh whole-program có tính chính xác và khả mở đều **không sound**. Chuẩn thực hành là: over-approximate hầu hết các đặc trưng ngôn ngữ, nhưng **cố ý under-approximate một tập con đặc trưng mà giới chuyên môn đều biết** — điển hình là **Java reflection** và **`eval` trong JavaScript**. Một phân tích thực dụng có thể giả vờ `eval` không làm gì, trừ khi phân giải được tham số chuỗi lúc biên dịch. Các tác giả đặt tên cho loại phân tích này là **"soundy"**.
- Bài báo còn có bảng liệt kê nguồn gốc unsoundness theo từng ngôn ngữ, và khuyến nghị cộng đồng phải nêu rõ hệ quả của unsoundness.
- **[DG, Cao] Đây là nguồn học thuật chuẩn để bảo vệ trường `confidence` trên cạnh `CALLS` trong graph.** Không được biểu diễn call graph tĩnh như tập cạnh chắc chắn. Trong Java dùng Spring, Python dùng import động, hay JS dùng dynamic dispatch, tập cạnh CALLS **vừa thiếu vừa thừa** cùng lúc.

---

### 3.4 Nhóm D — Traceability

**Gotel & Finkelstein** — "An Analysis of the Requirements Traceability Problem", ICRE 1994, pp. 94–101, DOI `10.1109/ICRE.1994.292398`.

- **[ĐN]** Dựa trên nghiên cứu thực nghiệm với **hơn 100 người hành nghề**. Đóng góp trung tâm: phân biệt **pre-RS traceability** (từ nguồn gốc nhu cầu đến bản đặc tả yêu cầu) và **post-RS traceability** (từ đặc tả xuống thiết kế/code/test).
- **[ĐN]** Kết luận then chốt: **phần lớn vấn đề bị quy cho "traceability kém" thực ra thuộc về pre-RS traceability**, và các tác giả nêu rõ lý do vì sao **một giải pháp bao trùm là khó xảy ra**.
- **[DG, Cao] Hệ quả cho code KG:** phần lớn công cụ (kể cả các code-graph hiện đại) chỉ giải quyết post-RS. Vấn đề "tại sao yêu cầu này tồn tại", "ai đề xuất", "đánh đổi nào đã được chấp nhận" — thuộc pre-RS và **về cấu trúc là không trích xuất được từ repository**. Đây là ranh giới phạm vi phải tuyên bố trong luận văn.
- Công trình tham chiếu: Ramesh & Jarke, "Toward Reference Models for Requirements Traceability", IEEE TSE 27(1):58–93, 2001.

**Architecture Decision Records:** Nygard (2011), "Documenting Architecture Decisions" — **[ĐN]** template gồm Title, Date, Status (proposed/accepted/deprecated/superseded/rejected), Context, Decision, Consequences. **Trạng thái: blog post của practitioner, không phải tiêu chuẩn.** Tuy nhiên khái niệm _decision log_ được ISO/IEC/IEEE 42010 khuyến nghị, nên có thể neo ADR vào tiêu chuẩn ở mức khái niệm chứ không ở mức format. **[DG, Trung bình]** Biến thể có công bố học thuật: MADR (Markdown ADR) và Y-Statements (Zdun et al.).

---

### 3.5 Nhóm E — Software visualization

**Diehl, S. (2007).** _Software Visualization: Visualizing the Structure, Behaviour, and Evolution of Software._ Springer. ISBN 978-3-540-46504-1 (hardcover 9783540465041; DOI sách `10.1007/978-3-540-46505-8`).

- **[ĐN]** Software visualization bao gồm các phương pháp biểu diễn đồ hoạ những khía cạnh khác nhau của phần mềm: **cấu trúc, sự thực thi, và sự tiến hoá**. Đây là textbook đầu tiên về chủ đề này.
- **[DG, Cao] Tại sao bộ ba này quan trọng bất thường:** nó là bộ phân chiều **trực giao** và **ngắn gọn nhất** trong toàn bộ tài liệu kinh điển — và nó gần như trùng khớp với ba loại tri thức mà một code KG cần: static (structure), dynamic (behaviour/execution), temporal (evolution). Nó cũng là nguồn _gốc_ duy nhất trong nhóm kinh điển đặt **evolution ngang hàng** với structure và behaviour.
- **Hạn chế:** đây là phân loại cho _visualization_, không phải cho _knowledge representation_. Việc mượn nó làm ba chiều của graph là **diễn giải của tôi**, không phải điều Diehl phát biểu. Phải ghi rõ điều này trong luận văn.
- Nguồn liên quan: Maletic, Marcus & Collard (2002), "A Task Oriented View of Software Visualization" — phân loại theo _task_, bổ trợ cho Diehl.

---

### 3.6 Nhóm F — Software quality

**ISO/IEC 25010:2023** — "Systems and software engineering — SQuaRE — Product quality model", ISO reference 78176.

- **[ĐN]** Định nghĩa mô hình chất lượng sản phẩm áp dụng cho sản phẩm ICT và phần mềm, gồm **chín đặc tính** (chia tiếp thành subcharacteristic). Bản 2023 sửa đổi so với 25010:2011 (Annex A của tiêu chuẩn có bảng so sánh) — trong đó **Safety, Interaction Capability và Flexibility** là các đặc tính của ấn bản mới.
- **[DG, Cao] Cảnh báo phạm vi nghiêm trọng:** 25010 là mô hình để **đặc tả, đo lường và đánh giá chất lượng**. Nó **không phải** mô hình về việc hiểu phần mềm. Việc dùng 9 đặc tính của 25010 làm "9 khía cạnh cần hiểu về hệ thống" là **trộn taxonomy khác mục tiêu** — chính điều mà đề bài yêu cầu tránh.
- **Vai trò đúng trong graph:** cung cấp **từ vựng chuẩn hoá** cho node `QualityRequirement` và cho perspective của Rozanski & Woods. Đó là toàn bộ vai trò hợp lệ của nó. Lưu ý: có nguồn liệt kê 8 đặc tính (theo bản 2011) và có nguồn liệt kê 9 (theo bản 2023) — **các nguồn không thống nhất vì trích ấn bản khác nhau**; luận văn phải nêu rõ ấn bản.

---

### 3.7 Nhóm G — Đặc tả kỹ thuật runtime & infrastructure

Nhóm này **không phải "lý thuyết"** — chúng là _đặc tả kỹ thuật chính thức_. Nhưng chúng cung cấp thứ mà nhóm A–F thiếu: **mô hình dữ liệu chuẩn hoá cho tri thức quan sát được và tri thức khai báo về hạ tầng.**

#### 3.7.1 OpenTelemetry

- **[ĐN]** OTel định nghĩa các _signal_: **traces, metrics, logs** (và profiles ở các phiên bản gần đây). Mô hình dữ liệu metric là đặc tả giao thức + semantic convention cho **dữ liệu chuỗi thời gian đã tiền tổng hợp**; nó được thiết kế để dịch không mất ngữ nghĩa từ các định dạng có sẵn — việc dịch từ Prometheus và StatsD được đặc tả tường minh.
- **[ĐN]** Khái niệm **Resource** — tập thuộc tính cố định mô tả nguồn phát telemetry, có bộ Resource Semantic Conventions riêng. Khái niệm **Instrumentation Scope**. Log record có thể mang **trace context fields**, cho phép nối log ↔ trace.
- **[ĐN]** **Semantic Conventions** định nghĩa tập thuộc tính chung, quy định span name và kind, metric instrument và unit, tên/kiểu/ý nghĩa/giá trị hợp lệ của attribute. Có convention cho: General, CI/CD, Cloud Providers, CloudEvents, Database, FaaS, GenAI, HTTP, Messaging, RPC, K8s, Container, Process, Runtime Environment.
- **[ĐN — chi tiết quan trọng cho mô hình hoá]** Trong pattern scatter/gather, span gốc khởi tạo nhiều thao tác hạ nguồn rồi tổng hợp lại; span cuối được **link** tới nhiều thao tác nó tổng hợp. OTel **khuyến nghị KHÔNG đặt parent** trong tình huống này, vì trường parent về mặt ngữ nghĩa biểu diễn quan hệ cha đơn.
- **[DG, Cao] Hệ quả:** cấu trúc trace **không phải cây thuần tuý** — nó là DAG với hai loại cạnh phân biệt (`PARENT_OF` và `LINKS_TO`). Bất kỳ mô hình graph nào gộp chúng lại đều sai đặc tả.
- Bổ trợ: **W3C Trace Context** — chuẩn định dạng lan truyền context.

#### 3.7.2 Kubernetes

- **[ĐN — API Conventions của SIG Architecture]** Theo quy ước, Kubernetes API phân biệt **đặc tả trạng thái mong muốn** của một object (trường lồng `spec`) với **trạng thái của object tại thời điểm hiện tại** (trường lồng `status`).
- **[ĐN]** **Conditions** được thêm để truyền đạt tường minh các thuộc tính mà người dùng/thành phần quan tâm, thay vì bắt suy ra từ quan sát khác. Ý nghĩa của một Condition, một khi đã định nghĩa, **trở thành một phần của API**. Với các condition đã biết, **vắng mặt trạng thái condition phải được diễn giải như `Unknown`**, và thường cho biết reconciliation chưa hoàn tất _hoặc trạng thái tài nguyên chưa quan sát được_.
- **[ĐN]** Trường `observedGeneration` trong status: controller cập nhật mỗi khi thấy generation mới của resource — cho phép phân biệt "đang trong quá trình" với "đã ổn định".
- **[ĐN — nguyên tắc thiết kế Kubernetes]** Status của object phải **tái dựng được 100% bằng quan sát**.
- **[DG, Cao] Hệ quả cho graph:** Kubernetes **đã chuẩn hoá sẵn** phân biệt DECLARED vs OBSERVED, kèm cả cơ chế biểu diễn "chưa biết" (`Unknown`) và "chưa hội tụ" (`observedGeneration` lệch). Code KG nên **mượn nguyên ngữ nghĩa này** thay vì phát minh lại — và nên biểu diễn được cả trạng thái thứ ba: _unknown_, không chỉ _desired_ và _observed_.

#### 3.7.3 Terraform

- **[ĐN — tài liệu HashiCorp]** **Mục đích chính của Terraform state là lưu các _binding_ giữa object trong hệ thống từ xa và resource instance được khai báo trong configuration.** Trước mọi thao tác, Terraform thực hiện **refresh** để cập nhật state theo hạ tầng thực.
- **[ĐN]** **Drift** là thuật ngữ chỉ tình huống trạng thái thực của hạ tầng khác với trạng thái định nghĩa trong configuration. `terraform plan` đối chiếu desired configuration với real-world state. `-refresh-only` cho phép cập nhật state mà không đề xuất thay đổi configuration.
- **[DG, Cao]** Vậy Terraform có **ba** trạng thái phân biệt, không phải hai: **configuration (khai báo)**, **state file (bản ghi binding, có thể cũ)**, và **hạ tầng thực (quan sát)**. Một code KG mô hình hoá IaC mà chỉ có hai mức sẽ mất một mức. Điều này khác Kubernetes (chỉ spec/status) và cần tách bạch.

#### 3.7.4 Git & Software Heritage

- **[ĐN — hành vi Git]** **Git không lưu tường minh thông tin rename.** Rename được **phát hiện dựa trên độ tương đồng nội dung** khi sinh diff (`git diff`, `git log`). Ngưỡng similarity index mặc định là **50%**, cấu hình qua `-M`/`--find-renames`. `git mv` chỉ là shortcut cho `git rm` + `git add`. Với `git log --follow`, việc theo dấu rename có thể **đứt** nếu khác biệt nội dung vượt ngưỡng, và mặc định không kiểm tra được merge commit.
- **Software Heritage** — Di Cosmo & Zacchiroli (iPRES 2017); Pietri, Spinellis & Zacchiroli, "The Software Heritage Graph Dataset", MSR 2019, DOI `10.1109/MSR.2019.00030`.
  - **[ĐN]** Mô hình dữ liệu là **một Merkle DAG duy nhất**, tổ chức thành **năm tầng logic**: **Content (blob)** → **Directory** → **Revision (commit)** → **Release** → **Snapshot** (toàn bộ trạng thái các branch của một repository). Cạnh nảy sinh tự nhiên: directory entry trỏ tới directory hoặc content; revision trỏ tới directory và revision trước; release trỏ tới revision; snapshot trỏ tới revision và release.
  - **[ĐN]** Dùng hash mật mã bền vững làm định danh node → **deduplication toàn cục**: mỗi blob lưu đúng một lần bất kể bao nhiêu directory trỏ tới; mỗi commit lưu một lần bất kể bao nhiêu repository chứa nó.
  - **[ĐN]** Ngoài Merkle DAG, lưu thêm **crawling information**: mỗi lần thăm một origin, trạng thái đầy đủ được ghi bằng một snapshot node (tái dùng snapshot cũ nếu trạng thái trùng), cùng **ánh xạ ba chiều origin (URL) ↔ visit timestamp ↔ snapshot object**, được thêm vào log append-only.
  - **[DG, Cao] Đây là bằng chứng thực tế ở quy mô hàng tỉ node rằng chiến lược "content-addressed + structural sharing" giải quyết được bài toán lưu trữ lịch sử.** Nó cũng cho thấy cách tách bạch _cái được quan sát_ (visit, timestamp) khỏi _cái được lưu_ (snapshot) — chính là provenance ở mức kiến trúc.

#### 3.7.5 Supply chain: SBOM & provenance

- **SPDX**: phiên bản 2.2.1 được chuẩn hoá thành **ISO/IEC 5962:2021**; SPDX 3.x là bản đặc tả hiện hành, do Linux Foundation phát triển, đang trong quy trình đệ trình cập nhật ISO. Nguồn gốc: license compliance.
- **CycloneDX**: dự án OWASP, được Ecma International chuẩn hoá thành **ECMA-424** (1.6 = ấn bản 1, 6/2024; 1.7 = ấn bản 2, 12/2025). Nguồn gốc: application security; object model bao gồm component, service, dependency, composition, vulnerability.
- **in-toto / SLSA**: framework đặc tả **provenance** — phát biểu về cách artifact được build. Nhiều hệ CI phát SLSA provenance nguyên bản.
- **[DG, Cao]** Đây là các nguồn chuẩn cho cạnh `BUILT_AS`, `PACKAGED_IN`, `DEPENDS_ON` ở mức package, và cho việc gắn provenance có chữ ký vào `BuildArtifact`.

---

### 3.8 Các framework bổ sung hay chồng lấn nhau như thế nào?

|                           | Trả lời câu hỏi                                  | Đơn vị cơ bản                    | Chồng lấn với                                                    | Không nói gì về                      |
| ------------------------- | ------------------------------------------------ | -------------------------------- | ---------------------------------------------------------------- | ------------------------------------ |
| **ISO 42010**             | Mô tả kiến trúc cho ai, gồm gì                   | Viewpoint / View / Concern       | Kruchten, R&W, SEI (đều là _instance_ của 42010)                 | Code, test, runtime                  |
| **Kruchten 4+1**          | Năm góc nhìn nào                                 | View                             | 42010 (là một ADF); R&W (là bản mở rộng)                         | Data, operations, evolution          |
| **SEI Views & Beyond**    | Ba loại cấu trúc nào                             | Viewtype (Module/C&C/Allocation) | Kruchten; KDM Structure package                                  | Test, telemetry, history             |
| **R&W**                   | Bảy viewpoint + perspective cắt ngang            | Viewpoint + Perspective          | Kruchten (tự nhận là mở rộng); ISO 25010 (perspective ≈ quality) | Biểu diễn hình thức                  |
| **Comprehension models**  | Con người hiểu bằng cách nào                     | Mental model / hypothesis        | Không chồng lấn nhóm A — **khác tầng hoàn toàn**                 | Cách biểu diễn dữ liệu               |
| **Sillito / LaToza**      | Con người hỏi gì                                 | Question                         | Là _cầu nối_ giữa comprehension và tool design                   | Cách trả lời                         |
| **KDM (ISO 19506)**       | Biểu diễn tài sản phần mềm hiện hữu              | Container / Element              | SEI (Structure package); FAMIX (Code package)                    | Test result, telemetry, IaC, history |
| **FAMIX / CPG**           | Biểu diễn code                                   | Class/Method/Statement           | KDM Program Elements (mịn hơn)                                   | Mọi thứ ngoài code                   |
| **Traceability**          | Nối intent ↔ implementation                      | Trace link                       | 42010 (rationale); ADR                                           | Cách trích xuất tự động đáng tin     |
| **Diehl**                 | Ba chiều nào cần trình bày                       | Structure/Behaviour/Evolution    | Bao trùm nhóm A+C ở mức chiều                                    | Chi tiết schema                      |
| **ISO 25010**             | Chất lượng nào cần đo                            | Quality characteristic           | R&W perspectives                                                 | Cấu trúc hệ thống                    |
| **OTel / K8s / TF / Git** | Dữ liệu vận hành & lịch sử được chuẩn hoá ra sao | Span/Metric/Resource/Commit      | Lấp khoảng trống của KDM                                         | Ngữ nghĩa domain                     |

**Nhận định tổng hợp [TH, Cao]:** ba nhóm A, C và G **chồng lấn có kiểm soát và có thể xếp tầng**: A quy định _cần mô tả gì_, C quy định _biểu diễn code ra sao_, G quy định _dữ liệu vận hành có dạng gì_. Nhóm B (comprehension) **không chồng lấn** — nó ở tầng khác và đóng vai trò **nguồn requirement**. Nhóm D và F là **cắt ngang**. Đây là cấu trúc quan hệ mà tôi cho là hợp lệ để tổng hợp — nhưng **không tác giả gốc nào phát biểu nó**; đây là synthesis.

---

## 4. So sánh và đánh giá nguồn (Phần B)

| Nguồn                                           | Loại artifact                     | Tính chính thống | Phổ biến (academia / industry) | Phạm vi                              | Hỗ trợ hiểu codebase  | Điểm mạnh                                                               | Điểm thiếu                                                        | Làm nền luận văn?                  |
| ----------------------------------------------- | --------------------------------- | ---------------- | ------------------------------ | ------------------------------------ | --------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------- |
| **ISO/IEC/IEEE 42010:2022**                     | International Standard            | Cao nhất         | Cao / Trung bình               | Kiến trúc system/software/enterprise | Gián tiếp             | Khung viewpoint trung lập; correspondence rule; tách architecture vs AD | Không chạm code; không có metamodel cụ thể                        | **Có** — làm khung tổ chức view    |
| **Kruchten 4+1 (1995)**                         | Peer-reviewed paper               | Cao              | Rất cao / Rất cao              | View model                           | Trung bình            | Ngắn gọn, dễ dạy                                                        | Cũ (1995); thiếu data/ops/evolution                               | Có — nhưng phải nêu hạn chế        |
| **SEI _Views and Beyond_**                      | Sách SEI (Addison-Wesley)         | Cao              | Cao / Trung bình               | Tài liệu kiến trúc                   | **Cao**               | Phân biệt Module/C&C/Allocation — trực tiếp áp dụng cho graph           | Không có test/runtime/history                                     | **Có — ưu tiên cao**               |
| **Rozanski & Woods**                            | Sách chuyên ngành                 | Trung bình-cao   | Trung bình / Cao               | Viewpoint + perspective              | Cao                   | Có Operational viewpoint; perspective cắt ngang                         | Không phải standard; không hình thức hoá                          | Có — bổ trợ                        |
| **von Mayrhauser & Vans (1995)**                | Peer-reviewed (IEEE Computer)     | Cao              | Rất cao / Thấp                 | Mô hình nhận thức                    | Cao (gián tiếp)       | Tích hợp 5 mô hình trước; giải thích switching                          | Không nói gì về biểu diễn dữ liệu                                 | **Có** — làm nền RQ1               |
| **Sillito et al. (2006/2008)**                  | Peer-reviewed (FSE/TSE)           | Cao              | Cao / Thấp                     | 44 câu hỏi thực nghiệm               | **Rất cao**           | Phân loại theo _đặc tính subgraph_ — cầu nối trực tiếp sang graph       | Cỡ mẫu nhỏ; tool năm 2006; task 30–45 phút                        | **Có — ưu tiên cao nhất cho RQ2**  |
| **LaToza & Myers (2010)**                       | Workshop paper (PLATEAU)          | Trung bình       | Trung bình-cao / Thấp          | 21 nhóm, 94 câu hỏi                  | Cao                   | Cho thấy intent/rationale là nhóm phổ biến nhất                         | Workshop, không phải journal; tự báo cáo                          | Có — bổ trợ Sillito                |
| **Maalej et al. (2014)**                        | Peer-reviewed (TOSEM)             | Cao              | Cao / Thấp                     | Thực hành comprehension              | Trung bình            | 28 quan sát + 1477 khảo sát                                             | Không đề xuất mô hình biểu diễn                                   | Có — làm căn cứ thực tiễn          |
| **Biggerstaff et al. (1994)**                   | Peer-reviewed (CACM/ICSE)         | Cao              | Cao / Thấp                     | Concept assignment                   | **Cao**               | Xác lập giới hạn lý thuyết của feature↔code                             | Giải pháp (DESIRE) đã lỗi thời                                    | **Có** — làm căn cứ giới hạn       |
| **Chikofsky & Cross (1990)**                    | Peer-reviewed (IEEE Software)     | Cao              | Rất cao / Trung bình           | Taxonomy 6 thuật ngữ                 | Cao                   | Chuẩn thuật ngữ; design recovery cần thông tin ngoài code               | Chỉ là taxonomy thuật ngữ                                         | **Có** — làm nền thuật ngữ         |
| **OMG KDM / ISO/IEC 19506:2012**                | International Standard + OMG spec | **Cao nhất**     | Trung bình / Thấp              | Metamodel tài sản phần mềm hiện hữu  | **Rất cao**           | Bao phủ rộng nhất ở cấp ISO; có Source traceability; extensible         | Thiếu test/telemetry/IaC/history; adoption công nghiệp thấp; nặng | **Có — ưu tiên cao nhất cho RQ3**  |
| **FAMIX / MSE**                                 | Tech report + tool                | Trung bình       | Trung bình / Thấp              | Code metamodel OO                    | Cao                   | Độc lập ngôn ngữ; nêu rõ trade-off hạt                                  | Thiên OO; ít hỗ trợ metadata & history                            | Có — bổ trợ tầng code              |
| **Code Property Graph (2014)**                  | Peer-reviewed (IEEE S&P)          | Cao              | Cao / Cao (Joern, CodeQL)      | Biểu diễn code hợp nhất              | Cao (mức hàm)         | Ý tưởng hợp nhất trên node chung                                        | **Schema để mở → không phải chuẩn**; không mở rộng ngoài code     | Có — trích ở mức **nguyên lý**     |
| **Dagstuhl Middle Metamodel**                   | Peer-reviewed (ENTCS)             | Trung bình       | Thấp / Rất thấp                | Schema reverse engineering           | Trung bình            | Nỗ lực chuẩn hoá sớm                                                    | Ít được dùng                                                      | Bổ trợ lịch sử                     |
| **Soundiness Manifesto (2015)**                 | CACM Viewpoint                    | Cao              | Cao / Trung bình               | Giới hạn phân tích tĩnh              | **Cao**               | Chuẩn học thuật để biện minh confidence score                           | Là viewpoint, không phải kết quả thực nghiệm                      | **Có** — làm nền §8                |
| **Gotel & Finkelstein (1994)**                  | Peer-reviewed (ICRE)              | Cao              | Cao / Thấp                     | Traceability                         | Cao                   | Pre-RS vs post-RS; nêu rõ giới hạn                                      | Không có giải pháp kỹ thuật                                       | **Có** — làm nền phạm vi           |
| **Diehl (2007)**                                | Sách Springer                     | Trung bình-cao   | Trung bình / Thấp              | Visualization                        | Trung bình            | Bộ ba structure/behaviour/evolution ngắn gọn, trực giao                 | Là phân loại cho _visualization_, không cho KR                    | Có — nhưng phải ghi rõ là mượn     |
| **ISO/IEC 25010:2023**                          | International Standard            | Cao nhất         | Cao / Cao                      | Mô hình chất lượng                   | **Thấp**              | Từ vựng chất lượng chuẩn hoá                                            | **Sai phạm vi nếu dùng làm taxonomy comprehension**               | Chỉ dùng cho `QualityRequirement`  |
| **OpenTelemetry spec**                          | Đặc tả chính thức (CNCF)          | Cao              | Trung bình / **Rất cao**       | Mô hình telemetry                    | Cao (tầng observed)   | Semantic conventions; Resource; scatter/gather links                    | Không có ngữ nghĩa domain; sampling gây thiếu dữ liệu             | **Có** — nền tầng Runtime          |
| **Kubernetes API conventions**                  | Tài liệu chính thức SIG           | Cao              | Trung bình / Rất cao           | Ngữ nghĩa desired/observed           | Cao                   | Chuẩn hoá sẵn desired vs observed vs unknown                            | Chỉ áp dụng cho K8s                                               | **Có** — nền §8                    |
| **Terraform docs**                              | Tài liệu vendor                   | Trung bình       | Thấp / Rất cao                 | State & drift                        | Trung bình            | Tách config / state / thực tế thành 3 mức                               | Vendor-specific                                                   | Có — bổ trợ                        |
| **Software Heritage / MSR 2019**                | Peer-reviewed + hạ tầng vận hành  | Cao              | Trung bình / Trung bình        | Merkle DAG lịch sử                   | Cao (tầng historical) | Bằng chứng ở quy mô tỉ node                                             | Không mô hình hoá ngữ nghĩa code                                  | **Có** — nền §9                    |
| **W3C PROV-O (2013)**                           | W3C Recommendation                | Cao              | Cao / Trung bình               | Ontology provenance                  | Cao (cắt ngang)       | Entity/Activity/Agent trung lập domain; OWL-RL                          | Trừu tượng — cần chuyên biệt hoá                                  | **Có** — nền provenance            |
| **SPDX ISO/IEC 5962:2021 / CycloneDX ECMA-424** | Standards                         | Cao              | Trung bình / Cao               | SBOM                                 | Trung bình            | Chuẩn cho dependency & provenance mức package                           | Không xuống mức code                                              | Có — bổ trợ                        |
| **C4 model**                                    | Industry practice                 | **Thấp**         | Thấp / Cao                     | Sơ đồ kiến trúc                      | Trung bình            | Dễ dùng                                                                 | Không có metamodel hình thức công bố                              | **Không** — chỉ trích như practice |

### 4.1 Ranh giới không được xoá nhoà

Đề bài yêu cầu phân biệt rõ sáu lĩnh vực. Đây là ranh giới, kèm nguồn:

| Lĩnh vực                     | Đối tượng                               | Câu hỏi trung tâm                      | Đại diện                          |
| ---------------------------- | --------------------------------------- | -------------------------------------- | --------------------------------- |
| **Architecture description** | Tài liệu mô tả kiến trúc                | Mô tả cái gì cho ai?                   | ISO 42010, Views & Beyond         |
| **Program comprehension**    | Quá trình nhận thức trong đầu người     | Con người hiểu bằng cách nào?          | von Mayrhauser & Vans, Pennington |
| **Program representation**   | Cấu trúc dữ liệu biểu diễn chương trình | Mã hoá chương trình thành gì?          | AST/CFG/PDG, FAMIX, KDM, CPG      |
| **Software visualization**   | Biểu diễn đồ hoạ                        | Hiển thị thế nào cho người xem?        | Diehl, Maletic et al.             |
| **Reverse engineering**      | Quy trình khôi phục thiết kế            | Từ code suy ra thiết kế bằng cách nào? | Chikofsky & Cross, Biggerstaff    |
| **Software quality**         | Thuộc tính sản phẩm                     | Sản phẩm tốt theo nghĩa nào?           | ISO/IEC 25010                     |

**Vi phạm phổ biến cần tránh [DG, Cao]:**

- Trình bày 4+1 như "tiêu chuẩn ISO" — sai; 4+1 là một view model, ISO 42010 là tiêu chuẩn về _cách_ mô tả.
- Dùng 9 đặc tính ISO 25010 làm "9 khía cạnh cần hiểu" — trộn quality model vào comprehension model.
- Gọi CPG là "chuẩn biểu diễn code" — chính tác giả nói schema để mở.
- Coi cạnh trong call graph tĩnh là fact — mâu thuẫn trực tiếp với soundiness manifesto.
- Gộp `Module` (SEI module viewtype) với `Service` (C&C) với `Deployment` (allocation) vì chúng cùng tên trong repo.

---

## 5. Checklist comprehension có truy nguyên nguồn (trả lời RQ2)

Bảng dưới là **synthesis [TH]**: nó gộp câu hỏi từ nhiều catalogue thực nghiệm và ánh xạ chúng vào các concern do các framework kiến trúc định nghĩa. **Không nguồn nào phát biểu toàn bộ bảng này.** Cột "Nguồn" ghi rõ xuất xứ từng dòng.

### C1 — Mục đích & bên liên quan

| Câu hỏi                                                        | Nguồn                            | Loại |
| -------------------------------------------------------------- | -------------------------------- | ---- |
| Hệ thống này tồn tại để phục vụ ai, giải quyết vấn đề gì?      | ISO 42010 (stakeholder, concern) | [ĐN] |
| Những concern nào của bên liên quan đang chi phối thiết kế?    | ISO 42010                        | [ĐN] |
| Ranh giới hệ thống ở đâu; nó tương tác với hệ thống ngoài nào? | R&W Context viewpoint            | [ĐN] |

### C2 — Từ domain/feature xuống code (concept location)

| Câu hỏi                                                                            | Nguồn                   | Loại |
| ---------------------------------------------------------------------------------- | ----------------------- | ---- |
| Kiểu nào biểu diễn khái niệm domain hoặc phần tử UI này?                           | Sillito Q1              | [ĐN] |
| Text trong thông báo lỗi / phần tử UI này nằm ở đâu trong code?                    | Sillito Q2              | [ĐN] |
| Có code nào tham gia cài đặt hành vi này không?                                    | Sillito Q3              | [ĐN] |
| Có tiền lệ / mẫu tham chiếu cho việc này không?                                    | Sillito Q4              | [ĐN] |
| Feature/concern này được cài đặt như thế nào?                                      | Sillito Q23             | [ĐN] |
| **Giới hạn:** ánh xạ concept→code đòi hỏi plausible reasoning, không phải suy diễn | Biggerstaff et al. 1994 | [ĐN] |

### C3 — Cấu trúc tĩnh

| Câu hỏi                                                     | Nguồn               | Loại |
| ----------------------------------------------------------- | ------------------- | ---- |
| Các thành phần của kiểu này là gì? Kiểu này thuộc kiểu nào? | Sillito Q6, Q7      | [ĐN] |
| Kiểu này nằm ở đâu trong cây phân cấp? Có sibling không?    | Sillito Q8, Q9      | [ĐN] |
| Ai cài đặt interface / method trừu tượng này?               | Sillito Q11         | [ĐN] |
| Hệ thống được phân rã thành module/layer nào?               | SEI Module viewtype | [ĐN] |
| Ánh xạ giữa nhóm kiểu này và nhóm kiểu kia là gì?           | Sillito Q37         | [ĐN] |

### C4 — Phụ thuộc & tác động thay đổi

| Câu hỏi                                                                            | Nguồn                     | Loại |
| ---------------------------------------------------------------------------------- | ------------------------- | ---- |
| Method này được gọi / kiểu này được tham chiếu ở đâu?                              | Sillito Q12               | [ĐN] |
| Instance của class này được tạo ở đâu?                                             | Sillito Q14               | [ĐN] |
| Biến / cấu trúc dữ liệu này được truy cập ở đâu?                                   | Sillito Q15               | [ĐN] |
| Tác động **trực tiếp** của thay đổi này là gì?                                     | Sillito Q42               | [ĐN] |
| Tác động **toàn phần** của thay đổi này là gì?                                     | Sillito Q43               | [ĐN] |
| Thay đổi này có giải quyết trọn vẹn vấn đề không?                                  | Sillito Q44               | [ĐN] |
| **Giới hạn:** call graph tĩnh không sound với reflection / eval / dynamic dispatch | Soundiness Manifesto 2015 | [ĐN] |

### C5 — Hành vi & luồng điều khiển

| Câu hỏi                                                                         | Nguồn               | Loại |
| ------------------------------------------------------------------------------- | ------------------- | ---- |
| Điều khiển đi từ đây tới đây bằng cách nào?                                     | Sillito Q29         | [ĐN] |
| Tại sao điều khiển **không** tới được điểm này?                                 | Sillito Q30         | [ĐN] |
| Đường thực thi nào được chọn trong trường hợp này?                              | Sillito Q31         | [ĐN] |
| Method này được gọi / exception này được ném trong hoàn cảnh nào?               | Sillito Q32         | [ĐN] |
| Method này được gọi vào lúc nào trong quá trình thực thi?                       | Sillito Q13         | [ĐN] |
| Hành vi mà nhóm kiểu này cung cấp chung là gì, phân bố ra sao?                  | Sillito Q25         | [ĐN] |
| Có thể tới X từ Y không (reachability)?                                         | LaToza & Myers 2010 | [ĐN] |
| Các component runtime tương tác qua connector nào?                              | SEI C&C viewtype    | [ĐN] |
| **Chỉ trả lời được bằng runtime:** giá trị đối số lúc chạy là gì?               | Sillito Q19         | [ĐN] |
| **Chỉ trả lời được bằng runtime:** cấu trúc dữ liệu này trông thế nào lúc chạy? | Sillito Q27         | [ĐN] |

### C6 — Dữ liệu & trạng thái

| Câu hỏi                                                     | Nguồn                                       | Loại |
| ----------------------------------------------------------- | ------------------------------------------- | ---- |
| Dữ liệu có thể tới điểm này bằng cách nào?                  | Sillito Q28                                 | [ĐN] |
| Phần nào của cấu trúc dữ liệu được truy cập trong code này? | Sillito Q33                                 | [ĐN] |
| Cách "đúng" để dùng cấu trúc dữ liệu này là gì?             | Sillito Q26                                 | [ĐN] |
| Dữ liệu bền vững nào tồn tại, sở hữu bởi ai, ràng buộc gì?  | R&W Information viewpoint; KDM Data package | [ĐN] |

### C7 — Chất lượng & ràng buộc

| Câu hỏi                                                                         | Nguồn                                            | Loại |
| ------------------------------------------------------------------------------- | ------------------------------------------------ | ---- |
| Yêu cầu chất lượng nào ràng buộc thiết kế (theo đặc tính nào)?                  | ISO/IEC 25010:2023                               | [ĐN] |
| Perspective nào (security, performance, availability, evolution…) cần được xét? | R&W perspectives                                 | [ĐN] |
| Concurrency được xử lý ra sao?                                                  | Kruchten process view; R&W Concurrency viewpoint | [ĐN] |

### C8 — Kiểm chứng (test)

| Câu hỏi                                               | Nguồn                                                 | Loại     |
| ----------------------------------------------------- | ----------------------------------------------------- | -------- |
| Hành vi này đã được test chưa, bằng test nào?         | **Không có nguồn kinh điển** — suy ra từ khoảng trống | **[ĐX]** |
| Làm sao biết object này đã được tạo và khởi tạo đúng? | Sillito Q41                                           | [ĐN]     |
| Test đó đã từng chạy chưa, kết quả gần nhất là gì?    | **[ĐX]**                                              |          |
| Vùng code này có được cover không, ở mức nào?         | **[ĐX]**                                              |          |

> **Phát hiện quan trọng [TH, Cao]:** trong toàn bộ nhóm framework kinh điển (A–F), **gần như không có framework nào coi "trạng thái kiểm chứng" là một khía cạnh của việc hiểu hệ thống**. Sillito chỉ có duy nhất Q41 chạm tới tính đúng đắn. ISO 42010 không có. Views & Beyond không có. KDM không có. Đây là **khoảng trống lý thuyết thực sự**, không phải chỗ tôi bỏ sót nguồn — và là một trong những đóng góp học thuật khả thi nhất của luận văn.

### C9 — Triển khai & vận hành

| Câu hỏi                                                  | Nguồn                               | Loại |
| -------------------------------------------------------- | ----------------------------------- | ---- |
| Phần mềm được ánh xạ vào môi trường tính toán nào?       | SEI Allocation viewtype             | [ĐN] |
| Cài đặt, migration, quản trị, hỗ trợ diễn ra thế nào?    | R&W Operational viewpoint           | [ĐN] |
| Trạng thái **mong muốn** của hạ tầng là gì?              | K8s `spec`; Terraform configuration | [ĐN] |
| Trạng thái **quan sát được** của hạ tầng là gì?          | K8s `status`; Terraform refresh     | [ĐN] |
| Có drift giữa hai trạng thái đó không?                   | Terraform docs (drift)              | [ĐN] |
| Service instance nào đang chạy ở đâu, phát telemetry gì? | OTel Resource semantic conventions  | [ĐN] |

### C10 — Tiến hoá & lý do

| Câu hỏi                                                                                      | Nguồn                                       | Loại |
| -------------------------------------------------------------------------------------------- | ------------------------------------------- | ---- |
| **Code này _định_ làm gì, và _tại sao_ làm theo cách này?** (nhóm được báo cáo nhiều nhất)   | LaToza & Myers 2010                         | [ĐN] |
| Tại sao thứ này lại được làm như vậy (why-conjecture)?                                       | Letovsky 1987                               | [ĐN] |
| Quyết định kiến trúc nào đã dẫn tới cấu trúc hiện tại, với hệ quả gì?                        | ISO 42010 (decision, rationale); Nygard ADR | [ĐN] |
| Khác biệt giữa các file/kiểu tương tự này là gì?                                             | Sillito Q35, Q36                            | [ĐN] |
| Ai đã thay đổi phần này, khi nào, cùng với những gì?                                         | Hismo; Software Heritage                    | [DG] |
| **Giới hạn:** lý do _trước khi_ có bản đặc tả (pre-RS) thường không tồn tại trong repository | Gotel & Finkelstein 1994                    | [ĐN] |

---

## 6. Vai trò của từng loại software artifact (Phần C)

Ký hiệu loại tri thức (theo taxonomy tổng hợp ở §8): **D**=Declared, **I**=Implemented, **V**=Verified, **O**=Observed, **H**=Historical.

| #   | Nguồn artifact                                        | Trả lời checklist | Loại                                    | Entity trích được                                                                                   | Relation trích được                                                 | Độ tin cậy                                                       | **Không thể suy ra chắc chắn**                                                                           |
| --- | ----------------------------------------------------- | ----------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1   | **Source code**                                       | C3, C4, C5, C6    | **I**                                   | File, Module, Class, Interface, Function, Method, Field, Parameter, APIEndpoint (nếu có annotation) | CONTAINS, DECLARES, IMPORTS, CALLS (tĩnh), IMPLEMENTS, READS/WRITES | **Rất cao** cho khai báo; **trung bình** cho CALLS               | Ý định; hành vi thực tế; cạnh động qua reflection/DI/eval (soundiness)                                   |
| 2   | **Comments / docstrings**                             | C1, C2, C10       | **D** (được viết) — nhưng gắn với **I** | DocFragment                                                                                         | DOCUMENTED_BY                                                       | **Thấp–trung bình**                                              | Comment có thể **lỗi thời hoặc sai**; không có cơ chế nào đảm bảo đồng bộ với code                       |
| 3   | **README / technical docs**                           | C1, C2, C9        | **D**                                   | Document, DocumentSection, Feature (được nêu tên)                                                   | DESCRIBES, MENTIONS                                                 | Thấp–trung bình                                                  | Doc mô tả **ý định**, không phải hiện trạng; feature nêu trong README có thể chưa/không còn tồn tại      |
| 4   | **Requirements / user stories / acceptance criteria** | C1, C7, C10       | **D**                                   | Stakeholder, Goal, Requirement, UseCase, Feature, BusinessRule, QualityRequirement                  | SATISFIES (giả định), CONSTRAINED_BY                                | Cao cho _nội dung yêu cầu_; **thấp cho liên kết tới code**       | Liên kết requirement→code phải **recover**, không extract (Gotel & Finkelstein)                          |
| 5   | **API specifications** (OpenAPI/gRPC/GraphQL)         | C3, C5, C6        | **D**                                   | APIEndpoint, Schema, DTO, ExternalSystem                                                            | EXPOSES, CONSUMES, HAS_SCHEMA                                       | **Cao** (máy đọc được, có schema)                                | Spec có thể lệch implementation nếu không sinh tự động; không nói gì về ai gọi thật                      |
| 6   | **Architecture docs & ADR**                           | C1, C7, C10       | **D**                                   | ArchitectureDecision, Component, ExternalSystem, QualityRequirement                                 | DECIDED_BY, CONSTRAINED_BY, SUPERSEDES                              | Cao cho _nội dung quyết định_; trung bình cho hiện trạng         | ADR ghi quyết định **tại thời điểm**; không đảm bảo code tuân thủ                                        |
| 7   | **DB schema & data dictionary**                       | C6                | **D** + **I**                           | Table, Column, Index, Constraint, Entity                                                            | HAS_COLUMN, FOREIGN_KEY, MAPS_TO (ORM)                              | **Rất cao** (schema là fact có thể truy vấn)                     | Ngữ nghĩa nghiệp vụ của cột; dữ liệu thực; ai đọc/ghi (cần phân tích code)                               |
| 8   | **Unit / integration / contract / e2e tests**         | C8, C2, C5        | **D** (định nghĩa)                      | TestSuite, TestCase, TestFixture, ExpectedOutcome                                                   | TESTS, ASSERTS, SETS_UP                                             | Cao cho cấu trúc; **trung bình cho cạnh TESTS**                  | **Test tồn tại ≠ test đã chạy ≠ test pass.** Cạnh TESTS→code thường phải suy luận từ import/mock         |
| 9   | **Manual / external test cases**                      | C8                | **D**                                   | TestCase (manual)                                                                                   | TESTS (heuristic)                                                   | Thấp–trung bình                                                  | Liên kết tới code hầu như luôn là suy luận NLP/LLM                                                       |
| 10  | **Test runs, results, coverage, benchmark**           | C8, C4            | **V**                                   | TestRun, TestResult, CoverageMeasurement, BenchmarkResult                                           | EXECUTED_IN, VERIFIES, COVERS                                       | **Cao** (là dữ kiện đo được)                                     | Coverage đo _dòng được thực thi_, **không đo tính đúng đắn**; benchmark phụ thuộc môi trường             |
| 11  | **Traces, logs, metrics**                             | C5, C9            | **O**                                   | Trace, Span, LogEvent, MetricSeries, MetricObservation, ServiceInstance, Environment                | PARENT_OF, **LINKS_TO** (scatter/gather), OBSERVED_IN, EMITTED_BY   | Cao cho _cái đã quan sát_; **không nói gì về cái chưa quan sát** | Vắng mặt trace **≠** code không chạy (sampling, cửa sổ quan sát, thiếu instrumentation)                  |
| 12  | **Git history, issues, PR, releases**                 | C10, C4           | **H**                                   | Commit, Branch, Tag, PullRequest, Issue, Release, Author                                            | MODIFIES, ADDS, DELETES, MERGES, CLOSES, RELEASED_IN                | **Rất cao** cho commit/diff; **thấp cho RENAMED_TO**             | **Git không lưu rename** — mọi cạnh rename là heuristic ngưỡng ~50%; ý định thật của commit              |
| 13  | **Build files & CI/CD pipelines**                     | C9, C4            | **D**                                   | Pipeline, BuildArtifact, Job, Dependency                                                            | BUILT_AS, DEPENDS_ON, TRIGGERS                                      | Cao                                                              | Pipeline định nghĩa ≠ pipeline đã chạy; dependency resolve động                                          |
| 14  | **Dockerfile / Docker Compose**                       | C9                | **D**                                   | ContainerImage, Service (compose), Volume, Network                                                  | PACKAGED_IN, EXPOSES_PORT, MOUNTS                                   | Cao cho khai báo                                                 | Image thực tế chạy có thể khác (tag `latest`, override); layer content cần SBOM                          |
| 15  | **Kubernetes manifests & Helm charts**                | C9                | **D** (`spec`)                          | Deployment, Pod (template), Namespace, Config, Secret ref                                           | DEPLOYED_AS, DEFINES, SELECTS                                       | Cao cho `spec`                                                   | **`spec` là mong muốn, không phải hiện trạng**; Helm value override làm manifest tĩnh không đủ           |
| 16  | **Terraform / IaC**                                   | C9                | **D** (config) + **O** (state)          | CloudResource, Provider, Module, Config                                                             | PROVISIONS, DEPENDS_ON                                              | Cao cho config; trung bình cho state                             | **Ba mức khác nhau**: config ≠ state file ≠ hạ tầng thực; state có thể cũ nếu chưa refresh               |
| 17  | **Runtime inventory (cluster/cloud)**                 | C9                | **O**                                   | RuntimeResource, Pod (thực), Host, Node, Network, CloudResource                                     | RUNS_ON, OBSERVED_IN                                                | **Cao tại thời điểm quan sát**                                   | Là snapshot; hết hạn nhanh; cần `valid_from`/`valid_to` bắt buộc                                         |
| 18  | **Runbooks, SLO, alerts, incidents**                  | C7, C9, C10       | **D** (SLO, runbook) + **H** (incident) | QualityRequirement (SLO), Alert, IncidentRecord, Runbook                                            | CONSTRAINED_BY, TRIGGERED_BY, AFFECTED                              | Trung bình–cao                                                   | Incident report là **tường thuật của con người** — root cause có thể sai; SLO có thể không được thực thi |
| 19  | **SBOM & build provenance**                           | C4, C9            | **D**/**V**                             | Component (package), License, Vulnerability, Attestation                                            | DEPENDS_ON, HAS_LICENSE, ATTESTS                                    | Cao nếu sinh tại build time                                      | SBOM sinh thủ công lỗi thời ngay; SBOM không xuống mức hàm                                               |

### 6.1 Ba nhận định tổng hợp về artifact

**[TH, Cao]** Ba nguyên tắc rút ra từ bảng trên:

1. **Không artifact nào tự đủ.** Code trả lời C3–C6 nhưng câm về C1 và C10. Doc trả lời C1, C10 nhưng không đáng tin về C3. Telemetry trả lời C5 nhưng chỉ cho những gì đã được instrument và sampled. Đây là bằng chứng thực nghiệm cho luận điểm của Chikofsky & Cross rằng design recovery cần thông tin ngoài code.

2. **Sự vắng mặt không bao giờ là bằng chứng phủ định.** Ba trường hợp riêng biệt, cùng một logic: (a) không có span trong trace **≠** đường code không bao giờ chạy; (b) không có cạnh CALLS tĩnh **≠** không có lời gọi (reflection); (c) không có test **≠** hành vi chưa được kiểm chứng (có thể được cover gián tiếp). Graph phải phân biệt **"không có cạnh"** với **"đã kiểm tra và xác nhận không tồn tại cạnh"** — hai điều này khác nhau về mặt nhận thức luận, và Kubernetes đã chuẩn hoá sẵn mức thứ ba (`Unknown`) cho đúng vấn đề này.

3. **Độ tin cậy của một cạnh phụ thuộc phương pháp trích, không phụ thuộc loại cạnh.** Cạnh `CALLS` từ compiler (Java, tĩnh, không reflection) đáng tin gần như tuyệt đối; cạnh `CALLS` suy ra từ Python với dynamic import gần như là phỏng đoán. Cùng nhãn cạnh. Vì vậy `confidence` và `extraction_method` phải nằm **trên instance của cạnh**, không nằm trên định nghĩa loại cạnh.

---

## 7. Mô hình graph được suy diễn (Phần D)

> **Nguyên tắc thiết kế được tuyên bố [ĐX]:** mỗi node type và edge type phải được biện minh bằng **ít nhất một câu hỏi trong §5** mà nó cần thiết để trả lời. Node không phục vụ truy vấn nào thì bị loại. Đây là hệ quả trực tiếp của việc chọn phương pháp question-driven, và của cảnh báo trade-off hạt mà chính tác giả FAMIX đã nêu.

### 7.1 Kiến trúc sáu tầng + một chiều cắt ngang

```
┌─────────────────────────────────────────────────────────┐
│  PROVENANCE (cắt ngang mọi tầng) — PROV-O aligned       │
└─────────────────────────────────────────────────────────┘
   ↑              ↑            ↑          ↑          ↑
┌────────┐  ┌──────────┐  ┌────────┐  ┌────────┐  ┌────────────┐
│ INTENT │→ │   CODE   │→ │  TEST  │  │RUNTIME │  │   INFRA    │
│  (D)   │  │   (I)    │  │  (V)   │  │  (O)   │  │  (D + O)   │
└────────┘  └──────────┘  └────────┘  └────────┘  └────────────┘
                  ↕            ↕           ↕            ↕
            ┌───────────────────────────────────────────────┐
            │        EVOLUTION (H) — trục thời gian         │
            └───────────────────────────────────────────────┘
```

**Cơ sở của việc chia tầng [TH]:** ba tầng CODE / RUNTIME / EVOLUTION tương ứng bộ ba structure–behaviour–evolution của Diehl (2007) [DG]; INTENT tương ứng architecture description + requirements của ISO 42010 và Gotel & Finkelstein [DG]; INFRA tương ứng Allocation viewtype của SEI cộng KDM Platform package [DG]; TEST là tầng **không có tiền lệ trong nhóm kinh điển** [ĐX] — xem §5/C8.

### 7.2 Quyết định về node: giữ, có điều kiện, loại

#### Tầng CODE

| Node                               | Quyết định                           | Lý do                                                                          |
| ---------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------ |
| Repository, Directory, File        | **Giữ**                              | Cần cho C3; là neo cho `source_location` trong provenance (KDM Source package) |
| Package, Module                    | **Giữ**                              | SEI Module viewtype; Sillito Q5, Q7                                            |
| Component, Service                 | **Giữ — nhưng KHÔNG gộp với Module** | SEI phân biệt Module (implementation) vs C&C (runtime). Xem §10                |
| Class, Interface, Function, Method | **Giữ — đơn vị nguyên tử**           | Sillito Q6–Q18 tập trung ở mức này; FAMIX core cũng ở mức này                  |
| Field, Parameter                   | **Giữ**                              | Sillito Q10, Q15, Q18                                                          |
| Variable (cục bộ)                  | **Có điều kiện**                     | Chỉ giữ nếu cần data-flow query. Bùng nổ số lượng                              |
| **Statement, Expression**          | **LOẠI khỏi graph mặc định**         | Xem lập luận bên dưới                                                          |
| APIEndpoint, EventHandler, Job     | **Giữ**                              | Điểm vào hệ thống; cầu nối tới tầng RUNTIME                                    |
| Entity, DTO, Schema, Table         | **Giữ**                              | C6; KDM Data package; R&W Information viewpoint                                |

**Lập luận loại Statement/Expression [ĐX, Trung bình]:**

Đây là quyết định thiết kế quan trọng nhất và cần biện minh cẩn thận.

- _Lập luận ủng hộ giữ:_ CPG (Yamaguchi et al.) đặt CFG/PDG edge **trên node AST của statement và predicate**; không có statement node thì không có data/control dependence. Sillito Q28–Q33 (data flow, control flow) cần chúng.
- _Lập luận loại:_ (a) chính tác giả FAMIX nêu trade-off giữa quá mịn và quá thô; (b) quy mô — một repository 1 triệu dòng sinh ~10⁷ statement node và nhiều hơn thế về cạnh, khiến truy vấn xuyên tầng (code↔runtime↔evolution) trở nên bất khả thi; (c) tầng statement **thay đổi ở gần như mọi commit**, làm nổ tung tầng EVOLUTION.
- **Đề xuất dung hoà [ĐX]:** kiến trúc **hai kho**. Kho 1 = Knowledge Graph, đơn vị nguyên tử là **Function/Method**, lưu quan hệ xuyên tầng và lịch sử. Kho 2 = **CPG store** riêng (Joern/CodeQL/tree-sitter index), tính **theo yêu cầu** cho một commit cụ thể, không lưu lâu dài. Cầu nối giữa hai kho là `source_location` = `(repo, commit_sha, path, byte_start, byte_end)`.
  Cách này giữ khả năng trả lời C5/C6 mà không phải vật chất hoá tầng statement. **Chưa được kiểm chứng thực nghiệm — mức tin cậy Thấp, cần đo.**

#### Tầng INTENT

| Node                          | Quyết định | Lý do                                                                                             |
| ----------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| Stakeholder, Goal             | **Giữ**    | ISO 42010 định nghĩa tường minh                                                                   |
| Requirement, UseCase, Feature | **Giữ**    | C1, C2; nhưng cạnh xuống code luôn có confidence < 1                                              |
| BusinessRule                  | **Giữ**    | KDM Conceptual package (căn chỉnh SBVR)                                                           |
| ArchitectureDecision          | **Giữ**    | ISO 42010 (decision + rationale); ADR. **Trả lời nhóm câu hỏi phổ biến nhất theo LaToza & Myers** |
| QualityRequirement            | **Giữ**    | ISO/IEC 25010 làm từ vựng; R&W perspectives                                                       |
| ExternalSystem                | **Giữ**    | R&W Context viewpoint                                                                             |
| Document, DocumentSection     | **Giữ**    | Cần làm **neo bằng chứng** — không phải để lưu nội dung, mà để `EXTRACTED_FROM` trỏ vào           |

#### Tầng TEST

Giữ toàn bộ: TestSuite, TestCase, TestFixture, ExpectedOutcome, TestRun, TestResult, CoverageMeasurement, BenchmarkResult, SecurityScanResult.

**Ràng buộc bắt buộc [ĐX]:** `TestCase` (định nghĩa, tầng D) và `TestRun`/`TestResult` (thực thi, tầng V) là **hai node khác nhau**, không được gộp. Đây chính là phân biệt "test definition vs test execution result" mà đề bài yêu cầu, và nó song song hoàn hảo với phân biệt `spec`/`status` của Kubernetes. **Một `TestCase` không có `TestRun` nào là trạng thái hợp lệ và có ý nghĩa** — nó trả lời câu hỏi "test này đã từng chạy chưa".

#### Tầng RUNTIME

| Node                                          | Quyết định                               | Lý do                                                                                      |
| --------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------ |
| Trace, Span                                   | **Giữ**                                  | OTel; C5                                                                                   |
| LogEvent                                      | **Giữ — nhưng chỉ lưu tham chiếu + mẫu** | Khối lượng quá lớn. Lưu `LogTemplate` (log đã chuẩn hoá) trong graph, raw log ở kho khác   |
| MetricSeries                                  | **Giữ**                                  | Định danh chuỗi (name + attribute set)                                                     |
| MetricObservation                             | **KHÔNG lưu trong graph**                | Chuỗi thời gian thuộc về TSDB, không thuộc graph. Graph lưu `MetricSeries` và trỏ tới TSDB |
| ServiceInstance, RuntimeResource, Environment | **Giữ**                                  | OTel Resource; C9                                                                          |

#### Tầng INFRA

Giữ: BuildArtifact, ContainerImage, Pipeline, Cluster, Namespace, Deployment, Pod, Host, Network, Database, Queue, Cache, Config, CloudResource.

**Ràng buộc bắt buộc [ĐX]:** mỗi node hạ tầng phải mang thuộc tính `state_kind ∈ {desired, recorded, observed}`. Ba giá trị, không phải hai — vì Terraform có ba mức (config / state file / thực tế) trong khi Kubernetes có hai (spec / status). Dùng ba giá trị bao được cả hai mô hình.

#### Tầng EVOLUTION

Giữ: Commit, Branch, Tag, PullRequest, Issue, Release, ChangeEvent.
`CodeEntityVersion`: **giữ, nhưng chỉ tạo cho thực thể thực sự thay đổi** — xem §9.

### 7.3 Danh mục cạnh và phương pháp trích xuất

Cột "Phương pháp" là phần quan trọng nhất — nó quyết định `confidence` và quyết định cạnh nào có thể tin.

| Cạnh                        | Từ → Đến                                | Phương pháp trích                                                                         | Độ chắc chắn                                          |
| --------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `CONTAINS`                  | Repo→Dir→File→Class→Method              | **Parser**                                                                                | Tất định                                              |
| `DECLARES`                  | Class → Method/Field                    | **Parser**                                                                                | Tất định                                              |
| `IMPORTS`                   | File/Module → Module                    | **Parser** (tĩnh) / **runtime** (import động)                                             | Tất định cho tĩnh; **cần runtime** cho động           |
| `CALLS`                     | Function → Function                     | **Compiler/type resolver**; degrade thành heuristic khi có reflection/DI/dynamic dispatch | **Soundy** — bắt buộc gắn confidence                  |
| `INHERITS` / `IMPLEMENTS`   | Class → Class/Interface                 | **Parser + type resolver**                                                                | Tất định (ngôn ngữ tĩnh); heuristic (duck typing)     |
| `READS` / `WRITES`          | Function → Field/Table                  | **Static analysis** (data flow) hoặc **SQL parsing**                                      | Static: soundy. ORM: heuristic                        |
| `TRANSFORMS`                | Function → DTO/Schema                   | **Heuristic hoặc LLM**                                                                    | Thấp                                                  |
| `PUBLISHES` / `CONSUMES`    | Component → Queue/Topic                 | **Config + static** cho tên topic tĩnh; **runtime** cho topic động                        | Trung bình. **Runtime là nguồn đáng tin nhất**        |
| `REALIZES`                  | Code → Feature/Requirement              | **LLM / IR-based recovery**                                                               | **Thấp — concept assignment problem**                 |
| `SATISFIES`                 | Component → QualityRequirement          | **Tài liệu bên ngoài** hoặc suy luận                                                      | Thấp                                                  |
| `TESTS`                     | TestCase → Function                     | **Static** (import/mock/naming) hoặc **coverage instrumentation**                         | Static: trung bình. **Coverage: cao**                 |
| `VERIFIES`                  | TestResult → ExpectedOutcome            | **Test report parsing**                                                                   | Cao                                                   |
| `COVERS`                    | CoverageMeasurement → Function/Line     | **Runtime instrumentation**                                                               | **Cao — đây là cạnh đáng tin nhất nối test↔code**     |
| `EXECUTED_IN`               | TestRun → Environment                   | **CI metadata**                                                                           | Cao                                                   |
| `OBSERVED_IN`               | Span/Log → Environment                  | **OTel Resource attributes**                                                              | Cao                                                   |
| `PARENT_OF`                 | Span → Span                             | **OTel**                                                                                  | Cao                                                   |
| `LINKS_TO`                  | Span → Span                             | **OTel span links** (scatter/gather)                                                      | Cao — **phải tách khỏi `PARENT_OF`**                  |
| `MAPS_TO_CODE`              | Span → Function                         | **Instrumentation metadata** (code.function attribute) hoặc heuristic tên                 | Cao nếu auto-instrument; **thấp nếu suy từ tên span** |
| `BUILT_AS`                  | Commit → BuildArtifact                  | **CI metadata / SLSA provenance**                                                         | Cao (có chữ ký thì rất cao)                           |
| `PACKAGED_IN`               | BuildArtifact → ContainerImage          | **Docker/OCI metadata + SBOM**                                                            | Cao                                                   |
| `DEPLOYED_AS`               | ContainerImage → Deployment             | **K8s manifest (`spec`)**                                                                 | Cao — nhưng là **desired**                            |
| `RUNS_ON`                   | Pod → Host                              | **K8s `status` / cluster API**                                                            | Cao — là **observed**, có `valid_from`/`valid_to`     |
| `DEPENDS_ON`                | Package → Package                       | **Lock file / SBOM**                                                                      | Rất cao (lock file); trung bình (manifest có range)   |
| `MODIFIES`/`ADDS`/`DELETES` | Commit → File/Entity                    | **Git diff + AST diff**                                                                   | File-level: tất định. Entity-level: cần AST diff      |
| `NEXT_VERSION`              | EntityVersion → EntityVersion           | **AST diff + matching**                                                                   | Cao khi không rename                                  |
| `RENAMED_TO`                | Entity → Entity                         | **Heuristic tương đồng**                                                                  | **Thấp — Git không lưu rename**                       |
| `DOCUMENTED_BY`             | Code → DocumentSection                  | **Docstring parsing** (cao) hoặc **LLM matching** (thấp)                                  | Phân hoá mạnh                                         |
| `EXTRACTED_FROM`            | Bất kỳ assertion → Artifact             | **Do extractor sinh**                                                                     | Tất định (metadata hệ thống)                          |
| `CONSTRAINED_BY`            | Component → QualityRequirement/SLO      | **Tài liệu / SLO config**                                                                 | Trung bình                                            |
| `DECIDED_BY`                | Component/Design → ArchitectureDecision | **ADR parsing + LLM linking**                                                             | Thấp–trung bình                                       |

### 7.4 Bảng phân loại theo nguồn tri thức

| Nhóm                            | Cạnh                                                                  | Đặc điểm nhận thức luận                                                  |
| ------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Tất định (parser/compiler)**  | CONTAINS, DECLARES, IMPORTS(tĩnh), INHERITS, IMPLEMENTS               | Có thể coi là fact trong phạm vi một commit cụ thể                       |
| **Soundy (static analysis)**    | CALLS, READS, WRITES, data/control dependence                         | **Vừa thiếu vừa thừa**. Bắt buộc gắn confidence + tên analyzer + version |
| **Cần runtime instrumentation** | COVERS, OBSERVED_IN, RUNS_ON, MAPS_TO_CODE, PUBLISHES/CONSUMES(động)  | Chính xác cho _cái đã quan sát_; **im lặng về cái chưa quan sát**        |
| **Cần heuristic hoặc LLM**      | REALIZES, TRANSFORMS, DECIDED_BY, DOCUMENTED_BY(suy luận), RENAMED_TO | **Không bao giờ là fact.** Concept assignment problem                    |
| **Cần tài liệu bên ngoài**      | SATISFIES, CONSTRAINED_BY, quan hệ Stakeholder–Goal                   | Không tồn tại trong repository (pre-RS traceability)                     |

---

## 8. Evidence và provenance

### 8.1 Đánh giá tính hợp lý của taxonomy DECLARED / IMPLEMENTED / VERIFIED / OBSERVED / HISTORICAL

**Tuyên bố rõ ràng: đây KHÔNG phải taxonomy có sẵn.** Tôi đã tìm và **không tìm thấy tiêu chuẩn hay công trình kinh điển nào định nghĩa đúng năm mức này**. Nó là **synthesis [TH]**.

Tuy vậy, nó _có thể bảo vệ được về mặt học thuật_, vì **mỗi mức tương ứng một phân biệt đã được chuẩn hoá hoặc công bố độc lập ở nơi khác**:

| Mức             | Tiền lệ độc lập có nguồn                                                                                                      | Loại              |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| **DECLARED**    | ISO 42010 architecture description (mô tả ≠ kiến trúc); Kubernetes `spec`; Terraform configuration; requirement specification | [ĐN ở từng nguồn] |
| **IMPLEMENTED** | KDM Program Elements layer; FAMIX core; AST/CFG/PDG                                                                           | [ĐN]              |
| **VERIFIED**    | **Không có tiền lệ trong nhóm kinh điển** — gần nhất là ISO/IEC/IEEE 29119 (test documentation) và khái niệm coverage         | **[ĐX]**          |
| **OBSERVED**    | Kubernetes `status` ("phải tái dựng được 100% bằng quan sát"); OTel signals                                                   | [ĐN]              |
| **HISTORICAL**  | Hismo (history as first-class entity); Software Heritage Merkle DAG; Diehl "evolution"                                        | [ĐN]              |

**Đánh giá trung thực:**

- **Điểm mạnh:** năm mức này **trực giao thực sự** — một assertion có thể tồn tại ở nhiều mức đồng thời (một cạnh CALLS có thể vừa IMPLEMENTED vừa OBSERVED), và **sự bất đồng giữa các mức chính là thông tin có giá trị nhất** trong graph. Điều này khớp với "discrepancy conjecture" của Letovsky — loại phỏng đoán mà chính ông ghi nhận là một hoạt động comprehension riêng.
- **Điểm yếu 1:** ranh giới DECLARED/IMPLEMENTED nhoè ở IaC. Một Kubernetes manifest trong repo vừa là code (được commit, versioned) vừa là declaration. Cần quy tắc rõ ràng.
- **Điểm yếu 2:** HISTORICAL **không cùng chiều** với bốn mức kia. Bốn mức đầu là _loại bằng chứng_; HISTORICAL là _chiều thời gian_. Trộn chúng vào một enum là **lỗi mô hình hoá**.
- **Khuyến nghị sửa [ĐX]:** tách thành **hai chiều độc lập**:
  - `evidence_type ∈ {declared, implemented, verified, observed, inferred}` — nguồn gốc bằng chứng. (Thêm `inferred` cho LLM/heuristic — đây là mức thứ năm còn thiếu và quan trọng nhất trong bối cảnh LLM.)
  - `temporal_validity` = cặp `(valid_from, valid_to)` — mọi assertion đều có, không riêng gì lịch sử.

  Cách này loại bỏ điểm yếu 2 và bổ sung chỗ trống cho tri thức do LLM sinh — vốn là loại assertion nguy hiểm nhất và cần đánh dấu rõ nhất.

### 8.2 Metadata cho node/edge — căn chỉnh theo PROV-O

**W3C PROV-O** (W3C Recommendation, 30/04/2013) định nghĩa ba lớp chính: **Entity** (thứ có các khía cạnh cố định), **Activity** (thứ tác động lên hoặc sinh ra entity theo thời gian), **Agent** (thứ chịu trách nhiệm cho một activity, một entity, hoặc hoạt động của agent khác); nối với nhau qua `wasGeneratedBy`, `used`, `wasAssociatedWith`, `wasDerivedFrom`, `wasAttributedTo`, `wasRevisionOf`, `actedOnBehalfOf`. **[ĐN]**

**Ánh xạ đề xuất [ĐX, Trung bình]:**

| Khái niệm code KG                                        | PROV-O                                 |
| -------------------------------------------------------- | -------------------------------------- |
| Assertion (node/edge trong graph)                        | `prov:Entity`                          |
| Lần chạy extractor                                       | `prov:Activity`                        |
| Extractor (parser, analyzer, LLM, instrumentation agent) | `prov:SoftwareAgent`                   |
| Source artifact được đọc                                 | `prov:Entity` + `prov:used`            |
| Con người xác nhận/sửa                                   | `prov:Person` + `prov:wasAttributedTo` |
| Assertion phái sinh từ assertion khác                    | `prov:wasDerivedFrom`                  |

Lợi ích: dùng ontology đã là W3C Recommendation, conform OWL-RL nên **suy luận tự động được**, thay vì tự phát minh vocabulary provenance.

**Schema metadata đầy đủ [ĐX]:**

```yaml
assertion:
  # --- Truy nguyên nguồn (căn chỉnh KDM Source package) ---
  source_artifact: # URI của artifact
  source_location: # {path, line_start, line_end, byte_start, byte_end}
  commit_hash: # SHA — neo bất biến (Git object model)

  # --- Bằng chứng ---
  evidence_type: # declared | implemented | verified | observed | inferred
  extraction_method: # parser | type_resolver | static_analysis |
    # runtime_instrumentation | test_report |
    # config_parse | heuristic | llm | human
  extractor: # tên công cụ  → prov:SoftwareAgent
  extractor_version: # PHẢI có — kết quả static analysis phụ thuộc version
  analysis_config: # cấu hình (vd: ngưỡng -M cho rename detection)
  confidence: # [0,1] — bắt buộc với soundy/heuristic/llm

  # --- Thời gian: BITEMPORAL ---
  valid_from: # thời điểm assertion bắt đầu đúng trong thế giới
  valid_to: # null = còn đúng
  recorded_at: # thời điểm hệ thống ghi nhận
  recorded_until: # null = chưa bị thay thế

  # --- Bối cảnh ---
  environment: # dev | staging | prod | <cluster-id> | null
  observation_window: # với assertion observed: cửa sổ quan sát
  sampling_rate: # với telemetry: PHẢI có để diễn giải sự vắng mặt
```

**Vì sao bitemporal là bắt buộc, không tùy chọn [ĐX, Trung bình]:** hai câu hỏi sau khác nhau và đều cần trả lời được:

- _"Ngày 15/03 hệ thống thực sự thế nào?"_ → cần **valid time**.
- _"Ngày 15/03 chúng ta **tin rằng** hệ thống thế nào?"_ → cần **transaction time**.

Câu thứ hai không phải học thuật suông: nó là câu hỏi bắt buộc trong điều tra sự cố ("lúc đó ta biết gì?") và trong đánh giá độ tin cậy của chính graph. Mô hình chỉ có một trục thời gian không trả lời được. Đây là mô hình bitemporal cổ điển trong CSDL thời gian (Snodgrass; sau này được đưa vào SQL:2011 dưới dạng system-versioned và application-time period tables).

**Lưu ý về `sampling_rate` [ĐX]:** đây là trường ít được chú ý nhưng quyết định. Không có nó, câu "không có span nào cho hàm này" là **vô nghĩa**. Với sampling 1%, việc không thấy span cho một hàm chạy 50 lần/ngày là hoàn toàn bình thường.

### 8.3 Cơ chế biểu diễn: làm sao gắn metadata lên _cạnh_?

Metadata này phải gắn lên **assertion**, kể cả assertion là một cạnh. Ba lựa chọn:

| Cơ chế                                                | Ưu                                                    | Nhược                                                                                               | Khuyến nghị                          |
| ----------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------ |
| **Edge properties** (property graph: Neo4j, Memgraph) | Đơn giản, truy vấn nhanh, tự nhiên                    | Không thể có nhiều assertion mâu thuẫn trên **cùng** cặp (u,v) với cùng nhãn; khó phát biểu về cạnh | Dùng khi mâu thuẫn hiếm              |
| **Reification / Assertion node**                      | Biểu diễn được mâu thuẫn; phát biểu về assertion được | Mỗi cạnh thành 3+ node → nổ kích thước; truy vấn dài dòng                                           | Dùng **chọn lọc** cho cạnh liên tầng |
| **Named graphs / RDF-star**                           | Chuẩn hoá; hợp với PROV-O; giữ được cả hai            | Hệ sinh thái công cụ hẹp hơn; hiệu năng ở quy mô lớn cần đo                                         | Dùng nếu ưu tiên tính chuẩn          |

**Đề xuất [ĐX, Thấp — cần thực nghiệm]:** **lai**. Cạnh nội-tầng có nguồn tất định (CONTAINS, DECLARES) dùng edge properties gọn nhẹ. Cạnh **liên tầng** và cạnh có `evidence_type ∈ {inferred, observed}` được **reify thành `Assertion` node**, vì đây chính là những cạnh có thể mâu thuẫn và cần lập luận về chúng. Đánh đổi kích thước chấp nhận được vì nhóm cạnh này ít hơn nhiều so với cạnh cấu trúc.

### 8.4 Xử lý năm tình huống mâu thuẫn

**Nguyên tắc chung [ĐX]:** graph **không được phép âm thầm chọn một bên**. Mâu thuẫn là _thông tin_, không phải _lỗi dữ liệu_. Cơ sở lý thuyết: "discrepancy conjecture" của Letovsky ghi nhận việc chất vấn mâu thuẫn là một hoạt động comprehension riêng biệt — nghĩa là công cụ hỗ trợ comprehension phải **hiển thị** mâu thuẫn chứ không phải giấu nó.

| Tình huống                                                               | Chẩn đoán                                                                      | Xử lý đề xuất                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Docs mâu thuẫn code**                                               | Hai assertion khác `evidence_type` (declared vs implemented) trên cùng chủ thể | Giữ **cả hai**. Sinh node `Discrepancy` nối hai assertion. **Không tự động ưu tiên code** — nếu doc là spec đã ký (hợp đồng, chuẩn ngành) thì code mới là cái sai. Việc ưu tiên là quyết định của người dùng, không của schema                                                                                                                                                                                                                                                                                                |
| **2. Có cạnh CALLS tĩnh nhưng trace không quan sát thấy**                | **Không phải mâu thuẫn.** Static = _possible_, trace = _actual observed_       | Không tạo Discrepancy. Bổ sung thuộc tính `observed_count = 0` kèm `observation_window` và `sampling_rate`. Chỉ nâng thành cảnh báo "dead code khả nghi" khi: coverage đầy đủ + sampling 100% + cửa sổ đủ dài. **Phải nêu rõ đây là dấu hiệu, không phải kết luận**                                                                                                                                                                                                                                                           |
| **3. Test tồn tại nhưng chưa từng chạy**                                 | **Không phải mâu thuẫn — là trạng thái hợp lệ và có giá trị**                  | `TestCase` không có cạnh tới `TestRun` nào. Đây chính xác là lý do tách TestCase khỏi TestRun. Truy vấn `MATCH (t:TestCase) WHERE NOT (t)-[:EXECUTED_AS]->() ` trả lời trực tiếp một câu hỏi C8                                                                                                                                                                                                                                                                                                                               |
| **4. K8s desired ≠ cluster thực tế**                                     | Đúng nghĩa drift                                                               | Hai node phân biệt `state_kind=desired` và `state_kind=observed`, nối bằng cạnh `RECONCILES_TO` mang `drift_detected`, `observed_generation`, `conditions`. **Mượn nguyên ngữ nghĩa Kubernetes** — kể cả giá trị `Unknown` khi condition vắng mặt. Với Terraform, thêm mức thứ ba `state_kind=recorded` (state file) vì Terraform có ba mức                                                                                                                                                                                   |
| **5. LLM suy luận feature/responsibility không có bằng chứng trực tiếp** | Assertion `evidence_type=inferred`                                             | **Bắt buộc**: `extraction_method=llm`, `extractor` + `extractor_version` (tên model + version), `confidence`, và `used` trỏ tới **chính xác** các artifact đã đưa vào prompt. Assertion inferred **không được dùng làm tiền đề** cho assertion inferred khác nếu không đánh dấu suy giảm confidence — nếu không sẽ có hallucination chồng chất. Nên có cơ chế `human_confirmed: bool` để nâng cấp `inferred → declared` khi có người xác nhận. **Cơ sở: Biggerstaff — concept assignment về bản chất là plausible reasoning** |

---

## 9. Evolution và infrastructure modeling

### 9.1 So sánh ba (bốn) phương án evolution

| Tiêu chí                    | **P1: Copy toàn bộ graph mỗi commit**                                    | **P2: Stable entity + ChangeEvent**                    | **P3: Version node cho entity thay đổi**    | **P4 [ĐX]: Lai P2+P3 + content-addressed snapshot**                                          |
| --------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ | ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **Storage**                 | **Rất tệ** — O(commits × entities). 10k commit × 50k entity = 5×10⁸ node | **Tốt nhất** — O(entities + changes)                   | Tốt — O(entities + changed_versions)        | Tốt — như P3, cộng snapshot manifest nhẹ nhờ structural sharing                              |
| **Query hiện tại**          | Tốt (chọn snapshot mới nhất)                                             | **Tốt nhất** (entity là node hiện tại)                 | Trung bình (phải resolve version mới nhất)  | Tốt (entity giữ con trỏ `current_version`)                                                   |
| **Query lịch sử**           | Tốt                                                                      | **Yếu** — phải replay ChangeEvent                      | **Tốt nhất** — truy cập trực tiếp version   | Tốt                                                                                          |
| **Snapshot reconstruction** | Tầm thường                                                               | **Đắt** — replay từ đầu                                | Trung bình — cần index theo commit          | **Tốt** — snapshot node trỏ trực tiếp tập version (như Software Heritage revision→directory) |
| **Rename/refactoring**      | **Rất tệ** — mất hoàn toàn danh tính                                     | Tốt nếu ChangeEvent ghi được rename                    | Tốt nếu có cạnh `NEXT_VERSION` xuyên rename | Tốt — nhưng vẫn phụ thuộc heuristic                                                          |
| **Branching & merge**       | Tệ — nhân bản theo nhánh                                                 | Trung bình — ChangeEvent cần gắn nhánh                 | Trung bình                                  | **Tốt** — DAG commit tự nhiên hỗ trợ merge, như Git/SWH                                      |
| **Traceability**            | Tốt                                                                      | Trung bình                                             | Tốt                                         | **Tốt nhất** — mỗi version neo vào commit_sha                                                |
| **Temporal consistency**    | Tự nhiên (mỗi snapshot nhất quán)                                        | **Khó** — trạng thái trung gian có thể không nhất quán | Trung bình                                  | Tốt — snapshot đảm bảo nhất quán tại mốc                                                     |
| **Thực tế đã kiểm chứng?**  | Không ai làm ở quy mô lớn                                                | Hismo (Gîrba & Ducasse) — có công bố                   | Phổ biến trong CSDL thời gian               | **Software Heritage vận hành ở quy mô ~tỉ node**                                             |

**Nguồn cho từng phương án:**

- P2 tương ứng tinh thần **Hismo** (Gîrba & Ducasse, JSME 18:207–236, 2006, DOI `10.1002/smr.325`): **[ĐN]** history được mô hình hoá như **thực thể tường minh** — một _history_ là **một dãy các version** — và Hismo **thêm một tầng thời gian lên trên thông tin cấu trúc**, cung cấp hạ tầng chung để biểu đạt và **kết hợp phân tích tiến hoá với phân tích cấu trúc**. Điểm mấu chốt các tác giả nhấn mạnh: các cách tiếp cận trước đó **không dựa trên metamodel tường minh**, khiến kết quả khó tái dùng và so sánh.
- P4 dựa trên **Software Heritage Merkle DAG** — xem §3.7.4.

### 9.2 Khuyến nghị: phương án lai P4

**[ĐX, Trung bình]**

```
CodeEntity  (danh tính ổn định, UUID)
    │ current_version →
    ├─ CodeEntityVersion (chỉ tạo khi nội dung thay đổi)
    │      ├─ content_hash        ← content-addressed, dedup tự nhiên
    │      ├─ introduced_in_commit
    │      ├─ NEXT_VERSION →
    │      └─ (giữ tất cả cạnh cấu trúc tại version đó)
    │
    └─ ChangeEvent (Commit → CodeEntity, kiểu: ADD|MODIFY|DELETE|RENAME|MOVE)
           └─ confidence  ← BẮT BUỘC với RENAME/MOVE

Snapshot (mỗi commit) → trỏ trực tiếp tập CodeEntityVersion "sống"
```

**Lý do chọn:**

1. **Version chỉ cho entity thay đổi** — quan sát thực nghiệm: một commit điển hình chạm rất ít entity so với tổng số. Chi phí lưu trữ tiệm cận P2.
2. **Content-addressed hash** — hai version giống hệt nhau (ví dụ file bị revert) tự động dedup, đúng cơ chế của Software Heritage.
3. **Snapshot node** — giải quyết điểm yếu chính của P2 (snapshot reconstruction đắt) mà không phải copy graph. Đây là cách Software Heritage giải: `revision → directory → content`, mỗi tầng dedup.
4. **ChangeEvent giữ lại** — vì nó là nơi ghi _semantics của thay đổi_ (rename, move, refactor), thứ mà version diff thuần tuý không diễn đạt được.

### 9.3 Cảnh báo bắt buộc về rename

**[ĐN, Cao]** **Git không lưu tường minh thao tác rename.** Nó phát hiện rename dựa trên độ tương đồng nội dung khi sinh diff; ngưỡng mặc định của similarity index là **50%**, cấu hình qua `-M`/`--find-renames`; `git mv` chỉ là shortcut cho `git rm` + `git add`. Việc theo dấu rename bằng `--follow` sẽ **đứt** nếu nội dung thay đổi vượt ngưỡng, và mặc định **không kiểm tra merge commit**.

**Hệ quả cứng cho graph [DG, Cao]:**

- Cạnh `RENAMED_TO` **luôn** phải mang `confidence`, `extraction_method=heuristic`, và `analysis_config` ghi rõ ngưỡng đã dùng.
- Ở mức **entity** (function, class) tình hình còn tệ hơn mức file, vì phải chạy AST diff + matching, và không có công cụ chuẩn nào.
- Việc "theo dấu lịch sử một hàm" — vốn là một trong những truy vấn hấp dẫn nhất của code KG — **về bản chất là ước lượng**, không phải truy hồi. Luận văn phải nói điều này thẳng.
- Refactoring làm đổi cả tên lẫn nội dung (ví dụ Extract Method) sẽ **cắt đứt** chuỗi `NEXT_VERSION` ở mọi phương án. Không có lời giải hoàn hảo.

### 9.4 Multi-repository

**[ĐX, Thấp]** Với nhiều repository:

- `CodeEntity` phải có định danh **toàn cục**, không phụ thuộc repo. Đề xuất: `(repo_origin_url, path, qualified_name)` băm lại, hoặc dùng lược đồ định danh bền vững tương tự **SWHID** của Software Heritage (định danh nội tại tính bằng hash mật mã, kèm qualifier `origin`, `visit`, `anchor`, `path`).
- Quan hệ liên repo (`DEPENDS_ON` giữa service, gọi API chéo repo) **không trích được bằng static analysis nội repo**. Nguồn đáng tin duy nhất: **distributed trace** (OTel) và **API contract** (OpenAPI/protobuf). Đây là lập luận mạnh cho việc bắt buộc có tầng RUNTIME trong hệ đa repo.
- **Thời gian không đồng bộ giữa repo** — commit trong repo A và repo B không có thứ tự toàn phần. Phải dùng timestamp thực + release/deployment làm mốc đồng bộ, không dùng commit order.

### 9.5 Infrastructure modeling

**[ĐX]** Ba quy tắc:

1. **Mỗi tài nguyên hạ tầng có ít nhất hai đại diện** — `desired` (từ manifest/config) và `observed` (từ cluster/cloud API) — cộng `recorded` cho Terraform (state file). Không gộp.
2. **Node observed bắt buộc có `valid_from`/`valid_to`.** Một Pod tồn tại 3 phút; biểu diễn nó không có khoảng hiệu lực là sai.
3. **Cạnh `DEPLOYED_AS` (desired) và `RUNS_ON` (observed) là hai cạnh khác nhau.** Cạnh nối chúng là `RECONCILES_TO`, mang `observedGeneration` và `conditions` theo đúng ngữ nghĩa Kubernetes — bao gồm cả việc vắng mặt condition được diễn giải là `Unknown`, chứ không phải `False`.

---

## 10. Phạm vi và giới hạn: bảy phân biệt không được xoá nhoà

| #   | Phân biệt                                                       | Vì sao không được gộp                                                                                                                                                                                            | Nguồn                                           |
| --- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| 1   | **Static possible behaviour** vs **observed runtime behaviour** | Static over-approximate (đường không bao giờ chạy) đồng thời under-approximate (reflection). Runtime chỉ nói về _mẫu đã quan sát_, phụ thuộc sampling và cửa sổ                                                  | Soundiness Manifesto (CACM 2015); OTel sampling |
| 2   | **Test definition** vs **test execution result**                | Test tồn tại là declaration; test pass là verification. Trạng thái "định nghĩa mà chưa chạy" là hợp lệ và có nghĩa                                                                                               | [ĐX] — song song với `spec`/`status` của K8s    |
| 3   | **Declared infrastructure** vs **observed infrastructure**      | Kubernetes chuẩn hoá tường minh `spec` vs `status`; status phải tái dựng được bằng quan sát. Terraform còn có mức thứ ba (state file)                                                                            | K8s API conventions; Terraform docs             |
| 4   | **Code entity** vs **runtime component**                        | SEI phân biệt Module viewtype (đơn vị implementation) với C&C viewtype (phần tử runtime). Một class có thể không tương ứng component nào; một service có thể gồm nhiều module                                    | Clements et al., _Views and Beyond_             |
| 5   | **Function** vs **trace span**                                  | Một function có thể sinh 0 span (không instrument), 1 span, hay N span (gọi nhiều lần). Span có identity riêng, có thời gian, thuộc một trace                                                                    | OTel data model                                 |
| 6   | **Feature** vs **module**                                       | Feature là khái niệm hướng-con-người; module là đơn vị hướng-cài-đặt. Ánh xạ giữa chúng là **concept assignment problem**, đòi hỏi plausible reasoning. Feature thường **crosscutting** — trải trên nhiều module | Biggerstaff, Mitbander & Webster (CACM 1994)    |
| 7   | **Documentation claim** vs **verified fact**                    | Doc mô tả ý định; không cơ chế nào đảm bảo đồng bộ. Chikofsky & Cross tách _redocumentation_ (phục hồi tài liệu) khỏi _design recovery_ (khôi phục hiểu biết đầy đủ, cần cả thông tin ngoài)                     | Chikofsky & Cross (1990)                        |

**Cảnh báo triển khai [ĐX, Cao]:** cám dỗ lớn nhất là gộp theo **tên**. Trong một repo microservice điển hình có: thư mục `payment-service/` (code entity), một `Deployment` tên `payment-service` (declared infra), một `ServiceInstance` phát telemetry với `service.name=payment-service` (observed runtime), và một "Payment" feature trong tài liệu (intent). **Bốn thực thể khác nhau, cùng một chuỗi ký tự.** Chúng phải là bốn node nối bằng cạnh có confidence, không phải một node. Đây là lỗi mà phần lớn công cụ code-graph thương mại mắc phải.

---

## 11. Research gaps

**Gap 1 — Không có metamodel nào bao phủ đủ sáu tầng. [Tin cậy: Cao]**
KDM (ISO/IEC 19506) là artifact bao phủ rộng nhất ở cấp tiêu chuẩn quốc tế, nhưng thiếu test execution, telemetry, IaC và evolution. Hismo mô hình hoá evolution nhưng chỉ trên cấu trúc code. OTel chuẩn hoá observed nhưng không có ngữ nghĩa domain. **Chưa có công trình nào hợp nhất chúng với ngữ nghĩa bằng chứng tường minh.** Đây là gap trung tâm và là chỗ đứng luận văn mạnh nhất.

**Gap 2 — Code graph cho LLM hầu như không có evidence typing, provenance, hay ngữ nghĩa thời gian. [Tin cậy: Cao]**
Làn sóng công trình 2024–2026 (RepoGraph — ICLR 2025; CodexGraph — NAACL 2025; Code Graph Model — NeurIPS 2025; LocAgent — ACL 2025; GraphCoder — ASE 2024) xây dựng graph từ repository để phục vụ LLM. Chúng được đánh giá bằng **metric tác vụ** (tỉ lệ giải SWE-bench, pass@k, exact match), không bằng **độ phủ câu hỏi comprehension**. Theo khảo sát tôi thực hiện, chúng chủ yếu là graph AST/dependency tĩnh của một snapshot, **không** phân biệt declared/observed, **không** mang provenance, **không** mô hình hoá thời gian. Điều này không phải chỉ trích — mục tiêu của chúng khác — nhưng nó là khoảng trống thật.

**Gap 3 — Không tồn tại benchmark đo "độ phủ câu hỏi comprehension" của một code KG. [Tin cậy: Cao]**
Đây có lẽ là **đóng góp khả thi và có giá trị nhất** cho một luận văn: chuyển 44 câu hỏi của Sillito et al. (và 94 câu hỏi của LaToza & Myers) thành một bộ benchmark truy vấn có thể thực thi trên codebase thật, rồi đo tỉ lệ câu hỏi mà một schema graph cho trước trả lời được, kèm precision/recall. Hiện chưa có công trình nào làm điều này một cách hệ thống, dù cả hai catalogue đều đã tồn tại 15+ năm và được trích dẫn rộng rãi.

**Gap 4 — Concept assignment vẫn mở, và LLM làm nó _khó kiểm chứng hơn_, không dễ hơn. [Tin cậy: Trung bình]**
Biggerstaff et al. (1994) xác lập rằng feature→code cần plausible reasoning. LLM năm 2026 làm việc này với chất lượng cao hơn DESIRE rất nhiều — nhưng **không** cung cấp bằng chứng kiểm chứng được. Nghịch lý: chất lượng tăng làm **giảm** khả năng phát hiện lỗi, vì output nghe hợp lý. Chưa có phương pháp đánh giá độ tin cậy của cạnh `REALIZES` do LLM sinh ở quy mô repository.

**Gap 5 — Truy vấn temporal graph đa repository chưa được nghiên cứu đầy đủ. [Tin cậy: Trung bình]**
Software Heritage chứng minh lưu trữ ở quy mô tỉ node là khả thi, nhưng nó là **archive** (tối ưu cho lưu và truy xuất theo hash), không phải **analytical graph** (tối ưu cho truy vấn quan hệ). Hiệu năng của truy vấn bitemporal xuyên tầng ở quy mô multi-repo là câu hỏi kỹ thuật mở.

**Gap 6 — Tri thức về kiểm chứng vắng mặt trong toàn bộ lý thuyết comprehension kinh điển. [Tin cậy: Cao]**
Như đã nêu ở §5/C8: không framework kinh điển nào coi "hành vi này đã được kiểm chứng chưa" là một khía cạnh của việc hiểu hệ thống. Trong bối cảnh code do AI sinh ra ngày càng nhiều, đây có thể là khía cạnh comprehension **quan trọng nhất** và **ít lý thuyết hoá nhất**. Đề xuất mở rộng lý thuyết comprehension để bao gồm chiều verification là một đóng góp lý thuyết chính đáng.

---

## 12. Kết luận

**Về RQ1.** Không có câu trả lời chuẩn tắc. Sáu dòng lý thuyết độc lập cùng đóng góp, không cái nào đủ. ISO/IEC/IEEE 42010 cố ý _không_ quy định tập view cố định — nên bất kỳ tuyên bố "phần mềm gồm đúng N khía cạnh" nào cũng là lựa chọn của người viết, không phải phát hiện. Cách trung thực để trả lời RQ1 là: liệt kê các concern mà từng framework định nghĩa, chỉ ra chỗ chồng lấn và chỗ trống, rồi tuyên bố rõ ràng rằng phần tổng hợp là synthesis.

**Về RQ2.** Đây là câu hỏi được trả lời tốt nhất trong ba câu, và nguồn tốt nhất là thực nghiệm chứ không phải lý thuyết. Sillito, Murphy & De Volder (2006/2008) cung cấp 44 câu hỏi **được phân loại theo đặc tính subgraph** — nghĩa là chính các tác giả gốc đã bắc cầu từ comprehension sang graph. LaToza & Myers bổ sung phát hiện then chốt: nhóm câu hỏi phổ biến nhất là **intent và rationale**, thứ không trích xuất được từ code. Kết hợp lại, chúng tạo thành bộ requirement khả dụng cho thiết kế graph — và có thể trở thành benchmark.

**Về RQ3.** Nền tảng tốt nhất hiện có là **KDM/ISO 19506 mở rộng**, không phải một schema mới. Mở rộng cần thiết gồm bốn hướng: (a) tầng TEST tách bạch definition/execution; (b) tầng RUNTIME theo OTel với ngữ nghĩa sampling tường minh; (c) tầng INFRA theo ngữ nghĩa desired/recorded/observed của K8s và Terraform; (d) tầng EVOLUTION theo Hismo + Merkle DAG. Cắt ngang cả bốn là provenance căn chỉnh PROV-O với mô hình thời gian bitemporal.

**Cảnh báo trung thực cuối cùng.** Ba điều mà một luận văn về chủ đề này phải nói thẳng, kẻo mất tính chính trực học thuật:

1. **Taxonomy bằng chứng năm mức là synthesis của tác giả, không phải chuẩn.** Nó có tiền lệ độc lập cho từng mức, nhưng không nguồn nào định nghĩa cả năm. Và như đã phân tích ở §8.1, nó nên được sửa thành hai chiều trực giao thay vì một enum.
2. **Phần lớn các cạnh thú vị nhất không phải là fact.** `REALIZES`, `DECIDED_BY`, `RENAMED_TO`, và ngay cả `CALLS` trong ngôn ngữ động — tất cả đều là ước lượng. Một code KG trung thực trông sẽ _kém ấn tượng hơn_ một code KG không trung thực, vì nó hiển thị confidence thay vì cạnh sạch sẽ. Đó là cái giá phải trả và phải nói rõ.
3. **Sự vắng mặt không bao giờ là bằng chứng phủ định** — không có span, không có cạnh CALLS, không có test đều **không** chứng minh điều tương ứng không tồn tại. Graph phải phân biệt "không có dữ liệu" với "đã kiểm tra và không có". Kubernetes đã chuẩn hoá sẵn giá trị `Unknown` cho đúng vấn đề này; code KG nên mượn.

---

## 13. Tài liệu tham khảo

### Tiêu chuẩn quốc tế

1. **ISO/IEC/IEEE 42010:2022** — _Software, systems and enterprise — Architecture description_. Edition 2, 11/2022. ISO ref. 74393. https://www.iso.org/standard/74393.html · https://standards.ieee.org/ieee/42010/6846/
2. **ISO/IEC/IEEE 42010:2011** — _Systems and software engineering — Architecture description_. (Inactive-Reserved; superseded by 42010:2022.) https://standards.ieee.org/standard/42010-2011.html
3. **ISO/IEC 19506:2012** — _Information technology — OMG Architecture-Driven Modernization (ADM) — Knowledge Discovery Meta-Model (KDM)_. https://www.iso.org/standard/32625.html · OMG spec: https://www.omg.org/spec/KDM/
4. **ISO/IEC 25010:2023** — _Systems and software engineering — SQuaRE — Product quality model_. ISO ref. 78176. https://www.iso.org/standard/78176.html
5. **ISO/IEC 5962:2021** — _Information technology — SPDX Specification V2.2.1_.
6. **ECMA-424** — _CycloneDX Bill of Materials Specification_. Ecma International (1st ed. 6/2024; 2nd ed. 12/2025).
7. **ISO/IEC 11404** — _General-Purpose Datatypes_ (được KDM Code package tham chiếu).

### Sách chuyên ngành

8. Clements, P., Bachmann, F., Bass, L., Garlan, D., Ivers, J., Little, R., Merson, P., Nord, R., Stafford, J. (2011). _Documenting Software Architectures: Views and Beyond_, 2nd ed. Addison-Wesley (SEI Series in Software Engineering). ISBN 978-0-321-55268-6.
9. Rozanski, N. & Woods, E. (2011). _Software Systems Architecture: Working with Stakeholders Using Viewpoints and Perspectives_, 2nd ed. Addison-Wesley. ISBN 032171833X (1st ed.: ISBN 0321112296). https://www.viewpoints-and-perspectives.info/
10. Diehl, S. (2007). _Software Visualization: Visualizing the Structure, Behaviour, and Evolution of Software_. Springer. ISBN 978-3-540-46504-1. DOI `10.1007/978-3-540-46505-8`.

### Bài báo peer-reviewed — kiến trúc

11. Kruchten, P. (1995). "Architectural Blueprints — The '4+1' View Model of Software Architecture." _IEEE Software_ 12(6):42–50. DOI `10.1109/52.469759`.

### Bài báo peer-reviewed — program comprehension

12. von Mayrhauser, A. & Vans, A.M. (1995). "Program Comprehension During Software Maintenance and Evolution." _IEEE Computer_ 28(8):44–55.
13. Brooks, R. (1983). "Towards a theory of the comprehension of computer programs." _Int. J. Man-Machine Studies_ 18(6):543–554.
14. Pennington, N. (1987). "Stimulus structures and mental representations in expert comprehension of computer programs." _Cognitive Psychology_ 19:295–341.
15. Letovsky, S. (1987). "Cognitive processes in program comprehension." _Journal of Systems and Software_ 7(4):325–339.
16. Soloway, E. & Ehrlich, K. (1984). "Empirical Studies of Programming Knowledge." _IEEE TSE_ SE-10(5):595–609.
17. Shneiderman, B. & Mayer, R. (1979). "Syntactic/semantic interactions in programmer behavior." _Int. J. Computer and Information Sciences_ 8(3).
18. **Sillito, J., Murphy, G.C. & De Volder, K. (2006).** "Questions Programmers Ask During Software Evolution Tasks." _SIGSOFT '06/FSE-14_, pp. 23–34. DOI `10.1145/1181775.1181779`. PDF: https://www.cs.ubc.ca/~murphy/papers/other/asking-answering-fse06.pdf
19. Sillito, J., Murphy, G.C. & De Volder, K. (2008). "Asking and Answering Questions During a Programming Change Task." _IEEE TSE_ 34(4):434–451.
20. LaToza, T.D. & Myers, B.A. (2010). "Hard-to-Answer Questions about Code." _PLATEAU '10_. DOI `10.1145/1937117.1937125`.
21. LaToza, T.D. & Myers, B.A. (2010). "Developers Ask Reachability Questions." _ICSE 2010_, pp. 185–194. DOI `10.1145/1806799.1806829`.
22. Maalej, W., Tiarks, R., Roehm, T. & Koschke, R. (2014). "On the Comprehension of Program Comprehension." _ACM TOSEM_ 23(4), Article 31. DOI `10.1145/2622669`.
23. Roehm, T., Tiarks, R., Koschke, R. & Maalej, W. (2012). "How do professional developers comprehend software?" _ICSE 2012_.
24. Ko, A.J., DeLine, R. & Venolia, G. (2007). "Information Needs in Collocated Software Development Teams." _ICSE 2007_.
25. Storey, M.-A. (2005/2006). "Theories, Methods and Tools in Program Comprehension: Past, Present and Future." _IWPC/ICPC_.

### Bài báo peer-reviewed — reverse engineering & representation

26. **Chikofsky, E.J. & Cross II, J.H. (1990).** "Reverse Engineering and Design Recovery: A Taxonomy." _IEEE Software_ 7(1):13–17. DOI `10.1109/52.43044`.
27. **Biggerstaff, T.J., Mitbander, B.G. & Webster, D.E. (1994).** "Program Understanding and the Concept Assignment Problem." _CACM_ 37(5):72–82. DOI `10.1145/175290.175300`. (Bản hội nghị: ICSE '93, pp. 482–498.)
28. **Yamaguchi, F., Golde, N., Arp, D. & Rieck, K. (2014).** "Modeling and Discovering Vulnerabilities with Code Property Graphs." _IEEE S&P 2014_.
29. Ferrante, J., Ottenstein, K.J. & Warren, J.D. (1987). "The Program Dependence Graph and Its Use in Optimization." _ACM TOPLAS_ 9(3):319–349.
30. Horwitz, S., Reps, T. & Binkley, D. (1990). "Interprocedural Slicing Using Dependence Graphs." _ACM TOPLAS_ 12(1):26–60.
31. Weiser, M. (1984). "Program Slicing." _IEEE TSE_ SE-10(4):352–357.
32. Demeyer, S., Tichelaar, S. & Ducasse, S. (2001). _FAMIX 2.1 — The FAMOOS Information Exchange Model_. Technical Report, University of Bern.
33. Ducasse, S., Anquetil, N., Bhatti, U., Hora, A., Laval, J. & Gîrba, T. (2011). _MSE and FAMIX 3.0: an Interexchange Format and Source Code Model Family_.
34. Lethbridge, T., Tichelaar, S. & Plödereder, E. (2004). "The Dagstuhl Middle Metamodel: A Schema for Reverse Engineering." _ENTCS_ 94:7–18.
35. Nierstrasz, O., Ducasse, S. & Gîrba, T. (2005). "The Story of Moose: an Agile Reengineering Environment." _ESEC/FSE 2005_.
36. **Livshits, B. et al. (2015).** "In Defense of Soundiness: A Manifesto." _CACM_ 58(2):44–46. https://cacm.acm.org/opinion/in-defense-of-soundiness/ · http://soundiness.org/
37. Pérez-Castillo, R., García-Rodríguez de Guzmán, I. & Piattini, M. (2011). "Knowledge Discovery Metamodel-ISO/IEC 19506: A standard to modernize legacy systems." _Computer Standards & Interfaces_.

### Bài báo peer-reviewed — traceability & evolution

38. **Gotel, O.C.Z. & Finkelstein, A.C.W. (1994).** "An Analysis of the Requirements Traceability Problem." _ICRE 1994_, pp. 94–101. DOI `10.1109/ICRE.1994.292398`. https://discovery.ucl.ac.uk/749/
39. Ramesh, B. & Jarke, M. (2001). "Toward Reference Models for Requirements Traceability." _IEEE TSE_ 27(1):58–93.
40. **Gîrba, T. & Ducasse, S. (2006).** "Modeling History to Analyze Software Evolution." _Journal of Software Maintenance and Evolution: Research and Practice_ 18(3):207–236. DOI `10.1002/smr.325`.
41. Gîrba, T. (2005). _Modeling History to Understand Software Evolution_. PhD thesis, University of Bern.
42. **Pietri, A., Spinellis, D. & Zacchiroli, S. (2019).** "The Software Heritage Graph Dataset: Public software development under one roof." _MSR 2019_. DOI `10.1109/MSR.2019.00030`. https://www.softwareheritage.org/wp-content/uploads/2020/01/msr-2019-swh.pdf
43. Di Cosmo, R. & Zacchiroli, S. (2017). "Software Heritage: Why and How to Preserve Software Source Code." _iPRES 2017_.
44. Rousseau, G., Di Cosmo, R. & Zacchiroli, S. (2020). "Software Provenance Tracking at the Scale of Public Source Code." _Empirical Software Engineering_.
45. Maletic, J.I., Marcus, A. & Collard, M.L. (2002). "A Task Oriented View of Software Visualization." _VISSOFT 2002_.

### Đặc tả kỹ thuật & tài liệu chính thức

46. **W3C (2013).** _PROV-O: The PROV Ontology_. W3C Recommendation, 30/04/2013. https://www.w3.org/TR/prov-o/ · PROV-DM: https://www.w3.org/TR/prov-dm/
47. **OpenTelemetry Specification.** https://opentelemetry.io/docs/specs/otel/ · Metrics Data Model: https://opentelemetry.io/docs/specs/otel/metrics/data-model/ · Logs Data Model: https://opentelemetry.io/docs/specs/otel/logs/data-model/ · Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/ · Repo: https://github.com/open-telemetry/opentelemetry-specification
48. **W3C Trace Context.** https://www.w3.org/TR/trace-context/
49. **Kubernetes API Conventions** (SIG Architecture). https://github.com/kubernetes/community/blob/main/contributors/devel/sig-architecture/api-conventions.md
50. **HashiCorp Terraform — State.** https://developer.hashicorp.com/terraform/language/state · Manage resource drift: https://developer.hashicorp.com/terraform/tutorials/state/resource-drift
51. **Software Heritage — Data model.** https://docs.softwareheritage.org/devel/swh-model/data-model.html · SWHIDs: https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html
52. **Git documentation** — `git-diff` (`-M`/`--find-renames`, similarity index), `git-log` (`--follow`).
53. **OMG** — Abstract Syntax Tree Metamodel (ASTM); Structured Metrics Metamodel (SMM); SBVR.

### Thực hành công nghiệp (trích với tư cách practice, không phải standard)

54. Nygard, M. (2011). "Documenting Architecture Decisions." https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions · https://adr.github.io/
55. Kopp, O., Armbruster, A. & Zimmermann, O. (2018). "Markdown Architectural Decision Records: Format and Tool Support." CEUR-WS Vol-2072.
56. Brown, S. — C4 model. (Industry practice; không có metamodel hình thức công bố qua kênh học thuật.)

### Công trình gần đây về code graph cho LLM (bối cảnh research gap)

57. Ouyang, S. et al. (2025). "RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph." _ICLR 2025_. arXiv:2410.14684.
58. Liu, X. et al. (2025). "CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases." _NAACL 2025_. arXiv:2408.03910.
59. "Code Graph Model (CGM): A Graph-Integrated Large Language Model for Repository-Level Software Engineering Tasks." _NeurIPS 2025_.
60. Chen, Z. et al. (2025). "LocAgent: Graph-guided LLM Agents for Code Localization." _ACL 2025_.
61. Liu, W. et al. (2024). "GraphCoder: Enhancing Repository-Level Code Completion via Coarse-to-Fine Retrieval Based on Code Context Graph." _ASE 2024_. DOI `10.1145/3691620.3695054`.
62. Tao, Y., Qin, Y. & Liu, Y. (2025). "Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches." arXiv:2510.04905.

---

## 14. Bảng truy nguyên luận điểm

| Claim / Concept                                                                                     | Original source                               | Directly stated or inferred               | Confidence                    | Suitable for thesis foundation?                         |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------- | ----------------------------------------- | ----------------------------- | ------------------------------------------------------- |
| Kiến trúc phải được mô tả qua nhiều view, mỗi view giải quyết concern của stakeholder               | ISO/IEC/IEEE 42010:2022                       | **Directly stated**                       | Cao                           | **Có** — nền tảng chính                                 |
| Tiêu chuẩn **không** quy định tập view cố định; không đặc tả process/method/notation                | ISO/IEC/IEEE 42010:2022 (Scope)               | **Directly stated**                       | Cao                           | **Có** — biện minh cho việc không giả định trước schema |
| Correspondence rule đảm bảo nhất quán giữa các view                                                 | ISO/IEC/IEEE 42010                            | **Directly stated**                       | Cao                           | **Có** — cơ sở cho ràng buộc liên tầng                  |
| 4+1 gồm logical, process, development, physical + scenarios                                         | Kruchten (1995), DOI 10.1109/52.469759        | **Directly stated**                       | Cao                           | Có — nêu kèm hạn chế (1995)                             |
| Ba viewtype: Module / Component-and-Connector / Allocation                                          | Clements et al., _Views and Beyond_           | **Directly stated**                       | Cao                           | **Có — ưu tiên cao**                                    |
| Bảy viewpoint (Context…Operational) + perspectives cắt ngang                                        | Rozanski & Woods, 2nd ed.                     | **Directly stated**                       | Cao                           | Có — bổ trợ                                             |
| R&W tự nhận là mở rộng 4+1, thêm Information và Operational                                         | Tài liệu chính thức của tác giả               | **Directly stated**                       | Cao                           | Có                                                      |
| Integrated Metamodel gồm 4 thành phần (top-down, program, situation, knowledge base)                | von Mayrhauser & Vans (1995)                  | **Directly stated**                       | Cao                           | **Có**                                                  |
| Lập trình viên chuyển đổi thường xuyên giữa các chế độ comprehension                                | von Mayrhauser & Vans (1995)                  | **Directly stated**                       | Cao                           | Có                                                      |
| Graph phải duyệt **hai chiều** intent↔code vì con người switching                                   | —                                             | **Inferred** (từ mục trên)                | Trung bình                    | Có — phải ghi là diễn giải                              |
| Letovsky: 5 loại conjecture, gồm **discrepancy**                                                    | Letovsky (1986/1987)                          | **Directly stated**                       | Cao                           | **Có** — nền cho xử lý mâu thuẫn                        |
| **44 loại câu hỏi, 4 nhóm, phân loại theo đặc tính subgraph**                                       | Sillito et al. (2006/2008)                    | **Directly stated**                       | Cao                           | **Có — nền tảng chính cho RQ2**                         |
| Câu hỏi của lập trình viên ánh xạ không khớp với câu hỏi tool trả lời được                          | Sillito et al. (2006)                         | **Directly stated**                       | Cao                           | **Có** — biện minh cho KG hợp nhất                      |
| 371 câu hỏi → 21 nhóm; nhóm phổ biến nhất là **intent & rationale**                                 | LaToza & Myers (2010)                         | **Directly stated**                       | Cao (nhưng là workshop paper) | Có — bổ trợ                                             |
| Reachability question được hỏi >9 lần/ngày                                                          | LaToza & Myers, ICSE 2010                     | **Directly stated**                       | Cao                           | Có                                                      |
| Công cụ comprehension chuyên dụng không được dùng trong thực tế                                     | Maalej et al. (2014) TOSEM                    | **Directly stated**                       | Cao                           | Có                                                      |
| Concept assignment đòi hỏi plausible reasoning (không tất định)                                     | Biggerstaff et al. (1994)                     | **Directly stated**                       | Cao                           | **Có** — nền cho giới hạn REALIZES                      |
| LLM không thay đổi bản chất concept assignment problem                                              | —                                             | **Inferred**                              | Trung bình                    | Có — phải ghi là suy luận                               |
| Design recovery cần thông tin **ngoài** code (domain, kinh nghiệm, external)                        | Chikofsky & Cross (1990)                      | **Directly stated**                       | Cao                           | **Có** — biện minh KG đa nguồn                          |
| KDM có 4 tầng; Resource layer gồm Platform/UI/Event/Data                                            | OMG KDM / ISO 19506                           | **Directly stated**                       | Cao                           | **Có — nền tảng chính cho RQ3**                         |
| KDM package Source cung cấp truy nguyên đầy đủ về source code                                       | OMG KDM                                       | **Directly stated**                       | Cao                           | **Có**                                                  |
| KDM **thiếu** test execution, telemetry, IaC, evolution                                             | —                                             | **Inferred** (từ đọc danh sách package)   | Cao                           | **Có** — định vị đóng góp luận văn                      |
| CPG hợp nhất AST+CFG+PDG trên node statement/predicate chung                                        | Yamaguchi et al. (2014)                       | **Directly stated**                       | Cao                           | Có                                                      |
| **Schema của CPG để mở; các cài đặt khác nhau đáng kể**                                             | Yamaguchi (tuyên bố của chính tác giả)        | **Directly stated**                       | Cao                           | **Có** — cảnh báo không trích CPG như chuẩn             |
| Code metamodel luôn là trade-off giữa quá mịn và quá thô                                            | Tác giả FAMIX                                 | **Directly stated**                       | Cao                           | **Có** — biện minh loại Statement node                  |
| Phân tích tĩnh thực dụng cố ý under-approximate reflection/eval → "soundy"                          | Soundiness Manifesto (CACM 2015)              | **Directly stated**                       | Cao                           | **Có** — nền cho confidence trên CALLS                  |
| Pre-RS vs post-RS traceability; phần lớn vấn đề nằm ở pre-RS                                        | Gotel & Finkelstein (1994)                    | **Directly stated**                       | Cao                           | **Có** — nền cho tuyên bố phạm vi                       |
| Bộ ba structure / behaviour / evolution                                                             | Diehl (2007)                                  | **Directly stated**                       | Cao                           | Có — nhưng ghi rõ là cho _visualization_                |
| Ba chiều của Diehl ≈ ba tầng của code KG                                                            | —                                             | **Inferred**                              | Trung bình                    | Có — phải ghi là mượn                                   |
| ISO 25010:2023 có 9 đặc tính chất lượng                                                             | ISO/IEC 25010:2023                            | **Directly stated**                       | Cao                           | Chỉ cho `QualityRequirement`                            |
| ISO 25010 **không** là mô hình comprehension                                                        | —                                             | **Inferred** (từ Scope của tiêu chuẩn)    | Cao                           | **Có** — cảnh báo chống trộn taxonomy                   |
| OTel: traces/metrics/logs + Resource + Semantic Conventions                                         | OpenTelemetry Specification                   | **Directly stated**                       | Cao                           | **Có**                                                  |
| Scatter/gather dùng **span links**, khuyến nghị **không** đặt parent                                | OTel Specification (overview)                 | **Directly stated**                       | Cao                           | **Có** — trace không phải cây thuần                     |
| K8s: `spec` = desired, `status` = current/observed                                                  | K8s API Conventions                           | **Directly stated**                       | Cao                           | **Có**                                                  |
| Vắng mặt condition status phải diễn giải là `Unknown`                                               | K8s API Conventions                           | **Directly stated**                       | Cao                           | **Có** — nền cho mức thứ ba                             |
| Status phải tái dựng được 100% bằng quan sát                                                        | K8s design principles                         | **Directly stated**                       | Cao                           | Có                                                      |
| Terraform state lưu **binding** giữa object thực và resource khai báo; refresh phát hiện drift      | HashiCorp docs                                | **Directly stated**                       | Cao                           | Có                                                      |
| Terraform có **ba** mức (config / state / thực tế), K8s có hai                                      | —                                             | **Inferred**                              | Trung bình                    | Có                                                      |
| **Git không lưu rename; phát hiện bằng similarity, mặc định 50%**                                   | Git docs / `-M` option                        | **Directly stated**                       | Cao                           | **Có** — cảnh báo bắt buộc                              |
| Mọi cạnh RENAMED_TO là ước lượng, không phải fact                                                   | —                                             | **Inferred** (từ mục trên)                | Cao                           | **Có**                                                  |
| Hismo: history là thực thể tường minh; history = dãy version; thêm tầng thời gian lên cấu trúc      | Gîrba & Ducasse (2006)                        | **Directly stated**                       | Cao                           | **Có** — nền cho §9                                     |
| Software Heritage: Merkle DAG 5 tầng (content→directory→revision→release→snapshot) + dedup toàn cục | Di Cosmo & Zacchiroli; MSR 2019               | **Directly stated**                       | Cao                           | **Có**                                                  |
| SWH lưu thêm ánh xạ 3 chiều origin↔visit↔snapshot trong log append-only                             | SWH / MSR 2019                                | **Directly stated**                       | Cao                           | Có — mô hình provenance tốt                             |
| PROV-O: Entity / Activity / Agent; W3C Rec 30/04/2013                                               | W3C PROV-O                                    | **Directly stated**                       | Cao                           | **Có** — nền provenance                                 |
| SPDX 2.2.1 = ISO/IEC 5962:2021; CycloneDX = ECMA-424                                                | ISO / Ecma / OpenSSF                          | **Directly stated**                       | Cao                           | Có                                                      |
| **Taxonomy DECLARED/IMPLEMENTED/VERIFIED/OBSERVED/HISTORICAL**                                      | **Không có nguồn gốc**                        | **Synthesis của báo cáo này**             | **Trung bình**                | **Có — nhưng BẮT BUỘC trình bày là synthesis**          |
| HISTORICAL không cùng chiều với 4 mức kia; nên tách thành 2 chiều                                   | —                                             | **Đề xuất mới**                           | Trung bình                    | Có — là đóng góp                                        |
| Nên thêm mức `inferred` cho tri thức LLM                                                            | —                                             | **Đề xuất mới**                           | Trung bình                    | Có — là đóng góp                                        |
| Kiến trúc hai kho (KG mức Function + CPG store theo yêu cầu)                                        | —                                             | **Đề xuất mới**                           | **Thấp**                      | Có — cần thực nghiệm chứng minh                         |
| Phương án evolution lai P4 (stable + version + ChangeEvent + snapshot)                              | —                                             | **Đề xuất mới**, lấy cảm hứng Hismo + SWH | Trung bình                    | Có — là đóng góp                                        |
| Bitemporal (valid time + transaction time) là bắt buộc                                              | Snodgrass; SQL:2011 (cho mô hình bitemporal)  | **Inferred** cho ứng dụng vào code KG     | Trung bình                    | Có                                                      |
| Không tồn tại benchmark đo độ phủ câu hỏi comprehension của code KG                                 | —                                             | **Inferred** từ khảo sát tài liệu         | Cao                           | **Có — đóng góp khả thi nhất**                          |
| Framework kinh điển thiếu chiều **verification**                                                    | —                                             | **Inferred** từ khảo sát A–F              | Cao                           | **Có — đóng góp lý thuyết**                             |
| Code graph cho LLM thiếu evidence typing / provenance / temporal                                    | Khảo sát RepoGraph, CodexGraph, CGM, LocAgent | **Inferred**                              | Cao                           | **Có**                                                  |

---

## 15. Bảng ánh xạ cuối cùng: câu hỏi → tri thức → artifact → graph → bằng chứng → giới hạn

| Software-understanding question                            | Required knowledge                          | Source artifacts                                                     | Possible graph entities/relations                                                                    | Evidence type                                                       | Remaining limitations                                                                                                                                                          |
| ---------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Hệ thống này phục vụ ai, giải quyết vấn đề gì?**         | Stakeholder, mục tiêu, concern              | Requirements, README, ADR, architecture docs                         | `Stakeholder`, `Goal`, `Requirement`, `Feature`; `HAS_CONCERN`, `MOTIVATES`                          | **Declared**                                                        | Thường không tồn tại trong repo. Pre-RS traceability về cấu trúc là không trích xuất được (Gotel & Finkelstein)                                                                |
| **Feature X được cài đặt ở đâu?**                          | Ánh xạ concept → code                       | Source code, tests, feature flags, README, issues, coverage per test | `Feature`, `Function`, `Class`; `REALIZES`, `TESTS`, `COVERS`                                        | **Inferred** (chính); **Verified** nếu có coverage per feature-test | **Concept assignment problem** (Biggerstaff). Feature thường crosscutting. Cạnh REALIZES không bao giờ là fact                                                                 |
| **Text trong thông báo lỗi này ở đâu?**                    | Ánh xạ chuỗi → vị trí code                  | Source code, i18n resource bundle                                    | `StringLiteral`/`ResourceKey`, `Function`; `CONTAINS`, `REFERENCES`                                  | **Implemented**                                                     | Chuỗi ghép động, template, i18n gián tiếp làm mất liên kết trực tiếp                                                                                                           |
| **Hàm này được gọi từ đâu?**                               | Call graph ngược                            | Source code + type info; runtime trace bổ sung                       | `Function`; `CALLS` (đảo chiều)                                                                      | **Implemented** (soundy) + **Observed** (bổ sung)                   | Reflection, DI, dynamic dispatch, callback, eval → **vừa thiếu vừa thừa cạnh** (Soundiness)                                                                                    |
| **Điều khiển đi từ A tới B bằng cách nào?**                | Đường đi CFG/liên thủ tục                   | Source code (CPG); distributed trace                                 | `Function`, `Span`; `CALLS`, `PARENT_OF`, `LINKS_TO`                                                 | **Implemented** (possible path) + **Observed** (actual path)        | Static: bùng nổ tổ hợp đường đi. Runtime: chỉ thấy đường đã được sample                                                                                                        |
| **Tại sao điều khiển KHÔNG tới được điểm này?**            | Điều kiện branch + dữ liệu thực             | Source code, trace, log, coverage                                    | `Function`, `CoverageMeasurement`, `Span`                                                            | **Implemented** + **Verified** + **Observed**                       | **Vắng mặt không chứng minh không thể tới.** Cần coverage đầy đủ + sampling 100% mới có tín hiệu                                                                               |
| **Tác động toàn phần của thay đổi này là gì?**             | Bao đóng phụ thuộc + co-change lịch sử      | Source code, Git history, tests, contract, trace                     | `Function`, `Commit`, `TestCase`, `APIEndpoint`; `DEPENDS_ON`, `MODIFIES`, `TESTS`                   | **Implemented** + **Historical** + **Verified**                     | Bao đóng tĩnh bùng nổ; co-change là tương quan không phải nhân quả; tác động xuyên repo cần trace                                                                              |
| **Dữ liệu này được đọc/ghi ở đâu?**                        | Data flow + truy cập persistence            | Source code, DB schema, ORM mapping, SQL log                         | `Function`, `Table`, `Column`, `Entity`; `READS`, `WRITES`, `MAPS_TO`                                | **Implemented**; **Observed** (SQL log)                             | ORM lazy loading, raw SQL string ghép động, stored procedure → không phân giải tĩnh được                                                                                       |
| **Hành vi này đã được kiểm chứng chưa?**                   | Test + kết quả thực thi + coverage          | Test files, CI test reports, coverage report                         | `TestCase`, `TestRun`, `TestResult`, `CoverageMeasurement`; `TESTS`, `VERIFIES`, `COVERS`            | **Declared** (test def) + **Verified** (run)                        | **Coverage đo dòng được thực thi, KHÔNG đo tính đúng đắn.** Test tồn tại ≠ đã chạy ≠ pass. Không framework kinh điển nào phủ khía cạnh này                                     |
| **Điều gì thực sự xảy ra trong production?**               | Telemetry                                   | Traces, logs, metrics, profiles                                      | `Trace`, `Span`, `LogEvent`, `MetricSeries`, `ServiceInstance`; `OBSERVED_IN`, `MAPS_TO_CODE`        | **Observed**                                                        | Sampling; thiếu instrumentation; cửa sổ giữ dữ liệu hữu hạn; PII redaction làm mất chi tiết                                                                                    |
| **Code này chạy ở đâu?**                                   | Deployment topology                         | K8s manifest, Helm, Terraform, cluster API, OTel Resource            | `Deployment`, `Pod`, `Host`, `Cluster`, `ServiceInstance`; `DEPLOYED_AS`, `RUNS_ON`, `RECONCILES_TO` | **Declared** (`spec`) + **Observed** (`status`, inventory)          | Drift giữa desired và actual. Inventory là snapshot hết hạn nhanh — bắt buộc `valid_from`/`valid_to`                                                                           |
| **Hạ tầng khai báo có khớp thực tế không?**                | Desired vs recorded vs observed             | Terraform config + state + cloud API; K8s spec + status              | `CloudResource(state_kind=desired/recorded/observed)`; `RECONCILES_TO`                               | **Declared** + **Observed**                                         | Terraform state có thể cũ nếu chưa refresh. Thay đổi ngoài băng không được ghi lại ở đâu                                                                                       |
| **Tại sao nó được thiết kế như vậy?** (nhóm phổ biến nhất) | Decision + rationale + alternatives bị loại | ADR, PR discussion, issue, commit message, design doc                | `ArchitectureDecision`, `PullRequest`, `Issue`; `DECIDED_BY`, `SUPERSEDES`, `CONSIDERED_ALTERNATIVE` | **Declared**; liên kết tới code là **Inferred**                     | **Thường không tồn tại.** Lý do bị loại (rejected alternatives) gần như không bao giờ được ghi. Là nhóm câu hỏi phổ biến nhất theo LaToza & Myers — và ít trích xuất được nhất |
| **Ai thay đổi cái này, khi nào, cùng với gì?**             | Lịch sử + co-change                         | Git history, PR, issue tracker                                       | `Commit`, `Author`, `PullRequest`, `ChangeEvent`, `CodeEntityVersion`; `MODIFIES`, `NEXT_VERSION`    | **Historical**                                                      | **Git không lưu rename** → theo dấu lịch sử một hàm là ước lượng. Refactoring lớn cắt đứt chuỗi version                                                                        |
| **Hàm này trước đây trông thế nào?**                       | Version history mức entity                  | Git + AST diff                                                       | `CodeEntityVersion`; `NEXT_VERSION`, `RENAMED_TO`                                                    | **Historical**                                                      | Đứt chuỗi khi rename+modify cùng lúc; AST diff không có chuẩn; merge commit khó xử lý                                                                                          |
| **Yêu cầu chất lượng nào ràng buộc phần này?**             | NFR + SLO                                   | Requirements, ADR, SLO config, alert rules                           | `QualityRequirement`, `SLO`, `Alert`; `CONSTRAINED_BY`, `MONITORS`                                   | **Declared**; vi phạm là **Observed**                               | ISO 25010 cho từ vựng nhưng không cho ngưỡng. SLO có thể tồn tại mà không được thực thi                                                                                        |
| **Dependency của tôi là gì và có lỗ hổng không?**          | Dependency graph + vulnerability            | Lock file, SBOM, security scan                                       | `Component`, `Vulnerability`, `SecurityScanResult`; `DEPENDS_ON`, `HAS_VULNERABILITY`                | **Declared** (manifest) + **Verified** (scan)                       | SBOM không xuống mức hàm → không biết hàm có lỗ hổng có thực sự được gọi không (cần reachability analysis)                                                                     |
| **Service A và service B liên hệ thế nào?** (đa repo)      | Quan hệ liên service                        | API spec, distributed trace, service mesh config                     | `Component`, `APIEndpoint`, `Span`; `CONSUMES`, `LINKS_TO`                                           | **Declared** (spec) + **Observed** (trace)                          | Static analysis nội repo **không** thấy được. Trace là nguồn đáng tin nhất — nhưng chỉ cho đường đã sample                                                                     |
| **Có mâu thuẫn nào giữa các nguồn không?**                 | So sánh chéo evidence type                  | Tất cả                                                               | `Discrepancy`; `CONTRADICTS`, `EXTRACTED_FROM`                                                       | Meta — so sánh giữa các mức                                         | Cần reification hoặc named graph. Chi phí lưu trữ và độ phức tạp truy vấn tăng đáng kể                                                                                         |

---

_Kết thúc báo cáo._
