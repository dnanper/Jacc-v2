### A

parser_loader
-> tạo AST với node type gốc của từng language

tree_sitter_queries
-> bắt các node quan trọng theo từng language

parsing_processor
-> đổi sang graph label chuẩn như Function, Method, Class

ast_helpers
-> helper để hiểu quan hệ/ngữ cảnh của node AST

### B

Parser tạo AST node type khác nhau theo từng ngôn ngữ. Query và parsing_processor map chúng về semantic label chuẩn, còn ast_helpers cung cấp các hàm tiện ích để hiểu node đó nằm ở đâu, gọi ai, thuộc class nào, tên gì, có bao nhiêu argument.

### C

source code
-> parser_loader.parse_file()
-> Tree-sitter AST
-> tree_sitter_queries.get_queries(language)
-> parsing_processor chạy query trên AST
-> lấy captures
-> tạo graph nodes / raw records

### D

name: tên 1 node (ví dụ tên hàm, tên class, ...)
modifie: từ khóa bổ nghĩa cho 1 khai báo
(ví dụ: public, static, async, ...)
