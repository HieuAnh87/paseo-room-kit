# 18 — Attention, Flow và Land tùy chọn

Các thành phần này bổ sung khả năng quan sát và thao tác Git cho workflow đang có. Paseo vẫn giữ agent/session/workspace; `lead-leases.json` vẫn là nguồn quyền cho managed room. Trạng thái native như `idle` chỉ là tín hiệu vận hành, không phải Peer `DONE`, Lead acceptance hay Human acceptance.

## Câu hỏi và tín hiệu cần chú ý

Lead có thể dùng `open_room_ask` để ghi một câu hỏi cho Supervisor đã bind, hoặc cho Human trong direct mode. Peer không nhận Paseo control MCP; `DEPENDENCY_REQUEST` trong report của Peer tạo câu hỏi gửi Lead khi report được ghi. Mỗi câu hỏi có ID, người gửi/nhận, work epoch và trạng thái `OPEN`/`ANSWERED`. `answer_room_ask` kiểm tra người nhận cùng epoch/revision; cùng câu trả lời có thể gọi lại an toàn, câu trả lời khác bị từ chối.

Từ owner shell:

```bash
paseo-room-workflow asks --lead-id LEAD_ID
paseo-room-workflow answer-ask REQUEST.json
paseo-room-workflow answer-ask REQUEST.json --apply
```

`REQUEST.json` chứa `leadAgentId`, `askId`, `answer`, `expectedWorkEpoch` và `expectedRevision` lấy từ danh sách mới nhất. CLI preview mặc định. Mốc nhắc sau 30 phút và chuyển cấp sau 2 giờ chỉ hiện trong view; chúng không tự gửi prompt, trả lời hoặc đổi quyền. `inspect_peer_attention` đọc status/activity để báo khả năng thiếu handback, terminal không có handback, hoặc permission đang chờ. Đây là nghi vấn để Lead kiểm tra, không phải quyết định kết quả.

## Flow/Health

Plugin trong [`plugin/`](../plugin/) dành cho Paseo 0.9.1 hiển thị dữ liệu read-only từ Paseo và lease hiện có: room, Lead/Peer, decision, câu hỏi và tín hiệu attention. Nó không tạo lane ledger và không thực hiện các operation được bảo vệ. Plugin được cài riêng, không nằm trong installer của kit; xem README trong thư mục plugin cho yêu cầu và lệnh cài. Kit pin Paseo 0.8.0 ở phiên bản nguồn hiện tại, nên plugin 0.9.1 là thành phần tùy chọn cho daemon tương thích.

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
