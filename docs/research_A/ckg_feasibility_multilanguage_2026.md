# Đánh giá khả thi: Versioned Software Evidence Graph đa ngôn ngữ

## Kết luận

Hướng phát triển khả thi nếu được định nghĩa là một **nền tảng evidence-backed,
progressive-capability**: mọi repository có mức structural navigation cơ bản;
chỉ các ngôn ngữ/build hệ thống đã có semantic adapter mới được hứa hẹn symbol
binding, call/data flow chính xác hơn. Không khả thi nếu hứa một bộ trích xuất
duy nhất có cùng độ chính xác cho mọi ngôn ngữ, framework, runtime và nguồn
bằng chứng.

## Công nghệ đã có và giới hạn

| Nhu cầu | Công nghệ / chuẩn | Kết luận |
|---|---|---|
| Parse source nhiều ngôn ngữ | [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) | Phù hợp cho CST, source anchor và incremental parsing. Mỗi ngôn ngữ cần grammar riêng; CST không thay thế binding, type resolution hay dispatch analysis. |
| Symbol navigation chuẩn hơn | [SCIP](https://sourcegraph.com/docs/code-navigation/precise-code-navigation) | Protocol language-agnostic; indexer vẫn phụ thuộc từng ngôn ngữ. Sourcegraph công bố mức hỗ trợ theo từng indexer, không coi đa ngôn ngữ là đồng đều. |
| Static semantic/data-flow | [CodeQL supported languages](https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/) | Phù hợp làm adapter sâu cho tập ngôn ngữ chính; phạm vi compiler/framework của từng ngôn ngữ là hữu hạn và thay đổi theo phiên bản. |
| Runtime evidence | [OpenTelemetry specification](https://opentelemetry.io/docs/specs/otel/overview/) và [semantic conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/) | Có chuẩn cho traces, metrics, logs và resources. Nó chuẩn hóa data format/attribute, không tự tạo instrumentation hoàn chỉnh hoặc mapping span-to-symbol. |
| Provenance/version | [W3C PROV-O](https://www.w3.org/TR/prov-o/) | Cung cấp vocabulary Entity--Activity--Agent và derivation; phù hợp làm khung provenance, nhưng cần extension software-domain. |
| Graph/query/search | [Kuzu](https://kuzudb.github.io/docs/) | Phù hợp graph lõi và analytical traversal; raw telemetry, log và coverage high-cardinality nên giữ ở artifact/fact store rồi project summary/evidence path vào graph. |

## Kiến trúc khả thi

```text
Artifact store / fact store: source snapshot, OTLP, test report, IaC, Git metadata
        -> language/source adapters + evidence adapters
        -> Assertion(subject, predicate, object, context, modality, provenance, validity)
        -> graph core + task-specific projections for agent/human
```

`context` phải chứa ít nhất revision; khi có thể phải thêm build variant,
configuration, environment, workload/test run và time. `modality` tách
DECLARED, MAY, MUST, OBSERVED, VERIFIED, CLAIMED và REFUTED. Một trace chỉ là
OBSERVED trong workload của trace; static relation không tự trở thành runtime
truth.

## Chiến lược đa ngôn ngữ

1. **Tier A -- semantic adapter sâu:** Python, TypeScript/JavaScript, Java/Kotlin,
   C# và Go. Chỉ cam kết sau khi adapter đã chứng minh được build/index, symbol
   resolution, import/module resolution và test fixture đại diện.
2. **Tier B -- source navigation tốt, semantic có điều kiện:** C/C++, Rust,
   Ruby, Swift. Dùng compiler/LSP/SCIP/CodeQL nếu project build được; nếu không
   hạ capability xuống structural/MAY relation.
3. **Tier C -- structural adapter:** legacy/DSL (ví dụ COBOL, ABAP, RPG, VB6,
   MUMPS). Parse/regex cung cấp anchors, declarations và dependency heuristic;
   không công bố precise call/data-flow nếu chưa có parser + resolver + corpus
   test riêng.

Mỗi adapter phải công bố capability card: supported language/version/framework,
build preconditions, relation types, precision/recall evaluation, known gaps,
revision freshness và confidence semantics.

## Điều kiện để khả thi về tiến độ

- Không bắt đầu bằng “mọi nguồn, mọi ngôn ngữ”. Bắt đầu source-only Tier A và
  3--5 query có người dùng thật cần.
- Chỉ thêm test output, Git, docs/ADR, IaC và telemetry qua adapter độc lập;
  không biến những artifact này thành fact không điều kiện.
- Tách graph identity/traversal khỏi payload dung lượng lớn; lưu raw evidence
  ở hệ thống phù hợp retention/privacy của nó.
- Đánh giá từng capability trên corpus có ground truth, kèm latency/index cost,
  precision, recall, coverage, stale-index và tỷ lệ agent dùng graph để tìm đúng
  source evidence.

## Phán quyết

Có thể build một sản phẩm hữu ích và một đóng góp nghiên cứu mạnh. Không thể
build một oracle “hiểu hoàn toàn mọi codebase” từ các công nghệ hiện có. Giá trị
thực tế nằm ở việc trả lời truy vấn với **bằng chứng, phạm vi và khoảng trống
được công bố**, thay vì giả vờ mọi quan hệ đều chính xác như nhau.
