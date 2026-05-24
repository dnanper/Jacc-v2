# `impact.py`

`ImpactMixin` dùng để xem một symbol thay đổi thì ảnh hưởng tới những symbol nào, hoặc xem file git diff đang chạm vào những symbol nào.

## `impact(target, direction="upstream", min_confidence=0.4)`

### Nhận vào

- `target`: tên symbol cần phân tích, ví dụ `build`, `Repository`, `save`.
- `direction`:
  - `upstream`: tìm những node đang phụ thuộc vào target.
  - `downstream`: tìm những node mà target đang phụ thuộc.
- `min_confidence`: chỉ đi qua edge có `confidence >= min_confidence`. Mặc định là `0.4`.

### Làm gì

1. Tìm target bằng:

```python
self._adapter.match_by_name(target, limit=5)
```

Nếu không tìm thấy symbol thì trả về lỗi.

2. Duyệt graph theo BFS qua quan hệ `CodeRelation`.

Với `direction="upstream"`:

```cypher
MATCH (caller)-[r:CodeRelation]->(n)
WHERE n.id IN $ids
```

Nghĩa là tìm node đang trỏ tới target. Đây là nhóm có thể bị ảnh hưởng nếu target đổi contract/hành vi.

Ví dụ:

```text
main -> build
test_build -> build
```

Sửa `build` có thể ảnh hưởng `main` và `test_build`.

Với `direction="downstream"`:

```cypher
MATCH (n)-[r:CodeRelation]->(callee)
WHERE n.id IN $ids
```

Nghĩa là tìm dependency mà target đang dùng.

Ví dụ:

```text
build -> Repository.load
build -> Repository.save
```

Muốn hiểu `build` phụ thuộc vào gì thì dùng `downstream`.

3. Chỉ đi qua các relation hợp lệ từ `VALID_RELATION_TYPES`.

Các edge metadata như `MEMBER_OF`, `STEP_IN_PROCESS`, `COMMUNITY_INTERACTS` không dùng để lan truyền impact.

4. Nếu gặp node loại `File`, nó cố đổi file đó thành symbol bên trong file:

```python
self._adapter.match_by_file(file_path, limit=10)
```

Lý do: report `Function/Class/Method` thường hữu ích hơn report chung chung `File`.

5. Dừng BFS khi:

- không còn node mới,
- hoặc tổng affected >= `200`,
- hoặc depth đạt `5`.

6. Đếm process bị ảnh hưởng.

Nó lấy các affected node rồi tìm process chứa chúng qua edge:

```text
affected_node -[STEP_IN_PROCESS]-> Process
```

Nhiều process bị chạm thì rủi ro cao hơn.

7. Tính `risk`.

- `CRITICAL`: depth-1 affected >= 30 hoặc processes >= 5.
- `HIGH`: depth-1 affected >= 15 hoặc processes >= 3.
- `MEDIUM`: depth-1 affected >= 5.
- `LOW`: còn lại.

Nếu có edge confidence thấp hơn `0.5`, risk `LOW/MEDIUM` sẽ bị nâng lên một bậc để thận trọng hơn.

### Trả về

```python
{
    "target": ...,       # target symbol đầu tiên match được
    "direction": ...,    # upstream hoặc downstream
    "risk": ...,         # LOW / MEDIUM / HIGH / CRITICAL
    "affected": [...],   # danh sách node bị ảnh hưởng
    "stats": {...},      # thống kê tổng hợp
}
```

Mỗi item trong `affected` là một node trong graph, thường có:

```python
{
    "id": "...",
    "name": "...",
    "type": "Function|Method|Class|File|...",
    "filePath": "...",
    "relType": "CALLS|IMPORTS|EXTENDS|...",
    "confidence": 0.9,
    "depth": 1,
    "source": "INFERRED",
}
```

Nếu có nhiều symbol cùng tên ở nhiều file, output có thêm:

```python
{
    "candidates": [...],
    "_disambiguation": "..."
}
```

### Node/Edge liên quan

- Node đầu vào: symbol match theo tên, ví dụ `Function`, `Method`, `Class`.
- Edge duyệt impact: `CodeRelation` với type nằm trong `VALID_RELATION_TYPES`.
- Node output chính: các affected symbol/node.
- Edge phụ để tính process: `STEP_IN_PROCESS`.
- Node phụ để tính risk: `Process`.

## `detect_changes(scope="all", base_ref="")`

### Nhận vào

- `scope`: phạm vi git diff, ví dụ `all`, `staged`, `unstaged`, hoặc scope mà `get_diff_files()` hỗ trợ.
- `base_ref`: ref dùng khi so sánh diff, nếu có.

### Làm gì

1. Lấy source repo path từ adapter:

```python
self._adapter.repo_source_path
```

2. Tìm git root.

Nếu repo không phải git repo thì trả lỗi.

3. Lấy danh sách file thay đổi:

```python
get_diff_files(git_root, scope=scope, base_ref=base_ref)
```

4. Với mỗi file thay đổi, tìm symbol trong file:

```python
self._adapter.match_by_file(fp, limit=20)
```

### Trả về

```python
{
    "changed_files": [...],       # các file thay đổi
    "affected_symbols": [...],    # symbol nằm trong các file đó
    "total_files": 0,
    "total_symbols": 0,
}
```

### Node/Edge liên quan

- Không tạo node mới.
- Không tạo edge mới.
- Chỉ đọc graph để map `changed_files` sang các symbol đã index.
