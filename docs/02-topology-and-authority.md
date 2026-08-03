# 02 — Topology và authority

## Luồng đúng

```text
Human đặt objective
  → Supervisor nhận và relay
  → Supervisor bootstrap/giữ đúng một Lead cho workspace
  → Lead điều phối engineering
  → Peer làm/review bounded work
  → Peer handback evidence + counterevidence
  → Lead quyết định engineering outcome
  → Supervisor quan sát governance/lifecycle và báo lại Human
```

## Ma trận quyền hạn

| Role | Được làm | Không được làm |
|---|---|---|
| Human | đặt objective; accepted decisions; product trade-off; final authority; authorize replacement/protocol change | không cần tự quản Lead/Peer trong vận hành thường ngày |
| Supervisor | front door; relay; bootstrap một Lead/workspace; quan sát health, ownership, lifecycle, dissent process; advice hẹp cho Lead; thực hiện operation explicit từ Human | không chia task, chọn Peer, chọn architecture/product trade-off, viết/review code, accept engineering result, micromanage heartbeat |
| Lead | engineering owner; decomposition; staffing bounded Peer; chọn engineering approach; validate; accept engineering result; đóng dissent | không tạo Lead; không biến Peer thành owner; không điều khiển Supervisor; không tự quyết vấn đề vượt Human authority |
| Peer | thực hiện bounded task; search/research/implement/review; trả evidence, uncertainty, counterevidence; handback dissent | không dispatch; không tạo agent; không route staff; không chọn product architecture; không accept toàn bộ engineering result |

## Supervisor là cửa trước

Human chỉ nên giao tiếp với Supervisor. Supervisor relay objective/decision/constraint/reporting contract cho Lead. Lead và Peer không cần biết provider, implementation hoặc MCP control channel của Supervisor.

Đây là interface isolation:

- profile/prompt không đưa topology control vào nội dung engineering;
- Supervisor không tự xưng hay tự tiết lộ là Paseo;
- Lead chỉ nhận owner/governance content cần thiết;
- Peer chỉ nhận bounded brief từ Lead.

Đây không phải secrecy tuyệt đối. Process, filesystem, daemon log hoặc admin access vẫn có thể làm lộ topology.

## Ownership lease và replacement

Khi Lead cần thay thế:

```text
Human authorize replacement
  → checkpoint decisions/ownership
  → handoff
  → revoke/close Lead cũ
  → activate Lead mới
  → reconcile workspace
```

Không để hai Lead cùng điều hành một workspace. Stock `codex/...` Lead cũ được coi là legacy/misrouted: giữ history để audit, không gửi objective mới, và phải handoff/replacement rõ ràng trước khi khởi động owner mới.

## Dấu hiệu vi phạm topology

- Supervisor tự chọn implementation task hoặc review code.
- Lead giao routine work trực tiếp cho nhiều Peer cùng lúc mà không có ownership boundary.
- Peer tự tạo Peer/Lead hoặc gọi native team orchestration.
- Agent có tên đúng nhưng provider là stock `codex/...`.
- Cùng workspace có hai Lead active.
- Dissent bị coi là veto hoặc bị bỏ qua không có evidence.
- Human bị đẩy xuống nói chuyện trực tiếp với Lead chỉ vì Supervisor relay không hoạt động.
