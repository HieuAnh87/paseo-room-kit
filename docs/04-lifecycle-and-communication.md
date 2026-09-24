# 04 — Lifecycle và communication

> Authority update: Supervisor is optional. Direct Human→root Lead and an independently bound root Supervisor observer use the same canonical lease and protected epoch operations as the compatible parented bootstrap. Parentage alone is not authority. `submit_work_result` resolves the active binding; direct mode persists a Human-queue receipt. See the shared [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) for repository gates, correlated reports, candidate review and owner-shell commands.


## Luồng một objective

```text
1. Human gửi objective cho Supervisor
2. Supervisor xác định workspace và ownership hiện tại
3. Nếu chưa có Lead khỏe, Supervisor tự chọn Codex Sol XHigh hoặc Claude Opus 5.5 XHigh cho objective; Human có thể chỉ định
4. Supervisor relay objective + accepted decisions + constraints + reporting contract
5. Lead phân rã engineering và quyết định có cần Peer hay không
6. Lead tạo bounded Peer theo category/model phù hợp
7. Peer làm việc, validate phần được giao, trả handback
8. Lead xem evidence/counterevidence, resolve dissent, accept engineering result
9. Lead gọi `handback_to_parent` đúng một lần cho current work epoch
10. Supervisor dùng decision queue để xin Human accept, abandon hoặc bounded follow-up
11. Protected operation record decision/reopen/resolve/archive với epoch+revision fencing
```

## Cơ chế trao đổi

### Human → Supervisor

Đây là front-door interaction. Human không cần biết Lead ID hoặc Peer ID trong vận hành bình thường.

### Supervisor → Lead

Supervisor relay faithful brief. Brief phải giữ nguyên:

- objective;
- accepted decisions;
- product/authority constraints;
- requested outcome;
- reporting contract;
- lifecycle/topology operation nếu Human yêu cầu.

Supervisor không thêm engineering plan vào brief.

### Lead → Peer

Lead tạo hoặc gửi task bounded với:

- assignment cụ thể;
- ownership boundary;
- expected handback;
- validation evidence cần trả;
- category/provider/model/thinking;
- điều gì Peer không được quyết định.

### Peer → Lead

Peer không “push” kết quả vào Supervisor. Peer handback về Lead qua Paseo agent relation/prompt result. Handback tối thiểu gồm:

```text
What changed / inspected
Evidence
Remaining uncertainty
Counterevidence
Requested resolution (nếu có)
```

### Lead → Supervisor

Sau khi tất cả Peer callback cần thiết đã được resolve và evidence đã được validate, Lead gọi tool hẹp `handback_to_parent` đúng một lần. Lead truyền report và candidateDigest khi gated; proxy resolve governance từ authority binding, hoặc ghi receipt trong Human queue ở direct mode và không lộ parent ID cho Lead.

Điều này cần explicit vì `notifyOnFinish` gắn với từng create/prompt turn. Callback Peer tạo một turn mới cho Lead, nhưng turn đó không kế thừa callback của turn Lead ban đầu lên Supervisor. `handback_to_parent` khép chuỗi mà không poll, heartbeat hoặc generic upward messaging.

Nếu expected Peer callback không render, Lead dùng `recover_peer_callbacks`
một lần. Proxy đọc durable Paseo status/activity, kiểm tra exact
parent/workspace/current epoch và lưu terminal message + digest receipt trong
lease. Lần gọi sau trả receipt đã lưu thay vì đọc activity lại.

Lead báo material uncertainty, ownership collision, product trade-off hoặc vấn đề vượt authority trong report này. Lead không tự mở direct Human chat.

## Finish/error/permission

Các notification sau chỉ là attention event:

- agent finished;
- agent errored;
- tool permission pending;
- session idle;
- handback message received.

Chúng không tự động có nghĩa là:

- code đúng;
- test pass là acceptance;
- Lead đã chấp nhận Peer output;
- Human đã chấp nhận product decision.

## Heartbeat, polling và event-driven flow

Paseo có ba khái niệm cần tách:

| Cơ chế | Mục đích |
|---|---|
| notification/finish callback | báo một agent vừa có attention event |
| heartbeat | gửi prompt định kỳ cho assistant/monitoring channel |
| schedule | tạo agent fresh theo cron |

Polling thủ công chỉ nên dùng để điều tra bounded state. Missing callback dùng
protected recovery một lần; không spin loop kiểm tra agent mỗi vài giây.

Tại snapshot hiện tại không có schedule/loop định kỳ đang được ghi nhận. Heartbeat nếu cần sau này dùng cho monitor/reminder, không dùng để biến Supervisor thành task dispatcher.

## Handoff

Handoff là lifecycle operation, không phải tạo thêm một owner song song. Trình tự:

```text
checkpoint → handoff brief → activate replacement → revoke/close old seat → reconcile
```

Handoff phải giữ decisions, ownership, unresolved dissent, evidence và reporting contract.

## Parentage và placement

`workspaceId`/cwd chỉ đặt agent vào workspace. `create_agent` từ context của agent vẫn tạo child của agent đó. Cross-workspace child vẫn thuộc subagent tree của parent.

Vì vậy khi trace phải xem:

```text
agent id + parent id + provider + model + cwd + status
```
