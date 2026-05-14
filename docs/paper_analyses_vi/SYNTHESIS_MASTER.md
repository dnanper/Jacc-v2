# Sơ đồ tri thức mã: Tổng hợp nghiên cứu toàn diện

**Ngày**: Tháng 4 năm 2025
**Giấy tờ được phân tích**: 11 (2404.00599, 2310.06770, 2505.14394, 2511.07584, 2406.07003, 2408.03910, 2503.21710, 2411.11532, 2304.09048, 2603.07326, 2603.21430)
**Phạm vi**: Tìm hiểu, tạo, sửa chữa và kiểm tra mã cấp kho lưu trữ

---

## Tóm tắt điều hành

Biểu đồ kiến ​​thức mã (KG) đã nổi lên như một **mô hình cơ bản** để nâng cao công nghệ phần mềm dựa trên LLM. Sau khi phân tích 11 bài báo chuyên đề, chúng tôi xác định:

1. **Sự đồng thuận**: Việc biểu diễn kho lưu trữ có cấu trúc đồ thị cải thiện đáng kể khả năng truy xuất ngữ cảnh (tăng 15-50% đối với các tác vụ phức tạp)
2. **Sự phát triển**: Từ tăng cường truy xuất đơn giản → tạo nhận thức ràng buộc → tích hợp tác nhân
3. **Tính năng quan trọng**: Truyền tải nhiều bước nắm bắt các mối quan hệ không thể tìm thấy chỉ bằng cách nhúng sự tương đồng
4. **Miền ứng dụng**: Tạo, sửa chữa, hoàn thiện, thử nghiệm, điều chỉnh miền
5. **Giới hạn hiệu suất**: SemanticForge dẫn đầu với 49,8% Pass@1 trên REPOKG-50, giảm 52% lỗi thông qua các ràng buộc SMT

---

## 1. Phân loại các phương pháp tiếp cận

### 1.1 Bằng ứng dụng chính

|Loại|giấy tờ|Vấn đề cốt lõi|Hiệu suất tốt nhất|
|----------|--------|--------------|------------------|
|**Điểm chuẩn**|2404.00599 (EvoCodeBench), 2310.06770 (SWE-Băng ghế)|Khoảng cách đánh giá|Thiết lập các tiêu chuẩn; tiết lộ <2% đường cơ sở|
|**Tạo mã**|2505.14394, 2511.07584 (SemanticForge)|Bối cảnh kho lưu trữ|36,36% (EvoCodeBench), 49,8% (REPOKG-50)|
|**Hoàn thành mã**|2406.07003 (Bộ mã hóa đồ thị)|Ngữ cảnh nội bộ tập tin|So khớp mã +6, so khớp mã định danh +6|
|**Sửa chữa phần mềm**|2503.21710 (KGCompass), 2603.07326 (Tiếng vang)|Định vị lỗi|58,3% (SWE-Bench Lite), 66,28% (sinh sản)|
|**Kiểm tra lông tơ**|2411.11532 (CKGFuzzer)|Thế hệ trình điều khiển|+ Độ bao phủ 8,73%, 11 lỗi (9 lỗi mới)|
|**Điều chỉnh tên miền**|2603.21430 (Đại lý trực tiếp)|Kiến thức chuyên ngành|67% trên DS-1000 (so với mức cơ bản 45%)|
|**Xây dựng KG**|2304.09048 (Mã KGC)|Tòa nhà KG tự động|+4,5% F1 trên ACE04|

### 1.2 Bằng phương pháp kỹ thuật

|Sự đổi mới|Giấy tờ sử dụng nó|Sự va chạm|
|------------|-----------------|--------|
|**Truy xuất kết hợp** (toàn văn bản + vectơ + đồ thị)|2505.14394, 2603.21430|Mẫu phổ biến nhất; lợi nhuận vững chắc|
|**Đồ thị tĩnh-động kép**|2511.07584 (chỉ)|+7,3% Pass@1 chỉ từ động|
|**Thế hệ tích hợp SMT**|2511.07584 (chỉ)|-52% lỗi sơ đồ, công nghệ biên giới|
|**Học truy vấn đồ thị**|2511.07584 (được đào tạo), 2408.03910 (LLM)|Độ chính xác 73% so với 51%|
|**Biểu đồ ngữ cảnh mã (CCG)**|2406.07003 (chỉ)|Cấp độ tuyên bố; +6 trận đấu|
|**Liên kết hiện vật** (vấn đề/PR)|2503.21710|Cho phép sửa chữa nhiều bước nhảy|
|**Lựa chọn trường hợp theo hướng dẫn của KG**|2603.21430|Đế hộp nhỏ, độ che phủ cao|
|**Nhắc nhở nhận biết lược đồ**|2304.09048|CodeLM cho xây dựng KG|

---

## 2. Các mẫu thiết kế lược đồ đồ thị

### 2.1 Các loại nút phổ biến (Đồng thuận)

```
Thiết yếu:
- TẬP TIN / MÔ-ĐUN
- LỚP HỌC
- CHỨC NĂNG (độc lập)
- PHƯƠNG PHÁP (giới hạn lớp)
- THUỘC TÍNH / TRƯỜNG
- BIẾN (tùy chọn)

Mở rộng (dành riêng cho nhiệm vụ):
- VẤN ĐỀ (sửa chữa/sao chép)
- PULL_REQUEST (sửa chữa)
- KIỂM TRA (kiểm tra)
- TEST_FILE (thử nghiệm)
- THAM SỐ (làm mờ)
- TYPE / DATA_STRUCTURE (dành riêng cho tên miền)
- GLOBAL_VARIABLE / CONSTANT
```

### 2.2 Các loại cạnh phổ biến (Đồng thuận)

```
Kết cấu:
- CHỨA / ĐỊNH NGHĨA (tệp → lớp/hàm)
- Kế thừa (lớp → lớp cha)
- HAS_METHOD (lớp → phương thức)
- HAS_FIELD (lớp/cấu trúc → trường)

Phụ thuộc:
- CUỘC GỌI / GỌI (chức năng → chức năng)
- SỬ DỤNG/TÀI LIỆU THAM KHẢO (câu lệnh → biến/hàm)
- NHẬP KHẨU (mô-đun → mô-đun)
- DEPENDS_ON (chung)

Ngữ nghĩa:
- RELATED_TO (tương tự về khái niệm)
- INSTANCE_OF (đối tượng → lớp)
- OVERRIDES (phương thức → phương thức gốc)
- TÀI LIỆU (doc → phần tử mã)
```

### 2.3 Phần mở rộng lược đồ dành riêng cho nhiệm vụ

**Sửa chữa** (2503.21710):
```
VẤN ĐỀ --đề cập--> TẬP TIN/CHỨC NĂNG
PR --sửa lỗi--> VẤN ĐỀ
PR --sửa đổi--> TỆP/CHỨC NĂNG
KIỂM TRA --covers--> CHỨC NĂNG
```

**Làm mờ** (2411.11532):
```
CHỨC NĂNG --đọc--> BIẾN
CHỨC NĂNG --ghi--> BIẾN
CHỨC NĂNG --phân bổ--> TÀI NGUYÊN
CHỨC NĂNG --miễn phí--> TÀI NGUYÊN
API_COMBINATION --includes--> {FUNCTIONS}
```

**Điều chỉnh tên miền** (2603.21430):
```
GÓI --chứa-->CHỨC NĂNG
CHỨC NĂNG --trả về--> LOẠI
CHỨC NĂNG --chấp nhận--> LOẠI
KHÁI NIỆM -- liên quan_ đến--> CHỨC NĂNG
CASE --trình diễn--> API_PATTERN
```

---

## 3. Biện pháp thi công: Đánh đổi

|Phương pháp|Sự chính xác|Tốc độ|Trị giá|Ảnh chụp|
|--------|----------|-------|------|----------|
|**AST tĩnh**|100% về kết cấu|Nhanh|Thấp|Gọi, chứa, kế thừa|
|**Dấu vết động**|Hành vi thời gian chạy|Chậm|Cao|Đường dẫn, loại thực tế|
|**Trích xuất LLM**|Ý định ngữ nghĩa|Trung bình|Trung bình-Cao|Tài liệu, mục đích|
|** Lai **|Tổng thể tốt nhất|Chậm|Cao|Cả cấu trúc + ngữ nghĩa|

**Xu hướng đồng thuận**: Bắt đầu với AST tĩnh (nhanh, đáng tin cậy), tăng cường bằng LLM (ngữ nghĩa), thêm động nếu cần (hành vi).

**Giấy sử dụng kết hợp**: 2511.07584 (tĩnh+động), 2505.14394 (AST+LLM), 2603.21430 (KG+CBR)

---

## 4. Chiến lược truy xuất: So sánh hiệu quả

### 4.1 Đường cơ sở: Dựa trên sự tương đồng

**Phương pháp**: BM25, nhúng tương tự
**Ưu điểm**: Đơn giản, nhanh chóng, phù hợp với kết quả rõ ràng
**Nhược điểm**: Sai lệch từ vựng, bỏ qua các mối quan hệ chuyển tiếp, không có cấu trúc
**Hiệu suất**: ~20-40% đối với các tác vụ kho lưu trữ

### 4.2 Truyền tải đồ thị (n-hop)

**Phương pháp**: Bắt đầu từ mục tiêu, mở rộng sang các mục tiêu lân cận với trọng số phân rã
**Giấy tờ**: 2406.07003 (CCG slicing), 2505.14394 (mở rộng đồ thị con)
**Ưu điểm**: Nắm bắt được các phần phụ thuộc, tôn trọng cấu trúc, phạm vi có thể định cấu hình
**Nhược điểm**: Tốn kém về mặt tính toán, cần cắt tỉa
**Hiệu suất**: ~33-36% Pass@1 (EvoCodeBench)

### 4.3 Tạo truy vấn đồ thị

**Phương pháp**: Chuyển đổi ngôn ngữ tự nhiên sang các truy vấn giống Cypher/SQL
**Các biến thể**:
- LLM đặc biệt (2408.03910): độ chính xác 51%
- Chính sách đã học (2511.07584): độ chính xác 73% (+ cải thiện 22%)
**Ưu điểm**: Chính xác, dễ hiểu, linh hoạt
**Nhược điểm**: Chất lượng truy vấn rất quan trọng; Truy vấn LLM không đáng tin cậy

### 4.4 Tìm kiếm kết hợp

**Phương pháp**: Kết hợp tín hiệu toàn văn + vector + đồ thị
**Giấy**: 2505.14394
**Công thức**: Điểm = α·text_match + β·vector_sim + γ·graph_proximity
**Ưu điểm**: Mạnh mẽ với các loại truy vấn khác nhau
**Nhược điểm**: Cần điều chỉnh thông số
**Kết quả**: Chất lượng truy xuất tốt nhất trong số các kết quả được so sánh

### 4.5 Truy xuất có hướng dẫn đường dẫn

**Phương pháp**: Đường dẫn thực thể nhiều bước nhảy (vấn đề → PR → chức năng)
**Giấy**: 2503.21710
**Thống kê quan trọng**: 89,7% sửa chữa thành công yêu cầu nhiều bước nhảy
**Thông tin chi tiết**: Single-hop (tương tự) không đủ cho các tác vụ phức tạp

---

## 5. Các mô hình tích hợp với LLM

### 5.1 Tăng cường bối cảnh (Phổ biến nhất)

**Mẫu**: Truy xuất sơ đồ con → định dạng dưới dạng văn bản → đưa vào dấu nhắc LLM

**Thực hiện**:
```python
context = kg.retrieve(query, top_k=20)
prompt = f"""
Repository context:
{format_subgraph(context)}

Task: {user_query}
"""
```

**Người sử dụng**: 2505.14394, 2406.07003, 2503.21710, 2603.07326, 2411.11532, 2603.21430

**Ưu điểm**: Đơn giản, hoạt động với mọi LLM, không cần đào tạo
**Nhược điểm**: Giới hạn độ dài ngữ cảnh, LLM phải hiểu định dạng biểu đồ

### 5.2 Tạo nhận thức ràng buộc (Biên giới)

**Mẫu**: Mã hóa các ràng buộc KG vào chính quá trình tạo

**Phương pháp**: Bộ giải SMT trong tìm kiếm chùm tia (2511.07584)
- Trong quá trình lấy mẫu mã thông báo, hãy kiểm tra xem ứng viên có vi phạm loại/chữ ký không
- Cắt bỏ những phần tiếp theo không hợp lệ
- Đảm bảo tuân thủ lược đồ

**Kết quả**: -52% lỗi sơ đồ, +15,6% Đạt@1

**Ưu điểm**: Ngăn ngừa sai sót, đảm bảo chính thức
**Nhược điểm**: Tích hợp phức tạp, chi phí SMT, các ràng buộc không thể quyết định

### 5.3 Dịch truy vấn

**Mẫu**: LLM tạo truy vấn biểu đồ, thực thi, sử dụng kết quả

**Phương pháp**: Hệ thống hai tác nhân (2408.03910):
- Tác nhân phân tích: Xác định thông tin cần thiết
- Đại lý dịch thuật: Chuyển đổi sang Cypher
- Thực hiện → kết quả → tổng hợp

**Ưu điểm**: Giao diện ngôn ngữ tự nhiên, linh hoạt
**Nhược điểm**: Chất lượng truy vấn khác nhau (độ chính xác 51-73%), xử lý lỗi phức tạp

### 5.4 Tích hợp truy xuất kép

**Mẫu**: Kết hợp các trường hợp KG có cấu trúc + phi cấu trúc

**Phương pháp**: 2603.21430:
- Từ trên xuống: KG cung cấp chữ ký, loại API
- Từ dưới lên: Các trường hợp hiển thị mô hình sử dụng
- LLM tổng hợp cả hai

**Ưu điểm**: Kiến thức đầy đủ (khái niệm + mẫu)
**Nhược điểm**: Cần duy trì hai hệ thống truy xuất

---

## 6. Bối cảnh biểu diễn

### 6.1 Điểm chuẩn và công nghệ tiên tiến

|Điểm chuẩn|Loại nhiệm vụ|Mẫu|SOTA tốt nhất|Giấy|
|-----------|-----------|---------|-----------|-------|
|**Đánh giá con người**|Chức năng độc lập|164|~80% (GPT-4)|Không tập trung vào KG|
|**EvoCodeBench**|Tạo cấp độ repo|275|36,36% (Claude 3,5 Sonnet + KG)|2505.14394|
|**REPOKG-50**|Nhiệm vụ cấp repo|4.250|49,8% (CodeLlama-34B + KG+SMT)|2511.07584|
|**SWE-Băng ghế**|Vấn đề sửa chữa|2.294|~2% (Claude 2)|Đường cơ sở 2310.06770|
|**SWE-Băng ghế dự bị Lite**|Vấn đề sửa chữa|300|58,3% (Claude-4 Sonnet + KG)|2503.21710|
|**SWT-Băng ghế đã được xác minh**|Kiểm tra sinh sản|~300|66,28% (Tiếng vang)|2603.07326|
|**DS-1000**|Khoa học dữ liệu miền|1.000|67% (Đại lý độc quyền)|2603.21430|
|**Đánh giá mã chéo**|Hoàn thành nhiều tập tin|Khác nhau|Cạnh tranh|2408.03910|

**Quan sát chính**: Các phương pháp tiếp cận KG cho thấy **lợi ích lớn nhất đối với các nhiệm vụ khó, ở quy mô kho lưu trữ**. Trên HumanEval (độc lập đơn giản), mức tăng tối thiểu (<5%). Điều này chứng tỏ KG giải quyết được **vấn đề bối cảnh** - khi bối cảnh quan trọng nhất, KG sẽ thực hiện.

### 6.2 Số liệu giảm lỗi

Ngoài Pass@1, một số bài viết đo lường các loại lỗi cụ thể:

|Giấy|Loại lỗi|Sự giảm bớt|
|-------|------------|-----------|
|2511.07584 (SemanticForge)|Ảo giác sơ đồ (loại/chữ ký)|49,8%|
|2511.07584|Ảo giác logic (điều khiển/luồng dữ liệu)|34,7%|
|2411.11532 (CKGFuzzer)|Khối lượng công việc xem xét sự cố thủ công|84,4%|
|2503.21710 (KGCompass)|Tìm kiếm bản địa hóa lỗi (đến 20 ứng viên)|Giảm hơn 95%|

**Thông tin chi tiết**: KG không chỉ cải thiện tỷ lệ thành công - chúng **loại bỏ một cách có hệ thống các chế độ thất bại cụ thể**.

---

## 7. Những thách thức chung giữa các bài báo

### 7.1 Khả năng mở rộng

**Vấn đề**: Kích thước đồ thị tăng theo kho lưu trữ:
- 500K LOC → hàng triệu nút/cạnh
- truyền tải n-hop đắt tiền (O(n2) trường hợp xấu nhất)
- Truy vấn DB đồ thị cần tối ưu hóa

**Giải pháp**:
- Neo4j có lập chỉ mục thích hợp (2505.14394, 2408.03910)
- Tuyên bố về độ phức tạp dưới tuyến tính (2511.07584: O(n^0.73))
- Cập nhật gia tăng (2511.07584: O(|R|·log n))
- Cắt tỉa/lọc top-k (tất cả các giấy tờ)

**Mở**: Làm thế nào để KG có thể mở rộng quy mô thành monorepos với 10 triệu+ LỘC? Không được giải quyết.

### 7.2 Thiết kế lược đồ

**Vấn đề**: Cần bao gồm những nút/cạnh nào?
- Quá ít: Bỏ lỡ những mối quan hệ quan trọng
- Quá nhiều: Tiếng ồn, chậm, bối cảnh LLM quá tải
- Ngôn ngữ cụ thể: Python ≠ Java ≠ C++

**Thực hành hiện tại**: Lược đồ khả thi tối thiểu (tệp, lớp, hàm, lệnh gọi, chứa)
**Nhu cầu trong tương lai**: Lược đồ thích ứng với nhiệm vụ hoặc lược đồ đã học

**Địa chỉ giấy tờ**:
- 2304.09048: Nhắc nhở xây dựng theo sơ đồ
- 2603.21430: Tiện ích mở rộng dành riêng cho tên miền
- 2505.14394: Ghi nhận nhu cầu về trang trí, loại, tệp phụ trợ

### 7.3 Tiêu chuẩn hóa đánh giá

**Vấn đề**: Khó so sánh:
- Điểm chuẩn khác nhau (EvoCodeBench vs SWE-Bench vs custom)
- Các số liệu khác nhau (Đạt @ 1, tỷ lệ sửa chữa, phạm vi bảo hiểm)
- Các xương sống LLM khác nhau
- Tác nhân và thủ tục không thể so sánh được

**Nhu cầu của cộng đồng**: Bộ tiêu chuẩn thống nhất với công thức nhiệm vụ nhất quán.

**Tiến trình**: EvoCodeBench, SWE-Bench trở thành tiêu chuẩn thực tế.

### 7.4 Ô nhiễm dữ liệu

**Vấn đề**: Dữ liệu đào tạo bao gồm các phiên bản thử nghiệm → hiệu suất tăng cao

**Giải pháp**:
- Điểm chuẩn ngày càng phát triển (EvoCodeBench cập nhật 6 tháng một lần)
- Lọc theo thời gian (2503.21710: chỉ các tạo phẩm trước khi phát hành)
- Sử dụng các kho lưu trữ gần đây sau thời gian đào tạo

**Rủi ro còn lại**: Vẫn có thể rò rỉ qua các đường gián tiếp.

### 7.5 Độ phức tạp về kỹ thuật

**Vấn đề**: Hệ thống KG phức tạp khó triển khai:
- Tích hợp SMT (2511.07584)
- Học truy vấn đồ thị (2511.07584)
- Phân tích tĩnh động kép (2511.07584)
- Điều phối nhiều tác nhân (2411.11532, 2603.21430)

**Đánh đổi**: Hệ thống đơn giản hơn (2505.14394) dễ triển khai hơn, hiệu suất thấp hơn một chút.
Hệ thống phức tạp (2511.07584) hiệu suất cao hơn, gánh nặng kỹ thuật.

---

## 8. Tiến độ đổi mới kỹ thuật

### Giai đoạn 1: Tăng cường truy xuất cơ bản (2023-đầu năm 2024)
- RepoCoder, RepoFusion: Truy xuất dựa trên sự tương đồng
- RAG đơn giản: tìm nạp các tệp có liên quan, đưa vào dấu nhắc
- **Hạn chế**: Không có cấu trúc, sai lệch từ vựng

### Giai đoạn 2: Truy xuất dựa trên đồ thị (2024)
- **2406.07003 GraphCoder**: CCG với chức năng cắt, giảm trọng số
- **2505.14394 KG Gen**: Tìm kiếm kết hợp + mở rộng n-hop
- **2408.03910 CodeXGraph**: DB đồ thị + dịch truy vấn
- **Đổi mới**: Vấn đề về cấu trúc, truyền tải nhiều bước nhảy

### Giai đoạn 3: Tạo nhận thức ràng buộc (2025)
- **2511.07584 SemanticForge**: Đồ thị kép + SMT trong tìm kiếm chùm
- **Đổi mới**: Ngăn chặn lỗi trong quá trình tạo, không phải sau đó
- **Đánh đổi**: Độ phức tạp so với đảm bảo một lần

### Giai đoạn 4: Ứng dụng chuyên ngành (2024-2025)
- **2503.21710 KGCompass**: Liên kết hiện vật để sửa chữa
- **2603.07326 Echo**: Tự động thực thi để tạo thử nghiệm
- **2411.11532 CKGFuzzer**: KG để làm mờ
- **2603.21430 DomAgent**: Thích ứng tên miền với CBR
- **Mẫu**: KG + quy trình làm việc theo miền cụ thể

---

## 9. Ma trận phân tích so sánh

### 9.1 Khả năng của hệ thống

|Khả năng|2404|2310|2505|2511|2406|2408|2503|2411|2304|2603|2603|
|------------|------|------|------|------|------|------|------|------|------|------|------|
|**Điểm chuẩn**|✓|✓| | | | | | | | | |
|**Thế hệ**| | |✓|✓| | | | | | |✓|
|**Hoàn thành**| | | | |✓| | | | | | |
|**Sửa chữa**| |✓| | | | |✓| | | | |
|**Thế hệ thử nghiệm**| | | | | | | |✓| |✓| |
|**Mờ mờ**| | | | | | | |✓| | | |
|**Điều chỉnh tên miền**| | | | | | | | | | |✓|
|**Xây dựng KG**| | | | | | | | |✓| | |

### 9.2 Sự phức tạp về mặt kỹ thuật so với tính thực tiễn

```
Độ tinh tế cao:
├── 2511.07584 SemanticForge (SMT, đồ thị kép, truy vấn đã học)
├── 2503.21710 KGCompass (liên kết tạo tác, đường dẫn)
└── 2411.11532 CKGFuzzer (đa tác nhân, vòng phủ sóng)

Độ tinh vi trung bình:
├── 2603.21430 DomAgent (truy xuất kép, RL)
├── 2408.03910 CodeXGraph (dịch truy vấn)
└── 2505.14394 KG Gen (truy xuất lai, LLM descs)

Độ phức tạp thấp hơn (Dễ thực hiện hơn):
├── 2406.07003 GraphCoder (cắt CCG)
├── 2304.09048 CodeKGC (lời nhắc lược đồ)
└── 2603.07326 Echo (biểu đồ + thực thi)
```

**Frontier**: 2511.07584 SemanticForge đại diện cho công nghệ tiên tiến về mặt kỹ thuật phức tạp với sự đảm bảo chính thức.

**Dễ triển khai nhất**: 2505.14394 và 2406.07003 - lợi ích vững chắc mà không quá phức tạp.

---

## 10. Những hiểu biết kỹ thuật quan trọng

### 10.1 Điều gì khiến việc truy xuất KG có hiệu quả?

1. **Lý luận nhiều bước nhảy** (2503.21710: 89,7% thành công cần có nhiều bước nhảy)
   - Sự tương tự một bước nhảy không thành công trên các mối quan hệ gián tiếp
   - Cấu trúc đồ thị cho phép truyền tải một cách có hệ thống
   - Khai thác đường dẫn đáng tin cậy hơn tìm kiếm nhúng

2. **Truyền bá ràng buộc** (2511.07584)
   - Các ràng buộc về loại/chữ ký ngăn chặn toàn bộ các loại lỗi
   - Tích hợp SMT phát hiện vi phạm trong quá trình tạo
   - Có thể đảm bảo chính thức

3. **Lược đồ dành riêng cho nhiệm vụ**
   - Sửa chữa: Cần liên kết giả tạo (sự cố, PR)
   - Làm mờ: Cần mô hình sử dụng API, luồng dữ liệu
   - Lĩnh vực: Cần khái niệm + kinh nghiệm
   - Lược đồ một kích cỡ phù hợp với tất cả dưới mức tối ưu

4. ** Cần thiết phải cắt tỉa bối cảnh **
   - Việc mở rộng n-hop mang lại đồ thị con khổng lồ
   - Phải lọc top-k theo mức độ liên quan
   - Không cắt tỉa: LLM bị choáng ngợp, độ trễ cao

5. **Phân tích kép nhịp đơn**
   - Tĩnh + động (2511.07584): +7,3%
   - Trường hợp KG + (2603.21430): +9% so với RAG đơn giản
   - Toàn văn + vector + đồ thị (2505.14394): Truy xuất tốt nhất

### 10.2 Điều gì không hoạt động tốt?

1. **Truy xuất sự tương đồng thuần túy** cho các tác vụ phức tạp
   - Hoạt động cho các kết quả phù hợp rõ ràng, không thành công trong các mối quan hệ ngầm
   - Xu hướng từ vựng đối với các hình thức bề mặt

2. **Tạo truy vấn đặc biệt LLM** (đường cơ sở 2408.03910)
   - Độ chính xác chỉ 51%
   - Truy vấn thường không đúng định dạng, quá rộng/hẹp
   - Học chính sách (2511.07584) tốt hơn nhiều

3. **Chỉ xác thực sau khi hoàn thành**
   - Tạo → xác thực → vòng lặp sửa chữa đắt tiền
   - Cần lặp lại nhiều lần (10-50 đối với tổng đài viên)
   - Tích hợp hạn chế loại bỏ nhu cầu

4. **Ngữ cảnh một tệp** cho các tác vụ kho lưu trữ
   - 2406.07003 giới hạn ở nội bộ tệp
   - Sự phụ thuộc giữa các tệp rất quan trọng (2505.14394 cho thấy mức tăng)
   - Cần cả bối cảnh nội bộ (câu lệnh) + nội bộ (tệp)

5. **Chỉ KG tĩnh**
   - Không nắm bắt được hành vi thời gian chạy
   - Dấu vết động thêm giá trị (2511.07584)

---

## 11. Câu hỏi nghiên cứu mở

### 11.1 Cơ bản

1. **Lược đồ đồ thị tối ưu**: Có lược đồ chung hay nó phải dành riêng cho nhiệm vụ?
2. **Lợi nhuận giảm dần**: Bao nhiêu ngữ cảnh là đủ? Top-5 vs Top-20 vs Top-50?
3. **Khả năng giải thích so với hiệu suất**: Có thể giải thích được theo hướng dẫn đường dẫn (2503.21710); SMT (2511.07584) ít hơn - đánh đổi?
4. **Tính đầy đủ của ràng buộc**: SMT có thể mã hóa tất cả các ràng buộc của kho lưu trữ không? Còn các mẫu kiến ​​trúc, hướng dẫn phong cách thì sao?

### 11.2 Kỹ thuật

1. **Cập nhật gia tăng trên quy mô lớn**: 2511,07584 yêu cầu O(|R|·log n) nhưng chỉ được đánh giá trên 50 repos. Cân Monorepo?
2. **KG đa ngôn ngữ**: Một biểu đồ có thể mở rộng Python, Java, C++ không? Hoặc các lược đồ cho mỗi ngôn ngữ có liên kết chéo?
3. **KG tự động hóa xây dựng**: Các phương pháp hiện tại vẫn cần thiết kế lược đồ thủ công. Chúng ta có thể học lược đồ từ mã không?
4. **Thời gian thực và hàng loạt**: Xây dựng đồ thị tốn kém. Chúng ta có thể xây dựng tăng dần khi mã thay đổi không?

### 11.3 Đánh giá

1. **Điểm chuẩn thống nhất**: Cần các nhiệm vụ tiêu chuẩn, số liệu, nền tảng LLM
2. **Đánh giá nhận thức về chi phí**: Lặp lại tác nhân so với chuyển một lần; sử dụng mã thông báo; đồng hồ treo tường
3. **Nghiên cứu trên con người**: Các bản vá do KG tạo ra có dễ bảo trì hơn không? Dễ dàng hơn để xem xét?
4. **Theo chiều dọc**: Hệ thống KG hoạt động như thế nào khi cơ sở mã phát triển?

---

## 12. Khuyến nghị thực tế

### 12.1 Dành cho người thực hành (Bài viết nào sẽ được thực hiện?)

**Kịch bản 1: Xây dựng trợ lý mã nhận biết kho lưu trữ**
- **Bắt đầu với**: 2505.14394 (KG Gen) hoặc 2408.03910 (CodeXGraph)
- **Tại sao**: Cân bằng tốt giữa hiệu suất và độ phức tạp
- **Triển khai**: Neo4j + trình phân tích cú pháp AST + mô hình nhúng
- **Mức tăng dự kiến**: ~15-20% so với RAG đơn giản

**Kịch bản 2: Hệ thống sửa lỗi tự động**
- **Bắt đầu với**: mẫu 2503.21710 (KGCompass)
- **Tại sao**: Liên kết hiện vật quan trọng để sửa chữa; bản địa hóa nhiều bước nhảy
- **Khóa**: Xây dựng KG bằng các vấn đề/PR, không chỉ bằng mã
- **Dự kiến**: Cải thiện hơn 50% so với LLM thuần túy

**Kịch bản 3: Thử nghiệm làm mờ/bảo mật**
- **Sử dụng**: phương pháp tiếp cận 2411.11532 (CKGFuzzer)
- **Tại sao**: Chỉ làm mờ hệ thống nhắm mục tiêu; tìm thấy lỗi thực sự
- **Đầu tư**: Cần có cơ sở hạ tầng phân tích chương trình
- **Dự kiến**: Mức độ bao phủ tăng ~9%, phát hiện lỗ hổng mới

**Kịch bản 4: Gen mã dành riêng cho miền** (thư viện độc quyền)
- **Sử dụng**: mẫu 2603.21430 (DomAgent)
- **Tại sao**: Không yêu cầu tinh chỉnh; hoạt động với bất kỳ LLM nào
- **Khóa**: Xây dựng miền KG + cơ sở trường hợp được quản lý
- **Dự kiến**: Phù hợp với các mô hình đã được tinh chỉnh mà không cần đào tạo lại

**Kịch bản 5: Biên giới nghiên cứu (hiệu suất tối đa)**
- **Nghiên cứu**: 2511.07584 (SemanticForge)
- **Tại sao**: Hiện đại; thế hệ nhận thức hạn chế
- **Độ phức tạp**: Cao (SMT, truy vấn đã học, đồ thị kép)
- **Dự kiến**: Kết quả được báo cáo tốt nhất nếu bạn có thể triển khai

### 12.2 Lộ trình thực hiện (Đơn giản hóa)

**Giai đoạn 1: KG tĩnh** (Tuần 1-2)
- Trình phân tích cú pháp AST → trích xuất tệp, lớp, hàm, lệnh gọi
- Xây dựng biểu đồ (NetworkX hoặc Neo4j)
- Xác minh: Bạn có thể truy vấn "X gọi là gì không?"

**Giai đoạn 2: Truy xuất** (Tuần 3-4)
- truyền tải n-hop từ mục tiêu
- Nhúng sự tương đồng cho tìm kiếm ngữ nghĩa
- Kết hợp với toàn văn để khớp tên
- Kiểm tra: Ngữ cảnh được truy xuất có giúp LLM không?

**Giai đoạn 3: Tích hợp** (Tuần 5-6)
- Định dạng sơ đồ con dưới dạng văn bản nhắc nhở
- Đưa vào yêu cầu hoàn thành LLM
- Đánh giá điểm chuẩn nhiệm vụ kho lưu trữ

**Giai đoạn 4: Tăng cường** (Tuần 7-8)
- Thêm siêu dữ liệu (mô tả do LLM tạo)
- Thực hiện cắt tỉa/xếp hạng lại
- Thử nghiệm với vòng lặp sàng lọc truy vấn
- Thêm xác thực thực thi nếu sửa chữa/kiểm tra

**Tổng cộng**: 2 tháng để làm việc nguyên mẫu dựa trên mẫu 2505.14394.

---

## 13. Định hướng tương lai (Tổng hợp)

### 13.1 Ngắn hạn (1-2 năm)

1. **Đánh giá được tiêu chuẩn hóa**: EvoCodeBench + SWE-Bench trở thành tiêu chuẩn; bảng xếp hạng xuất hiện
2. **KG-as-a-service**: DB biểu đồ đám mây cho kho mã; API cho LLM
3. **Tích hợp IDE**: Truy vấn KG thời gian thực trong trình chỉnh sửa (như bản demo CodeXGraph)
4. **Lược đồ đa ngôn ngữ**: Các khái niệm trừu tượng phổ biến trên Python/Java/JS
5. **Cập nhật gia tăng**: Thuật toán tốt hơn để phát triển cơ sở mã

### 13.2 Trung hạn (3-5 năm)

1. **Giải quyết ràng buộc chính thống**: SMT/Z3 được tích hợp vào gen mã (bằng chứng khái niệm SemanticForge)
2. **Chính sách truy vấn đã học**: Thay thế LLM đặc biệt bằng trình truy xuất đã được huấn luyện (hướng 2511.07584)
3. **Lý luận trên nhiều kho lưu trữ**: Lỗi trải rộng trên nhiều kho lưu trữ (vấn đề phụ thuộc)
4. **KG liên tục**: Cập nhật trực tiếp với mọi cam kết; được sử dụng trong CI/CD
5. **Sửa chữa có thể giải thích**: Đường dẫn KG cung cấp lý luận minh bạch (mô hình KGCompass)

### 13.3 Dài hạn (trên 5 năm)

1. **Hiểu biết về mã thống nhất**: Một KG bao gồm tất cả các tạo phẩm mã (mã, vấn đề, PR, kiểm tra, tài liệu, lần chạy)
2. **Công nghệ phần mềm tự động**: Từ đầu đến cuối: vấn đề → PR bằng các bài kiểm tra, tất cả đều do KG hướng dẫn
3. **Tích hợp xác minh chính thức**: Các ràng buộc KG đưa vào thông số kỹ thuật chính thức
4. **Học tập liên dự án**: Chuyển đổi mô hình giữa các dự án thông qua tính năng trừu tượng hóa KG
5. **Nén KG**: Tóm tắt các kho lưu trữ lớn thành các ràng buộc thiết yếu

---

## 14. Kết luận

Biểu đồ kiến ​​thức mã thể hiện **sự thay đổi mô hình** từ "LLM dưới dạng trình hoàn thiện mẫu" sang "LLM dưới dạng trình tổng hợp dựa trên ràng buộc hoạt động trên bộ nhớ kho lưu trữ có cấu trúc".

**Bằng chứng thực nghiệm**: cải tiến 15-50% đối với các tác vụ lưu trữ thực tế. Không chỉ mang tính học thuật - được triển khai trong môi trường công nghiệp (Volvo, Huawei, Alibaba).

**Nền tảng lý thuyết**: Cấu trúc biểu đồ nắm bắt được những gì phần nhúng không thể - mối quan hệ bắc cầu, lan truyền kiểu, bất biến kiến ​​trúc.

**Bài học rút ra thực tế**: Nếu bạn đang xây dựng AI cho công nghệ phần mềm trong thế giới thực (không phải điểm chuẩn đồ chơi), **đầu tư vào cơ sở hạ tầng mã KG**. Lợi ích lớn nhất ở nơi chúng quan trọng nhất: mã phức tạp, tích hợp.

**Thử thách mở**: Độ phức tạp về mặt kỹ thuật. Công nghệ tiên tiến nhất (SemanticForge) yêu cầu SMT, truy vấn đã học, phân tích kép. Làm cho điều này có thể tiếp cận được với những người thực hành là bước tiếp theo.

**Đánh giá cuối cùng**: Code KG không phải là mốt nhất thời. Chúng giải quyết những hạn chế cơ bản của LLM thuần túy: thiếu hiểu biết chính xác về kho lưu trữ, không có khả năng thực thi các ràng buộc, không có lý do có thể theo dõi được. Các bài báo cùng nhau chứng minh một lĩnh vực đang trưởng thành đang chuyển từ thăm dò sang triển khai.

---

## Phụ lục: Tài liệu tham khảo nhanh trên giấy

|Giấy|Năm|Ý tưởng chính|Tốt nhất cho|Độ phức tạp|
|-------|------|----------|----------|------------|
|2304.09048|2024|CodeLM cho xây dựng KG|Tòa nhà KG tự động|Thấp-Trung bình|
|2404.00599|2024|Điểm chuẩn phát triển|Tiêu chuẩn đánh giá|không áp dụng|
|2310.06770|2024|Các vấn đề thực sự của GitHub|Sửa điểm chuẩn|không áp dụng|
|2406.07003|2024|CCG bị phân rã|Hoàn thành mã|Trung bình|
|2408.03910|2024|Giao diện đồ thị DB|Tương tác cơ sở mã LLM chung|Trung bình|
|2503.21710|2025|Liên kết tạo tác + đường dẫn|Vấn đề sửa chữa|Trung bình-Cao|
|2505.14394|2025|Truy xuất kết hợp + mô tả LLM|Tạo mã chung|Trung bình|
|2511.07584|2025|Đồ thị kép + giải mã SMT|Thế hệ tiên tiến|Rất cao|
|2411.11532|2024|Làm mờ hướng dẫn KG|Kiểm tra bảo mật|Cao|
|2603.07326|2026|Tự động thực thi + xác thực kép|Kiểm tra sinh sản|Trung bình|
|2603.21430|2026|KG + lý luận dựa trên trường hợp|Thích ứng tên miền|Trung bình-Cao|

**Thứ tự đọc khuyến nghị**:
1. Bắt đầu: 2404.00599 (động lực chuẩn), 2406.07003 (CCG cơ bản)
2. Cốt lõi: 2505.14394 (đường ống hoàn chỉnh), 2511.07584 (biên giới)
3. Ứng dụng: Chọn dựa trên sở thích (sửa chữa: 2503.21710; làm mờ: 2411.11532; tên miền: 2603.21430; kiểm tra: 2603.07326)
4. Xây dựng: 2304.09048 nếu xây dựng KG từ đầu

---

**Phiên bản tài liệu**: 1.0
**Cập nhật lần cuối**: Tháng 4 năm 2025
**Phạm vi bảo hiểm**: 11 bài báo, 2023-2026
