# 03 — Provider và model routing

## Routing preference hiện tại

Nguồn chính: `~/.paseo/orchestration-preferences.json`.

| Category | Provider/model | Thinking | Dùng cho |
|---|---|---|---|
| `planning` | `codex-lead/gpt-6.1-sol` | High / XHigh / Max | Codex Lead cho objective mới |
| `planning_claude` | `claude-lead/claude-opus-5-5` | High / XHigh / Max | Claude Lead cho objective mới |
| `impl` | `codex-peer/gpt-6-luna` | High / XHigh / Max | bounded implementation |
| `impl_deep` | `codex-peer/gpt-6.1-sol` | High / XHigh / Max | bounded implementation khó |
| `search` | `codex-peer/gpt-6-luna` | High / XHigh / Max | delegated codebase navigation/search |
| `audit` | `claude-reviewer/claude-opus-5-5` | High | review độc lập, read-only |
| `research` | `codex-peer/gpt-6-luna` | High / XHigh / Max | research/background scan |
| `ui` | `codex-peer/gpt-6-luna` | High / XHigh / Max | UI/design work |


`impl_deep` và `search` là custom semantic routes do Lead profile hiểu. Các Paseo skill chuẩn biết các category `impl`, `ui`, `research`, `planning`, `audit`; vì vậy khi dùng skill generic cần kiểm tra preference và brief của Lead, không tự giả định `impl_deep`/`search` là category built-in.

Codex/Claude Supervisor tự chọn giữa `planning` và `planning_claude` lúc mở một bounded objective, theo tính chất việc và ưu tiên Human nếu có. Khi không có lợi thế rõ, dùng Codex. Model được pin vào binding cho suốt phiên Lead. Mỗi Lead sở hữu một objective/workstream trong một workspace; objective độc lập cần workspace/worktree riêng và chỉ chạy song song khi phạm vi ghi không chồng nhau. Giới hạn một Lead mỗi workspace do guard bảo vệ; kiểm tra chồng phạm vi giữa workspace hiện là quy tắc workflow của Supervisor.

Các adapter `opencode-peer` và `gemini-ui` đang tắt trên host hiện tại; route `research`/`ui` dùng Codex Peer đang bật. Catalog adapter bên dưới là cấu hình dự phòng, không phải route đang hoạt động. Không tự rơi về stock provider.

## Model catalog theo provider

### `codex-supervisor`

- GPT-6.1 Sol: High hoặc XHigh; High là mặc định của role provider.
- Mục đích: governance/front door; không dùng model choice để nhận engineering ownership.

### `claude-supervisor`

- Opus 5.5: High hoặc XHigh; High là mặc định của role provider; active context auto-compact ở 300K.
- Là front door song song với Codex Supervisor; không thay `planning` route.
- Có thể chọn `planning` hoặc `planning_claude` như Codex Supervisor; không dùng Claude native Workflow/Agent/Task.
- Chỉ nhận Paseo control MCP qua role proxy explicit.


### `codex-lead`

- GPT-6.1 Sol: High, XHigh (mặc định) hoặc Max. Guard giữ nguyên mức hợp lệ đã chọn.
- Mục đích: engineering owner của workspace.

### `claude-lead`

- Opus 5.5 1M: High, XHigh (mặc định) hoặc Max; là model duy nhất của provider.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000`: 1M là capacity ceiling, active window được compact sớm.
- Được Supervisor chọn bằng `planning_claude` khi mở objective mới; Human có thể chỉ định Codex hoặc Claude.
- Dùng `claude-room lead`, role-aware Paseo MCP và cùng Lead lease/handback contract; Claude native Workflow/Agent/Task bị deny.


### `codex-peer`

- GPT-6 Luna có ba mức High (mặc định), XHigh và Max cho Peer chuẩn. Guard giữ nguyên mức hợp lệ đã chọn.
- `impl`, `search`, `research` và `ui` dùng Luna. `impl_deep` dùng GPT-6.1 Sol, cũng với High (mặc định), XHigh hoặc Max. Effort hợp lệ được giữ nguyên.

### `claude-reviewer` và `codex-watcher`

- Reviewer: Opus 5.5 High, Plan Mode, route `audit` với `disposition=reviewer` và `write_mode=read_only`.
- Watcher: GPT-6 Luna Medium, unattended mode với built-in mutation/read tools bị deny; proxy chỉ mở các Paseo read tools. Schedule độc lập quét managed rooms mỗi ngày lúc 01:00 giờ Việt Nam.

### `opencode-peer`

- `aibox/deepseek-v4-flash`: Max.
- `aibox/glm-5.2`: Max.
- Đây là catalog đã rút gọn. Không route internal Peer qua stock `opencode` nếu cần role contract.

### `gemini-ui`

Được expose trong Paseo bằng ACP bridge và giới hạn model list về:

- Gemini 3.6 Flash: Low/Medium/High;
- Gemini 3.5 Flash: Low/Medium/High;
- Gemini 3.1 Pro: Low/High.

Antigravity CLI còn có thể quảng bá model không phải Gemini, nhưng `gemini-ui.models` trong Paseo thay toàn bộ catalog hiển thị để UI route không lẫn Claude/GPT/OSS.

## Search model: hai trường hợp khác nhau

### Search trực tiếp

Lead/Supervisor tự gọi `rg`, GitNexus hoặc MCP search thì không có model thứ hai. Tool chạy trong context của agent hiện tại; model là model của agent đó.

### Search delegated

Lead tạo một Peer cho việc navigation/search thì dùng:

```text
provider = codex-peer/gpt-6-luna
thinkingOptionId = high  # hoặc xhigh, max
```

Delegated search dùng cùng GPT-6 Luna High/XHigh/Max profile của Peer.

## Implementation split

Các route implementation/search và review:

```text
standard implementation/search/research/ui → GPT-6 Luna High (default) / XHigh / Max
deep implementation                       → GPT-6.1 Sol High (default) / XHigh / Max
standard review                → Claude Opus 5.5 High
```

DeepSeek/GLM trên AI Box hiện chỉ khai báo Max; không tự thêm `none`/`low` vào catalog nếu provider chưa hỗ trợ.

## Guard sau khi tạo agent

Lead phải inspect agent ngay sau `create_agent`:

1. provider phải khớp role route (`codex-peer/`, `claude-reviewer/`, `opencode-peer/`, `gemini-ui/`);
2. model phải khớp model đã chọn;
3. thinking phải khớp assignment;
4. nếu rơi về stock `codex/` hoặc sai provider thì dừng chain, không gửi work tiếp.

Lý do guard tồn tại được ghi ở [12-decision-log.md](12-decision-log.md): trace `<redacted-agent-id>` từng tạo stock `codex/gpt-5.4` cho Lead và Peer.
