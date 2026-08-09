# 06 — MCP và visibility boundary

## Hai loại MCP khác nhau

### MCP của Codex baseline

Các server trong `~/.codex/config.toml` được giữ ở baseline và được `codex-room-sync` đưa vào runtime role config. Đây là catalog tool phục vụ coding/research/browser/database/observability tùy project.

### Paseo control MCP

Paseo daemon có:

```json
{
  "enabled": true,
  "injectIntoAgents": false
}
```

Paseo `0.2.5` không hỗ trợ `injectIntoProviders`. Field này từng có trong config local nhưng chỉ được schema giữ như unknown field và không có implementation; nó đã bị xóa. Vì global injection không chọn được role, config mới tắt `injectIntoAgents`.

Selective authority được cấp lại có chủ đích:

- `codex-supervisor`, `claude-supervisor`, `opencode-supervisor`, `codex-lead`, `claude-lead` và `opencode-lead` nhận MCP server `paseo` qua role-specific `paseo-room-mcp`;
- proxy forward tới `http://127.0.0.1:6767/mcp/agents?callerAgentId=...` sau khi kiểm tra role, route, ownership và lease;
- Lead còn thấy synthetic tool `handback_to_parent`; tool tự resolve đúng parent Supervisor và không nhận `agentId` từ Lead;
- `codex-peer` không có Paseo MCP server;
- OpenCode Supervisor/Lead deny native `task`, dùng role proxy cho `paseo_*`; OpenCode Peer deny cả `paseo_*` và direct Paseo CLI;
- ACP catalog probe chạy trước khi có agent identity chỉ thấy MCP catalog rỗng; session thật phải resolve được `PASEO_AGENT_ID` mới nhận control tools;
- `gemini-ui` khai báo `params.supportsMcpServers=false`;
- room launchers prepend một `paseo` CLI wrapper chỉ cho phép lifecycle bridge `paseo hooks codex`, còn lại deny.

`codex-room-sync` còn set `features.code_mode.direct_only_tool_namespaces=["mcp__paseo"]` để trace rõ và tránh nested tool path. Policy thật nằm trong proxy, không phụ thuộc Codex lifecycle hook.

Daemon đã được restart có chủ đích và hiện đã nạp `injectIntoAgents=false` cùng Gemini capability change. Chỉ cần restart lại nếu có thay đổi daemon/provider mới và Human đã chấp thuận.

## MCP inventory an toàn

| Nhóm | Server hiện có | Ghi chú |
|---|---|---|
| Code graph/search | `gitnexus`, `serena`, `websearch`, `zread` | navigation, graph, external/repo search |
| Browser/runtime | `node_repl`, `chrome-devtools`, `computer-use` (disabled) | browser/desktop integration |
| CCS utilities | `ccs-image-analysis`, `ccs-websearch` | image/web helper |
| UI/design | `pencil` | Pencil desktop MCP |
| Database | `postgres-mcp-mrag-prod`, `postgres-mcp-mrag-staging`, `postgres-mcp-mosa-dev` | database access; credentials nằm trong source config, không copy vào docs |
| Observability | `kibana`, `signoz`, `sentry-selfhosted-mcp` | log/trace/issue inspection |
| Editing/reasoning | `morph-mcp`, `sequential-thinking` | bounded editing/search and reasoning utility |
| External agent/tool | `zread` | remote MCP URL, auth header được redacted |

Chi tiết command/env thật chỉ đọc từ config local có kiểm soát. [references/mcp-inventory.md](references/mcp-inventory.md) ghi lại phân loại mà không chép secret.

## Quy tắc MCP

1. Không đưa secret vào prompt, handback hoặc docs.
2. Không dùng MCP access để biến Peer thành owner.
3. Khi debug MCP, xác nhận provider nào nhận được server: role proxy và baseline Codex là hai đường khác nhau.
4. Database/observability MCP có thể có quyền mạnh; không coi tool availability là authorization cho product decision.
5. `MCP server available` không đồng nghĩa `tool result accepted`; Lead vẫn cần validate evidence.
6. Không thêm lại `injectIntoProviders`; Paseo hiện không đọc field đó.
7. Không bật lại global `injectIntoAgents` nếu vẫn cần Peer không có control-plane tools.

## Vì sao codebase search không nhất thiết spawn model?

`rg`, GitNexus hoặc MCP call là tool execution trong agent hiện tại. Chỉ khi Lead tạo một delegated `search` Peer thì Luna Low mới là model riêng. Đây là lý do routing docs tách “direct search” và “delegated search”.
