# 03 — Provider và model routing

## Routing preference hiện tại

Nguồn chính: `~/.paseo/orchestration-preferences.json`.

| Category | Provider/model | Thinking | Dùng cho |
|---|---|---|---|
| `planning` | `codex-lead/gpt-6-sol` | XHigh | Codex Lead cho objective mới |
| `planning_claude` | `claude-lead/claude-opus-5-5` | XHigh | Claude Lead cho objective mới |
| `planning_budget` | `opencode-lead/aibox/glm-5.2` | Max | chỉ từ DeepSeek budget Supervisor |
| `impl` | `codex-peer/gpt-6-luna` | Medium | bounded implementation |
| `impl_deep` | `codex-peer/gpt-6-luna` | Medium | bounded implementation khó |
| `search` | `codex-peer/gpt-6-luna` | Medium | delegated codebase navigation/search |
| `audit` | `claude-reviewer/claude-opus-5-5` | High | review độc lập, read-only |
| `research` | `opencode-peer/aibox/deepseek-v4-flash` | Max | research/background scan |
| `ui` | `gemini-ui/gemini-3.6-flash-medium` | model suffix | UI/design work |

Budget stack dùng các key `impl_budget`, `impl_deep_budget`, `search_budget`,
`research_budget`, `audit_budget` cùng trỏ tới
`opencode-peer/aibox/deepseek-v4-flash` Max. `ui_budget` vẫn trỏ tới
`gemini-ui/gemini-3.6-flash-medium` qua agy. Guard chọn các key này từ
`stack_profile=budget`, không dựa vào việc Lead nhớ prompt.

`impl_deep` và `search` là custom semantic routes do Lead profile hiểu. Các Paseo skill chuẩn biết các category `impl`, `ui`, `research`, `planning`, `audit`; vì vậy khi dùng skill generic cần kiểm tra preference và brief của Lead, không tự giả định `impl_deep`/`search` là category built-in.

Codex/Claude Supervisor tự chọn giữa `planning` và `planning_claude` lúc mở một bounded objective, theo tính chất việc và ưu tiên Human nếu có. Khi không có lợi thế rõ, dùng Codex. Model được pin vào binding cho suốt phiên Lead. Mỗi Lead sở hữu một objective/workstream trong một workspace; objective độc lập cần workspace/worktree riêng và chỉ chạy song song khi phạm vi ghi không chồng nhau. Giới hạn một Lead mỗi workspace do guard bảo vệ; kiểm tra chồng phạm vi giữa workspace hiện là quy tắc workflow của Supervisor.

## Model catalog theo provider

### `codex-supervisor`

- GPT-6 Sol: XHigh, model và thinking duy nhất của role provider.
- Mục đích: governance/front door; không dùng model choice để nhận engineering ownership.

### `claude-supervisor`

- Opus 4.8: Medium mặc định, High hoặc Max cho governance khó.
- Là front door song song để thử nghiệm, không thay `planning` route.
- Có thể chọn `planning` hoặc `planning_claude` như Codex Supervisor; không dùng Claude native Agent/Task.
- Chỉ nhận Paseo control MCP qua role proxy explicit.

### `opencode-supervisor`

- DeepSeek V4 Flash trên AI Box, Max, là budget front door.
- Chỉ được bootstrap `planning_budget`; không được tạo Codex/Claude Lead chuẩn.
- Dùng OpenCode role config riêng, deny native task delegation và chỉ nhận Paseo control MCP qua role proxy.

### `codex-lead`

- GPT-6 Sol: XHigh, model và thinking duy nhất của role provider.
- Mục đích: engineering owner của workspace.

### `claude-lead`

- Opus 5.5 1M: XHigh, là model duy nhất của provider.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000`: 1M là capacity ceiling, active window được compact sớm.
- Được Supervisor chọn bằng `planning_claude` khi mở objective mới; Human có thể chỉ định Codex hoặc Claude.
- Dùng `claude-room lead`, role-aware Paseo MCP và cùng Lead lease/handback contract; Claude native Agent/Task bị deny.

### `opencode-lead`

- GLM 5.2 trên AI Box, Max, engineering owner của budget stack.
- Chỉ dùng các route `*_budget`; mọi non-UI Peer là DeepSeek Max, UI vẫn Gemini/agy.
- Dùng cùng Lead lease, callback và final handback contract; native OpenCode task delegation bị deny.

### `codex-peer`

- GPT-6 Luna Medium là model/effort duy nhất của Peer chuẩn.
- `impl`, `impl_deep` và delegated `search` dùng cùng profile bounded này.

### `claude-reviewer` và `claude-watcher`

- Reviewer: Opus 5.5 High, Plan Mode, route `audit` với `disposition=reviewer` và `write_mode=read_only`.
- Watcher: Sonnet 5 Medium, unattended mode với built-in mutation/read tools bị deny; proxy chỉ mở các Paseo read tools. Schedule độc lập quét managed rooms mỗi 60 phút.

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
thinkingOptionId = medium
```

Delegated search dùng cùng GPT-6 Luna Medium profile đã chốt cho Peer.

## Implementation split

Standard và budget stack có route khác nhau:

```text
standard implementation/search → GPT-6 Luna Medium
standard review                → Claude Opus 5.5 High
budget non-UI Peer             → DeepSeek Flash Max
```

DeepSeek/GLM trên AI Box hiện chỉ khai báo Max; không tự thêm `none`/`low` vào catalog nếu provider chưa hỗ trợ.

## Guard sau khi tạo agent

Lead phải inspect agent ngay sau `create_agent`:

1. provider phải khớp role route (`codex-peer/`, `claude-reviewer/`, `opencode-peer/`, `gemini-ui/`);
2. model phải khớp model đã chọn;
3. thinking phải khớp assignment;
4. nếu rơi về stock `codex/` hoặc sai provider thì dừng chain, không gửi work tiếp.

Lý do guard tồn tại được ghi ở [12-decision-log.md](12-decision-log.md): trace `<redacted-agent-id>` từng tạo stock `codex/gpt-5.4` cho Lead và Peer.
