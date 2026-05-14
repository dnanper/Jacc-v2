# Sơ đồ tri thức mã: Hướng dẫn tham khảo nhanh

## Tóm tắt nhanh chóng

```
┌────────────────── ──────────────────── ──────────────────── ───────────────────┐
│ BIỂU ĐỒ KIẾN THỨC MÃ CẢNH QUAN │
├────────────────── ──────────────────── ──────────────────── ───────────────────┤
│ │
│ ┌─────────────────────────────────── ───────────────────────────────────┐ │
│ │ MẪU XÂY DỰNG ĐỒ HỌA │ │
│ ├─────────────┬─────────────┬────── ──────────┬────────────────────────┤ │
│ │ AST tĩnh │ Động │ Tăng cường LLM │ Hỗn hợp │ │
│ │ (Tất cả các giấy tờ)│ (chỉ 2511) │ (2505, 2304) │ (2511, 2603.21430) │ │
│ │ Nhanh, │ Thời gian chạy │ Ngữ nghĩa │ Độ chính xác tốt nhất │ │
│ │ đáng tin cậy │ hành vi │ ý định │ Phức tạp │ │
│ └─────────────┴─────────────┴────── ──────────┴────────────────────────┘ │
│ │
│ ┌─────────────────────────────────── ───────────────────────────────────┐ │
│ │ CHIẾN LƯỢC PHỤC HỒI (Tốt nhất đến tệ nhất) │ │
│ ├──────────────┬─────────────┬───── ─────────┬─────────────────────────┤ │
│ │ Được hướng dẫn bởi SMT │ Được hướng dẫn theo đường dẫn │ Tìm kiếm kết hợp│ Truy vấn đồ thị (LLM) │ │
│ │ thế hệ │ (multi-hop) │ (văn bản+vec+gr)│ (độ chính xác 51%) │ │
│ │ (2511) │ (2503) │ (2505) │ (2408) │ │
│ │ -52% lỗi │ 89,7% cần │ Đường cơ sở │ Cần cải thiện │ │
│ │ +15,6% Pass@1│ nhiều bước nhảy │ │ │ │
│ └──────────────┴─────────────┴───── ─────────┴─────────────────────────┘ │
│ │
│ ┌─────────────────────────────────── ───────────────────────────────────┐ │
│ │ HIỆU SUẤT BẰNG ỨNG DỤNG │ │
│ ├─────────────────────┬───────────── ┬──────────────────────────────────┤ │
│ │ Thế hệ │ Đạt 33-50%│ 2505 (36%), 2511 (50%) │ │
│ │ Sửa chữa │ 58% │ 2503 (KGCompass) │ │
│ │ Tái tạo thử nghiệm │ 66% │ 2603.07326 (Tiếng vọng) │ │
│ │ Hoàn thành │ +6 trận đấu │ 2406 (GraphCoder) │ │
│ │ Làm mờ │ +9% cov │ 2411 (CKGFuzzer) │ │
│ │ Thích ứng tên miền │ 67% │ 2603.21430 (DomAgent) │ │
│ └─────────────────────┴───────────── ┴──────────────────────────────────┘ │
│ │
│ ┌─────────────────────────────────── ───────────────────────────────────┐ │
│ │ NHỮNG THÔNG TIN CHÍNH (Dựa trên bằng chứng) │ │
│ ├─────────────────────────────────── ───────────────────────────────────┤ │
│ │ 1. Multi-hop rất quan trọng: 89,7% số lần sửa chữa thành công cần đến nó │ │
│ │ 2. Tích hợp ràng buộc đánh bại quá trình xác thực hậu kiểm: lỗi -52% │ │
│ │ 3. KG + thu hồi: Tăng 15-50% khi thực hiện các nhiệm vụ phức tạp │ │
│ │ 4. Vấn đề về bối cảnh: Lợi ích lớn từ nhiệm vụ repo, lợi ích nhỏ từ HumanEval │ │
│ │ 5. Phân tích kép: Tĩnh + động = +7,3% (2511.07584) │ │
│ └─────────────────────────────────── ───────────────────────────────────┘ │
│ │
└────────────────── ──────────────────── ──────────────────── ───────────────────┘
```

---

## Ma trận quyết định giấy

```
Tôi nên đọc/thực hiện bài viết nào cho nhu cầu của mình?

┌─────────────────────┬────────────── ───────┬─────────────────────────────┐
│ Cần: │ Đọc trước: │ Độ phức tạp triển khai: │
├─────────────────────┼────────────── ───────┼─────────────────────────────┤
│ Tổng quan chung │ TỔNG HỢP_MASTER │ Không áp dụng │
│ Vấn đề về điểm chuẩn │ 2404.00599, 2310 │ Không áp dụng │
│ │ │ │
│ Tạo mã │ 2505.14394 │ ◐◐◐ (Trung bình) │
│ │ rồi 2511.07584 │ ◐◐◐◐◐ (Cao - SMT) │
│ │ │ │
│ Hoàn thành mã │ 2406.07003 │ ◐◐ (Trung bình-Thấp) │
│ │ │ │
│ Sửa lỗi │ 2503.21710 │ ◐◐◐ (Trung bình-Cao) │
│ │ │ │
│ Tạo thử nghiệm │ 2603.07326 │ ◐◐◐ (Trung bình) │
│ │ │ │
│ Làm mờ │ 2411.11532 │ ◐◐◐◐ (Cao - đa tác nhân) │
│ │ │ │
│ Điều chỉnh tên miền │ 2603.21430 │ ◐◐◐ (Trung bình-Cao) │
│ │ │ │
│ KG xây dựng │ 2304.09048 │ ◐◐ (Thấp-Trung bình) │
│ │ │ │
│ Giao diện đồ thị │ 2408.03910 │ ◐◐◐ (Trung bình) │
└─────────────────────┴────────────── ───────┴─────────────────────────────┘

Độ phức tạp: ◐ Thấp ◐◐ Trung bình ◐◐◐ Trung bình-Cao ◐◐◐◐ Cao ◐◐◐◐◐ Rất cao
```

---

## Tham khảo nhanh lược đồ

### Lược đồ khả thi tối thiểu (đối với bất kỳ mã KG nào)

```cypher
// Nodes
(:File {path, language})
(:Class {name, signature, file})
(:Function {name, signature, file})
(:Method {name, signature, class, file})
(:Attribute {name, type, owner})  // owner = class or function

// Edges
(:File)-[:CONTAINS]->(:Class|:Function)
(:Class)-[:CONTAINS]->(:Method)
(:Class)-[:INHERITS]->(:Class)
(:Function)-[:CALLS]->(:Function)
(:Statement)-[:USES]->(:Variable|:Function)
(:Function)-[:HAS_PARAM]->(:Parameter)
```

### Tiện ích mở rộng dành riêng cho việc sửa chữa

```cypher
(:Issue {id, title, description, created_at})
(:PR {id, title, description, created_at})
(:Issue)-[:MENTIONS]->(:File|:Function)
(:PR)-[:FIXES]->(:Issue)
(:PR)-[:MODIFIES]->(:File|:Function)
(:Test)-[:VERIFIES]->(:Function)
```

### Phần mở rộng dành riêng cho Fuzzing

```cypher
(:APIGroup {name, library})
(:APICombination {id, confidence})
(:APICombination)-[:INCLUDES]->(:Function)
(:Function)-[:READS]->(:Variable)
(:Function)-[:WRITES]->(:Variable)
(:Function)-[:ALLOCATES]->(:Resource)
(:Function)-[:INITIALIZES]->(:Object)
```

### Tiện ích mở rộng dành riêng cho tên miền

```cypher
(:Package {name, domain})
(:DomainConcept {name, description})
(:Concept)-[:RELATED_TO]->(:Function)
(:Example)-[:DEMONSTRATES]->(:Pattern)
(:Pattern)-[:INVOLVES]->(:Function)
```

---

## Danh sách kiểm tra thực hiện

### Giai đoạn 1: Nền tảng (Tuần 1-2)
- [ ] Chọn cơ sở dữ liệu đồ thị (Neo4j được khuyến nghị để tạo mẫu)
- [ ] Xác định lược đồ cho nhiệm vụ của bạn
- [ ] Triển khai trình phân tích cú pháp AST cho ngôn ngữ đích
- [ ] Trích xuất các thực thể cơ bản (tệp, lớp, hàm)
- [ ] Xây dựng biểu đồ ban đầu cho kho lưu trữ thử nghiệm

### Giai đoạn 2: Tăng cường (Tuần 3-4)
- [ ] Thêm các cạnh phụ thuộc (GỌI, SỬ DỤNG, NHẬP KHẨU)
- [ ] Tạo phần nhúng (sử dụng MiniLM hoặc tương tự)
- [ ] Triển khai truyền tải n-hop với trọng số phân rã
- [ ] Thêm chỉ mục tìm kiếm toàn văn
- [ ] Kiểm tra chất lượng truy xuất theo cách thủ công

### Giai đoạn 3: Tích hợp LLM (Tuần 5-6)
- [ ] Định dạng sơ đồ con dưới dạng văn bản thân thiện với LLM
- [ ] Mẫu gợi ý thiết kế
- [ ] Triển khai thế hệ tăng cường truy xuất
- [ ] Đánh giá trên điểm chuẩn nhỏ
- [ ] Lặp lại thiết kế nhanh chóng

### Giai đoạn 4: Các tính năng cụ thể của nhiệm vụ (Tuần 7-8)
- [ ] Thêm các nút/cạnh dành riêng cho nhiệm vụ (xem ở trên)
- [ ] Thực hiện kiểm tra ràng buộc nếu cần
- [ ] Thêm vòng lặp thực thi/xác thực nếu sửa chữa/kiểm tra
- [ ] Tối ưu hóa hiệu suất (bộ nhớ đệm, lập chỉ mục)
- [ ] Phân tích chi phí

### Giai đoạn 5: Đánh giá (Tuần 9-10)
- [ ] Chọn điểm chuẩn phù hợp
- [ ] Chạy so sánh cơ sở
- [ ] Nghiên cứu cắt bỏ (có/không có KG, có/không có n-hop)
- [ ] Phân tích lỗi
- [ ] Kết quả tài liệu

---

## Những cạm bẫy và giải pháp phổ biến

|cạm bẫy|triệu chứng|Giải pháp|
|---------|---------|----------|
|**Lược đồ quá thưa thớt**|KG bỏ lỡ những mối quan hệ quan trọng|Thêm nhiều loại cạnh hơn, phân tích các trường hợp thất bại|
|**Lược đồ quá dày đặc**|LLM quá tải, truy vấn chậm|Cắt bớt các cạnh có giá trị thấp, giới hạn n-hop|
|**Truy xuất quá rộng**|Đã vượt quá độ dài ngữ cảnh|Hạ top-k, tăng ngưỡng tương tự|
|**Truy xuất quá hẹp**|Thiếu bối cảnh cần thiết|Giảm ngưỡng, tăng bước nhảy, tìm kiếm kết hợp|
|**LLM phớt lờ KG**|Mã được tạo không sử dụng ngữ cảnh được cung cấp|Cải thiện lời nhắc, thêm hướng dẫn "sử dụng các API này"|
|**KG cũ**|Mã đã thay đổi, KG đã lỗi thời|Cập nhật gia tăng, xây dựng lại theo cam kết|
|**KG ồn ào**|Nhiều cạnh CUỘC GỌI/SỬ DỤNG sai|Cải thiện phân tích tĩnh, lọc dựa trên loại|
|**Độ trễ cao**|Quá trình truy xuất mất >5 giây|Lập chỉ mục, bộ nhớ đệm, tính toán trước tốt hơn|

---

## Kỳ vọng về hiệu suất

Dựa trên kết quả trên giấy, hãy mong đợi những **cải thiện tương đối** này so với đường cơ sở (không có KG):

|Độ phức tạp của nhiệm vụ|Mức tăng dự kiến|Hãy cẩn thận|
|-----------------|---------------|---------|
|**Đơn giản** (chức năng độc lập)|5-10%|Bối cảnh ít quan trọng hơn|
|**Trung bình** (tệp chéo, 2-3 phần phụ thuộc)|15-25%|Cần truy xuất tốt|
|**Phức tạp** (quy mô repo, nhiều dep)|30-50%|Cần thiết phải có nhiều bước nhảy|
|**Sửa chữa** (bản địa hóa lỗi)|40-60%|Liên kết tạo phẩm quan trọng|
|**Tên miền cụ thể**|20-40%|KG phải chiếm được miền|

**Chi phí**: Độ trễ bổ sung ~2-5 giây cho mỗi truy vấn (truyền tải biểu đồ + LLM). Chấp nhận được cho hầu hết các ứng dụng.

**Cơ sở hạ tầng**: Phiên bản Neo4j ($0-$500/tháng tùy theo quy mô), mô hình nhúng (miễn phí hoặc $), API LLM ($0,001-0,05/truy vấn).

---

## Hướng dẫn lựa chọn điểm chuẩn

```
Tôi nên sử dụng điểm chuẩn nào để đánh giá hệ thống KG của mình?

┌──────────────────────────────────── ─────────────────────────────────────┐
│ Điểm chuẩn │ Loại nhiệm vụ │ Kích thước │ Độ khó │ Sử dụng Khi: │
├────────────────── ──┼───────────────── ┼───────┼─────────── ─┼─────────────────┤
│ HumanEval │ Độc lập │ 164 │ Dễ │ LLM cơ bản │
│ MBPP │ Độc lập │ 974 │ Dễ-Trung bình│ Gen đơn giản │
├────────────────── ──┼───────────────── ┼───────┼─────────── ─┼─────────────────┤
│ EvoCodeBench │ Tạo repo │ 275 │ Cứng │ Repo thực tế │
│ RepoEval │ Comp chéo tệp │ Khác nhau│ Khó │ Hoàn thành │
├────────────────── ──┼───────────────── ┼───────┼─────────── ─┼─────────────────┤
│ SWE-Bench Lite │ Sửa chữa sự cố │ 300 │ Rất khó │ Sửa chữa │
│ SWT-Bench │ Thế hệ thử nghiệm │ ~500 │ Cứng │ Sinh sản │
├────────────────── ──┼───────────────── ┼───────┼─────────── ─┼─────────────────┤
│ DS-1000 │ Tên miền (dữ liệu sci│ 1000 │ Trung bình │ Điều chỉnh tên miền │
│ └─ danh mục phụ │ cụ thể) │ │ │ │
├────────────────── ──┼───────────────── ┼───────┼─────────── ─┼─────────────────┤
│ Tùy chỉnh │ Nhiệm vụ của bạn │ Bất kỳ │ Nhiệm vụ của bạn │ Tên miền cụ thể │
└────────────────── ──┴───────────────── ┴───────┴─────────── ─┴─────────────────┘

Khuyến nghị: Bắt đầu với EvoCodeBench (thế hệ) hoặc SWE-Bench Lite (sửa chữa).
```

---

## Thuật ngữ

**KG**: Sơ đồ tri thức - các nút (thực thể) được kết nối bởi các cạnh (mối quan hệ)

**n-hop**: Đi qua n cạnh từ nút bắt đầu. 1-hop = hàng xóm trực tiếp, 2-hop = hàng xóm của hàng xóm

**Pass@k**: Xác suất mà ít nhất một trong k mẫu được tạo vượt qua tất cả các thử nghiệm

**RAG**: Thế hệ tăng cường truy xuất - tìm nạp ngữ cảnh bên ngoài, đưa vào dấu nhắc LLM

**SMT**: Lý thuyết Modulo thỏa mãn - giải toán cho các ràng buộc

**CCG**: Biểu đồ ngữ cảnh mã (GraphCoder) - CFG + DDG + CDG chồng lên nhau

**AST**: Cây cú pháp trừu tượng - cây biểu diễn cấu trúc mã

**CFG**: Biểu đồ luồng điều khiển - đường dẫn thực hiện có thể có

**DDG**: Biểu đồ phụ thuộc dữ liệu - mối quan hệ sử dụng định nghĩa biến

**CDG**: Biểu đồ phụ thuộc kiểm soát - điều kiện nào ảnh hưởng đến câu lệnh nào

**Nhúng**: Biểu diễn dạng vector của văn bản/mã để tìm kiếm sự tương đồng

**Trọng số phân rã**: Bối cảnh ở xa có trọng số thấp hơn (ví dụ: exp(-λ×distance))

**Xác thực phiên bản kép**: Kiểm tra phải thất bại đối với mã lỗi, chuyển mã đã vá

**Không đạt**: Bài kiểm tra tương tự thay đổi từ không đạt thành vượt qua sau khi sửa

**Đường dẫn thực thể**: Các thực thể liên kết chuỗi nhiều bước (vấn đề → PR → chức năng)

**Lược đồ**: Định nghĩa các loại nút và loại cạnh trong KG

**Xuất xứ**: Theo dõi thông tin đến từ đâu (quan trọng đối với KG)

---

## Trích dẫn Tham khảo nhanh

```bibtex
@inproceedings{2404.00599,
title={EvoCodeBench: Điểm chuẩn tạo mã đang phát triển},
tác giả={Li, Jia và Li, Ge và Zhang, Huyền Minh và Dong, Yihong và Jin, Zhi},
năm={2024},
tựa sách={ICLR}
}

@inproceedings{2511.07584,
title={SemanticForge: Biểu đồ tri thức tĩnh-động kép},
tác giả={Zhang, Wuyang và Zhang, Chenkai và Luo, Zhen và Ma, Jianming và những người khác},
năm={2025},
tựa sách={JEAAI}
}

@inproceedings{2503.21710,
title={KGCompass: Sơ đồ tri thức nhận biết kho lưu trữ để sửa chữa},
tác giả={Yang, Boyang và Ren, Jiadong và Jin, Shunfu và Liu, Yang và những người khác},
năm={2025},
booktitle={Hội nghị ACM}
}

@inproceedings{2406.07003,
title={GraphCoder: Biểu đồ ngữ cảnh mã để hoàn thành},
tác giả={Liu, Wei và Yu, Ailun và Zan, Daoguang và Shen, Bo và Wang, Qianxiang và những người khác},
năm={2024}
}

@article{2603.21430,
title={DomAgent: KG + Lý do dựa trên trường hợp cho mã miền},
tác giả={Wang, Shuai và Parthasarathy, Dhasarathy và Feldt, Robert và Yu, Yinan},
năm={2026},
tạp chí={AAMAS}
}
```

---

**Cập nhật lần cuối**: Tháng 4 năm 2025
**Số giấy tờ được bảo hiểm**: 11
**Trang**: Tài liệu tham khảo nhanh + 11 phân tích chi tiết + 1 tổng hợp

Để biết phân tích chi tiết, hãy xem các tệp đánh dấu riêng lẻ trong thư mục `paper_analyses/`.
