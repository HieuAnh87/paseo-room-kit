# 00 — Trạng thái và phạm vi hiện tại

## Kết luận ngắn

Task mới chọn L, LP (mặc định khi Human bind root Lead) hoặc SLP, với provider custom tách vai trò. Standard stack dùng GPT-6 Luna High/XHigh/Max cho bounded Peer, GPT-6.1 Sol cho `impl_deep` và Claude Opus 5.5 High cho Reviewer; route UI hiện dùng Codex Peer.

Điểm quan trọng: topology được bảo vệ bằng provider/profile contract, role-aware Paseo MCP proxy, OpenCode permission, CLI wrapper và Lead lease registry. Codex lifecycle hooks chỉ còn là defense-in-depth vì `app-server` có specialized tool paths không phát hook. Đây là deterministic workflow isolation, không phải cryptographic isolation khỏi một process hostile có quyền đọc filesystem/process.

## Runtime snapshot

Bảng dưới là snapshot lịch sử của lần kiểm kê trước. Pin Paseo hiện tại trong
`versions.lock.json` là `0.11.2`; kiểm tra app/CLI/daemon live bằng doctor.

| Hạng mục | Giá trị tại thời điểm chụp |
|---|---|
| Paseo CLI/daemon | `0.8.0` |
| Listen | `127.0.0.1:6767` |
| Daemon | running/reachable |
| Relay | enabled, `wss://relay.paseo.sh:443` |
| Paseo MCP | enabled; canonical config giữ `injectIntoAgents=false` và per-provider `paseoTools.enabled=false` |
| Selective authority | mọi internal provider deny native Paseo catalog; Supervisor/Lead dùng role-aware MCP proxy; Peer không có control MCP |
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
          thinking: high
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
| `claude-supervisor` | custom Human-facing Supervisor song song, Opus 5.5 High/XHigh (mặc định High) |
| `codex-supervisor` | custom Supervisor, GPT-6.1 Sol High/XHigh (mặc định High) |
| `codex-lead` | custom Lead, GPT-6.1 Sol High/XHigh/Max (mặc định XHigh) |
| `claude-lead` | custom Lead, Opus 5.5 High/XHigh/Max (mặc định XHigh), auto-compact window 300K |
| `codex-peer` | custom bounded Codex Peer, GPT-6 Luna và GPT-6.1 Sol High/XHigh/Max (mặc định High) |
| `claude-reviewer` | custom read-only Reviewer, Opus 5.5 High |
| `codex-watcher` | custom independent Watcher, GPT-6 Luna Medium |
| `opencode-peer` | adapter OpenCode ACP Peer, AI Box DeepSeek/GLM; hiện disabled |
| `gemini-ui` | adapter ACP qua antigravity-acp, model catalog giới hạn về Gemini; hiện disabled |
| `claude` | built-in Claude đang enabled cho direct/manual use; không phải internal role route |
| stock `codex`/`opencode` | vẫn có thể xuất hiện trong daemon nhưng không được profile cho phép dùng để tạo Lead/Peer mới trong chain custom |
| `omp`, `pi`, `copilot` | disabled trong config |

## Những gì tài liệu này không làm

- Không chép secret hoặc auth state vào folder docs.
- Không archive/delete agent, workspace hoặc log.
- Không yêu cầu thêm daemon restart sau snapshot này.
- Không biến history cũ thành topology hiện tại.
- Không coi trạng thái `idle`/`finished` là engineering acceptance.
