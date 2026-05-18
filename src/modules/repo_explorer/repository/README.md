repository/git.py: biết repo đang ở commit nào / file nào đổi.

repository/repo_manager.py: biết index graph của repo này lưu ở thư mục nào.

graph/schema/\_\_schema.py: biết graph database có cấu trúc bảng/quan hệ thế nào.

graph/storage/\_\_adapter.py: biết ghi/đọc graph database như thế nào.

ingestion/pipeline.py: là lớp nối các phần trên lại với nhau.
