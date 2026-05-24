# `mutations.py`

`MutationsMixin` gom các thao tác có thể thay đổi hoặc quản lý dữ liệu: preview rename, chạy Cypher read-only, liệt kê/xóa repo đã index, và chạy ingestion/analyze.

## Nó dùng `_helpers.py` để làm gì?

`mutations.py` chỉ dùng một thứ từ `_helpers.py`:

```python
from ._helpers import CYPHER_WRITE_RE
```

`CYPHER_WRITE_RE` là regex phát hiện câu Cypher có thao tác ghi như `CREATE`, `DELETE`, `SET`, `MERGE`, `REMOVE`, `DROP`, `ALTER`, `COPY`, `DETACH`.

Nó được dùng trong `cypher()` để chặn query ghi dữ liệu. Vì vậy `cypher()` chỉ cho đọc graph.

## Nó dùng `_search/` để làm gì?

Hiện tại `mutations.py` không dùng `_search/` trực tiếp.

Folder `_search/` phục vụ các luồng tìm kiếm như BM25, hybrid search, tokenizer, MMR. Các phần đó thuộc `SearchMixin` hoặc `ExploreMixin`, không phải `MutationsMixin`.

## `rename(symbol_name, new_name, dry_run=True)`

### Nhận vào

- `symbol_name`: tên symbol muốn đổi.
- `new_name`: tên mới.
- `dry_run`: mặc định `True`.

### Làm gì

1. Gọi:

```python
self.context(symbol_name)
```

để lấy symbol chính và các caller/reference liên quan.

2. Tạo danh sách `references` gồm:

- definition: file chứa symbol gốc.
- reference: các caller lấy từ `context()`.

3. Đếm:

- số definition.
- số usage/reference.
- danh sách file bị ảnh hưởng.

4. Nếu có nhiều symbol cùng tên ở nhiều file, trả thêm `candidates` để người dùng biết cần disambiguate.

5. Nếu `dry_run=False`, nó mới sửa file thật bằng regex word-boundary:

```python
\bsymbol_name\b
```

Sau khi sửa file, nếu có adapter repo source path, nó publish event `source_changed` để luồng re-ingestion có thể chạy lại.

### Trả về

```python
{
    "symbol": "build",
    "new_name": "make",
    "dry_run": True,
    "affected_files": [...],
    "references": [...],
    "counts": {
        "definitions": 1,
        "usages": 2,
    },
    "candidates": [...],          # chỉ có khi trùng tên nhiều nơi
    "_disambiguation": "...",     # chỉ có khi trùng tên nhiều nơi
}
```

Nếu `dry_run=False`, output có thêm:

```python
{
    "files_modified": 2
}
```

### Node/Edge liên quan

- Đọc symbol node qua `context()`.
- Đọc caller/reference edge từ output `context()`, thường là `CALLS`, `HAS_METHOD`, `CONTAINS`, ...
- Không tạo node mới.
- Không tạo edge mới.
- Có thể sửa source file thật nếu `dry_run=False`.

## `cypher(query)`

### Nhận vào

- `query`: một câu Cypher.

### Làm gì

1. Kiểm tra query bằng `CYPHER_WRITE_RE`.
2. Nếu query có dấu hiệu ghi dữ liệu, trả lỗi.
3. Nếu là read query, gọi:

```python
self._query(query)
```

### Trả về

Với read query thành công:

```python
{
    "results": [...],
    "count": 3,
}
```

Với write query:

```python
{
    "error": "Write operations are not allowed. Only read queries are supported."
}
```

Với query lỗi:

```python
{
    "error": "..."
}
```

### Node/Edge liên quan

- Không tự tạo node/edge.
- Chỉ đọc graph nếu query là read-only.

## `list_repos()`

### Nhận vào

Không nhận tham số.

### Làm gì

Đọc registry repo đã index:

```python
list_registered_repos()
```

### Trả về

```python
{
    "repos": [
        {
            "name": "...",
            "path": "...",
            "indexed_at": "...",
        }
    ],
    "total": 1,
}
```

### Node/Edge liên quan

- Không đọc graph.
- Không tạo node/edge.
- Chỉ đọc registry metadata.

## `delete_repo(repo="", clean_storage=True, delete_all=False)`

### Nhận vào

- `repo`: tên repo muốn xóa khỏi registry.
- `clean_storage`: nếu `True`, xóa luôn storage folder.
- `delete_all`: nếu `True`, xóa tất cả repo trong registry.

### Làm gì

1. Đọc registry.
2. Chọn repo target theo `repo` hoặc `delete_all`.
3. Gọi `unregister_repo(target.path)`.
4. Nếu `clean_storage=True`, đóng KuzuDB lock rồi xóa storage folder.

### Trả về

Khi thiếu input:

```python
{
    "status": "error",
    "error": "Provide a repo name, or set delete_all=true",
}
```

Khi không tìm thấy repo:

```python
{
    "status": "not_found",
    "error": "Repository 'x' not found",
    "available": [...],
}
```

Khi xóa thành công:

```python
{
    "status": "ok",
    "deleted": [
        {
            "name": "...",
            "path": "...",
            "storage_cleaned": true,
        }
    ],
    "count": 1,
}
```

### Node/Edge liên quan

- Không tạo node/edge.
- Không sửa graph bên trong DB theo kiểu Cypher.
- Có thể xóa cả DB/storage trên disk nếu `clean_storage=True`.

## `analyze(path="", force=False, embeddings=True, exclude=None, paths=None)`

### Nhận vào

- `path`: một repo hoặc zip cần index.
- `paths`: nhiều repo/zip cần index tuần tự.
- `force`: ép index lại.
- `embeddings`: có chạy embedding hay không.
- `exclude`: danh sách folder loại trừ thêm.

### Làm gì

1. Gom `path` và `paths` thành danh sách input.
2. Nếu không có path nào, trả lỗi.
3. Nếu một path, gọi `_analyze_single(...)`.
4. Nếu nhiều path, chạy `_analyze_single(...)` tuần tự từng repo.

### `_analyze_single(...)` làm gì

1. Nếu input là zip, extract zip vào storage.
2. Kiểm tra path có phải directory không.
3. Nếu repo quá lớn và `embeddings=True`, có thể tự tắt embeddings để tránh chạy quá lâu.
4. Gộp exclude mặc định với exclude người dùng.
5. Tạo `PipelineConfig`.
6. Gọi ingestion pipeline:

```python
run_pipeline(config)
```

### Trả về

Single repo thành công:

```python
{
    "status": "ok",
    "path": "...",
    "stats": {...},
    "warning": "...",   # chỉ có khi embeddings bị auto-disable
}
```

Batch:

```python
{
    "status": "ok|partial",
    "results": [...],
    "total": 2,
    "succeeded": 1,
    "failed": 1,
}
```

Lỗi thiếu input:

```python
{
    "error": "Provide 'path' (single) or 'paths' (batch) to analyze."
}
```

### Node/Edge liên quan

- Bản thân `analyze()` không trực tiếp tạo node/edge.
- Node/edge được tạo bởi ingestion pipeline mà nó gọi.
- Output graph sau analyze phụ thuộc vào các processor trong pipeline: file/folder, symbol, import, call, heritage, community, process, ...
