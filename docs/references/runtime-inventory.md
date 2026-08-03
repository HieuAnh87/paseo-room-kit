# Runtime inventory

Snapshot từ Paseo daemon lúc `2026-08-03T18:55:02+07:00`.

## Active workspace records

| Workspace ID | Path | Kind | Title |
|---|---|---|---|
| `<redacted-workspace>` | `$HOME/Documents` | directory | Custom OpenCode provider |
| `<redacted-workspace>` | `$HOME/Documents/PERSONAL/keyboard-system` | directory | Keyboard website mockups |
| `<redacted-workspace>` | `$HOME/Documents/PERSONAL/keyboard-system` | directory | Project status and next step |
| `<redacted-workspace>` | `$HOME/Documents/LEARN/discord` | directory | Explore Discrawl repository |
| `<redacted-workspace>` | `$HOME/Documents` | directory | Paseo setup status |
| `<redacted-workspace>` | `$HOME/Documents` | directory | Git commit trace for July 1-7, 2026 |
| `<redacted-workspace>` | `$HOME/Documents/paseo-pilot` | directory | Paseo Supervisor pilot |
| `<redacted-workspace>` | `$HOME/.config/room-workflow` | directory | Paseo Supervisor control |
| `<redacted-workspace>` | `$HOME/Documents/WORK/HDC/MRAG/mosa-be` | local checkout, `main` | OCR beyond sandbox timeout |

Registry có `18` workspace records tổng cộng; phần còn lại đã archive. Có nhiều record cùng path vì Paseo lưu từng workspace/session context, không phải tất cả đều là worktree độc lập.

## Agent provider history

| Provider/model | Record count | Ý nghĩa |
|---|---:|---|
| `codex-lead/gpt-5.6-sol` | 7 | custom Lead history |
| `codex-supervisor/gpt-5.6-luna` | 2 | custom Supervisor Luna history |
| `codex-supervisor/gpt-5.6-sol` | 4 | custom Supervisor Sol history |
| `codex/gpt-5.4` | 3 | legacy stock routing; không dùng cho chain mới |
| `codex/gpt-5.6-luna` | 9 | top-level/direct Codex history |
| `codex/gpt-5.6-sol` | 1 | top-level/direct Codex history |
| `opencode/aibox/deepseek-v4-flash` | 5 | historical AI Box work |
| `opencode/openai/gpt-5.6-luna` | 2 | historical native OpenCode work |
| `opencode/opencode-go/glm-5.2` | 1 | historical native OpenCode work |
| `opencode/opencode/deepseek-v4-flash-free` | 4 | historical native OpenCode work |

Tổng `38` agent records: `35 closed`, `1 idle`, `2 running` tại snapshot. Chỉ `<redacted-agent>` → `<redacted-agent>` được ghi là custom Supervisor → Lead active chain; không có custom Peer active trong snapshot.
