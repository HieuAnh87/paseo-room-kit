# L / LP / SLP và callback

Mode được chọn khi Human bind **task mới**, không đổi topology của lease đang
chạy. Giữ model và effort đã chọn; số tầng orchestration không quyết định effort.

| Mode | Authority | Dùng khi |
| --- | --- | --- |
| L | Human → Lead | Việc tiny/read-only, policy cho Lead tự làm, không cần review độc lập |
| LP | Human → Lead → Peer | Mặc định cho việc bounded cần delegation |
| SLP | Human → Supervisor → Lead → Peer | Cần governance riêng, nhiều workstream hoặc lifecycle phức tạp |

Owner shell, ngoài managed role:

```sh
paseo-room-workflow bind --lead-id UUID --mode L
paseo-room-workflow bind --lead-id UUID --mode LP
paseo-room-workflow bind --lead-id UUID --mode SLP --supervisor-id UUID
```

L mặc định task class `tiny`, LP/SLP mặc định `bounded`. Có thể dùng
`--task-class read_only` cho L. Các lệnh trên preview; thêm `--apply` để bind.
Không có `--mode`: có Supervisor thì SLP, không có thì LP, tương thích lệnh cũ.
L bị từ chối nếu policy yêu cầu delegation/review; proxy và role hook cùng chặn
Peer dispatch. Muốn đổi mode cần kết thúc/withdraw binding và tạo task/binding
mới qua checkpoint Human. Supervisor tạo Lead vẫn là luồng SLP hiện có, không
biến thành LP ngầm.

## Callback transport

Room-kit chủ động tắt native catalog bằng hai lớp cấu hình:
`daemon.mcp.injectIntoAgents=false` và
`agents.providers.<id>.paseoTools.enabled=false` cho các internal role providers.
Supervisor/Lead nhận lại tool quản lý qua proxy có role filter và lease guard;
Peer không nhận control MCP. Theo code bundled Paseo 0.11.2, global injection
tắt làm session mới nhận tool policy disabled; policy riêng của provider cũng
có thể tắt catalog. Caller-scoped MCP áp dụng policy của session đó, nên catalog
của các Lead hiện tại bị lọc hết tool quản lý. Đây là hệ quả cấu hình room-kit.

Top-level fallback vẫn có tool, giữ parent labels nhưng không giữ native caller
identity, vì vậy không arm callback native. Chỉ bật global injection chưa đủ để
khôi phục native callback cho role providers đang có policy disabled; đổi
provider policy và refresh session cần được đánh giá cùng proxy/guard. Hiện
relay giải quyết finish notification trong khi giữ nguyên hai lớp cấu hình.
Xem [Paseo MCP reference](https://paseo.sh/docs/mcp#limit-paseo-tools-by-provider).

Plugin [room-callback](../callback-plugin/OVERVIEW.md) dùng lifecycle hook chính
thức. Proxy chọn native scoped callback nếu có, hoặc relay đã healthy cho Peer
mới. Nếu cả hai không sẵn sàng, dispatch bị chặn **trước** reservation/network
mutation. Relay chỉ gửi thông báo về Lead theo canonical assignment/epoch,
`notifyOnFinish=false`, và ghi transport receipt vào lease. Không tự accept,
settle hay thay Human decision. Lead → Supervisor vẫn dùng `submit_work_result`.

`paseo-room-workflow asks --lead-id UUID` hiển thị callback attention.
`UNCERTAIN` cần Human kiểm tra; không retry tự động. `NEEDS_LEAD_DECISION` nói rõ
turn kết thúc nhưng thiếu handback hiện tại, không suy ra DONE từ idle. Restart
plugin có một lần reconcile hữu hạn; hook best-effort không bảo đảm replay mọi
event bị mất. Không polling tiến độ và không thay thế engineering acceptance.

Validation: fixture offline cho mode, binding drift, epoch/assignment, stale
DONE, concurrent dedupe, timeout/no retry, transport selection và lifecycle
hook. Kiểm tra plugin running và heartbeat trên daemon thật không phải paid E2E
Peer → Lead. Probe trước đó vẫn là FAIL lịch sử; không relabel thành PASS.

## Outbox v2 cho binding mới

Binding mới có `callback_outbox_version=2`. Binding cũ giữ relay v1 đến khi
withdraw và bind mới ở checkpoint: proxy dài hạn của Lead cũ có thể vẫn dùng
code cũ, nên không nâng cấp lease đang chạy bằng cách sửa JSON.

V2 lưu nguyên handback (tối đa 64 KiB), identity Lead/Peer, epoch, assignment,
activity counter và digest trước khi gửi. Message ID cố định theo
Peer/epoch/assignment/activity counter; retry dùng lại ID và payload đó.
Đây là chống trùng tại outbox; Paseo chưa có recipient idempotency receipt cho
API này nên không tuyên bố exactly-once delivery.

`READY → SENDING → DELIVERED | REJECTED | UNCERTAIN`. `READY` có thể được gửi từ
payload đã lưu khi reconcile, không cần đọc lại timeline. Authority hết hiệu lực
thì `CANCELLED`. Process lock theo Peer ngăn hai sender đồng thời. Trong lúc gửi,
registry không giữ global lock; reservation `SENDING` chặn thay đổi đúng lease đó
ở cả proxy và role guard. Lease khác vẫn đọc/ghi được.

Nếu sender chết ở `SENDING`, process lock được OS thả; lần reconcile sau đánh dấu
`UNCERTAIN`, kể cả khi chưa biết request đã tới daemon hay chưa. Payload và ID
vẫn còn. Receipt v1 không được tự hydrate hoặc replay. Receipt không accept task.

Owner đọc nội dung và CAS hiện tại:

```sh
paseo-room-workflow callback-outbox --lead-id UUID
```

Owner tạo request JSON với `leadAgentId`, `messageId`, `expectedWorkEpoch`,
`expectedRevision`, `resolution` và `evidence`, rồi preview/apply:

```sh
paseo-room-workflow resolve-callback /absolute/path/to/request.json
paseo-room-workflow resolve-callback /absolute/path/to/request.json --apply
```

`DELIVERED` hoặc `NOT_DELIVERED` chỉ giải quyết một receipt `UNCERTAIN`/`SENDING`
sau khi xác minh phía nhận; từ chối nếu sender còn sống. `NOT_DELIVERED` chuyển
sang `REJECTED`, chưa gửi lại. Muốn gửi lại cần request `RETRY` riêng, CAS mới,
evidence và assignment vẫn hiện hành; chỉ receipt v2 `REJECTED` được retry.
Lifecycle hook vẫn best effort, startup sweep hữu hạn, chưa có guaranteed wake
cho mọi event bị mất. Outbox bảo vệ handback đã capture, không thay thế event log.

### Kết quả thử ngày 2026-10-14

Gate offline: 177 repository tests (24 callback), 54 role-guard tests, 2 plugin
tests và plugin typecheck pass. Callback fixtures có process exit thật sau
network send, crash trước send, READY resume từ payload cũ, duplicate/concurrent
delivery, stale epoch/assignment, payload corruption, Human resolution/CAS,
legacy binding và khóa không chặn lease khác.

Một LP mới chạy trên fixture riêng với Lead GPT-6.1-Sol/High và đúng một Peer
GPT-6-Luna/High. Outbox lưu một payload v2, tự giao đúng Lead, receipt DELIVERED
với zero transport retries. Lần chạy nghiêm ngặt đầu bị BLOCKED ở report schema:
Peer trả evidence dạng array thay vì string. Đã làm rõ prompt schema; cùng Lead
được một follow-up chuẩn hóa evidence đã nhận, không gọi lại hay tạo thêm Peer.
Sau đó check cố định PASSED (exit 0, candidate ổn định), task ACCEPTED, Peer
archived và final handback HANDBACK_READY. Đây là engineering acceptance sau
report normalization; không phải Human acceptance hoặc strict first-run E2E PASS.
Fixture tracked không thay đổi; tooling tạo metadata `.serena` chưa tracked.
Binding/session smoke đã đóng; các lease trước đó không được nâng cấp.
