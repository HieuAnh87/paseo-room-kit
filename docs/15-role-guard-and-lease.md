# 15 — Role proxy, guard, Lead lease và terminal state

## Vì sao cần lớp này?

Paseo native quản lý parentage, callback, permissions, archive và runtime lifecycle. Paseo không có native Supervisor/Lead/Peer authorization, provider route policy, engineering acceptance hoặc một-Lead-per-workspace lease.

Ngoài ra, Paseo `0.2.5` không implement `injectIntoProviders`. Global `injectIntoAgents` chỉ inject theo capability của provider, không theo custom role.

## Enforcement path

```text
Codex Supervisor/Lead
  → stdio MCP: paseo-room-mcp <role>
  → room-role-guard.py PreToolUse
  → Paseo HTTP MCP /mcp/agents?callerAgentId=...
  → room-role-guard.py PostToolUse
```

`paseo-room-mcp` là enforcement boundary chính. Nó filter catalog theo role, gọi guard trước khi forward, rồi gọi post guard với response thật.

Codex lọc `PASEO_AGENT_ID` khi launch stdio MCP subprocess. Proxy ưu tiên env trực tiếp; nếu bị lọc, nó chỉ recover trường identity không-secret này từ cùng chuỗi parent process của Codex. Không ghi agent ID động vào shared role config vì nhiều agent cùng role có thể chạy đồng thời.

Guard trước upstream:

- Supervisor `create_agent` chỉ chấp nhận exact `planning` provider;
- Lead phải khai báo `route` và dùng exact provider/model từ orchestration preferences;
- canonicalize role, route, task state, thinking, full-access Codex mode và `notifyOnFinish`;
- Peer deny toàn bộ Paseo tools;
- mutation vào agent khác phải đúng parent→child và expected role.

Guard sau upstream:

- activate pending Lead lease bằng `agentId` Paseo trả về;
- release lease khi Supervisor archive/kill Lead.

Proxy còn cung cấp synthetic `handback_to_parent` riêng cho Lead. Nó không nhận target ID từ model, chỉ resolve active parent governance seat từ Paseo-owned parent metadata rồi forward final report. Supervisor và Peer không thấy tool này.

`codex-room-sync` cấp proxy MCP cho Supervisor/Lead và không cấp cho Peer. Nó cũng ép `mcp__paseo` đi direct-only trong Codex code mode.

## Vì sao không chỉ dùng Codex hooks?

Static tests của `PreToolUse` pass, nhưng live `app-server` test cho thấy cả nested `exec` và direct Paseo MCP có thể đi specialized path không phát hook. Ba duplicate test agents đã lọt qua trong lúc chẩn đoán và đều được stop + soft-archive ngay. Vì vậy:

- lifecycle hook vẫn được materialize như defense in depth cho surface hỗ trợ hook;
- proxy gọi cùng guard script trực tiếp, không chờ Codex phát hook;
- launcher không dùng `--dangerously-bypass-hook-trust`;
- direct CLI name trong room runtime bị shadow bằng wrapper deny.

## OpenCode và Gemini

- OpenCode Peer deny `task`, `paseo_*` và direct `paseo` CLI command patterns trong `paseo-peer.json`; launcher còn prepend CLI deny wrapper.
- `gemini-ui` dùng `params.supportsMcpServers=false` để không nhận Paseo MCP fallback. Thay đổi provider config cần daemon reload/restart trước khi áp dụng cho session mới.

## Lease

Registry: `lead-leases.json`.

- `pending`: reservation trước create;
- `active`: PostToolUse đã bind Lead ID;
- `released`: old Lead đã archive/kill;
- `failed`: create không trả agent ID;
- pending tự hết hiệu lực sau năm phút.

Guard còn đối chiếu agent records theo `workspaceId + role=lead + archivedAt`, không chỉ tin registry.

## Terminal state

Peer handback bắt đầu bằng:

```text
Task outcome: DONE|BLOCKED_PERMISSION|NEEDS_LEAD_DECISION|FAILED
```

Lead cập nhật `task_state`, validate evidence, rồi mới chọn `ACCEPTED` hoặc `REWORK`. Native `idle` hay Peer `DONE` không phải acceptance.

Contract đầy đủ: `WORKFLOW_PROTOCOL.md`.

## Verification

```bash
python3 ~/.codex/hooks/test-room-role-guard.py
python3 -m py_compile ~/.codex/hooks/room-role-guard.py ~/.local/bin/codex-room-sync ~/.local/bin/paseo-room-mcp
bash -n ~/.local/bin/codex-room ~/.local/bin/opencode-paseo-peer
for role in supervisor lead peer; do ~/.local/bin/codex-room-sync "$role"; done
```

Live proxy verification phải chứng minh:

- duplicate Lead bị deny và không có agent record mới;
- wrong provider cho declared Peer route bị deny;
- registry reconcile đúng active Lead;
- Peer runtime không có `mcp_servers.paseo`;
- Lead thấy và gọi được `handback_to_parent`, Supervisor không thấy tool;
- final report tới Supervisor sau callback-driven Lead turn;
- cleanup archive Peer rồi Lead làm lease về `released`.

Proxy là deterministic guardrail cho cooperative coding agent runtime. CLI wrapper có thể bị một process hostile bypass bằng absolute binary path, nên toàn bộ setup vẫn không thay thế OS sandbox hoặc native daemon RBAC.
