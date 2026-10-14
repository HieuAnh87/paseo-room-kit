# 19 — Đối chiếu bài SLP với room-kit

Đọc toàn bộ phần thân [bài của Vũ Hoàng Lâm](https://vhlam.com/article/agent-orchestration-multi-agent-slp), ngày 27/09/2026, gồm Better SLP, các hướng liên quan và phần giới hạn áp dụng. Đọc hết không đồng nghĩa đã xác minh các case study, paper hay hiệu quả vận hành. Không coi ba thay đổi này là triển khai đầy đủ Better-SLP.

`Source` nghĩa là đã có contract/code; `Fixture` nghĩa là có test hành vi. Cả hai đều không thay thế bằng chứng một room thật làm đúng. Bảng dưới là đánh giá room-kit theo các chủ đề của bài, không phải chứng nhận của tác giả.

| Chủ đề đối chiếu | Room-kit và giới hạn |
|---|---|
| Bối cảnh, vertical dependency | Report dependency/reopen về Lead. Đường phối hợp có; chất lượng integration vẫn cần case dự án. |
| Agent ownership / state ownership | Lease giữ quyền agent. Trách nhiệm state của code phải do Lead/Peer kiểm chứng riêng. |
| Tiền đề sai, pre-solve | Ba Lead profile phân biệt mục tiêu, constraint bắt buộc, phương án tạm và câu hỏi cần kiểm chứng. Đây là instruction, chưa có semantic detector. |
| Phạm vi sửa / quyền chất vấn | Assignment ceiling giữ nguyên; dissent có đường về Lead. Không tự mở quyền ghi sang owner khác. |
| Plan có thể thay đổi | Disposition có evidence và next action; thay quyết định đã đóng cần report mới. Source + fixture. |
| Nova: thứ tự tick/handoff | Không có code Nova để tái hiện. Snapshot/review không chứng minh integration runtime đúng. |
| Quark: ACK, entity lifecycle | Không có code Quark để xác minh các regression. Test room-kit dùng phản ví dụ về stale evidence/delivery, không tuyên bố tái hiện lỗi Quark. |
| Green tests / thiết kế | Candidate digest xác định trạng thái được báo cáo; không phán định thiết kế hoặc chứng minh test đã chạy. |
| Model mạnh và workaround | Brief/dissent cho phép mở lại premise. Không có bằng chứng model sẽ luôn sử dụng đường này. |
| V1/V2 và Human steering | Grant exact assignment/epoch; notice Lead trước, callback về Lead. Fixture kiểm tra thứ tự, drift, dedup và uncertainty. Delivery chưa chứng minh effect. |
| Roles là trách nhiệm | Binding/guard giữ authority; tên seat không cấp quyền. Supervisor room-kit giữ governance, có phạm vi hẹp hơn vai trò kiến trúc trong bài. |
| Một writer; review phiên bản | Assignment và candidate proof có. Pause writers/cross-workspace scope vẫn là quy tắc phối hợp, không phải khóa filesystem. |
| Dissent tới outcome | Lead-only resolution; evidence-pending chặn handback; Human escalation hiện trong outcome. Candidate đổi cần proof mới. Source + fixture. |
| Không phản biện hình thức | Không bắt mọi Peer tìm lỗi hoặc mọi task có Reviewer. Gate độc lập do repo chọn theo rủi ro. Hiệu quả gate cần quan sát. |
| Benchmark và CPU thực tế | Chưa có CPU exclusivity enforcement. Worktree không cách ly CPU; phải kiểm tra process/load và điều kiện đo tại dự án. |
| Better-SLP, học từ outcome | Observer nối receipt trong lease hiện có, hiển thị unknown/truncation. Chưa có phân tích nhân quả, token cost hay chứng minh review/intervention đáng giá. |
| Đồ thị phối hợp / cây spawn | Authority binding tách parentage. Dependency đi qua Lead; chưa có đồ thị dependency đa owner tự điều phối. |
| Công cụ, paper và applicability | Tham chiếu bên ngoài không xác nhận hiệu quả kit. Task nhỏ có self-work gate; việc cần feedback Human liên tục cần chọn topology theo tình huống. |

Ba thay đổi đã làm: Human steering có receipt; dissent có disposition bền vững; observation read-only có correlation. Hướng dẫn vận hành và schema ở [18](18-attention-and-land.md), [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) và [dissent protocol](../protocols/DISSENT_PROTOCOL.md).

Phần chưa được chứng minh là tác động trên công việc thật: instruction đã tới đúng Peer và callback về Lead trên từng adapter; Peer có đưa ra evidence đổi quyết định; Lead có xử lý và kiểm chứng correction; chi phí điều phối có hợp lý. Tiếp tục đánh giá bằng các episode cụ thể thay vì thêm luật chỉ để hoàn thiện sơ đồ. Nên xem xét bỏ cơ chế nếu chi phí không đổi được outcome.

Thay đổi đã được cài vào runtime trên máy ngày 28/09/2026: proxy, CLI, role instructions/config, hooks và protocol; Codex Lead/Supervisor runtime được đồng bộ. Room Flow được reload và daemon báo `running`. Watcher hiện có giữ lịch mỗi giờ và chạy thử thành công; không có managed Lead đang hoạt động nên chưa gọi observations trên room live hoặc gửi steering tới Peer thật. Catalog tool của Watcher/Lead/Supervisor và lệnh observations read-only trên một Lead lịch sử đã được kiểm tra. Test hành vi vẫn dùng registry/agent/repository tạm và transport giả lập. Điều kiện resource benchmark và chất lượng reasoning chưa được tự động xác minh.

Peer steering yêu cầu upstream caller-scoped của Lead; không fallback sang unscoped vì mất routing callback. Method không khả dụng bị từ chối. Doctor trên máy hiện phát hiện app `0.9.2` lệch pin kit `0.9.1`; pin không đổi trong lần sửa này. Gate source chạy riêng với `PASEO_APP_PATH` trỏ tới đường dẫn không có app sẽ skip đúng một kiểm tra installed bundle, không xác nhận tương thích runtime.
