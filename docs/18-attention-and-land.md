# 18 — Attention, Flow và Land tùy chọn

Các thành phần này bổ sung khả năng quan sát và thao tác Git cho workflow đang có. Paseo vẫn giữ agent/session/workspace; `lead-leases.json` vẫn là nguồn quyền cho managed room. Trạng thái native như `idle` chỉ là tín hiệu vận hành, không phải Peer `DONE`, Lead acceptance hay Human acceptance.

## Câu hỏi và tín hiệu cần chú ý

Lead có thể dùng `open_room_ask` để ghi một câu hỏi cho Supervisor đã bind, hoặc cho Human trong direct mode. Peer không nhận Paseo control MCP; `DEPENDENCY_REQUEST` trong report của Peer tạo câu hỏi gửi Lead khi report được ghi. Mỗi câu hỏi có ID, người gửi/nhận, work epoch và trạng thái `OPEN`/`ANSWERED`. `answer_room_ask` kiểm tra người nhận cùng epoch/revision; cùng câu trả lời có thể gọi lại an toàn, câu trả lời khác bị từ chối.

Supervisor mở trực tiếp từ custom provider có thể chưa có nhãn `role=supervisor`. Attention vẫn nhận seat đó khi provider là `codex-supervisor`, `claude-supervisor` và exact lease bind nó làm Supervisor; stock provider hoặc seat không bind vẫn bị từ chối.

Từ owner shell:

```bash
paseo-room-workflow asks --lead-id LEAD_ID
paseo-room-workflow answer-ask REQUEST.json
paseo-room-workflow answer-ask REQUEST.json --apply
```

`REQUEST.json` chứa `leadAgentId`, `askId`, `answer`, `expectedWorkEpoch` và `expectedRevision` lấy từ danh sách mới nhất. CLI preview mặc định. Mốc nhắc sau 30 phút và chuyển cấp sau 2 giờ chỉ hiện trong view; chúng không tự gửi prompt, trả lời hoặc đổi quyền. `inspect_peer_attention` đọc status/activity để báo khả năng thiếu handback, terminal không có handback, hoặc permission đang chờ. Đây là nghi vấn để Lead kiểm tra, không phải quyết định kết quả.

Watcher độc lập chạy GPT-6 Luna Medium theo lịch mỗi ngày lúc 01:00 giờ Việt Nam. Nó chỉ đọc danh sách agent/workspace, attention và observations của managed rooms đang hoạt động qua role-scoped proxy, rồi ghi báo cáo trong scheduled agent run. Unattended mode tránh kẹt ở prompt đọc MCP; settings deny các built-in tools và proxy lọc exact read-only tools. Nó không có quyền trả lời câu hỏi, điều phối agent, chấp nhận kết quả hoặc đổi lease. Trạng thái schedule và lần chạy gần nhất xem bằng `paseo schedule ls` và `paseo schedule logs`.

## Steering, dissent và evidence giao tiếp

Ba thay đổi đã được cài vào runtime trên máy ngày 28/09/2026 và kiểm chứng bằng source/fixture, catalog tool của các role thật, lệnh observations read-only cùng các lần chạy watcher. Chưa có room managed đang hoạt động để xác nhận hiệu quả steering/dissent trong công việc thật.

Human cấp một chỉ thị cụ thể từ owner shell. Ví dụ file `/tmp/peer-grant.json` (thay các ID/version bằng dữ liệu hiện tại):

```json
{
  "leadAgentId": "LEAD_ID",
  "peerAgentId": "PEER_ID",
  "assignmentId": "ASSIGNMENT_ID",
  "grantId": "human-steering-001",
  "humanInstruction": "Kiểm tra lại tiền đề trong phạm vi đã giao.",
  "prompt": "Tái hiện vấn đề, đối chiếu phương án và gửi evidence về Lead.",
  "expectedWorkEpoch": 1,
  "expectedRevision": 7
}
```

```bash
paseo-room-workflow authorize-peer-steering /tmp/peer-grant.json
paseo-room-workflow authorize-peer-steering /tmp/peer-grant.json --apply
paseo-room-workflow observations --lead-id LEAD_ID
```

Sau khi grant được tạo, lấy revision mới từ observations/bindings. Request gửi chỉ gồm `leadAgentId`, `grantId`, `expectedWorkEpoch`, `expectedRevision`; dùng `steer-peer REQUEST.json` rồi `--apply`, hoặc bound Supervisor dùng `steer_room_peer`. Agent không có tool cấp grant. Proxy thông báo đúng chỉ thị cho Lead trước, rồi mới gửi Peer; callback của Peer vẫn về Lead. Assignment, disposition, write mode và scope giữ nguyên. Nếu room đổi revision trước reservation đầu tiên, Human hủy grant và cấp grant mới. Không gửi prompt trực tiếp bằng generic mutation tool để bỏ qua đường này.

Gửi Peer yêu cầu method khả dụng trên upstream caller-scoped của Lead. Không fallback sang unscoped vì sẽ mất callback; method thiếu bị từ chối. Cần kiểm tra runtime trước khi dùng đường này trên room thật.

`DELIVERED` chỉ chứng minh transport. `UNCERTAIN` hoặc trạng thái SENDING sau interruption cần Human kiểm tra timeline/message thực tế. `resolve-peer-steering REQUEST.json --apply` nhận Lead/grant IDs, `resolution=DELIVERED|NOT_DELIVERED`, `evidence` và exact epoch/revision; không gửi message. Xác nhận NOTICE đã gửi cho phép một lần gọi steer riêng để gửi Peer. `CANCELLED` chỉ dùng khi chưa gửi Peer; grant bị từ chối không tự retry. Steering còn pending chặn final handback/withdrawal.

Lead ghi `REOPEN_REQUEST` bằng `record_peer_report`, sau đó gọi `resolve_peer_report` với report ID, outcome, decision, evidence, nextAction, changesWork và exact epoch/revision. `NEEDS_MORE_EVIDENCE`/`ESCALATED_TO_HUMAN` cần owner/checkpoint. Chỉ `RESOLVED_BY_LEAD` đóng ask; ACK thường không đóng được. Sửa candidate cần `changesWork=true`, digest hiện tại và evidence mới; integration làm digest đổi thì phải xác minh lại cùng quyết định. Quy tắc này áp dụng cả repo legacy chưa bật candidate gate.

Handback chặn report chưa xử lý hoặc còn chờ evidence; escalation Human được giữ nguyên trong final outcome, không biến thành engineering success. Report cũ thiếu ask vẫn pending và Lead có thể resolve sau khi Peer archive. Chi tiết: [dissent protocol](../protocols/DISSENT_PROTOCOL.md).

`observations --lead-id` hoặc `list_room_observations` cho Lead/bound Supervisor/Watcher nối brief → report → disposition theo exact assignment/epoch, kèm steering receipt. Brief dispatch được lưu digest và excerpt tối đa 4000 ký tự trong lease; window giữ 64 brief và 64 report mới nhất theo thời điểm ghi. Report lớn hiện excerpt/truncated và số report bị bỏ khỏi view. Không có brief/handling thì `UNKNOWN`; context thiếu không chứng minh vi phạm. Watcher chỉ báo việc pending và evidence cần đọc, không chấm code, reasoning hoặc acceptance. Flow hiện reopen disposition và steering pending/uncertain từ cùng lease.

## Flow/Health

Plugin trong [`plugin/`](../plugin/) tương thích Paseo 0.9.0–0.9.x và hiển thị dữ liệu read-only từ Paseo và lease hiện có: room, Lead/Peer, decision, câu hỏi và tín hiệu attention. Nó không tạo lane ledger và không thực hiện các operation được bảo vệ. Plugin được cài riêng, không nằm trong installer của kit; xem README trong thư mục plugin cho yêu cầu và lệnh cài. Kit pin CLI/daemon Paseo 0.9.1; plugin vẫn là thành phần tùy chọn.

## Land kết quả đã được Human chấp nhận

Land là thao tác owner shell **riêng** sau Human `ACCEPTED`; quyết định chấp nhận không tự cập nhật nhánh Git. Chỉ ứng viên đã commit, worktree/index sạch, có candidate proof và còn đúng epoch/revision mới đủ điều kiện. Land không tạo commit, không push và không tự chạy test command. Bằng chứng kiểm thử vẫn do Lead/Reviewer/Human đánh giá trong workflow hiện có.

```bash
paseo-room-workflow land-prepare --lead-id LEAD_ID --target-branch main > /tmp/room-land-plan.json
# Nếu nhánh đích đang checkout, thêm --target-worktree /path/to/clean/base-checkout.
paseo-room-workflow land-apply /tmp/room-land-plan.json --approve-plan-digest sha256:...
paseo-room-workflow land-apply /tmp/room-land-plan.json --approve-plan-digest sha256:... --apply
```

Human đọc plan/diff stat và duyệt **đúng plan digest**. Apply đọc lại lease, candidate, source/target SHA, trạng thái agent và working copies. Nếu một giá trị đổi, nó từ chối và cần chuẩn bị plan mới. Với base đang checkout và sạch, apply dùng `git merge --ff-only`; nếu base không checkout, nó cập nhật local ref bằng compare-and-swap. Không cho override gate đỏ. Không archive room trước khi Land nếu muốn dùng quyền từ lease đó.

Land chỉ phối hợp với writer của managed room. Một lệnh Git thủ công ngoài room có thể chạy đồng thời; cần giữ checkout yên trong lúc prepare/apply. Base branch, source branch và plan đều là local; deploy hoặc push vẫn là quyết định/tác vụ riêng.
