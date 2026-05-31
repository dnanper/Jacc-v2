Mini explore nhiều hơn

mini có xu hướng “cẩn thận”: đọc thêm file, kiểm tra thêm giả thuyết, gọi lại CKG nhiều lần. Với SWE-Bench, điều này dễ phản tác dụng vì task cần localization nhanh -> patch nhỏ -> verify -> dừng. nano đôi khi thắng vì nó “ngắn mạch” hơn: CKG tìm file, đọc ít, sửa luôn.

Tool budget là tài nguyên chính

Mini gọi tool nhiều hơn nên dễ chạm max_steps=50. Một khi chạm max step, dù đã gần đúng vẫn fail vì empty_final_answer, pending_tool_call_at_stop, hoặc chưa collect patch đúng.

Schema/tool lỗi làm mini mất bước

Mini thử các giá trị như limit=120, timeout=120000. Về ý định thì hợp lý: nó muốn nhiều context hoặc timeout dài. Nhưng tool schema giới hạn limit <= 10, timeout <= 600, nên bị lỗi. Nano ít “tham context” hơn nên ít đâm vào rào schema hơn.

Mini hay thao tác giống engineer thật hơn, nhưng runner không hỗ trợ hết

Ví dụ nó git add -A rồi xem git diff --staged. Với người thật thì bình thường. Nhưng runner của mình chỉ collect bằng git diff, nên staged patch bị mất. Đây là lỗi harness/policy, không hẳn lỗi model.

CKG làm tăng không gian hành động

Có thêm CKG tools nghĩa là model phải quyết định: gọi CKG tiếp hay chuyển sang bash? Mini có xu hướng tận dụng tool hơn, nhưng nếu không có hard policy “CKG chỉ dùng 1-3 bước đầu”, nó dễ bị loop exploration.

Nói ngắn gọn: mini thông minh hơn nhưng agent loop hiện tại chưa đủ kỷ luật để biến năng lực đó thành resolved rate. nano thắng ở vài task vì nó ít overthink hơn và ít chạm lỗi harness hơn.

=> Có thể khi tăng max-steps lên thì mini sẽ thắng nano
