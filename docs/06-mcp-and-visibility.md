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

Paseo `0.9.1` hỗ trợ policy theo provider qua
`agents.providers.<id>.paseoTools`. Canonical config vừa giữ
`injectIntoAgents=false`, vừa đặt `paseoTools.enabled=false` cho các
internal custom providers. Vì vậy nếu global injection vô tình bật về sau,
những provider này vẫn không nhận native unrestricted catalog.

Selective authority được cấp lại có chủ đích:

- `codex-supervisor`, `claude-supervisor`, `codex-lead`, `claude-lead` nhận MCP server `paseo` qua role-specific `paseo-room-mcp`;
- proxy thử caller-scoped `/mcp/agents?callerAgentId=...`; khi per-provider
  policy làm catalog này rỗng/method-not-found, proxy dùng top-level catalog,
  khôi phục chỉ caller workspace/parent defaults, rồi role-filter và guard;
- Lead thấy protected `handback_to_parent` và `recover_peer_callbacks`;
  Supervisor thấy decision/ownership operations;
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
6. Không thêm lại field lịch sử `injectIntoProviders`; dùng
   `paseoTools.enabled=false` đúng schema 0.9.1.
7. Global `injectIntoAgents` vẫn nên fail closed ở `false`; per-provider deny
   là defense in depth, không phải lý do mở global injection.

## Vì sao codebase search không nhất thiết spawn model?

`rg`, GitNexus hoặc MCP call là tool execution trong agent hiện tại. Chỉ khi Lead tạo một delegated `search` Peer thì GPT-6 Luna Medium mới là model riêng. Đây là lý do routing docs tách “direct search” và “delegated search”.

UI providers `antigravity-cli` and `claude-ui` also disable native Paseo tools. Antigravity uses its installed provider plugin and own tool permissions; its assignment constraints are cooperative, not an OS sandbox or enforced ban on its native subagents. Claude UI uses a separate writable Peer profile; Claude Reviewer remains read-only.
