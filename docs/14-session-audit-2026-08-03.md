# 14 — Audit toàn bộ session Paseo

Thời điểm audit: `2026-08-03 20:23 +07`.

Phạm vi:

- toàn bộ `38` agent record từ `2026-07-31` đến `2026-08-03`;
- activity/timeline của từng agent, gồm cả agent đã archive;
- quan hệ parent–child, provider/model/thinking, workspace và lifecycle;
- daemon log hiện tại và log đã rotate;
- trạng thái provider, permission, schedule, loop và workspace hiện tại.

Đây là audit chỉ đọc. Không agent/workspace nào bị archive, không permission nào được duyệt, không config nào bị đổi và daemon không bị restart.

## Kết luận điều hành

Paseo hiện đã vượt qua mức “thử agent khác trong UI” và đạt mức **pilot dùng được** cho engineering thật. Hai chuỗi WebSocket/Sentry và OCR đã tạo được patch, validation rộng, commit và MR với review độc lập. Chất lượng engineering cao.

Tuy nhiên, governance chưa đạt đúng mô hình mục tiêu một cách ổn định. Ba điểm yếu lớn nhất là:

1. lịch sử từng route Lead/Peer sang stock `codex/gpt-5.4`;
2. Supervisor mới vẫn can thiệp vào quyết định staffing của Lead;
3. lifecycle/permission chưa biểu diễn trạng thái đủ rõ: tại snapshot Lead chờ permission commit nhưng `requiresAttention=false`, trong khi Supervisor idle. Trong lúc audit, permission được xử lý và Lead tiếp tục chạy, nên đây là visibility gap chứ không còn là blocker hiện tại.

Đánh giá tổng thể: **7.0/10**.

Nếu chỉ tính chuỗi mới nhất với custom Supervisor và custom Lead: **8.0/10 về topology**, nhưng mới **6.5/10 về lifecycle**, vì custom Peer chưa được chạy end-to-end và permission handoff đang mắc.

## Scorecard

| Mặt đánh giá | Điểm | Nhận xét |
|---|---:|---|
| Chất lượng engineering và evidence | 9.0 | Trace Sentry/SigNoz, GitNexus, test rộng, giữ dirty worktree, commit/MR scoped tốt |
| Human-facing Supervisor | 7.5 | Đã là front door và relay trạng thái tốt; vẫn đi hơi sâu vào staffing/permission kỹ thuật |
| Lead ownership | 8.0 | Lead làm impact analysis, review, validation và handback tốt |
| Peer delegation/review | 7.5 | Peer OCR/UI có giá trị, Lead bắt được lỗi của Peer; custom Peer mới chưa được chứng minh |
| Provider/model routing | 7.0 | Supervisor/Lead mới route đúng; lịch sử có ba role seat dùng stock `gpt-5.4` |
| Authority separation | 6.0 | Supervisor từng sửa workflow/config và hiện còn phủ quyết Peer staffing trong phạm vi của Lead |
| Lifecycle/notification | 5.5 | Có callback nhưng vẫn poll; permission hiện không được nâng attention đúng lúc |
| Workspace/session hygiene | 6.0 | Có archive và parentage; vẫn có duplicate/stub session, nhiều workspace cùng cwd và status semantics dễ nhầm |
| Hiệu quả context/cost | 5.5 | Một Lead đã dùng khoảng 76% context; nhiều vòng tạo lại Lead và status chatter |
| Portfolio model thực chiến | 4.5 | Sol/Luna/DeepSeek đã chạy; GLM, Gemini UI, Claude và search route chưa được chứng minh trong topology mới |
| Bảo mật local | 7.0 | Home Paseo là `0700`, config/keypair `0600`; agent record vẫn chứa control token trong persistence metadata |

## Toàn cảnh 38 session

Metadata hiện chia thành:

- `22` record được lưu như standalone;
- `6` Supervisor custom;
- `7` Lead custom;
- `1` stock Codex có label Lead;
- `1` stock Codex có label Peer;
- `1` OpenCode implementer.

Nội dung timeline cho thấy một record standalone khác (`<redacted-agent>`) thực tế cũng là Peer nhưng thiếu label. Đây là bằng chứng rằng label hiện chưa đủ tin cậy để dùng làm policy duy nhất.

### Nhóm A — thử nghiệm trước topology

Các session từ `2026-07-31` đến đầu `2026-08-03` chủ yếu dùng Paseo như launcher/UI cho Codex hoặc OpenCode:

| Nhóm | Agent tiêu biểu | Đánh giá |
|---|---|---|
| Setup provider/OpenCode | `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>` | Hữu ích để khám phá provider/model, nhưng chưa có role isolation |
| GitNexus/config investigation | `<redacted-agent>`, `<redacted-agent>` | Tác vụ bounded, phù hợp standalone |
| Product/research | `<redacted-agent>`, `<redacted-agent>` | Không phải bằng chứng cho orchestration engineering |
| Direct MOSA work | `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>` | Chất lượng implementation có thể tốt nhưng bypass Supervisor–Lead–Peer |
| OpenCode experiments | `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>`, `<redacted-agent>` | Có cả session rỗng/failed/duplicate; nên coi là lịch sử thử nghiệm |

Các session này không nên dùng để kết luận topology mới thất bại. Chúng tồn tại trước khi custom provider/profile và authority contract được hoàn thiện.

### Nhóm B — proto Lead → implementer

```text
<redacted-agent>  stock Codex Luna
  └── <redacted-agent>  OpenCode / AI Box DeepSeek V4 Flash Max
```

Kết quả:

- DeepSeek triển khai đầy đủ keyboard-store MVP;
- lint, typecheck, `28/28` test và build đều xanh;
- E2E checkout/inventory/admin/group-buy chạy được;
- parent agent tiếp tục review và chỉnh UI.

Điểm tốt:

- Đây là bằng chứng rõ nhất rằng DeepSeek có thể làm implementation worker thực tế.
- Brief và handback đủ chi tiết.
- Parent giữ phần UX/final adjustment.

Điểm chưa đúng topology:

- không có Supervisor;
- parent là stock Codex, chưa phải `codex-lead`;
- child dùng stock `opencode`, chưa phải `opencode-peer`;
- title/role là `implementer`, chưa dùng protocol Peer/dissent thống nhất.

Kết luận: **thành công engineering, proto orchestration**, chưa phải bằng chứng full chain.

### Nhóm C — Supervisor đầu tiên cho Sentry 946/948

```text
<redacted-agent>  codex-supervisor / Sol Medium
  ├── <redacted-agent>  codex-lead / Sol Medium
  ├── <redacted-agent>  codex-lead / Sol Medium
  ├── <redacted-agent>  codex-lead / Sol Medium
  ├── <redacted-agent>  codex-lead / Sol Medium
  ├── <redacted-agent>  codex-lead / Sol Medium
  └── <redacted-agent>  codex-lead / Sol Medium, mosa-ui
        └── <redacted-agent>  stock codex/gpt-5.4 Peer
```

Kết quả engineering:

- backend MR `!259` được tạo với validation khoảng `5,009` test;
- UI MR `!77` được tạo với `840` test pass, `117` WS test và Peer audit;
- patch giữ privacy boundary, không đưa token/payload/PII vào telemetry;
- dirty worktree và thay đổi ngoài scope được bảo toàn.

Điểm mạnh:

- Supervisor giữ giao tiếp với Human và điều phối hai repo.
- UI Lead dùng audit Peer và xử lý outcome `RESOLVED_BY_LEAD`.
- Peer audit có evidence rõ, nêu coverage gap thay vì sửa lén.
- MR handback có branch, SHA, validation và blocker.

Điểm yếu:

- Một Supervisor tạo `6` Lead. Năm Lead đầu nối tiếp nhau chủ yếu vì MCP/Sentry runtime thay đổi; continuity bị phân mảnh.
- Supervisor trực tiếp tham gia sửa config/runtime trong lịch sử, vượt vai trò governance mục tiêu.
- UI Peer dùng stock `codex/gpt-5.4`, không phải `codex-peer`.
- Timeline có nhiều `get status`, `get activity` và follow-up hơn mức cần thiết.
- Daemon từng không notify được Supervisor hai lần vì active run cancellation chưa được acknowledge.

Kết luận: **đầu ra rất tốt, lifecycle tốn kém và chưa ổn định**.

### Nhóm D — OCR issue 1105

```text
<redacted-agent>  codex-supervisor / Sol Medium
  └── <redacted-agent>  stock codex/gpt-5.4, label Lead
        └── <redacted-agent>  stock codex/gpt-5.4, Peer nhưng thiếu role label
```

Kết quả:

- tìm đúng timeout-budget mismatch giữa OCR render budget và global `30s` clamp;
- Peer làm patch graceful degradation;
- Lead bắt được hai lỗi quan trọng trong Peer output:
  - chưa nhận raw DOMException `TimeoutError`;
  - phase-B failure vẫn có thể phát outward ready event;
- tách thành hai commit:
  - `<redacted-agent>` — graceful degradation/telemetry/event boundary;
  - `<redacted-agent>` — trusted OCR sandbox deadline;
- validation từ focused test đến `93/93` và `74/74`.

Đây là chain có chất lượng review tốt nhất. Nó chứng minh mô hình Lead review Peer có giá trị thực: Peer không hoàn hảo, nhưng Lead phát hiện và buộc sửa bằng evidence.

Sai lệch:

- cả Lead và Peer đều route sang stock `codex/gpt-5.4`;
- orchestration preference lúc đó bị báo missing và không được áp dụng;
- label Peer không nhất quán;
- có polling trong khi callback/notification đã bật.

Kết luận: **mẫu hành vi đúng, provider binding sai**.

### Nhóm E — chain custom mới nhất

```text
<redacted-agent>  codex-supervisor / Luna Max
  └── <redacted-agent>  codex-lead / Sol Medium
        └── custom codex-peer / Luna Max: đã request nhưng không được chạy
```

Điểm đúng:

- Supervisor dùng Luna Max;
- Lead được tạo bằng đúng `codex-lead/gpt-5.6-sol`;
- parentage và label `role=lead` đúng;
- Lead thử tạo `codex-peer/gpt-5.6-luna` Max ở plan/read-only;
- Supervisor giữ Human-facing status;
- implementation giữ global timeout boundary, test `5,027` pass và staging scope sạch.

Điểm cần sửa:

- Supervisor phủ quyết việc Lead tạo audit Peer chỉ vì Human chưa phê duyệt thêm seat.
- Sau đó Supervisor còn brief “không tạo/use Peer”, khiến Lead tự implement.
- Đây là authority inversion: việc chọn bounded Peer nằm trong engineering staffing của Lead, miễn objective/authority không đổi.
- Lead hiện có khoảng `195k/258k` context token, tức khoảng `76%`.
- Tại snapshot Lead `running` nhưng thực chất chờ permission cho `git commit`, trong khi `requiresAttention=false` và Supervisor idle.
- Trong lần kiểm tra cuối, permission đã hết; Lead tạo commit `<redacted-agent>`, push branch `fix/ocr-phase-b-sandbox-timeout` và đang chạy bước tạo MR.
- Việc chain tự tiến tiếp là tín hiệu tốt, nhưng trạng thái chờ permission đã không được phản ánh rõ cho Human trong khoảng chờ.

Kết luận: **provider topology đã đúng, governance runtime chưa đúng hoàn toàn**.

## Provider routing: tiến bộ và khoảng trống

### Đã chứng minh

- `codex-supervisor` với Sol và Luna đều chạy.
- `codex-lead/gpt-5.6-sol` chạy engineering thật.
- stock Luna chạy được direct coding/review.
- AI Box DeepSeek V4 Flash Max triển khai được MVP lớn.

### Chỉ mới cấu hình hoặc mới request

- `codex-peer/gpt-5.6-luna` Max: request đúng nhưng bị Supervisor từ chối trước khi chạy.
- `opencode-peer/aibox/deepseek-v4-flash`: chưa có child trong full custom chain.
- `opencode-peer/aibox/glm-5.2`: chưa có orchestration run thực tế.
- `gemini-ui`: provider available nhưng chưa có UI Peer session trong lịch sử.
- Claude: CLI status và provider snapshot hiện không thống nhất; chưa nên coi là route đã verify.
- `search` bằng Luna Low: chưa có một delegated search Peer đúng preference để kiểm chứng.

### Lỗi phụ ở structured generation

Daemon log ghi:

- `11` lần auxiliary structured-generation provider fail/fallback;
- phần lớn thử stock OpenCode model `opencode/claude-haiku-4-5` và bị `Insufficient balance`;
- một stock Codex turn bị stream disconnect;
- lỗi này không phải bằng chứng `opencode-peer/AI Box` hỏng, nhưng gây latency và log noise.

Nên tách rõ:

```text
role routing: codex-supervisor / codex-lead / codex-peer / opencode-peer
auxiliary structured generation: title/metadata/structured response fallback
```

Không được dùng lỗi auxiliary stock OpenCode để kết luận AI Box Peer không chạy.

## Authority audit

### Human → Supervisor

Đã đúng phần lớn:

- Human nói chuyện với Supervisor;
- Supervisor relay objective, report status và xin quyết định;
- Supervisor không trực tiếp viết product code trong chain mới.

Rủi ro:

- Supervisor đang review từng command permission và quyết định có được spawn Peer hay không.
- Permission governance là hợp lý khi kiểm soát side effect, nhưng không nên biến thành engineering staffing.

Quy tắc nên áp dụng:

```text
Supervisor được chặn:
- scope/authority expansion;
- sai provider/parent/workspace;
- destructive/external action chưa được Human cho phép;
- hai Lead cùng lease.

Supervisor không được chặn:
- Lead chọn bounded Peer trong objective đã chốt;
- Lead chọn cách chia task/review;
- Lead yêu cầu dissent/audit kỹ thuật.
```

### Supervisor → Lead

Chain mới bind đúng provider và parent. Điểm còn thiếu là lease semantics rõ:

- một workspace chỉ có một active Lead;
- replacement phải checkpoint → handoff → archive/revoke;
- không tạo Lead mới chỉ để retry MCP nếu Lead cũ có thể nhận follow-up.

### Lead → Peer

Hành vi tốt nhất xuất hiện ở OCR:

- Peer implement;
- Lead review;
- Lead phát hiện mismatch với evidence thực tế;
- Peer sửa lại;
- Lead validate và accept.

Đó là mẫu nên chuẩn hóa. Dissent protocol chưa xuất hiện nhiều vì các Peer chủ yếu trả finding thay vì formal dissent. Không cần ép mọi review thành dissent; chỉ dùng protocol khi có claim ngược direction.

## Lifecycle và notification

### Trạng thái quan sát được

Tại snapshot ban đầu:

- Supervisor `<redacted-agent>` idle;
- Lead `<redacted-agent>` running;
- Lead có pending permission cho focused commit;
- `requiresAttention=false`;
- không có heartbeat/schedule/loop;
- không có active custom Peer.

Trong lúc audit, permission được xử lý mà không có can thiệp từ audit này. Lead đã tạo commit `<redacted-agent>`, push branch và chuyển sang tạo MR; danh sách pending permission trở về rỗng.

Vấn đề còn lại là semantic gap: một chain không nên được hiển thị như “đang chạy bình thường” khi foreground turn chỉ còn chờ permission nhưng attention flag không nổi. Dù lần này nó tự tiến tiếp, Human/Supervisor không có trạng thái trung gian đáng tin cậy.

### Polling

Skill Paseo ưu tiên notification. Trong lịch sử:

- callback `notifyOnFinish=true` được dùng đúng;
- nhưng các Supervisor vẫn gọi `get_agent_status`/`get_agent_activity` khá nhiều;
- một `wait_for_finish_request` kéo dài khoảng `126s`;
- daemon từng fail notify caller do active run chưa cancel xong.

Khuyến nghị:

1. callback là đường chính;
2. poll một lần chỉ khi Human hỏi “done chưa?” hoặc callback có evidence bị mất;
3. pending permission phải tạo attention/notification riêng;
4. không gửi prompt mới vào Supervisor đang có foreground run;
5. Lead handback phải có terminal state rõ: `DONE`, `BLOCKED_PERMISSION`, `NEEDS_HUMAN_DECISION`, `FAILED`.

## Workspace và state hygiene

Hiện có:

- `18` workspace record trong registry;
- `9` active workspace record;
- `6` cwd unique trong active list;
- nhiều local workspace cùng trỏ một cwd ở `~/Documents` và `keyboard-system`.

Với standalone chat, nhiều workspace cùng cwd không nguy hiểm. Với custom topology, ownership phải dựa vào `workspaceId + parentAgentId + lease`, không chỉ cwd.

Status semantics cũng dễ gây nhầm:

- `list_agents(includeArchived=true)` trả các record cũ là `closed`;
- `get_agent_status` trên một số record đã archive vẫn trả native runtime `idle`;
- `archivedAt` và active-set query mới quyết định agent còn thuộc active topology hay không.

Runbook nên ghi rõ:

```text
active ownership =
  not archived
  AND present in active list
  AND correct workspaceId
  AND correct parentAgentId
  AND lease not superseded
```

Không dùng riêng `idle/running` từ native runtime để suy ra ownership.

## Context và hiệu quả

Lead hiện tại:

- context used khoảng `195,519/258,400`;
- tương đương khoảng `76%`;
- timeline có `660` update;
- nhiều vòng validation, plan, implementation, branch và permission đã dồn vào cùng một seat.

Đây là vùng nên checkpoint/handoff. Không cần thay Lead giữa một atomic commit, nhưng sau khi commit/MR xong nên:

1. ghi checkpoint ngắn;
2. archive Lead hiện tại;
3. tạo Lead mới cho objective tiếp theo nếu còn việc;
4. không kéo một Lead vượt nhiều workstream độc lập.

Ngưỡng vận hành đề xuất:

- cảnh báo ở `60%` context;
- checkpoint bắt buộc ở `70%`;
- replacement sau atomic boundary ở `75–80%`.

## Daemon và provider health

Daemon local vẫn reachable, nhưng log có noise đáng kể:

- relay disconnect/error lặp lại, phần lớn do DNS hoặc stale relay lease;
- nhiều `ws_slow_request`;
- background git fetch/forge self-heal fail;
- auxiliary OpenCode structured generation bị thiếu balance;
- hai lần notification vào Supervisor cũ thất bại do run cancellation chưa acknowledge.

Các lỗi relay không làm local control plane chết, nhưng nếu mobile/remote Supervisor là quan trọng thì cần health check riêng cho relay.

Provider status cũng có discrepancy:

- `paseo daemon status` báo Claude available;
- provider snapshot qua MCP báo Claude enabled nhưng unavailable.

Claude chưa được tính là verified cho tới khi có smoke-test agent thật.

## Security

Điểm tốt:

- `~/.paseo` là `0700`;
- `config.json` và daemon keypair là `0600`;
- docs/snapshot không chứa raw secret;
- engineering patch đã chú ý PII/token boundary.

Điểm cần biết:

- agent persistence JSON có thể chứa per-agent Paseo MCP Authorization header;
- file agent hiện là `0644`, nhưng nằm dưới parent `~/.paseo` `0700`, nên user khác không traverse được theo permission hiện tại;
- backup/sync tool chạy dưới chính user vẫn có thể sao chép token.

Khuyến nghị:

- không đưa `~/.paseo/agents` vào cloud sync;
- rotate/revoke token khi archive;
- nếu Paseo hỗ trợ, lưu token ngoài agent JSON hoặc redacted-at-rest;
- không copy raw agent record vào docs/ticket.

## Việc nên sửa theo thứ tự

### P0 — harden lifecycle permission

- Pending permission phải bật `requiresAttention`.
- Supervisor phải relay `BLOCKED_PERMISSION` ngay.
- Sau quyết định Human, turn phải resume hoặc fail terminal; không để Lead “running” vô hạn.

### P1 — trả staffing authority cho Lead

- Bỏ rule yêu cầu Human phê duyệt mỗi bounded Peer.
- Supervisor chỉ kiểm tra role/provider/workspace/authority, không chọn có spawn Peer hay không.
- Implementation bình thường nên route `impl` sang DeepSeek; difficult/audit sang Luna.

### P1 — enforce routing sau create

- Lead phải là `codex-lead/*`.
- Codex Peer phải là `codex-peer/*`.
- OpenCode implementation phải là `opencode-peer/*`.
- Nếu stock `codex`/`opencode` xuất hiện trong role chain, cancel và báo routing error.

### P1 — chuẩn hóa labels

Mọi seat cần:

```json
{
  "role": "supervisor|lead|peer",
  "objective_id": "...",
  "lease_id": "...",
  "parent_agent_id": "...",
  "route": "planning|impl|impl_deep|search|ui|audit"
}
```

### P2 — giảm churn và polling

- reuse Lead trong cùng objective;
- replacement chỉ ở checkpoint/handoff;
- callback trước, poll khi có lý do;
- archive stub session rỗng sau khi xác nhận không còn ownership.

### P2 — smoke-test các route chưa chạy

Chạy các task nhỏ, không phá hoại:

1. DeepSeek qua `opencode-peer` implement một change cơ học;
2. Luna Low qua `codex-peer` làm codebase search;
3. Luna Max qua `codex-peer` audit;
4. Gemini UI qua `gemini-ui` review một component;
5. GLM 5.2 qua `opencode-peer` làm bounded alternative implementation;
6. Claude chỉ sau khi status discrepancy được giải quyết.

### P2 — tách auxiliary structured generation

- bỏ stock OpenCode model thiếu balance khỏi fallback;
- hoặc nạp credit nếu thực sự muốn dùng;
- không để title/metadata generation tạo phantom turn failure.

### P3 — context budget

- warning/checkpoint theo ngưỡng;
- handoff sau atomic boundary;
- không để một Lead ôm review, implementation, commit, MR và objective tiếp theo vô hạn.

## Mẫu chain nên giữ

```text
Human
  → Supervisor nhận objective và authority
  → Supervisor bind đúng workspace + đúng một Lead
  → Lead chia bounded work
      → DeepSeek Peer: implementation cơ học
      → Luna Peer: search/deep implementation/audit
      → Gemini Peer: UI/design
  → Peer handback hoặc dissent
  → Lead review + validation + acceptance
  → Supervisor chỉ relay decision/status/permission boundary
  → Human quyết định external/destructive/product trade-off
```

Điểm mấu chốt sau audit: **không cần thiết kế lại từ đầu**. Hệ thống đã chứng minh được giá trị. Việc tiếp theo là harden lifecycle và authority boundary, rồi chạy smoke-test đủ các route đã cấu hình.
