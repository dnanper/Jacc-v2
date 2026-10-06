# Tài liệu thiết kế

Hướng đi đã chốt cho Jacc-v2. Tài liệu khảo sát và nghiên cứu nền nằm ở `../research/`, `../research_A/`, `../research_B/`, `../paper_analyses/`.

| Tài liệu | Nội dung |
|---|---|
| `graph-schema.md` | Schema đồ thị mục tiêu: node, edge, hợp đồng metadata, ranh giới suy luận |
| `roadmap.md` | Khoảng cách giữa mã hiện tại và schema, chia P0 / P1 / P2 |
| [agent-workflow.md](agent-workflow.md) | Non-graph agent workflow: chiến thuật rộng/sâu, parameter có kiểm tra, bộ nhớ bằng chứng, chọn vị trí sửa, roadmap W0–W3 và đánh giá tách graph/workflow |

`agent-workflow.md` là thiết kế đề xuất, chưa triển khai. Roadmap W0–W3 của workflow độc lập P0–P2 của đồ thị; giữ graph chỉ đọc và không chạy mã repo đích.

Phạm vi: SWE-bench Lite (300 Python), Loc-Bench V1 (559 Python), Multi-SWE-bench Java (128 Java). Đánh giá ba mức file / class / function.
