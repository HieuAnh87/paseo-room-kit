# Paseo setup — tài liệu tổng thể

Bộ tài liệu này mô tả toàn bộ setup Paseo hiện tại trên máy `$HOME`, gồm:

- daemon, provider registry và MCP injection;
- mô hình Human → Supervisor → Lead → Peer;
- vai trò, quyền hạn, handback, dissent, heartbeat và lifecycle;
- routing model cho Codex, OpenCode/AI Box, DeepSeek, GLM, Gemini và Claude;
- `codex-room`/`codex-room-sync` và runtime isolation;
- trạng thái workspace/agent, lịch sử lỗi routing và các quyết định đã chốt;
- runbook vận hành, trace và troubleshooting.

## Đọc từ đâu?

| Nếu cần biết | Đọc |
|---|---|
| Setup hiện tại đang ra sao | [00-status-and-scope.md](00-status-and-scope.md) |
| Luồng tổng thể | [01-architecture.md](01-architecture.md) |
| Ai được làm gì | [02-topology-and-authority.md](02-topology-and-authority.md) |
| Gọi model/provider nào | [03-provider-routing.md](03-provider-routing.md) |
| Lead–Peer giao tiếp, heartbeat, handback | [04-lifecycle-and-communication.md](04-lifecycle-and-communication.md) |
| Dissent xử lý thế nào | [05-dissent-and-heartbeats.md](05-dissent-and-heartbeats.md) |
| MCP và visibility boundary | [06-mcp-and-visibility.md](06-mcp-and-visibility.md) |
| Codex role runtime | [07-codex-room.md](07-codex-room.md) |
| OpenCode, Claude, Gemini ACP | [08-provider-integrations.md](08-provider-integrations.md) |
| Tạo workspace/agent, restart, archive | [09-operations-runbook.md](09-operations-runbook.md) |
| Debug provider/model/chain | [10-troubleshooting-and-trace.md](10-troubleshooting-and-trace.md) |
| Secrets, auth và giới hạn bảo mật | [11-security-and-boundaries.md](11-security-and-boundaries.md) |
| Những gì đã thay đổi từ đầu | [12-decision-log.md](12-decision-log.md) và [13-history-and-legacy.md](13-history-and-legacy.md) |
| Đánh giá toàn bộ 38 session đã chạy | [14-session-audit-2026-08-03.md](14-session-audit-2026-08-03.md) |
| Guard, lease và terminal-state mới | [15-role-guard-and-lease.md](15-role-guard-and-lease.md) |
| Context window và compaction cho Lead | [16-context-window-and-compaction-research.md](16-context-window-and-compaction-research.md) |
| Workspace/agent records hiện có | [references/runtime-inventory.md](references/runtime-inventory.md) |

## Source of truth

Tài liệu này là bản giải thích và snapshot; các file dưới đây mới là nguồn thực thi:

| Thành phần | File thực thi |
|---|---|
| Paseo daemon/provider/MCP | `~/.paseo/config.json` |
| Routing preference | `~/.paseo/orchestration-preferences.json` |
| Codex baseline | `~/.codex/config.toml` |
| Supervisor profile | `~/.codex/supervisor.config.toml` |
| Lead profile | `~/.codex/lead.config.toml` |
| Peer profile | `~/.codex/peer.config.toml` |
| Codex launcher | `~/.local/bin/codex-room` |
| Runtime materializer | `~/.local/bin/codex-room-sync` |
| Role-aware Paseo MCP proxy | `~/.local/bin/paseo-room-mcp` |
| Shared route/lease policy | `~/.codex/hooks/room-role-guard.py` |
| OpenCode Peer wrapper | `~/.local/bin/opencode-paseo-peer` |
| Shared workflow contract | `WORKFLOW_PROTOCOL.md` |
| Lead lease registry | `lead-leases.json` |
| Gemini ACP installation | `~/.local/share/antigravity-acp/` |

## Snapshot policy

Snapshot được chụp ngày `2026-08-03` lúc khoảng `18:55` (Asia/Ho_Chi_Minh), khi Paseo daemon `0.2.5` đang chạy.

Portable kit không commit `snapshots/`: chúng chứa runtime identity, đường dẫn và trạng thái dễ lỗi thời. Chạy `../scripts/doctor.sh --live` trên từng máy để kiểm tra routing/runtime. `auth.json`, URI database, API key, token, password và secret environment luôn nằm ngoài repository.

Thông tin bên ngoài được dùng để giải thích ACP/Paseo có link trong [08-provider-integrations.md](08-provider-integrations.md); phần mô tả runtime local được lấy trực tiếp từ máy này.
