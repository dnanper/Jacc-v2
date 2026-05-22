impact.py trả lời câu hỏi: “Nếu sửa symbol này thì ảnh hưởng tới ai?”
Luồng chính:
Tìm target:
python

targets = self.\_adapter.match_by_name(target, limit=5)

Nếu nhiều symbol cùng tên, nó vẫn phân tích tất cả match, nhưng trả thêm candidates để disambiguate.
Chuẩn bị BFS:
python

target_ids = [t["id"] for t in targets]
visited_ids = set(target_ids)

Nó duyệt graph theo từng depth, tối đa \_IMPACT_MAX_DEPTH = 5.
Nếu direction="upstream":
cypher

MATCH (caller)-[r:CodeRelation]->(n)
WHERE n.id IN $ids
RETURN caller...

Ý nghĩa: tìm các node đang phụ thuộc target. Đây là “ai sẽ bị ảnh hưởng nếu target thay đổi?”
Ví dụ:
text

A -> target
B -> target

Sửa target có thể ảnh hưởng A, B.
Nếu direction="downstream":
cypher

MATCH (n)-[r:CodeRelation]->(callee)
WHERE n.id IN $ids
RETURN callee...

Ý nghĩa: tìm các dependency mà target đang dùng. Đây là “target phụ thuộc vào ai?”
Ví dụ:
text

target -> C
target -> D

Nếu muốn hiểu target hoạt động dựa vào gì, dùng downstream.
Nó chỉ đi qua relation hợp lệ:
python

rel_types = list(VALID_RELATION_TYPES)

Và lọc confidence:
cypher

r.confidence >= $minConf

Default min_confidence=0.4, để bỏ edge quá yếu.
Nếu kết quả là File node, nó cố resolve thành symbols trong file:
python

file_symbols = self.\_adapter.match_by_file(file_path, limit=10)

Vì File quá thô. Impact report hữu ích hơn nếu nói “function/class nào trong file đó” thay vì chỉ nói “file X”.
Cập nhật frontier BFS:
python

new_ids = [r["id"] for r in rows if r["id"] not in visited_ids]
target_ids = list(set(new_ids))

Depth 1 là ảnh hưởng trực tiếp. Depth 2 là node ảnh hưởng gián tiếp qua depth 1. Dừng khi:
không có node mới
hoặc affected >= 200
hoặc depth > 5
Đếm process bị ảnh hưởng:
cypher

MATCH (n)-[r:CodeRelation]->(p:Process)
WHERE r.type = 'STEP_IN_PROCESS' AND n.id IN $ids
RETURN DISTINCT p.id

Nếu nhiều affected symbols nằm trong nhiều process, rủi ro cao hơn.
Tính risk:
text

CRITICAL: d1 >= 30 hoặc processes >= 5
HIGH: d1 >= 15 hoặc processes >= 3
MEDIUM: d1 >= 5
LOW: còn lại

Nếu confidence thấp dưới 0.5, risk LOW/MEDIUM sẽ bị nâng lên một bậc. Lý do: edge không chắc chắn thì impact report cũng không chắc, nên thận trọng hơn.
Tóm lại:
text

ImpactMixin = BFS trên CodeRelation
upstream = ai phụ thuộc target
downstream = target phụ thuộc ai
depth = mức xa gần của ảnh hưởng
d1 = ảnh hưởng trực tiếp
processes = execution flows bị đụng
risk = tổng hợp từ d1 + processes + confidence
