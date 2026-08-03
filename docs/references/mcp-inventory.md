# MCP inventory (redacted)

Nguồn: `~/.codex/config.toml`. Giá trị secret/env/auth không được chép.

| Server | Kiểu | Mục đích/ghi chú |
|---|---|---|
| `gitnexus` | local command | code graph/navigation |
| `node_repl` | ChatGPT bundled command | browser, Chrome, Computer Use integration |
| `ccs-image-analysis` | local Node server | image analysis |
| `ccs-websearch` | local Node server | web search helper |
| `chrome-devtools` | npx server | browser/devtools |
| `kibana` | npx server + secret env | Kibana/log inspection |
| `morph-mcp` | npx server + API key | editing/codebase search |
| `pencil` | local desktop binary | UI/design canvas |
| `postgres-mcp-mrag-prod` | local command + DB URI | MRAG production DB |
| `postgres-mcp-mrag-staging` | local command + DB URI | MRAG staging DB |
| `postgres-mcp-mosa-dev` | local command + DB URI | MOSA dev DB |
| `sequential-thinking` | npx server | structured reasoning utility |
| `signoz` | local binary + secret env | observability/traces |
| `zread` | remote URL + auth header | repository/document reading |
| `computer-use` | local command, disabled | desktop control fallback |
| `serena` | uvx/git server | code intelligence; launched on demand |
| `websearch` | local command | websearch MCP |
| `sentry-selfhosted-mcp` | local Node server + secret env | Sentry issue/trace inspection |

## Injection map

| Consumer | Paseo control MCP | Codex baseline MCP |
|---|---:|---:|
| `codex-supervisor` | yes, qua role proxy | yes, via role runtime baseline |
| `codex-lead` | yes, qua role proxy | yes, via role runtime baseline |
| `codex-peer` | no | baseline is materialized by `codex-room-sync` |
| `opencode-peer` | no | not inherited from Codex baseline; own OpenCode config |
| `gemini-ui` | no | Antigravity/agy side has its own provider boundary |

Global Paseo `injectIntoAgents=false` đã được daemon nạp sau restart có chủ đích. Supervisor/Lead lấy control MCP qua role proxy; không dựa vào global injection.

## Security note

Database URI, API key, auth header, password và token chỉ được đọc từ source config khi thật sự cần. Không copy chúng vào prompt, docs, git hoặc agent handback.
