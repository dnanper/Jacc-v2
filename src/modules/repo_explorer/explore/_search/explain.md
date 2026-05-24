Chạy FTS query trên nhiều index: File, Function, Class, Method, Interface, Section, Struct, Enum,...

Có 2 hàm chính:

- search_fts(...): trả kết quả gom theo filePath.

- search_fts_symbols(...): trả kết quả theo symbol/node, dùng cho ExploreMixin.relevance.

Trước khi search, query được mở rộng:

camelCase/snake_case split.

compound word split: websocket -> web socket.

prefix cho từ dài: authentication -> auth.

bỏ stop words.
