# 09 — Operations runbook

## Bắt đầu một phiên/workspace mới

Human không cần biết Lead ID. Luồng vận hành:

1. Mở hoặc tạo workspace ở project root.
2. Nói objective/constraint/accepted decision với Supervisor.
3. Supervisor kiểm tra workspace ownership.
4. Nếu chưa có Lead khỏe, Supervisor tạo `codex-lead/gpt-5.6-sol` theo `planning` preference.
5. Creation có labels `role=lead`, `route=planning`, `task_state=LEASED`; MCP proxy reserve lease trước khi forward.
6. Supervisor inspect provider/model và active lease ngay sau creation.
7. Lead nhận brief và tự quyết định có cần Peer hay không.
8. Sau callback/validation, Lead gọi `handback_to_parent` đúng một lần.
9. Human nhận report qua Supervisor.

Nếu đang mở nhầm một stock `codex` chat, không dùng chat đó để gửi engineering objective vào chain custom; hãy quay về Supervisor-facing channel hoặc explicit handoff.

## Read-only health checks

```bash
paseo status
paseo provider ls
paseo provider models codex-supervisor
paseo provider models claude-supervisor
paseo provider models codex-lead
paseo provider models codex-peer
paseo provider models opencode-peer
paseo provider models gemini-ui
paseo ls --all --global
paseo inspect <agent-id>
curl -sS http://127.0.0.1:6767/api/health
```

Khi trace identity, dùng full ID hoặc prefix đủ dài; không dùng tên agent vì tên có thể trùng hoặc chứa prompt cũ.

## Trace chain

```bash
paseo inspect <supervisor-id> --json
paseo inspect <lead-id> --json
paseo logs <supervisor-id>
paseo logs <lead-id>
```

Kiểm tra tối thiểu:

```text
Supervisor: provider starts codex-supervisor/ hoặc claude-supervisor/
Lead: provider starts codex-lead/
Peer: provider starts codex-peer/, opencode-peer/ hoặc gemini-ui/
ParentAgentId: đúng owner
Cwd/workspace: đúng project
Model/thinking: đúng route
```

## Tạo Peer đúng cách

Lead phải:

1. đọc `~/.paseo/orchestration-preferences.json`;
2. chọn category theo task;
3. tạo bounded brief;
4. truyền labels `role=peer`, `route=<category>`, `task_state=ASSIGNED`;
5. để `notifyOnFinish` bật; không poll;
6. truyền `thinkingOptionId` nếu route yêu cầu;
7. inspect agent ngay lập tức;
8. khi callback về, cập nhật `task_state` theo outcome rồi chỉ đặt `ACCEPTED` sau validation;
9. dừng nếu provider/model sai;
10. khi toàn bộ bounded work đã accepted, gọi `handback_to_parent` đúng một lần với outcome, evidence, remaining risk và decision cần Human.

Không hardcode stock `codex/gpt-5.4` hoặc `codex/...` trong workflow mới.

## Đổi model của agent đang tồn tại

Đổi model/thinking của một agent đang chạy là runtime operation, không phải sửa catalog. Trước khi đổi:

- xác định đúng agent;
- xem có active turn không;
- xem đổi model có phá context/lease không;
- chỉ đổi khi Human/owner cho phép;
- kiểm tra lại `paseo inspect` sau update.

Catalog trong `config.json` chỉ quyết định các lựa chọn provider/session mới và picker; nó không retroactively đổi model của agent cũ.

## Handoff/replacement

Không archive/kill Lead trước khi có checkpoint. Checklist:

- objective và accepted decisions;
- current direction;
- code/branch/worktree ownership;
- validation evidence;
- unresolved dissent;
- next action;
- reporting contract.

Replacement order: checkpoint → handoff → archive Lead cũ → xác nhận lease `released` → tạo Lead mới → verify provider → reconcile workspace. Guard sẽ deny nếu Lead/lease cũ còn active.

## Archive/delete

- `archive` là lifecycle soft-close, giữ history.
- `delete` là hard-delete/interrupt và cần scope rõ.
- Archive chỉ sau handback hoặc abandonment đã xác nhận.
- Không archive một agent chỉ vì nó idle.
- Không dùng archive để che misrouting; giữ legacy record cho audit.

## Config change

1. Backup file cấu hình liên quan nếu thay đổi lớn.
2. Sửa canonical config/profile/preferences.
3. Validate JSON/TOML và command path.
4. Kiểm tra provider catalog.
5. Chỉ restart daemon khi Human cho phép và không còn agent cần bảo toàn.
6. Tạo session/agent mới để verify; agent cũ giữ nguyên runtime.

Paseo skill quy định không tự restart daemon vì restart có thể kill cả agent đang hỏi.

## MCP check

Nếu một tool biến mất:

1. xác định agent provider;
2. xem tool thuộc Codex baseline hay Paseo control injection;
3. kiểm tra `injectIntoAgents=false`; nếu vừa đổi config thì xác nhận daemon đã restart có chủ đích;
4. không tìm `injectIntoProviders`: Paseo `0.2.5` không implement field này;
5. kiểm tra Supervisor/Lead runtime có `[mcp_servers.paseo]` trỏ `paseo-room-mcp`, Peer runtime không có;
6. chạy stdio proxy smoke test và xác nhận wrong route/duplicate Lead bị deny trước upstream;
7. với Lead, xác nhận catalog có `handback_to_parent`; với Supervisor, xác nhận tool này không xuất hiện;
8. kiểm tra OpenCode permission hoặc ACP `supportsMcpServers`;
9. kiểm tra executable/env/credential source của MCP;
10. không copy secret vào prompt để “test nhanh”.
