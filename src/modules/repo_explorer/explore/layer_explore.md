1. Query trong ExploreMixin dùng để làm gì
   ExploreMixin là implementation của csg_explore. Nó query graph theo 6 layer trong explore.py.
   Layer 0: topology()
   Mục tiêu: lấy “bản đồ tổng quan” của repo.
   Các query chính:
   cypher

MATCH (c:Community)
RETURN c.id, c.name, c.heuristicLabel, c.symbolCount, c.cohesion

Lấy các community/module đã detect sau ingestion. Dùng để biết repo có những cụm logic nào.
cypher

MATCH (c1:Community)-[r:CodeRelation]->(c2:Community)
WHERE r.type = 'COMMUNITY_INTERACTS'

Lấy quan hệ giữa các community. Ví dụ community A gọi/import nhiều sang community B.
cypher

MATCH (f:Folder)-[r:CodeRelation]->(child:File)
WHERE r.type = 'CONTAINS'

Lấy folder tree ở mức graph.
cypher

MATCH (n:Function|Class|Method)-[r:CodeRelation]->(c:Community)
WHERE r.type = 'MEMBER_OF'

Lấy top members của từng community, ưu tiên symbol có fanIn cao hoặc entryPointScore cao.
cypher

MATCH (f:File)
RETURN count(f), binary count, sum(lineCount)

Lấy thống kê file.
Layer 1: relevance(query)
Mục tiêu: câu hỏi của user liên quan đến community/symbol nào.
Nó không chỉ Cypher. Nó chạy 2 search song song:
text

BM25 FTS: search_fts_symbols(...)
Semantic: adapter.vector_search(...)

Sau đó gom các hit theo node id. Nếu một node match cả BM25 và semantic thì boost score.
Rồi query:
cypher

MATCH (n:<label>)-[r:CodeRelation]->(c:Community)
WHERE r.type = 'MEMBER_OF' AND n.id IN $ids
RETURN n.id, c.heuristicLabel

Tác dụng: map symbol hit sang community. Nhờ vậy csg_explore("auth login") không chỉ trả symbol rời rạc, mà trả “community nào liên quan nhất tới auth login”.
Sau đó code còn boost theo:
query term match tên symbol
query term match path
query term match community label
score spread giữa các community
Nếu hit phân tán nhiều community, nó đánh dấu is_crosscutting=True.
Layer 2: context_layer(scope)
Mục tiêu: đi sâu vào một scope cụ thể: community, symbol, hoặc file.
Với scope="community:<name>":
cypher

MATCH (n:Function|Method)-[m:CodeRelation]->(c:Community)
WHERE m.type = 'MEMBER_OF' AND c.heuristicLabel = $comm
RETURN n.id

Lấy function/method trong community.
cypher

MATCH (n:Function|Method)-[s:CodeRelation]->(p:Process)
WHERE s.type = 'STEP_IN_PROCESS' AND n.id IN $memberIds

Tìm các process/flow liên quan đến members của community đó.
cypher

MATCH (n:Function|Method|Class)-[r:CodeRelation]->(p:Process {id: $pid})
WHERE r.type = 'STEP_IN_PROCESS'

Lấy các bước của từng process, sắp theo step-1, step-2, ...
cypher

MATCH (n:Function|Method|Class|Interface)-[m:CodeRelation]->(c:Community)
WHERE m.type = 'MEMBER_OF' AND c.heuristicLabel = $comm
RETURN n...

Lấy danh sách symbol trong community.
Với scope="symbol:<name>":
match_by_name() tìm symbol.
Query incoming edges để lấy callers.
Query outgoing edges để lấy callees.
Query STEP_IN_PROCESS để biết symbol nằm trong process nào.
Với scope="file:<path>":
cypher

MATCH (n:Function|Method|Class|Interface)
WHERE n.filePath = $path
RETURN n...
ORDER BY n.startLine

Lấy các symbol trong file theo thứ tự dòng.
Layer 3: crosscut()
Mục tiêu: tìm vấn đề hoặc concern cắt ngang nhiều module.
cypher

MATCH (f1:File)-[r:CodeRelation]->(f2:File)
WHERE r.type = 'IMPORTS' AND r.inCycle = true

Tìm import cycle giữa file. Sau đó Python gom thành component cycle.
cypher

MATCH (f:File)
WHERE f.fanIn >= 5
RETURN f.filePath, f.name, f.fanIn

Tìm file dùng chung nhiều nơi. fanIn cao nghĩa là nhiều node/edge trỏ vào nó.
Sau đó với top shared symbols, nó gọi:
python

self.\_adapter.vector_search(name, top_k=5)

để tìm symbol tương tự về embedding, nhằm detect duplicate/similar concerns.
Layer 4: contract(symbols)
Mục tiêu: hiểu interface của symbol mà chưa cần đọc source.
Helper chính là \_resolve_one_contract().
Các query:
cypher

MATCH (n:<Function|Method> {id: $id})
RETURN n.parameterCount, n.returnType, n.signature

Lấy signature, số param, return type.
cypher

MATCH (caller)-[r:CodeRelation]->(n {id: $id})
WHERE r.type = 'CALLS'

Ai gọi symbol này.
cypher

MATCH (n {id: $id})-[r:CodeRelation]->(callee)
WHERE r.type = 'CALLS'

Symbol này gọi ai.
cypher

MATCH (n {id: $id})-[r:CodeRelation]->(parent)
WHERE r.type IN ['EXTENDS', 'IMPLEMENTS']

Lấy inheritance/interface implementation.
cypher

MATCH (n {id: $id})-[r:CodeRelation]->(method)
WHERE r.type = 'OVERRIDES'

Lấy override relation.
Layer 5: implementation(symbols)
Mục tiêu: đọc source snippet của symbol.
Helper chính là \_resolve_one_implementation():
cypher

MATCH (n:<SymbolType> {id: $id})
RETURN n.content, n.startLine, n.endLine, n.filePath

Nó trả content đã lưu trong node lúc ingestion. Với function/class/method, đây là snippet source từ AST, tối đa khoảng 200 dòng theo parser hiện tại.
