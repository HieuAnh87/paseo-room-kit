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
