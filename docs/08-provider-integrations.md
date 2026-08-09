# 08 — OpenCode, Claude và Gemini ACP

## OpenCode Peer

Provider:

```text
opencode-peer
  → ~/.local/bin/opencode-paseo-peer
  → opencode --pure acp
  → ~/.config/opencode/paseo-peer.json
```

Wrapper hiện tại cố ý dùng `--pure` để OpenCode Peer không tự dựng một control plane khác. Catalog được rút gọn còn:

- `aibox/deepseek-v4-flash`;
- `aibox/glm-5.2`.

Cả hai hiện khai báo thinking `max`. OpenCode native provider vẫn tồn tại cho direct/manual use, nhưng internal Peer route dùng `opencode-peer` để có role/profile boundary.

## Claude

`claude` built-in vẫn enabled cho direct/manual use và dùng auth/config mặc
định của Claude Code. Orchestration có thêm provider:

```text
claude-supervisor
  → ~/.local/bin/claude-room supervisor
  → Claude Opus 4.8
  → explicit Supervisor instructions/settings/Paseo MCP

claude-lead
  → ~/.local/bin/claude-room lead
  → Claude Sonnet 5 1M · High
  → 300K auto-compact window + Lead instructions/settings/Paseo MCP
```

`claude-supervisor` là Human-facing front door song song. `claude-lead` là
engineering-owner pilot riêng và chỉ được route khi Human yêu cầu rõ; stable
`planning` vẫn là `codex-lead/gpt-5.6-sol`. Wrapper dùng strict MCP config,
chặn native `Agent`/`Task`, tắt background tasks/slash commands/Chrome, và đưa
mọi delegation qua Paseo. Lead pilot dùng biến `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
chính thức của Claude Code để giới hạn active window ở 300K dù model có ceiling
1M.

## Gemini qua `antigravity-acp`

Provider custom:

```json
{
  "gemini-ui": {
    "extends": "acp",
    "label": "Gemini UI · Antigravity ACP",
    "command": [
      "$HOME/.local/share/antigravity-acp/dist/agy-acp-darwin-arm64"
    ]
  }
}
```

Paseo hỗ trợ bất kỳ agent nói ACP qua stdio bằng `extends: "acp"` và `command`; trường `models` hiện được dùng để thay model catalog runtime bằng danh sách Gemini đã kiểm tra. Xem [Paseo custom providers](https://paseo.sh/docs/custom-providers).

Local installation:

- source: `$HOME/.local/share/antigravity-acp`;
- ACP binary: `dist/agy-acp-darwin-arm64`;
- sibling CLI binary: `dist/agy`;
- ACP smoke test: `initialize` trả `agentInfo.name = Antigravity`;
- `agy models` hiện trả Gemini 3.6/3.5/3.1 cùng một số model khác; Paseo filter chỉ giữ Gemini.

`agy` có thể cần Google authentication trước khi chạy prompt thực tế. ACP README mô tả bridge này là server ACP chạy official `agy` subprocess, đồng thời cảnh báo việc dùng Antigravity OAuth qua công cụ bên thứ ba có thể vi phạm Terms của Google và có nguy cơ suspension/termination. Nếu cần tránh rủi ro OAuth, xem khuyến nghị Vertex AI/AI Studio trong [antigravity-acp README](https://github.com/shubzkothekar/antigravity-acp#readme).

## Khi nào dùng provider nào?

| Nhu cầu | Chọn |
|---|---|
| mechanical implementation | `opencode-peer/aibox/deepseek-v4-flash` |
| hard implementation/review | `codex-peer/gpt-5.6-luna` |
| UI/design | `gemini-ui/gemini-3.6-flash-medium` |
| external research | `opencode-peer/aibox/deepseek-v4-flash` |
| governance Supervisor thử nghiệm | `claude-supervisor/claude-opus-4-8` |
| engineering Lead pilot dài hạn | `claude-lead/claude-sonnet-5[1m]` |
| direct interactive Claude | built-in `claude`, không tự đưa vào Peer route |

## Auth/config boundary

Paseo chỉ launch external CLI. Provider subscription, login, model catalog và MCP riêng của CLI vẫn do CLI quản lý. `gemini-ui` đặt `params.supportsMcpServers=false`; sau khi daemon nhận config mới, Paseo sẽ không inject MCP fallback vào UI worker.
