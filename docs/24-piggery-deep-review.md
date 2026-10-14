# Piggery: identity, mailbox, topology và recovery

Đọc source ngày 2026-10-14 tại commit
[`c51499299462ac5fe7766de869f2c69d6fd94f64`](https://github.com/sting8k/piggery/tree/c51499299462ac5fe7766de869f2c69d6fd94f64).
Checkout riêng ở `/tmp/piggery-deep-review-20261014`. Changelog đầu file là
v0.10.2. Không cài Piggery, không mở model session hay đổi runtime room-kit.

## Kết luận

Piggery là một runtime mailbox/gate riêng, không phải proxy sửa native callback
của Paseo. Nó tự sở hữu participant identity, process/harness adapters, durable
mail và acknowledgment; topology là dữ liệu manifest. Điểm đáng học nhất cho
room-kit là tách **lưu kết quả**, **đánh thức recipient**, **ack turn**, và
**engineering/Human acceptance** thành các bằng chứng khác nhau.

Room-kit có contract chuyên biệt hơn cho epoch/CAS, writer reservations và
candidate-bound check receipts. Piggery tập trung mạnh hơn vào giao tiếp giữa
harness và delivery/recovery. Không thể thay thế hai control plane bằng cách
đồng nhất ack hoặc team `settled` với task `ACCEPTED`.

## 1. Runtime và ownership

Piggery có daemon Go, SQLite và local socket. Core không branch theo tên harness;
workers đi qua `RuntimeDriver`, interactive sessions qua adapter protocol. State
tables là source of truth, events là audit/lifecycle, không replay events để
dựng lại toàn bộ state. [Design rules](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/AGENTS.md#L42-L66).

DB có `participants`, `messages`, `deliveries`, `batches`; message dedupe dùng
unique `(from_id, client_msg_id)` khi key có mặt. DB mở với WAL, busy timeout và
foreign keys. Các migration mở rộng schema, không sửa schema ban đầu.
[Schema](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/store/schema.sql#L11-L79),
[DB open](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/store/store.go#L106-L123).

Paseo chỉ là một bề mặt quan sát tùy chọn trong README: PigMonitor là companion
plugin bên ngoài hiển thị teams/transcripts/mail. Điều đó không biến Piggery
workers thành native Paseo Peers do room-kit lease quản lý.
[Paseo integration](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/README.md#L99-L114).

## 2. Identity không đến từ lời tự khai của model

Workers có participant ID/token/run ID. Server authenticate token và lấy role,
team, current run từ DB; core từ chối `run.stale`. Connection đã identify giữ run
của connection, không tự chuyển sang run mới nhất chỉ vì token còn hợp lệ.
[Authentication](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/team.go#L199-L256),
[Connection binding](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/server.go#L560-L638),
[Current-run check](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/engine.go#L482-L495).

Session do Human mở có thể authenticate bằng host process. Server lấy socket
peer PID, kiểm tra PID/start time và ancestry hữu hạn; PID reuse không tự được
coi là process cũ. `identify`/`harness.event` của bound worker còn có process
check để nested harness không báo lifecycle thay nó. Không phải mọi token-based
verb đều có ancestry check: ordinary shell verbs chỉ cần token.
[Host/process gate](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/peer.go#L11-L65),
[Worker event gate](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/server.go#L571-L590).

`join.auto` không đòi token; trust boundary của enrollment là socket cùng user
mode 0600. Admin verbs và participant verbs không fallback credential cho nhau.
Đây là local same-user trust, không phải cô lập OS giữa các agent full-access.
[Enrollment/admin split](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/server.go#L465-L483),
[Socket permissions](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/transport_unix.go#L11-L31).

Do identity nằm trong chính runtime/adapter này, Piggery không cần chữa generic
Paseo proxy mất `callerAgentId`. Đây là khác biệt thiết kế, không phải bằng chứng
rằng parent labels đủ thay caller identity.

## 3. Topology được enforce bằng code; semantics chủ yếu trong prompt

Bốn model tools chung là `send`, `inbox`, `who`, `agent`; adapters dùng cùng
schema. Role grant kiểm tra ở core. Spawn còn kiểm tra role tồn tại, `can_spawn`,
depth, concurrency, routing và cwd bounds. Mail kiểm tra visibility/routing;
`op=assign` phải gửi tới member `reports_to` caller. Routing thường kiểm tra
role pair; không nên suy ra mọi mail đều có exact assignment-owner guard.
[Tools](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/extensions/pi/tools.json),
[Role grant](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/roles.go#L108-L132),
[Spawn gates](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/agent.go#L84-L136),
[Send gates](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/mail.go#L149-L233).

| Layout | Human giao tiếp qua | Spawn/mail chính |
|---|---|---|
| `lead-peer` | Lead | Lead spawn Peer; Peer chỉ route mail về Lead |
| `slp` | Supervisor | Supervisor spawn Lead; Lead spawn Peer; S↔L↔P |
| `advisor` | Caller của taskforce | Một advisor, không spawn tiếp; caller đóng taskforce |
| `council`, `dual-lens` | Chair/caller | Các góc nhìn độc lập theo layout |
| `amp-like` | Lead | Lead tự làm, gọi oracle/reviewer khi cần |
| `gastown-like` | Mayor | Workers/worktrees và refinery theo prompt/layout |

Các layout là template files, không cần một engine mới cho từng topology.
Manifest được freeze khi team thành lập; sửa template không đổi team đang chạy.
[Layouts](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/README.md),
[Frozen manifest](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/docs/reference.md#L87-L95).

Điểm khác authority của room-kit: prompt SLP của Piggery yêu cầu Supervisor đọc
diff, chạy checks, accept và merge lane. Trong room-kit, Lead giữ engineering
ownership và Supervisor là governance tùy chọn. Không copy nguyên SLP prompt
mà giữ tên role rồi coi authority đã tương đương.
[Piggery Supervisor](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/prompts/slp/supervisor.md#L19-L26),
[Room-kit workflow](../protocols/WORKFLOW_PROTOCOL.md).

## 4. Đường giao việc → nhận kết quả

```mermaid
sequenceDiagram
    participant L as Lead
    participant D as Piggery DB/Core
    participant A as Peer adapter
    participant P as Peer model
    L->>D: send task / spawn(task)
    D->>D: Gate rồi persist mail
    D-->>A: Wake sau commit
    A->>D: Turn start / pull batch
    D-->>A: Mail + delivery binding
    A->>P: Đưa mail vào turn
    P->>D: send handback, reply_to task
    D-->>L: Wake để đọc handback
    A->>D: Matching turn ended OK
    D->>D: Ack delivery của run/batch
    Note over L,D: Lead xét evidence; ack không phải acceptance
```

`spawn(task)` ghi participant và task mail trước khi gọi driver start.
Peer reuse bằng `send op=assign`; handback/rework nối `reply_to`. Assignment
trong UI theo task mail và reply chain; không phải task acceptance state machine
với candidate-bound check receipts như room-kit.
[Initial task](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/agent.go#L139-L163),
[Assignment contract test](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/assign_test.go#L11-L67).

`send` persist trước khi notify recipient. Stable `client_msg_id`, nếu được cấp,
trả lại original message ID cho repeated sender/key. Key này optional; model
tool schema không có field đó, nên không suy ra mọi send của model tự động có
idempotency. Core không diễn giải free-form `kind`/body để hiểu DONE/PASS.
[Persist/dedupe/wake](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/mail.go#L47-L126),
[Model schema](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/extensions/pi/tools.json#L4-L38).

Ack chỉ ở đúng current-run/batch completion. Mail delivered không tự ack do idle,
retry hay đọc một view. Turn lỗi/ngắt giữ mail chưa ack; next applicable turn có
thể thấy lại. At-least-once processing có thể lặp side effects đã làm trước crash,
nên task nghiệp vụ vẫn cần idempotency/guard riêng.
[Batch completion](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/mail.go#L377-L452),
[Turn outcome](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/harness.go#L282-L332).

Nói chính xác: ack chứng minh adapter báo turn xử lý batch đã kết thúc OK; không
chứng minh model hiểu mail, đã gửi handback, task đạt yêu cầu hay Human accept.
Lead prompt yêu cầu tự xét evidence và trả `rework` nếu cần.
[Lead judgment](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/prompts/lead-peer/lead.md#L17-L28).

## 5. Recovery và những giới hạn cần giữ nguyên khi đánh giá

- Startup `Reconcile` sửa state trước khi serve; không ack và không auto-respawn
  chỉ vì daemon restart. Mail vẫn trong DB. Resume/new mail là trigger khác.
  [Reconcile](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/reconcile.go#L11-L55).
- Gone member có thể được new mail resume thành headless, trong limits và một
  lần mỗi mail; gate/solo/left/closed team có exceptions. Gate không tự hồi sinh
  khi Human session biến mất. Worker crash và owner stop có policy khác nhau.
  [Recovery policy](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/docs/guide.md#L192-L212).
- Permission wait giữ mail. Bù lifecycle thiếu của Claude có local status-file
  watcher mỗi giây; đây không phải hệ thống tuyệt đối không polling. Changelog
  0.10.1 đã sửa interrupt behavior, nhưng một câu trong reference còn mô tả
  đóng turn ở next prompt; khi xung đột ưu tiên code/current changelog.
  [Watcher](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/cli/mcp.go#L135-L154),
  [Changelog](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/CHANGELOG.md#L30-L57),
  [Reference](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/docs/reference.md#L121-L135).
- Reserved `notify` là operator hook sau commit, stored already acked, không có
  inbox/ack/reply. Không gán guarantees của mailbox participant cho hook này.
  [Notify contract](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/notify.go#L9-L20).
- Wake sau commit là best effort: socket push failure chỉ log; không có atomic
  wake receipt/outbox bảo đảm mọi pending message tự đánh thức recipient. Mất
  wake có thể cần reconnect/new turn/new mail/manual resume. Queued turn-end
  evidence khi adapter mất kết nối cũng nằm trong RAM; adapter chết có thể làm
  mail replay dù side effect của turn cũ đã xảy ra.
  [Wake failure](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/server/server.go#L421-L440),
  [Adapter queue](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/extensions/pi/adapter.mjs#L31-L62).
- Có crash window suy ra từ thứ tự code: OS process start trước khi core persist
  process row. Daemon chết giữa hai bước có thể để lại child không có durable
  PID record; `Reconcile` nhánh `no_process` không có PID để verify/kill. Chưa tái
  hiện bằng crash injection, nên đây là inference, không báo lỗi live đã chứng
  minh. Mailbox durability không làm process launch thành atomic.
  [OS start](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/driver/local/runner.go#L301-L358),
  [Record sau start](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/agent.go#L401-L447),
  [No-process decision](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/reconcile.go#L139-L145).
- Late same-run `turn_end` sai prompt key không ack nhầm, nhưng vẫn đóng open
  batch hiện tại và set idle. Test bảo vệ mail còn pending; không chứng minh
  newer batch được giữ mở. Đây là giới hạn hành vi đọc từ code/test, chưa probe
  live race. [End behavior](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/harness.go#L286-L331),
  [Wrong-key test](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/harness_test.go#L75-L87).

## 6. Harness, model và effort

Model/thinking resolution: role override → harness profile → founding ancestor
session khi cùng harness → harness default. Model names không translate giữa
harnesses. Đây là runtime config inheritance; chưa thấy equivalent guard pin
model/thinking của room-kit qua lease v2. Template `inherit` không tạo model
diversity cho council/dual-lens; muốn diversity phải cấu hình rõ.
[Resolver](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/roles.go#L67-L105),
[Dual-lens guidance](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/README.md#L131-L158).

Native tool blacklists hạn chế đường subagent/messaging bên ngoài runtime,
nhưng không tạo OS sandbox. Codex driver mặc định approval never/full access;
Claude bypassPermissions. Advisor read-only là role prompt, không tự biến thành
filesystem read-only vì role thiếu `agent` tool.
[Codex launch](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/driver/local/codex.go#L137-L156),
[Claude launch](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/driver/local/claude.go#L171-L183),
[Advisor template](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/advisor.yaml).

Worktrees do agents tạo; runtime kiểm tra spawn cwd nằm trong root, repo worktrees
hoặc configured allowed roots. Contract không tự reserve path cho mỗi writer.
[Bounds](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/cwd.go#L18-L41),
[Worktree prompt](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/manifests/prompts/lead-peer/lead.md#L4-L16).

## 7. Phần nên học và phần nên giữ ở room-kit

| Hạng mục | Piggery | Room-kit / quyết định kiến trúc đề xuất |
|---|---|---|
| Identity | Participant/token/host + current run | Giữ canonical lease/binding/epoch; không dùng labels làm auth |
| Transport | Durable mailbox + harness adapter | Học persist result trước wake, stable IDs và receipt replay |
| Finish | Ack matching run/batch | Tách callback delivery khỏi task/engineering acceptance |
| Topology | Frozen declarative manifests | L/LP/SLP đã đủ cho hiện tại; thêm layout chỉ khi có use case |
| Assignment | Task mail + reply chain | Giữ DAG, scope reservation, candidate/check receipts |
| Recovery | Unacked replay + bounded revive policy | Reconcile hữu hạn; retry chỉ khi có dedupe/delivery evidence |
| Visibility | `top`, state, unread mail, notices | Có thể thêm queued/delivered/seen/accepted states nếu có evidence |

Đề xuất ưu tiên: nâng transport theo mailbox pattern bên trong control plane
hiện có, thay vì cài thêm runtime tự spawn/resume cạnh Paseo cho cùng một task.
Nếu thử Piggery sau này, dùng task/workspace tách biệt, một runtime sở hữu writer
lifecycle; không cho Piggery và room-kit đồng thời dispatch/resume cùng writer.
Đây là suy luận kiến trúc từ source, không phải migration đã thực hiện.

## 8. Evidence và validation trong lượt này

- Root chạy bốn file Node: pi adapter, pi client, dsh last-step steering,
  opencode records; **15/15 pass**. Không có model calls hoặc daemon thật.
- Background research chạy pure mapping/replay ở pi adapter, opencode bridge,
  dsh bridge; **22/22 pass**. Hai nhóm có overlap, không cộng thành 37 unique.
- Không chạy Go core/race/vet: `go` không có trong PATH; không cài toolchain để
  hoàn thành research. Đã đọc implementation và relevant regression tests.
- Không chạy paid end-to-end; fixture/source proof không chứng minh compatibility
  với các phiên bản harness hay installed setup trên máy này.
- Changelog 0.10.1/0.10.2 liệt kê nhiều mail/interrupt/reconnect race fixes. Đây là
  evidence tác giả đã xử lý các tình huống cụ thể; không đồng nghĩa mọi crash gap
  và exactly-once side effect đã được giải quyết.
  [Regression history](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/CHANGELOG.md#L3-L87),
  [Harness contract fixtures](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/contract_test.go#L13-L22).
