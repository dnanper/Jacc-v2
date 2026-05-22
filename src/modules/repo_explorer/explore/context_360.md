backend/context.py phục vụ csg_context.
Luồng:
text

symbol name
-> match_by_name()
-> lấy symbol target
-> query incoming edges: callers
-> query outgoing edges: callees
-> query STEP_IN_PROCESS: processes
-> lấy contract
-> lấy implementation/content

Các query chính:
Callers:
cypher

MATCH (caller)-[r:CodeRelation]->(n {id: $id})
WHERE r.type IN $relTypes

Nghĩa là: ai trỏ vào symbol này.
Callees:
cypher

MATCH (n {id: $id})-[r:CodeRelation]->(target)
WHERE r.type IN $relTypes

Nghĩa là: symbol này trỏ tới ai.
Processes:
cypher

MATCH (n {id: $id})-[r:CodeRelation]->(p:Process)
WHERE r.type = 'STEP_IN_PROCESS'

Nghĩa là: symbol này nằm trong execution flow nào.
Sau đó context_360() gọi thêm method từ ExploreMixin:
python

\_resolve_one_contract()
\_resolve_one_implementation()

nên trả được cả signature và source content.

Hai hàm này thuộc ExploreMixin:
\_resolve_one_contract() là helper của Layer 4: Contract
\_resolve_one_implementation() là helper của Layer 5: Implementation
Tác dụng:
context() trong ContextMixin lấy callers, callees, processes.
\_resolve_one_contract() bổ sung signature, return type, parameter count, heritage, overrides.
\_resolve_one_implementation() bổ sung source code content.
Vì vậy csg_context(symbol) thực chất là shortcut 360 độ: nó gom cả context layer, contract layer, và implementation layer vào một response.
