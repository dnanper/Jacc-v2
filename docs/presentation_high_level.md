# Code Knowledge Graph — Trình bày ý tưởng dự án

---

## 1. Bài Toán

Khi AI agent (như ChatGPT, Claude) cần hỗ trợ lập trình viên hiểu hoặc sửa đổi một dự án phần mềm, nó cần phải **đọc hiểu codebase**. Cách tiếp cận phổ biến nhất hiện nay là đưa toàn bộ source code vào context window của LLM — nhưng cách này gặp 2 vấn đề lớn:

| Vấn đề | Hậu quả |
|--------|---------|
| **Context window giới hạn** | Repo lớn (hàng nghìn file) không thể đưa hết vào prompt |
| **Thiếu cấu trúc** | LLM nhận text phẳng, không thấy được mối quan hệ giữa các thành phần (ai gọi ai, ai kế thừa ai, luồng thực thi ra sao) |

**Mục tiêu của dự án:** Xây dựng hệ thống chuyển đổi codebase thành **Knowledge Graph / Knowledge Fabric** — một lớp biểu diễn tri thức nhiều mức trừu tượng, không chỉ mô tả cấu trúc tĩnh của source code mà còn hỗ trợ biểu diễn phụ thuộc, hợp đồng giao tiếp, kiến trúc, luồng xử lý, lịch sử thay đổi, và các nguồn bằng chứng liên quan. AI agent sau đó truy vấn lớp tri thức này để lấy đúng thông tin cần thiết, thay vì phải đọc toàn bộ repository dưới dạng text phẳng.

### 1.1. Theo research, "hiểu một codebase" nghĩa là gì?

Nghiên cứu về **program comprehension**, **software architecture**, **static/dynamic analysis**, **traceability**, và **software knowledge graph** cho thấy: để hiểu một hệ thống phần mềm, ta không chỉ cần biết "có những hàm nào" mà cần trả lời được **một họ câu hỏi** ở nhiều mức nhìn khác nhau.

| Mức tri thức | Cần nắm được điều gì? | Ví dụ câu hỏi |
|-------------|------------------------|---------------|
| **Lexical / Terminology** | Từ vựng của hệ thống, tên miền nghiệp vụ, tên feature | "Invoice ở đây tương ứng với khái niệm nào trong business?" |
| **Physical / Workspace** | File, folder, package, module, build target, service nằm ở đâu | "Phần auth nằm ở thư mục nào?" |
| **Syntactic / Symbolic** | Function, class, method, interface, schema, route được định nghĩa ra sao | "Hàm này nhận tham số gì?" |
| **Static Dependency** | Ai gọi ai, ai import ai, ai kế thừa ai, ai dùng kiểu nào | "Nếu sửa hàm X thì phần nào bị ảnh hưởng?" |
| **Contract / Type / API** | Signature, pre/post-condition, exception, giao tiếp giữa các thành phần | "Endpoint này trả về kiểu gì?" |
| **Behavioral** | Luồng xử lý, control flow, data flow, event flow, use-case flow | "Khi user login thì qua các bước nào?" |
| **Architectural** | Component, layer, service, boundary, trách nhiệm, phụ thuộc giữa các khối | "Auth phụ thuộc vào DB hay vào User service?" |
| **Runtime / Operational** | Cái gì thực sự xảy ra lúc chạy: trace, latency, error path, coverage | "Đường đi nóng nhất khi checkout là gì?" |
| **Evolutionary** | Lịch sử thay đổi, change coupling, hotspot, ai sửa, vì sao sửa | "Phần này hay đổi cùng module nào?" |
| **Socio-technical** | Ownership, team responsibility, PR/issue liên quan | "Ai là người hiểu rõ khu vực này nhất?" |
| **Domain / Intent** | Requirement, user story, ADR, tài liệu, business rule | "Đoạn code này tồn tại để phục vụ feature nào?" |
| **Quality / Risk** | Độ phức tạp, mức mong manh, testability, bảo mật, hiệu năng | "Khu vực nào rủi ro cao khi refactor?" |

**Ý chính:** Không có **một** mức nhìn nào đủ để trả lời mọi câu hỏi. Một graph tốt phải cho phép đi qua lại giữa các mức: từ file → symbol → contract → behavior → architecture → history → domain intent.

### 1.2. Các họ phương pháp luận chính để hiểu codebase (đến năm 2026)

| Họ phương pháp | Đóng góp chính | Hạn chế nếu dùng một mình |
|---------------|----------------|---------------------------|
| **Program Comprehension / Cognitive Models** | Chỉ ra rằng lập trình viên xây dựng hiểu biết theo nhiều mức trừu tượng và nhiều chiến lược top-down / bottom-up | Không cung cấp trực tiếp dữ liệu hay graph |
| **Static Program Analysis** | Trích xuất AST, symbol table, type relation, call graph, dependency graph | Khó nắm được hành vi runtime thật, reflection, DI, async |
| **Dependence Representations** (CFG, PDG, SDG, CPG) | Mô hình hoá control flow, data flow, interprocedural dependence, security reasoning | Chi phí xây dựng cao hơn, khó mở rộng sang domain/history nếu chỉ bám vào code |
| **Software Architecture Recovery** | Phục hồi component, layer, responsibility, viewpoints cho stakeholder | Kết quả thường là suy diễn, không phải ground truth tuyệt đối |
| **Traceability / Feature Location** | Liên kết docs, issues, requirements, tests với code | Cần dữ liệu ngoài code, chất lượng link phụ thuộc artifact |
| **Mining Software Repositories** | Khai thác commit, PR, issue, ownership, change coupling, hotspot | Không phản ánh chi tiết semantics nội tại của code |
| **Ontology / Knowledge Graph** | Hợp nhất nhiều nguồn tri thức vào một schema truy vấn được | Dễ trở nên nặng nề nếu ontology quá cứng hoặc quá rộng |
| **Graph-backed Retrieval for AI Agents** | Dùng graph như substrate để lấy đúng context, giảm token, tăng explainability | Chất lượng phụ thuộc mạnh vào coverage và độ đúng của graph |

### 1.3. Nguyên tắc thiết kế rút ra từ research

- **Multi-view hơn là single-view:** không đồng nhất "graph code" với chỉ AST hay chỉ call graph.
- **Tách facts và inferred views:** fact là quan hệ quan sát được; view là cấu trúc suy diễn như community, workflow, hotspot, ownership area.
- **Mọi quan hệ cần evidence và provenance:** biết edge đến từ parser nào, file nào, commit nào, trace nào.
- **Confidence không chỉ cho retrieval mà cho cả modeling:** đặc biệt với resolution, linking, workflow inference, architecture inference.
- **Codebase không chỉ là code:** config, build, test, docs, issue, commit, schema, route, trace đều có thể là first-class artifact.
- **Kiến trúc nên hỗ trợ thời gian:** một codebase sống thay đổi liên tục; graph nên chịu được versioning và incremental update.
- **Viewpoint phải gắn với task:** câu hỏi về architecture, impact analysis, feature comprehension, debugging cần các projection khác nhau của cùng một knowledge base.

---

## 2. Tổng Quan Hệ Thống

Từ góc nhìn rộng hơn của **program comprehension**, một hệ thống hiểu codebase nên được tổ chức thành **4 lớp**:

```
┌────────────────────────────────────────────────────────────────────┐
│  NGUỒN TRI THỨC                                                   │
│  Source code + build/config + tests + docs/issues + traces        │
└────────────────────────────┬───────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  CANONICAL INGESTION                                              │
│  Parse / resolve / normalize / link                               │
│  → trích xuất "facts" ổn định: file, symbol, dependency, type,    │
│    contract, endpoint, test, config, commit, issue, ...           │
└────────────────────────────┬───────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE GRAPH / KNOWLEDGE FABRIC                               │
│                                                                    │
│  1. Canonical facts        2. Derived views                        │
│  3. Provenance/evidence    4. Confidence/version                   │
│                                                                    │
│  Ví dụ view: community, workflow/scenario, architecture, impact    │
└────────────────────────────┬───────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  TASK-AWARE RETRIEVAL & ANALYSIS                                   │
│                                                                    │
│  Topology → Architecture → Behavior → Impact → Implementation      │
│  Hybrid Search + graph traversal + view selection                  │
└────────────────────────────────────────────────────────────────────┘
```

> **Điểm nhấn:** Phần **core ingestion** nên ưu tiên tối đa các bước deterministic như parsing, symbol resolution, dependency analysis, schema extraction, và linking giữa các artifact. LLM có thể hữu ích ở các lớp diễn giải hoặc tóm tắt sau này, nhưng không nên là nền tảng duy nhất để xây graph.

---

## 3. Ingestion Pipeline — Xây Dựng Knowledge Graph

### 3.1. Tổng quan các bước

Pipeline gồm **4 giai đoạn lớn**, mỗi giai đoạn gồm nhiều bước nhỏ:

```
Giai đoạn 1: PHÂN TÍCH CÚ PHÁP (AST Parsing)
    ├── Quét file trong repository
    ├── Parse AST bằng tree-sitter (hỗ trợ 13 ngôn ngữ)
    └── Trích xuất: hàm, lớp, import, lời gọi hàm, kế thừa

Giai đoạn 2: PHÂN GIẢI QUAN HỆ (Resolution)
    ├── Import resolution: "import X from Y" → File A imports File B
    ├── Call resolution: "functionA()" → hàm nào đang được gọi?
    ├── Heritage resolution: "class Dog extends Animal" → kế thừa
    └── Cross-file propagation: truyền thông tin kiểu dữ liệu giữa các file

Giai đoạn 3: PHÂN TÍCH ĐỒ THỊ (Graph Analysis)
    ├── Community Detection: nhóm code liên quan (Leiden algorithm)
    └── Workflow / Scenario Detection: xấp xỉ luồng xử lý qua call graph

Giai đoạn 4: LƯU TRỮ & ĐÁNH CHỈ MỤC
    ├── Lưu graph vào KuzuDB (graph database)
    ├── Tạo Full-Text Search indexes
    └── (Tùy chọn) Tạo semantic embeddings cho vector search
```

### 3.2. Giai đoạn 1: Phân Tích Cú Pháp

**Công cụ:** [tree-sitter](https://tree-sitter.github.io/) — parser engine chuyên dùng cho code editors (VS Code, Neovim, ...). Mỗi ngôn ngữ có grammar riêng.

**Quy trình:** Source code → Abstract Syntax Tree (AST) → trích xuất thông tin.

**Ví dụ minh họa:**

```python
# File: auth/login.py

from database.users import UserRepository    # ← Import record

class LoginService:                           # ← Class definition
    def authenticate(self, username, password): # ← Method definition
        repo = UserRepository()
        user = repo.find_by_username(username)  # ← Call record
        if user and user.check_password(password):
            return self.create_token(user)      # ← Call record

    def create_token(self, user):               # ← Method definition
        return jwt.encode({"user_id": user.id})
```

Sau khi parse, hệ thống trích xuất:

| Loại dữ liệu | Kết quả |
|--------------|---------|
| **Definitions** | `LoginService` (Class), `authenticate` (Method), `create_token` (Method) |
| **Imports** | `auth/login.py` imports `UserRepository` from `database/users.py` |
| **Calls** | `authenticate` gọi `find_by_username`, `check_password`, `create_token` |
| **Heritage** | (nếu có extends/implements) |

### 3.3. Giai đoạn 2: Phân Giải Quan Hệ

Dữ liệu thô từ AST chỉ là text (ví dụ: "gọi hàm tên `find_by_username`"). Giai đoạn này **phân giải** (resolve) để biết chính xác hàm nào, ở file nào đang được gọi.

**Import Resolution:**
```
"from database.users import UserRepository"
  → Tìm file database/users.py
  → Tìm symbol UserRepository trong file đó
  → Tạo edge: auth/login.py --IMPORTS--> database/users.py
```

**Call Resolution:**
```
"repo.find_by_username(username)"
  → repo có kiểu UserRepository (từ type analysis)
  → UserRepository.find_by_username được định nghĩa ở database/users.py:line 15
  → Tạo edge: authenticate --CALLS--> find_by_username
```

**Cross-file Propagation:**
Khi `file A` import `X` từ `file B`, và gọi `X.method()` → hệ thống cần truyền thông tin kiểu dữ liệu từ `file B` sang `file A` để resolve chính xác `method()` thuộc về class nào.

### 3.4. Giai đoạn 3: Phân Tích Đồ Thị

Sau khi có đầy đủ nodes và edges, hệ thống chạy 2 thuật toán đồ thị:

#### a) Community Detection — Thuật toán Leiden

**Mục đích:** Tự động nhóm các symbol (hàm, class) thường tương tác với nhau thành **communities** (cụm chức năng).

**Tại sao cần:** Trong một repo lớn có hàng trăm file, developer (và AI) cần biết "vùng nào của codebase đảm nhận chức năng gì" — ví dụ: cụm Authentication, cụm Database, cụm API handlers, ...

**Cách hoạt động:**
1. Xây dựng đồ thị vô hướng từ các cạnh CALLS, EXTENDS, IMPLEMENTS
2. Chạy **thuật toán Leiden** — một thuật toán community detection tối ưu hóa modularity (mức độ phân tách giữa các nhóm)
3. Mỗi community được tự động đặt tên dựa trên folder chứa nhiều thành viên nhất (ví dụ: "Auth", "Database", "API")
4. Tính **cohesion** (độ gắn kết): tỉ lệ cạnh nội bộ / tổng cạnh — cho biết community có chặt chẽ hay không

**Ví dụ kết quả:**
```
Community "Auth" (cohesion: 0.85, 12 symbols):
  ├── LoginService.authenticate
  ├── LoginService.create_token
  ├── AuthMiddleware.verify_token
  └── ...

Community "Database" (cohesion: 0.92, 8 symbols):
  ├── UserRepository.find_by_username
  ├── UserRepository.create_user
  └── ...
```

Ngoài ra, hệ thống tạo cạnh **COMMUNITY_INTERACTS** khi 2 communities có nhiều lời gọi qua lại (≥3 edges) — cho thấy các khu vực nào phụ thuộc lẫn nhau.

#### b) Workflow / Scenario Detection — Xấp Xỉ Luồng Xử Lý

**Mục đích:** Phát hiện các **workflow khả dĩ** trong codebase — chuỗi các hàm có nhiều khả năng tham gia vào cùng một tác vụ xử lý.

> **Lưu ý học thuật:** Nếu chỉ dùng static call graph + BFS thì đây là **xấp xỉ hành vi** (behavioral approximation), chưa phải execution trace ground-truth. Muốn biết "code thực sự đã chạy thế nào", cần thêm dynamic evidence như trace, log, test coverage, profiling, hoặc framework-specific runtime metadata.

**Cách hoạt động:**
1. **Tìm entry points** — các hàm có nhiều khả năng là điểm bắt đầu:
   - Ít callers (không ai gọi → entry point)
   - Nhiều callees (gọi nhiều hàm khác → orchestrator)
   - Tên khớp patterns: `main`, `handle_request`, `process_*`, `on_*`
   - Có marker framework: `@app.route`, `@Controller`, ...
2. **BFS tracing** — từ mỗi entry point, duyệt theo cạnh CALLS để sinh các scenario khả dĩ:
   - Giới hạn độ sâu tối đa 10
   - Tránh loop (cycle detection)
   - Chỉ giữ traces ≥ 3 bước
3. **Loại bỏ trùng lặp** — remove traces là subset của traces khác

**Ví dụ kết quả:**
```
Workflow "Authenticate → CreateToken" (5 steps, cross-community):
  1. [Auth]     LoginService.authenticate
  2. [Database] UserRepository.find_by_username
  3. [Database] User.check_password
  4. [Auth]     LoginService.create_token
  5. [Auth]     jwt.encode

Workflow "CreateUser → SendEmail" (4 steps):
  1. [API]      UserController.create
  2. [Database] UserRepository.create_user
  3. [Email]    EmailService.send_welcome
  4. [Email]    EmailTemplate.render
```

### 3.5. Phương Pháp Luận: Tại Sao Thiết Kế Graph Như Vậy?

#### a) Cơ sở lý thuyết cho 5 nhóm Node

Trong lĩnh vực **Program Comprehension** (hiểu chương trình), việc hiểu một codebase đòi hỏi phải nắm bắt thông tin ở **nhiều mức trừu tượng khác nhau** — không mức nào thay thế được mức nào. Năm nhóm node trong hệ thống tương ứng với 5 mức trừu tượng này:

```
Mức trừu tượng tăng dần
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⑤ BEHAVIORAL    Workflow / Process      "Code chạy thế nào?"
                  (luồng xử lý khả dĩ)   Trả lời: scenario / flow
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ④ SEMANTIC      Community nodes         "Code tổ chức theo
                  (cụm chức năng)         chức năng thế nào?"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ③ CONCEPTUAL    Concept nodes           "Các representation nào
                  (khái niệm lõi)         thuộc cùng một concept?"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ② SYNTACTIC     Symbol nodes            "Code định nghĩa
                  (Function, Class, ...)  những gì?"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ① PHYSICAL      File, Folder nodes      "Code nằm ở đâu?"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

| Nhóm | Mức trừu tượng | Nguồn gốc lý thuyết | Trả lời câu hỏi |
|------|---------------|---------------------|-----------------|
| **File/Folder** | Physical | Cấu trúc hệ thống file — đơn vị biên dịch (compilation unit), tổ chức vật lý của dự án | "Code nằm ở đâu?", "Dự án có bao nhiêu file?" |
| **Symbol** (Function, Class, Method, ...) | Syntactic | **Lý thuyết ngôn ngữ lập trình (Programming Language Theory)** — mỗi ngôn ngữ định nghĩa các cấu trúc cú pháp (constructs) riêng | "Code định nghĩa những gì?", "Hàm này nhận tham số gì?" |
| **Concept** | Conceptual | **Domain modeling / ontology nhẹ / information architecture** — gom các representation cùng nói về một khái niệm dữ liệu hoặc nghiệp vụ | "Book trong hệ thống này gồm những representation nào?", "Các lớp nào cùng đại diện cho User?" |
| **Community** | Semantic | **Lý thuyết mạng (Network Science)** — thuật toán community detection phát hiện cấu trúc ẩn (emergent structure) trong đồ thị | "Các phần của code tổ chức theo chức năng thế nào?" |
| **Workflow / Process view** | Behavioral | **Phân tích luồng điều khiển (Control Flow Analysis)** — suy diễn các bước xử lý khả dĩ qua call graph | "Khi user login, code đi qua những bước nào?" |

**Tại sao cần cả 5 nhóm?**

Mỗi nhóm phục vụ một dạng câu hỏi khác nhau mà AI agent cần trả lời. Nếu chỉ có Symbol nodes (hàm, class), ta biết "code định nghĩa gì" — nhưng **không biết** chúng thuộc khu vực chức năng nào (cần Community), **không biết** các representation nào thực chất cùng nói về một khái niệm nghiệp vụ/dữ liệu (cần Concept), cũng **không biết** luồng xử lý khả dĩ (cần Workflow / Process view), và **không biết** tổ chức vật lý (cần File/Folder).

Ví dụ cụ thể khi thiếu từng nhóm:

| Nếu thiếu... | Không trả lời được |
|---------------|-------------------|
| File/Folder | "File nào chứa hàm authenticate?", "Cấu trúc thư mục?" |
| Concept | "BookEntity, BookDTO, AddBookRequest có cùng thuộc một concept không?", "Các representation của User là gì?" |
| Community | "Khu vực nào của code xử lý authentication?", "Phần nào phụ thuộc phần nào?" |
| Workflow / Process view | "Khi user login, flow xử lý đi qua những đâu?", "Hàm nào có khả năng chạy trước hàm nào?" |
| Symbol | "Hàm này nhận tham số gì?", "Class nào kế thừa class nào?" → Mất toàn bộ ngữ nghĩa code |

#### b) Tại sao Symbol node cần nhiều sub-types?

Symbol nodes có nhiều types (Function, Method, Class, Interface, Struct, Enum, ...) vì mỗi type được Syntax (cú pháp) của ngôn ngữ lập trình định nghĩa khác nhau, và mang **ý nghĩa cấu trúc khác nhau**:

| Type | Ý nghĩa cấu trúc | Quan hệ đặc trưng |
|------|-------------------|-------------------|
| **Function** | Đơn vị logic độc lập | CALLS → gọi hàm khác |
| **Method** | Logic gắn với một class | HAS_METHOD ← thuộc class |
| **Class** | Bản thiết kế (blueprint) cho object | EXTENDS, HAS_METHOD, HAS_PROPERTY |
| **Interface** | Hợp đồng (contract) mà class phải tuân theo | IMPLEMENTS ← được class implement |

Nếu gộp tất cả thành chung 1 type "Symbol", hệ thống sẽ **mất khả năng truy vấn có ngữ nghĩa**:
- Không phân biệt được "hàm nào kế thừa hàm nào" (chỉ Class mới EXTENDS)
- Không biết "interface nào đang được implement" (chỉ Interface mới làm đích của IMPLEMENTS)
- Không thể tính Method Resolution Order (chỉ áp dụng cho class hierarchy)

Việc giữ riêng các types cũng giúp tạo **Full-Text Search index riêng** cho mỗi type → tăng precision khi tìm kiếm.

#### c) Cơ sở lý thuyết cho các nhóm Edge (cạnh)

Tương tự nodes, các cạnh được nhóm theo nguồn gốc lý thuyết:

| Nhóm cạnh | Lý thuyết nền | Các cạnh | Giải thích |
|-----------|--------------|----------|------------|
| **Structural** (Chứa) | Cấu trúc file system | CONTAINS, HAS_METHOD, HAS_PROPERTY | Biểu diễn quan hệ vật lý "chứa trong" — giống cây thư mục |
| **Dependency** (Phụ thuộc) | **Call Graph** + **Dependency Graph Analysis** | CALLS, IMPORTS, USES | Biểu diễn phụ thuộc thời gian chạy/biên dịch — **đây là nền tảng cho thuật toán Leiden và workflow/scenario detection** |
| **Inheritance** (Kế thừa) | **Type Theory / OOP Theory** | EXTENDS, IMPLEMENTS, OVERRIDES | Biểu diễn hệ thống kiểu (type hierarchy) — cần thiết cho MRO, polymorphism |
| **Analytical** (Phân tích) | **Network Science**, **Control Flow** | MEMBER_OF, STEP_IN_PROCESS, COMMUNITY_INTERACTS | **Cạnh phát sinh từ thuật toán** — không có sẵn trong source code, được tính toán bởi Leiden và BFS |

**Điểm quan trọng:** Ba nhóm đầu (Structural, Dependency, Inheritance) được trích xuất trực tiếp từ source code (AST parsing). Nhóm thứ tư (Analytical) **không tồn tại trong code** — nó được **sinh ra bởi thuật toán** (Leiden → MEMBER_OF, BFS → STEP_IN_PROCESS). Đây chính là giá trị cốt lõi của Knowledge Graph: phát hiện cấu trúc ẩn (emergent structure) mà developer không thể thấy bằng mắt thường.

#### d) Trường `confidence` — Tại sao cạnh cần độ tin cậy?

Không phải mọi quan hệ đều chắc chắn 100%. Ví dụ:

| Tình huống | Confidence | Lý do |
|-----------|-----------|-------|
| `authenticate` gọi `self.create_token(user)` | **1.0** | Cùng class, resolve chính xác |
| `repo.find_by_username(name)` — repo được import | **0.8** | Cross-file, cần type inference |
| `process(data)` — nhiều hàm tên `process` tồn tại | **0.4** | Ambiguous, không chắc gọi hàm nào |

Confidence cho phép hệ thống:
- **Lọc noise** khi chạy Leiden (chỉ dùng edges confidence ≥ 0.5 cho repo lớn)
- **Đánh giá risk** trong impact analysis (cạnh confidence thấp → "có thể ảnh hưởng, nhưng không chắc chắn")
- **Xếp hạng kết quả** trong retrieval (ưu tiên quan hệ chắc chắn hơn)

### 3.6. Góc nhìn tổng quan hơn: một graph tốt không chỉ mô tả code, mà mô tả **hệ thống**

Thiết kế hiện tại là một **MVP rất tốt cho code-centric comprehension**, nhưng nếu xét theo mặt bằng phương pháp luận rộng hơn đến năm 2026 thì một kiến trúc đồ thị kiến thức mạnh hơn nên phân biệt rõ:

1. **Code facts** — những gì trích xuất được khá chắc chắn từ code và artifact kỹ thuật
2. **System views** — những lát cắt phục vụ câu hỏi ở mức kiến trúc, hành vi, feature, vận hành
3. **Evidence** — bằng chứng nào khiến ta tin vào node/edge này
4. **Version / Time** — graph này đúng ở commit, branch, release, hay môi trường nào

Nói cách khác, một codebase không chỉ là "graph của function/class", mà là một **hệ thống tri thức nhiều nguồn**.

### 3.7. Hàm ý thiết kế: nên tách `canonical graph` và `derived views`

Đây là điểm nâng cấp quan trọng nhất so với thiết kế hiện tại.

| Lớp | Nên chứa gì? | Ví dụ |
|-----|---------------|-------|
| **Canonical facts** | Quan hệ có nguồn gốc rõ ràng, tương đối ổn định | File chứa Symbol, Class implements Interface, Route gọi Handler, Test cover Function |
| **Linked artifacts** | Artifact ngoài source code nhưng liên quan trực tiếp | Build manifest, config, dependency, schema, issue, commit, ADR |
| **Derived analytical views** | Cấu trúc suy diễn từ thuật toán | Community, workflow/scenario, architecture component, hotspot, change-coupling area |
| **Evidence & provenance** | Bằng chứng và nguồn gốc của mọi fact/view | extractor, source file, trace id, commit sha, timestamp, confidence |

Nếu không tách các lớp này, hệ thống dễ gặp 2 vấn đề:
- **Trộn lẫn fact và hypothesis:** làm người dùng tưởng workflow/community là "sự thật tuyệt đối"
- **Khó mở rộng:** mỗi lần thêm một loại tri thức mới lại phải sửa schema cũ theo cách đan chéo

**Nguyên tắc đề xuất:** Graph lõi nên là `factual, normalized, incrementally maintainable`; còn các khái niệm như community, scenario, architecture recovery, impact cone nên được mô hình như **view** hoặc **overlay** dựng trên graph lõi.

---

## 4. Knowledge Graph — Cấu Trúc Lưu Trữ

### 4.1. Nơi lưu trữ

| Thành phần | Công nghệ | Vai trò |
|-----------|-----------|---------|
| **Đồ thị quan hệ** | KuzuDB (embedded graph database) | Lưu nodes + edges, truy vấn bằng Cypher |
| **Full-Text Search** | KuzuDB FTS Indexes | Tìm kiếm theo keyword (BM25) |
| **Vector Embeddings** | FAISS (in-memory) | Tìm kiếm theo ngữ nghĩa (semantic) |

### 4.2. Định dạng Node — Mỗi node chứa gì?

#### Code Symbol nodes (Function, Method, Class, Interface, ...)

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| [id](file:///f:/FPT/code-knowledge-graph/csg/ingestion/process_processor.py#322-324) | Định danh duy nhất (hash) | `"fn_a1b2c3"` |
| [name](file:///f:/FPT/code-knowledge-graph/csg/graph/lbug_schema.py#298-309) | Tên symbol | `"authenticate"` |
| `filePath` | Đường dẫn file | `"auth/login.py"` |
| `startLine`, `endLine` | Vị trí trong file | `10, 25` |
| [content](file:///f:/FPT/code-knowledge-graph/csg/agent/planner.py#129-178) | Mã nguồn nguyên bản | `"def authenticate(self, ...):\n  ..."` |
| `signature` | Chữ ký hàm | `"authenticate(self, username: str, password: str) -> Token"` |
| `parameterCount` | Số tham số | `2` |
| `returnType` | Kiểu trả về | `"Token"` |
| `isExported` | Có được export/public không | `true` |
| `fanIn` | Số symbol gọi đến nó | `5` |
| [description](file:///f:/FPT/code-knowledge-graph/csg/agent/planner.py#200-255) | Docstring/comment | `"Verify user credentials"` |
| `searchText` | Text đã xử lý cho FTS | `"authenticate login service auth"` |

#### Concept node

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| `name` | Tên khái niệm lõi | `"Book"` |
| `conceptKind` | Dữ liệu hay nghiệp vụ | `"data_concept"` |
| `alias` | Tên tương đương / biến thể | `["BookEntity", "BookDTO", "AddBookRequest"]` |
| `description` | Mô tả ngắn | `"Các representation của thực thể Book trong hệ thống"` |
| `confidence` | Độ chắc chắn khi gom nhóm | `0.82` |

> Đây là node semantic mặc định nhưng nên giữ **nhẹ**: nó không thay thế Symbol, mà chỉ gom các Symbol có nhiều khả năng cùng nói về một concept.

#### Community node

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| [name](file:///f:/FPT/code-knowledge-graph/csg/graph/lbug_schema.py#298-309) | Tên community (auto-generated) | `"Auth"` |
| `heuristicLabel` | Nhãn mô tả | `"Auth"` |
| `symbolCount` | Số symbol trong community | `12` |
| [cohesion](file:///f:/FPT/code-knowledge-graph/csg/ingestion/community_processor.py#282-314) | Độ gắn kết (0-1) | `0.85` |

#### Workflow / Process node (analytical view)

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| [name](file:///f:/FPT/code-knowledge-graph/csg/graph/lbug_schema.py#298-309) | Tên workflow / process | `"Authenticate → CreateToken"` |
| `processType` | Nội bộ hay cross-community | `"cross_community"` |
| `stepCount` | Số bước | `5` |
| `entryPointId` | ID của hàm bắt đầu | `"fn_auth_001"` |
| `terminalId` | ID của hàm kết thúc | `"fn_jwt_042"` |

> Nên xem node này như **behavioral view** được suy diễn từ graph, không phải execution trace ground-truth.

#### File node

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| [name](file:///f:/FPT/code-knowledge-graph/csg/graph/lbug_schema.py#298-309) | Tên file | `"login.py"` |
| `filePath` | Đường dẫn | `"auth/login.py"` |
| [content](file:///f:/FPT/code-knowledge-graph/csg/agent/planner.py#129-178) | Nội dung file | (toàn bộ source code) |
| `lineCount` | Số dòng | `150` |
| `fanIn` | Số file import file này | `8` |

### 4.3. Định dạng Edge — Mỗi cạnh chứa gì?

Tất cả cạnh được lưu trong một bảng quan hệ duy nhất (`CodeRelation`) với các trường:

| Trường | Ý nghĩa | Ví dụ |
|--------|---------|-------|
| `type` | Loại quan hệ | `"CALLS"`, `"IMPORTS"`, `"MEMBER_OF"` |
| `confidence` | Độ tin cậy (0-1) | `0.95` |
| `reason` | Lý do/chi tiết | `"direct_call"`, `"step-3"` |
| `inCycle` | Có nằm trong circular import? | `true/false` |

**Các loại cạnh quan trọng:**

| Cạnh | Source → Target | Ý nghĩa |
|------|-----------------|---------|
| `CALLS` | Function → Function | Hàm A gọi hàm B |
| `IMPORTS` | File → File | File A import từ File B |
| `EXTENDS` | Class → Class | Class A kế thừa Class B |
| `IMPLEMENTS` | Class → Interface | Class implement Interface |
| `CONTAINS` | Folder → File, File → Function | Chứa |
| `MEMBER_OF` | Symbol → Community | Symbol thuộc community nào |
| `STEP_IN_PROCESS` | Symbol → Process | Symbol là bước thứ N trong workflow/process view |
| `COMMUNITY_INTERACTS` | Community → Community | 2 community tương tác qua lại |
| `OVERRIDES` | Method → Method | Method ghi đè method cha |
| `REPRESENTS_CONCEPT` | Symbol → Concept | Symbol là một representation của concept nào |
| `RELATED_CONCEPT` | Concept → Concept | Hai concept có liên hệ gần (ví dụ Book và Author) |

### 4.4. Minh họa Knowledge Graph

```
                    ┌────────────────┐
                    │  Community     │
                    │  "Auth"        │
                    │  cohesion:0.85 │
                    └───────┬────────┘
                   MEMBER_OF│
                            │
┌──────────┐  CALLS   ┌─────▼──────┐  CALLS  ┌──────────────┐
│ API      │─────────▶│ Login      │────────▶│ User         │
│ handler  │          │ Service.   │         │ Repository.  │
│          │          │ authenticate│         │ find_by_user │
└──────────┘          └─────┬──────┘         └──────┬───────┘
                            │                       │
                       CALLS│                  MEMBER_OF
                            │                       │
                      ┌─────▼──────┐         ┌──────▼───────┐
                      │ Login      │         │  Community   │
                      │ Service.   │         │  "Database"  │
                      │ create_    │         │  cohesion:   │
                      │ token      │         │  0.92        │
                      └────────────┘         └──────────────┘

             ┌───────────────────────────┐
             │  Workflow / Process       │
             │  "Authenticate→CreateToken"│
             │  type: cross_community    │
             │  steps: 5                 │
             └───────────────────────────┘
```

### 4.5. Những loại node/edge nên bổ sung để kiến trúc mạnh hơn

Nếu mục tiêu là hỗ trợ **AI agent hiểu và thao tác trên codebase** chứ không chỉ dựng call graph đẹp, schema nên mở rộng theo các nhóm sau:

| Nhóm bổ sung | Nên có gì? | Lý do |
|-------------|-------------|-------|
| **Concept nodes** | Book, User, Order, Invoice, ... | Gom các Symbol cùng đại diện cho một khái niệm dữ liệu/nghiệp vụ; khác với Community vì Community nhóm theo tương tác, còn Concept nhóm theo nghĩa |
| **Architecture nodes** | Module, Component, Layer, Service, Bounded Context | Community do Leiden tìm ra rất hữu ích nhưng không tương đương với kiến trúc mà team thiết kế |
| **Entry-point nodes** | Route, Endpoint, CLI command, Job, Event handler, Queue consumer | Nhiều câu hỏi thực tế bắt đầu từ "request nào", "event nào", không bắt đầu từ một function bất kỳ |
| **Data / Schema nodes** | Table, Column, DTO, Message schema, Config schema | Để trả lời "data nào bị ảnh hưởng?" và nối code với persistence / integration |
| **Build & Environment nodes** | Package, Dependency, Build target, Env var, Feature flag, Config file | Nhiều lỗi và hành vi phụ thuộc môi trường, không nằm hoàn toàn trong source code |
| **Test nodes** | Test case, Assertion, Coverage slice, Fixture | Test là bằng chứng quan trọng cho behavior và contract |
| **Evolution nodes** | Commit, PR, Issue, Release, Author/Owner | Giúp trả lời câu hỏi về intent, hotspot, change coupling, ownership |
| **Document / Intent nodes** | ADR, Requirement, Feature, Glossary concept | Đưa domain intent và rationale vào cùng graph |
| **Runtime evidence nodes** | Trace, Span, Log event, Profile sample | Cần thiết nếu muốn nâng từ "workflow khả dĩ" lên "execution happened" |

**Metadata nên bổ sung cho mọi fact / edge:**
- `sourceKind`: AST, parser, build file, git, issue tracker, trace, test
- `sourceRef`: file path, commit sha, trace id, issue id
- `observedAt` / `validForVersion`: đúng ở version hoặc environment nào
- `status`: observed / inferred / user-asserted / deprecated
- `confidence`: độ chắc chắn

**Khuyến nghị quan trọng:** Thay vì nhét tất cả vào chung một loại node `Symbol`, nên để graph có một **schema lõi nhỏ nhưng giàu semantics**. Theo hướng tối giản mở rộng, `Concept` là node semantic mặc định đáng có; còn các family khác chỉ nên thêm khi bài toán thật sự cần.

---

## 5. Layered Retrieval — Thuật Toán Truy Vấn

### 5.1. Ý tưởng cốt lõi

Thay vì đưa toàn bộ code vào prompt, hệ thống truy vấn theo **các view phân tầng** — từ tổng quan (ít chi tiết, ít token) đến chi tiết (nhiều token nhưng chỉ cho thành phần cần thiết). Với bản MVP có thể giữ 6 tầng, nhưng về nguyên lý mỗi tầng nên tương ứng với **một loại câu hỏi**:

```
Tầng 0: TOPOLOGY / ARCHITECTURE
    "Dự án này có những khu vực, component, boundary nào?"
    → Community, module, component, layer, service interaction

Tầng 1: RELEVANCE / FEATURE
    "Câu hỏi này liên quan đến feature, artifact, hay khu vực nào?"
    → Hybrid search + traceability + grouping theo view phù hợp

Tầng 2: BEHAVIOR / SCENARIO
    "Use-case này đi qua những bước xử lý nào?"
    → Workflow khả dĩ, entry points, handlers, downstream calls

Tầng 3: CROSSCUT / IMPACT / EVOLUTION
    "Có phụ thuộc chéo, hotspot, circularity, change coupling nào?"
    → Shared utility, dependency smell, ownership, history, impact cone

Tầng 4: CONTRACT / INTERFACE
    "Symbol hoặc component này hứa hẹn điều gì?"
    → Signature, schema, callers, callees, tests, invariants

Tầng 5: IMPLEMENTATION / EVIDENCE
    "Code cụ thể, config cụ thể, bằng chứng cụ thể là gì?"
    → Source code, config, test, trace, commit, issue, ADR
```

**Ưu điểm:** Mỗi câu hỏi chỉ cần 1-3 tầng, tiết kiệm đáng kể token. Ví dụ:
- "Project structure?" → chỉ cần Tầng 0 (~200 tokens)
- "How does auth work?" → Tầng 1 + 2 (~800 tokens)
- "What breaks if I change function X?" → Tầng 4 + impact analysis (~500 tokens)

Khi graph được mở rộng thêm các artifact ngoài code, cùng một cơ chế này còn trả lời được:
- "Feature này bắt nguồn từ issue/ADR nào?"
- "Endpoint này dùng config, schema, test, và dependency nào?"
- "Đường đi tĩnh nói gì, runtime trace thực tế nói gì?"

### 5.2. Tầng 1 — Hybrid Search (Chi tiết)

Khi user đặt câu hỏi, hệ thống kết hợp 2 phương pháp tìm kiếm:

**BM25 (Keyword Search):**
- Tìm theo từ khóa chính xác trong Full-Text Search indexes
- Tiền xử lý query: tách camelCase (`getUserInfo` → `get user info`), loại stop words, tách compound words (`websocket` → `web socket`)
- Query 11 indexes song song (Function, Class, Method, ...)

**Semantic Search:**
- Embed câu hỏi thành vector
- Tìm nearest neighbors trong FAISS index
- Tìm theo ý nghĩa, không cần khớp từ chính xác ("xác thực" ↔ "authentication")

**Reciprocal Rank Fusion (RRF) — Kết hợp kết quả:**

Thay vì so sánh trực tiếp điểm BM25 với điểm cosine similarity (thang đo khác nhau), RRF dùng **thứ hạng**:

```
RRF_Score(item) = 1/(K + rank_bm25) + 1/(K + rank_semantic)
   với K = 60 (hằng số smoothing)
```

Nếu một symbol xếp hạng cao ở CẢ HAI phương pháp → RRF score cao → đó là kết quả chất lượng nhất.

**Sau khi có kết quả search:** Nhóm các symbol theo community (qua cạnh MEMBER_OF) → biết câu hỏi liên quan đến khu vực code nào nhất. Kèm theo **confidence score** và signal (strong/moderate/weak) để agent biết mức độ chắc chắn.

### 5.3. Tầng 2 — Truy vấn workflow / scenario

Sau khi biết community liên quan, hệ thống truy vấn:
1. Tất cả workflow/process nodes có bước thuộc community đó (qua STEP_IN_PROCESS + MEMBER_OF)
2. Sắp xếp các bước theo thứ tự (step-1, step-2, ...)
3. Trả về luồng hoàn chỉnh: "Authenticate gọi FindUser gọi CheckPassword gọi CreateToken"

### 5.4. Auto-Resolution — Tự động duyệt các tầng

Khi nhận một câu hỏi, hệ thống tự động quyết định cần duyệt bao nhiêu tầng:

```
Câu hỏi vào → Tầng 1 (search, nhóm theo community)
           → Nếu confidence cao:
               → Tầng 2 (lấy top workflow + symbols)
               → Tầng 4 (lấy signature cho 2-3 symbol quan trọng)
           → Nếu cross-cutting (trải đều nhiều community):
               → Tầng 3 (kiểm tra patterns xuyên suốt)
           → Gộp kết quả, nén (compress), trả về
```

---

## 6. Kiến Trúc Knowledge Graph Mở Rộng Đề Xuất

### 6.1. Mô hình kiến trúc nên hướng tới

Một kiến trúc mạnh hơn, bền hơn trước thay đổi thuật toán, nên gồm các lớp sau:

| Lớp | Vai trò |
|-----|---------|
| **Artifact Layer** | Biểu diễn các nguồn tri thức: source code, config, test, build, schema, docs, issues, commits, traces |
| **Canonical Fact Layer** | Lưu các quan hệ được quan sát hoặc resolve rõ ràng: defines, contains, imports, calls, implements, depends_on, tests, mentions |
| **Semantic / System Layer** | Mô hình các khối có ý nghĩa hệ thống: module, component, service, feature, concept, API boundary |
| **Analytical View Layer** | Các cấu trúc suy diễn: community, workflow/scenario, architecture view, impact cone, hotspot, ownership area |
| **Retrieval / Agent Layer** | Cung cấp projection theo task: topology, architecture, behavior, impact, implementation, evolution |

### 6.2. Những nâng cấp nên ưu tiên

| Mức ưu tiên | Nâng cấp | Lý do |
|------------|----------|-------|
| **P0** | **Tách graph lõi và analytical views** | Giúp phân biệt fact với hypothesis; dễ giải thích và mở rộng |
| **P0** | **Thêm provenance / evidence / version cho mọi edge** | Không chỉ biết "có quan hệ", mà biết quan hệ này đến từ đâu và đúng ở version nào |
| **P0** | **Thêm lightweight Concept nodes** | Cho phép nhóm các representation cùng nói về một khái niệm như Book/User mà không phải lạm dụng Community |
| **P0** | **Thêm entry-point nodes**: Route, Endpoint, Command, Job, Event handler | Câu hỏi thực tế thường bắt đầu từ trigger hệ thống, không phải từ function bất kỳ |
| **P0** | **Thêm build/config/dependency nodes** | Rất nhiều hành vi và lỗi đến từ môi trường, DI, feature flag, package version |
| **P1** | **Thêm architecture nodes**: Module, Component, Layer, Service | Community chỉ là cụm thống kê; cần một view kiến trúc rõ ràng hơn cho AI agent |
| **P1** | **Thêm data/schema nodes**: Table, DTO, Message, Config schema | Bổ sung trục "data flow" và "integration boundary" cho impact analysis |
| **P1** | **Thêm test/coverage nodes** | Test là bằng chứng tốt cho contract, expected behavior, và regression risk |
| **P1** | **Thêm evolution nodes**: Commit, PR, Issue, Owner | Trả lời tốt hơn câu hỏi về intent, hotspot, change coupling, ownership |
| **P2** | **Thêm domain/intent nodes**: Feature, Requirement, ADR, Glossary concept | Đưa AI agent đến gần hơn với cách con người hiểu hệ thống |
| **P2** | **Thêm runtime evidence nodes**: Trace, Span, Log event, Profile sample | Cần khi muốn nâng từ static approximation lên runtime-grounded reasoning |

### 6.3. Những gì nên giữ từ thiết kế hiện tại

- **tree-sitter + deterministic extraction** vẫn là lựa chọn rất tốt cho lớp ingest lõi.
- **Confidence** là ý tưởng đúng, nhưng nên mở rộng thành `evidence + provenance + status + version`.
- **Community detection** vẫn hữu ích, nhưng nên xem là **exploratory view**, không phải architecture truth.
- **Workflow/process tracing** vẫn hữu ích cho program comprehension, nhưng nên được trình bày là **scenario approximation** nếu chưa có runtime evidence; nó không đồng nhất với mọi mẫu gọi cục bộ như `A -> {B,C,D}`.
- **Layered retrieval** là hướng rất phù hợp cho AI agent; chỉ cần tổng quát hóa các tầng theo task thay vì gắn cứng vào schema hiện tại.

### 6.4. Hình dung ngắn gọn về thiết kế nâng cấp

```
Artifacts
  ├── Code / Config / Tests / Build / Docs / Issues / Git / Traces
  ↓
Canonical Facts
  ├── File, Symbol, Type, Contract, Route, Dependency, Test, Commit, Issue
  ↓
Semantic System Model
  ├── Module, Component, Service, Feature, Concept, Data Schema
  ↓
Analytical Views
  ├── Community, Workflow, Architecture View, Impact Cone, Hotspot
  ↓
Task-aware Retrieval
  ├── Structure / Architecture / Behavior / Impact / Evolution / Evidence
```

---

## 7. Tổng Kết

| Khía cạnh | Định hướng thiết kế |
|-----------|---------------------|
| **Biểu diễn codebase** | Multi-view Knowledge Graph / Knowledge Fabric |
| **Nguồn tri thức** | Source code + config + build + test + docs + issues + git + traces (tùy giai đoạn) |
| **Lõi ingestion** | Ưu tiên deterministic parsing / resolution / linking |
| **Mô hình dữ liệu** | Tách `canonical facts` khỏi `derived analytical views` |
| **Mức tri thức** | Physical, syntactic, dependency, contract, behavioral, architectural, evolutionary, domain |
| **Truy vấn** | Task-aware layered retrieval thay vì chỉ retrieve code text |
| **Bằng chứng** | Mỗi relation nên có confidence + provenance + version |
| **Vai trò của LLM** | Dùng ở lớp diễn giải/tóm tắt nếu cần; không phụ thuộc hoàn toàn cho ingestion |

## 8. Cơ Sở Phương Pháp Luận Tham Khảo

- **Program comprehension / mental models:** Brooks, Pennington, Letovsky, von Mayrhauser & Vans. Điểm chung: hiểu chương trình là xây mô hình ở nhiều mức trừu tượng.
- **Architecture viewpoints & recovery:** Kruchten 4+1, ISO/IEC/IEEE 42010, Reflexion Model, Symphony. Điểm chung: không có một view duy nhất cho mọi stakeholder.
- **Dependence-based program representation:** CFG, PDG, SDG, CPG. Điểm chung: cần biểu diễn phụ thuộc điều khiển và dữ liệu, không chỉ AST/call graph.
- **Software knowledge graph:** IntelliDE / Software Knowledge Graph, CodeOntology, GitGraph, SemRepo. Điểm chung: cần nối code với artifact ngoài code.
- **Graph-backed retrieval for AI coding:** các hướng repository-level graph retrieval gần đây cho thấy graph hữu ích nhất khi đóng vai trò substrate cho search, navigation, explainability và context compression.
