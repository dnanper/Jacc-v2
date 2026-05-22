infle_processor: chỉ sử dụng extract_docstring, is_exported, build_type_env, named_bindings từ extraction, chưa có resolve import

import_resolution.py chỉ biết “raw import path này resolve thành file nào?”, còn import_processor.py biến kết quả resolve đó thành dữ liệu graph và context để các phase sau trong pipeline.py dùng tiếp.
