# 00 — Trạng thái và phạm vi hiện tại

## Kết luận ngắn

Setup hiện tại đã có đủ topology Human-facing Supervisor → Lead → Peer, với provider custom tách vai trò. Paseo daemon đang sống, `gemini-ui` đã được nhận, và routing mới đã có DeepSeek cho implementation, Luna cho deep implementation/audit/search, Gemini cho UI.

Điểm quan trọng: topology được bảo vệ bằng provider/profile contract, role-aware Paseo MCP proxy, OpenCode permission, CLI wrapper và Lead lease registry. Codex lifecycle hooks chỉ còn là defense-in-depth vì `app-server` có specialized tool paths không phát hook. Đây là deterministic workflow isolation, không phải cryptographic isolation khỏi một process hostile có quyền đọc filesystem/process.

## Runtime snapshot

| Hạng mục | Giá trị tại thời điểm chụp |
|---|---|
| Paseo CLI/daemon | `0.2.5` |
| Listen | `127.0.0.1:6767` |
| Daemon | running/reachable |
| Relay | enabled, `wss://relay.paseo.sh:443` |
| Paseo MCP | enabled; daemon đã nạp `injectIntoAgents=false` sau restart có chủ đích |
| Selective authority | Supervisor/Lead dùng role-aware MCP proxy; Peer không có Paseo MCP; OpenCode permission; Gemini ACP MCP disabled |
| Browser tools | enabled |
| Auto archive after merge | disabled |
| Terminal agent hooks | enabled |
| Codex CLI | `0.144.5` |
| OpenCode | `1.18.11` |
| Bun | `1.3.5` |
| Antigravity CLI cạnh ACP | `1.1.10` tại snapshot |
| antigravity-acp binary | `1.0.0` |
| Workspace records | `18` trong registry; có record đã archive và record trùng thư mục do các phiên trước |
| Agent records | `46` records; last status gồm `44 closed`, `1 idle`, `1 running` |
| Scheduled jobs/loops | không có schedule/loop đang được ghi nhận |

Snapshot runtime của máy nguồn không được commit vào portable kit. Dùng `../scripts/doctor.sh --live` để chụp lại trạng thái trên từng máy.

## Chain smoke gần nhất

```text
Supervisor <redacted-agent>
  provider: codex-supervisor/gpt-5.6-sol
  status: idle
  cwd: ~/.config/room-workflow
      │
      └── Lead <redacted-agent> (archived sau smoke)
          provider: codex-lead/gpt-5.6-sol
          thinking: medium
          terminal status: closed
          cwd: ~/Documents/paseo-pilot
              │
              └── Peer <redacted-agent> (archived sau smoke)
                  provider: codex-peer/gpt-5.6-luna
                  thinking: low
                  terminal status: closed
```

Đây là chain read-only đã hoàn tất để chứng minh parentage, native Peer callback, `ASSIGNED → DONE → ACCEPTED`, explicit final Lead handback và release lease. Lead/Peer thử nghiệm đã được soft-archive; không còn test Lead/Peer active. Supervisor `<redacted-agent>` vẫn là front door idle. Khi cần đánh giá topology, luôn nhìn `Provider`, `ParentAgentId`, `Cwd` và trạng thái cùng nhau; không suy luận chỉ từ tên agent.

## Provider availability

| Provider | Trạng thái/ý nghĩa |
|---|---|
| `claude-supervisor` | custom Human-facing Supervisor thử nghiệm, dùng Opus 4.8 Medium/High/Max |
| `codex-supervisor` | custom Supervisor, dùng Sol/Luna |
| `codex-lead` | custom Lead, dùng Sol/Luna |
| `codex-peer` | custom bounded Codex Peer, dùng Sol/Luna |
| `opencode-peer` | custom OpenCode ACP Peer, AI Box DeepSeek/GLM |
| `gemini-ui` | custom ACP provider qua antigravity-acp, model catalog giới hạn về Gemini |
| `claude` | built-in Claude đang enabled cho direct/manual use; không phải Peer route mặc định |
| stock `codex`/`opencode` | vẫn có thể xuất hiện trong daemon nhưng không được profile cho phép dùng để tạo Lead/Peer mới trong chain custom |
| `omp`, `pi`, `copilot` | disabled trong config |

## Những gì tài liệu này không làm

- Không chép secret hoặc auth state vào folder docs.
- Không archive/delete agent, workspace hoặc log.
- Không yêu cầu thêm daemon restart sau snapshot này.
- Không biến history cũ thành topology hiện tại.
- Không coi trạng thái `idle`/`finished` là engineering acceptance.
