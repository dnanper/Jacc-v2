docstring_extractor: trích xuất docstring từ node function/method

export_detection: lấy thông tin rằng 1 node chứa đoạn code có public/export hay không

named_binding: lúc import 1 object, có dùng alias không (Ví dụ: from A import AB as abc)

type_env.py
bảng chứa: biến -> object/data type trong một file
Cần priority vì một biến có thể có nhiều nguồn suy đoán type, nhưng không phải nguồn nào cũng đáng tin như nhau.
Ví dụ: const user: AdminUser = new User()
==> Ưu tiên AdminUser hơn là User

type_extractors/
bộ extractor theo từng language để điền TypeEnv

import_rules.py lấy luật import của project; import_resolvers/ áp dụng luật đó để biến import string thành file path thật.

parse_cache: Cache kết quả extract theo file
