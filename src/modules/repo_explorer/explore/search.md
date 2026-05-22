SearchMixin: search cơ bản
backend/search.py xử lý search kiểu “tìm file/symbol liên quan đến query”.
Luồng query():
text

query text
-> BM25 full-text search trên Kuzu FTS
-> semantic vector search trên CodeEmbedding
-> merge bằng RRF trong hybrid_search.py
-> enrich mỗi file bằng match_by_file()

Cụ thể:
BM25 tìm theo keyword trong searchText, content.
Semantic search embed query rồi tìm vector gần nhất.
merge_with_rrf() trong hybrid_search.py ghép 2 danh sách rank lại.
Sau đó backend lấy thêm symbols trong file bằng match_by_file.
Kết quả thiên về “file nào/symbol nào liên quan tới câu hỏi này”.
