# 15 — Role proxy, guard, Lead lease và terminal state

> Authority update: Supervisor is optional. Direct Human→root Lead and an independently bound root Supervisor observer use the same canonical lease and protected epoch operations as the compatible parented bootstrap. Parentage alone is not authority. `submit_work_result` resolves the active binding; direct mode persists a Human-queue receipt. See the shared [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) for repository gates, correlated reports, candidate review and owner-shell commands.


## Vì sao cần lớp này?

Paseo native quản lý parentage, callback, permissions, archive và runtime lifecycle. Paseo không có native Supervisor/Lead/Peer authorization, provider route policy, engineering acceptance hoặc một-Lead-per-workspace lease.

Paseo 0.8 có per-provider `paseoTools.enabled`. Mọi custom internal SLP
provider đặt field này thành `false`, nên global injection nếu bật sau này vẫn
không cấp native unrestricted catalog. Supervisor/Lead chỉ nhận role-aware
proxy; Peer không có control surface.

Paseo 0.8 áp cùng policy cho caller-scoped `/mcp/agents`. Khi endpoint đó trả
empty catalog hoặc tool/method-not-found, proxy gọi top-level catalog và tự khôi phục chỉ caller
workspace/parent defaults, sau đó vẫn role-filter và chạy deterministic guard.
Regression test bắt buộc blocked tools không xuất hiện và guarded calls vẫn chạy.

## Enforcement path

```text
Codex or Claude Supervisor/Lead
  → stdio MCP: paseo-room-mcp <role>
  → room-role-guard.py PreToolUse
  → Paseo HTTP MCP /mcp/agents?callerAgentId=...
  → room-role-guard.py PostToolUse
```

`paseo-room-mcp` là enforcement boundary chính. Nó filter catalog theo role, gọi guard trước khi forward, rồi gọi post guard với response thật.

Codex lọc `PASEO_AGENT_ID` khi launch stdio MCP subprocess. Proxy ưu tiên env trực tiếp; nếu bị lọc, nó chỉ recover trường identity không-secret này từ cùng chuỗi parent process của Codex. Không ghi agent ID động vào shared role config vì nhiều agent cùng role có thể chạy đồng thời.

Guard trước upstream:

- Codex/Claude Supervisor `create_agent` mặc định chỉ chấp nhận exact `planning`; `planning_pilot` cần explicit `lead_profile=pilot`;
- OpenCode budget Supervisor chỉ chấp nhận `planning_budget` với `lead_profile=budget` và `stack_profile=budget`; Supervisor khác không được tạo budget Lead;
- Lead phải khai báo `route` và dùng exact provider/model từ orchestration preferences; budget Lead được guard chuyển sang exact `*_budget` route;
- canonicalize role, route, Lead profile, `room_kind`, current `work_epoch`,
  task state, thinking, provider-specific unattended mode và `notifyOnFinish`;
- Peer deny toàn bộ Paseo tools;
- mutation vào agent khác phải đúng parent→child và expected role.

Guard sau upstream:

- activate pending Lead lease bằng `agentId` Paseo trả về;
- release lease khi Supervisor archive/kill Lead.

Proxy cung cấp protected epoch lifecycle: `handback_to_parent`,
`list_slp_decisions`, `record_slp_decision`, `reopen_work_epoch`,
`resolve_slp_delivery`, và `archive_slp_workspace`. Reserve/deliver dùng
correlation ID + monotonic revision; response mơ hồ không tự retry.

`recover_peer_callbacks` là Lead-only bounded exception khi native callback
không render. Nó đọc activity một lần và lưu digest-deduplicated receipt trong
lease. `inspect_slp_ownership` hiển thị cả owned, unparented và foreign-parent
custom Leads. `retire_legacy_lead` chỉ soft-archive exact parent-owned orphan
bằng authority digest; managed lease holder, foreign/unparented target và
unreadable authority fail closed.

`codex-room-sync` cấp proxy MCP cho Codex Supervisor/Lead và không cấp cho Peer. `claude-room` cấp cùng proxy bằng strict role MCP config cho Claude Supervisor/Lead. Codex còn ép `mcp__paseo` đi direct-only trong code mode.

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
- version 2 giữ `room_kind`, `work_epoch`, `handback_epoch`, monotonic
  `revision`, evidence digest, delivery reservation và Peer recovery receipts;
- malformed registry/nested lease/revision fail closed;
- `slp-decision-history.jsonl` là append-only evidence, không replay để
  override registry.

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
- Lead thấy `submit_work_result` (alias `handback_to_parent`), `inspect_work_context`, `inspect_work_candidate`, `record_peer_report` và `recover_peer_callbacks`; Supervisor thấy
  decision/ownership tools nhưng không thấy Lead-only handback;
- final report tới Supervisor sau callback-driven Lead turn;
- cleanup archive Peer rồi Lead làm lease về `released`.

Proxy là deterministic guardrail cho cooperative coding agent runtime. CLI wrapper có thể bị một process hostile bypass bằng absolute binary path, nên toàn bộ setup vẫn không thay thế OS sandbox hoặc native daemon RBAC.
