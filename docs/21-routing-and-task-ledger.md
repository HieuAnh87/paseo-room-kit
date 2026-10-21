# 21 — Routing và task ledger

Ngày thay đổi: 13/10/2026. Xem [routing](03-provider-routing.md) và [workflow](17-provider-independent-workflow.md).

## Model và effort

- Lead Sol/Opus giữ High, XHigh (default), Max; giữ nguyên effort hợp lệ được chọn.
- Peer có Luna (default) và Sol, mỗi model có High (default), XHigh, Max. `impl_deep` dùng Sol; `impl`, `search`, `research` dùng Luna.
- Supervisor Sol/Opus mặc định High; vẫn chọn được XHigh. Reviewer Opus High và Watcher Luna Medium giữ nguyên.
- Research/UI dùng provider Codex Peer đang bật. Các adapter AI Box/Gemini đang tắt trên host; không bật lại chúng qua thay đổi này.
- Đây là routing và lựa chọn, chưa phải benchmark chất lượng/cost. Không thay model/effort của session đang chạy hoặc suy catalog là chứng nhận model inference thực tế.

## Task opt-in trong canonical lease

Lead dùng `inspect_work_context` và `inspect_work_tasks` để lấy epoch/revision hiện tại. Trước khi dispatch Peer đầu tiên, có thể dùng `define_work_task` với `taskId`, `objective`, `write`, `scope`, `dependsOn`, `requiredChecks`, `expectedWorkEpoch`, `expectedRevision`.

- Task tối đa 64/epoch; dependency chỉ trỏ tới task đã định nghĩa trong cùng epoch. Definition bất biến; không có forward reference/cycle.
- Scope dùng literal path tương đối. Directory bao phủ subtree; `.` bao phủ repo. Không nhận glob, traversal, `.git` hoặc symlink path.
- Peer creation thêm labels `task_id`, `task_revision`. Proxy atomically reserve trước khi gửi upstream; native hook chỉ validate preview để tránh reserve hai lần.
- Writer scope không chồng reservation đang giữ trong cùng logical Git repository, kể cả worktree khác. Peer của task nằm trong workspace đã pin của Lead. Read-only task dùng disposition scout/architect/reviewer; engineer là write assignment.
- Khi đã có ledger, mọi Peer creation của epoch phải tham chiếu task. Không bật ledger quanh Peers đã dispatch; settle/archive họ trước, hoặc bắt đầu epoch mới theo existing lifecycle.
- Task chỉ dispatch sau khi prerequisites ACCEPTED; lưu revision đã consume. Peer report/idle/callback không tự accept task.
- `settle_work_task` cần decision ACCEPTED/CANCELLED, evidence, `writersQuiescent=true` và CAS. Acceptance cần đúng candidate hiện tại và passing receipts cho các required checks. Native Peer status phải quiescent; đây vẫn là Lead technical judgment, không phải Human acceptance.
- `reopen_work_task` chỉ dùng sau settlement. Tăng task revision và hold descendants. Peer đang chạy không bị auto-kill; Lead phải quiesce. Reservation giữ nguyên cho đến explicit cancellation. Descendant đã ACCEPTED cũng bị hold; không được handback với proof cũ.
- Sau cancellation, reopen descendant tạo attempt mới. Dispatch lại chỉ khi prerequisites được accept ở revision mới. Final handback chặn các task chưa ACCEPTED/CANCELLED và interrupted checks.

Scope reservation là dispatch/settlement contract, không phải OS write sandbox. Nó không tự phát hiện writer bên ngoài ledger, không chứng minh code đã được viết trong scope, và không chuyển engineering ownership khỏi Lead.

## Fixed check recipes và executor receipts

Human/project protocol có thể thêm optional `checks` vào `.orchestration/workflow.json` trước binding. Ví dụ:

```json
{
  "verify": {
    "argv": ["python3", "-m", "unittest", "discover", "-s", "tests"],
    "timeoutSeconds": 120,
    "maxOutputBytes": 262144
  }
}
```

Đây là giá trị của field `checks`, không phải thay toàn bộ workflow policy. Policy cũ không có checks vẫn hợp lệ. Sửa policy khi đang bound gây drift và cần existing Human replacement/checkpoint; không tự repin.

`run_work_check` chỉ nhận task/recipe/candidate/version, không nhận command tự do. Executor chạy argv đã pin với stdin đóng, timeout tối đa 300s, output tối đa 1MiB; không shell-interpolate. Repository recipe vẫn có thể chủ động gọi shell hoặc sửa file; đây không phải security sandbox.

Receipt giữ task/revision/recipe digest, argv, candidate trước/sau, exit code, thời gian, process group, output/hash và limits. Timeout, overflow, nonzero exit, candidate đổi hoặc authority đổi đều không pass. Hash incomplete được ghi rõ. Runtime snapshot trước/sau không chứng minh candidate chưa từng bị đổi rồi khôi phục trong khoảng giữa; pause writers vẫn là contract cần tuân thủ.

Executor không giữ lease lock trong lúc chạy lệnh. Check process group được cleanup khi kết thúc hoặc timeout. Nếu proxy bị dừng bất ngờ, receipt RUNNING giữ blocker; không tự retry hoặc xem là pass.

Owner xem bằng `paseo-room-workflow tasks --lead-id LEAD_ID`. Sau khi xác minh/quiesce process group, dùng owner-shell `resolve-check REQUEST.json` để preview, thêm `--apply` để ghi INTERRUPTED. Request gồm `leadAgentId`, `runId`, `evidence`, `writersQuiescent`, `expectedWorkEpoch`, `expectedRevision`. Resolution không tạo passing proof. PID reuse hoặc process group còn sống fail closed; owner phải inspect trước, tool không tự kill.

## Verification boundary

Fixture tests exercise CAS/authority, logical worktree overlap, dependency invalidation, native-hook/proxy admission, read-only inspection, process limits, candidate change và interrupted receipt resolution. Chưa chạy real-agent task episode hoặc paired model cost/quality benchmark.

Các public-export/doctor/installed-version gates từng có lỗi baseline riêng trong lần rollout đầu; kết quả sửa tiếp được ghi bên dưới.

Kết quả rollout đầu ngày 13/10, trước đợt sửa baseline: 110 tests workflow/task/attention/land/proxy/model-catalog/install và 53 role-guard tests pass. Full suite chạy 138 tests, có 4 failures + 7 errors; cùng 11 test lỗi đã tái hiện trên snapshot trước thay đổi, không có test lỗi mới. Các lỗi baseline gồm doctor fixtures tham chiếu OpenCode Lead/Supervisor đã bị xóa, app 0.11.2 khác pin 0.9.1, private report 20 chứa path máy, và public-export review list/doctor chưa đồng bộ với baseline.

Targeted runtime assets đã được cài và Paseo reload áp dụng `agents.providers`, không có restart-required path. Catalog live xác nhận Lead High/XHigh/Max, Peer Luna/Sol High/XHigh/Max và Supervisor default High. Runtime Codex catalogs chứa cả Peer models và disable native multi-agent. Canonical lease/notebook giữ nguyên checksum trong rollout; không đổi model của session hiện có, không sửa lịch Watcher và không tạo agent benchmark.

## Sửa các gate baseline ngày 13/10

11 test đỏ ban đầu gồm:

| Nhóm | Số test | Nguyên nhân và bản sửa |
|---|---:|---|
| Doctor environment | 6 | Fixture dựng OpenCode Lead/Supervisor đã bỏ; thay bằng Codex Watcher template/runtime hiện hành. Giữ nguyên các ca version mismatch, native-tool denial và CLI wrapper fail-closed. |
| Public export contract | 2 | Expected payload còn bốn file OpenCode cũ và thiếu Codex Watcher; đồng bộ danh sách review độc lập với allowlist hiện tại. |
| Installed provider policy | 1 | App 0.11.2 khác pin 0.9.1; xác nhận app, CLI, daemon và schema/policy source trong app bundle, đồng bộ cả hai lock lên 0.11.2. |
| Portability | 1 | Báo cáo 20 chứa đường dẫn home của máy; đổi thành biến root và link tương đối. |
| Exported doctor | 1 | Doctor chạy trong bản export bị kéo đỏ bởi contract/scanner; giữ kiểm tra export và round-trip, thêm output subprocess vào assertion để thấy nguyên nhân khi thất bại. |

Sau khi gỡ các lỗi chặn đầu tiên, scanner phát hiện nhầm tham số reservation và source tạo ID/fixture là credential/runtime identity. Đổi tên tham số sang `reservation_id`; scanner chỉ nhận thêm cú pháp source sinh UUID và identifier có dấu đóng container. Test hồi quy xác nhận source hợp lệ được nhận và ID literal thật vẫn bị chặn; các negative fixtures credential, runtime ID và private material được giữ nguyên.

Doctor live cũng phát hiện global MCP injection bật và bản role-guard tests cài trên máy cũ. Đã đặt lại `daemon.mcp.injectIntoAgents=false`, đồng bộ guard/module/tests và reload; chỉ path injection được áp dụng, không cần restart. Provider/model/effort giữ nguyên và lease/notebook giữ nguyên checksum. Bản backup runtime nằm dưới `~/.paseo-room-kit-backups/`.

Xác minh sau sửa: `python3 -m unittest discover -s tests` chạy **139 tests, tất cả pass**, không còn 11 lỗi baseline. `./scripts/doctor.sh --live` pass toàn bộ, gồm **53 role-guard tests**, CLI/daemon pin và installed-copy checks. Public export tự chạy doctor trong artifact, scan private material và export/scan round-trip đều pass. `git diff --check` sạch. Kết quả này xác nhận các gate của kit; real-agent benchmark và compatibility của plugin Room Flow vẫn nằm ngoài đợt sửa baseline này.

## Native binding và callback checkpoint ngày 14/10

Smoke sidebar Snapshot phát hiện extractor cũ đọc runtime fields phẳng, trong khi native record lưu cấu hình trong `config` và effective values trong `runtimeInfo`. Binding mới dùng `runtime_binding_version=2`: normalize các nguồn này, từ chối null/mâu thuẫn cho provider/model/thinking/mode, digest-bind settings và feature values. Không lưu credentials trong pin và không coi persisted metadata là model attestation.

Lease không có version vẫn ở v1 trong epoch hiện tại và hiện `LEGACY_UNVERIFIED` qua attention. Giữ extractor/first-pin v1 để không làm hỏng work/handback đang chạy; không tự nâng cấp null pin. Epoch mới cần binding v2. Owner có thể release rồi bind lại, hoặc preview `paseo-room-workflow rebind-runtime REQUEST.json` tại checkpoint HANDBACK_READY với Lead idle, task settled, check quiescent và descendants archived. `--apply` yêu cầu exact epoch/revision/runtime digest cùng evidence kiểm tra launch độc lập. Operation không thay candidate/report evidence, không ghi Human acceptance và không tự reopen.

Peer không có identity có thể trả `peerAgentId=null`. Lead chỉ correlate từ đúng một durable post-create brief và native Peer record khớp assignment/epoch/workspace/parentage, rồi lưu method trong receipt. Không repair ID sai, không đoán identity; thiếu hoặc mơ hồ trả NEEDS_LEAD_DECISION. Resolver MCP chỉ nhận UUID hợp lệ, và parent-process recovery chỉ đọc ancestor cùng UID. Unit fixture kiểm tra environment bị lọc; chưa tự nó chứng minh ảnh hưởng của `injectIntoAgents=false` lên daemon hoặc callback.

Các regression gates nằm trong `tests/test_native_binding.py`, được đưa vào doctor và public export. Khi đồng bộ các file runtime, process MCP đã chạy có thể giữ module cũ đến lần khởi động session tiếp theo; không restart các role đang hoạt động để ép chuyển version. Real callback probe phải dùng session mới, đúng một Lead/Peer, không owner recovery sau dispatch, receipt và candidate khớp. Failure có recovery không được ghi thành automatic E2E pass.


## Callback context on top-level MCP fallback

A top-level MCP fallback can restore workspace and parent labels, but it cannot restore the daemon caller context used to arm native finish notifications. Callback-dependent `create_agent` and `send_agent_prompt` now preflight the exact agent-scoped catalog before guard admission. If unavailable, dispatch is denied before reserving or launching work. Both JSON and SSE fallback paths also refuse a top-level callback-dependent mutation if the scoped catalog changes after admission. Explicit no-notification owner operations and read-only fallback remain available.

This guard prevents silent callback loss; it does not restore native callbacks on a daemon that provides no agent-scoped tools. A callback probe with a finished Peer and no delivered callback is a failed gate, not a pending gate indefinitely or a pass after recovery. Changing native tool exposure requires a separate compatibility design; enabling duplicate ungoverned tools is not part of this change.
