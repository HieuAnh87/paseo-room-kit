# Các repo khác xử lý tool, identity và callback thế nào?

Đối chiếu source ngày 2026-10-14, theo GitHub HEAD xác minh trong lượt này.
Đọc source không chứng minh setup của tác giả đã chạy thành công trên daemon,
provider hoặc session của máy này. Không chạy agent/model probe, đổi cấu hình
hay restart daemon. Các link dưới đây pin commit để kết luận có thể kiểm tra lại.

## Kết luận cho room-kit

Các repo dùng những cơ chế khác nhau: native tools cho role phù hợp; bridge có
identity riêng; observer nhận lifecycle event; mailbox có acknowledgment; hoặc
heartbeat/native wait để thu kết quả. Không có source được kiểm tra nào chứng
minh generic proxy có thể bỏ native `callerAgentId` mà vẫn arm native callback.

Room-kit hiện tắt cả global injection và catalog của internal role providers,
cấp tool qua proxy/lease guard, rồi dùng relay cho Peer → Lead. Relay này gần
observer pattern của Hoang; không tương đương durable explicit-result runtime
của Cuong. Xem [hợp đồng hiện tại](22-modes-and-callback.md#callback-transport).

Khuyến nghị kiến trúc, chưa phải thay đổi được thực hiện:

1. Giữ một đường chính cho finish notification của mỗi assignment, tránh cùng
   một kết quả đánh thức Lead từ cả relay lẫn native callback.
2. Nếu cần phục hồi chắc hơn qua restart, học Cuong: persist báo cáo/receipt
   trước khi notify; notify failure không làm mất hay phủ nhận báo cáo đã lưu.
   Retry notification cần stable ID và kiểm tra delivery evidence; không retry
   mù một send đang `UNCERTAIN` của room-kit.
3. Native tools là phương án đơn giản hơn về transport, nhưng chỉ dùng khi
   preserve caller context và vẫn enforce lease/epoch/target authorization.
   Chỉ bật injection không đủ chứng minh điều này. Cần kiểm tra với session mới
   sau khi sửa exact-provider policy; không bypass proxy guard để chữa callback.

Các điểm trên là suy luận từ so sánh source, không phải kết quả E2E mới.

## Các cơ chế cụ thể

### Native catalog và callback

- **hoangnb24/codex-room-setup:** global `injectIntoAgents=true`; exact Lead và
  Supervisor `paseoTools.enabled=true`, Peer opt out. Cách này giữ native control
  path cho các role chủ quản. Nó khác cấu hình room-kit hiện tắt cả hai lớp.
  [Config](https://github.com/hoangnb24/codex-room-setup/blob/91141ea1d4b060284725d0ad538855c2894f1160/home/.paseo/config.json.template#L3-L77),
  [Lead/Peer policy và cảnh báo defaults](https://github.com/hoangnb24/codex-room-setup/blob/91141ea1d4b060284725d0ad538855c2894f1160/paseo/notes/mcp-injection.md#L1-L12).
- **duongvm57/pi-paseo-orchestration:** Lead dispatch phải có
  `notifyOnFinish=true`, bind exact parent Lead/model route; Peer có tool riêng
  `peer_lead_message`. Runtime gửi message envelope bằng `paseo send`, recipient
  đọc lại sender parent/provider trước khi nhận. Native finish và message riêng
  là các loại giao tiếp khác nhau; inspected message path không phải durable
  transactional outbox. [Dispatch validator](https://github.com/duongvm57/pi-paseo-orchestration/blob/c21328b286660e7b189b01636321f382842397c7/extensions/pi-paseo-orchestration.ts#L701-L741),
  [Peer message transport/validation](https://github.com/duongvm57/pi-paseo-orchestration/blob/c21328b286660e7b189b01636321f382842397c7/extensions/pi-paseo-orchestration.ts#L4850-L4900).
- **Minnyat/paseo-team-orchestration:** example bật global injection; Pi extension
  áp role allowlist bằng `setActiveTools`, kiểm tra tiếp ở `tool_call`. Đây là
  agent-extension guard, không tự chứng minh native callback delivery hay độ bền
  khi restart. [Config](https://github.com/Minnyat/paseo-team-orchestration/blob/1a8fbb642ece4e8b5efe46d2b58e4ace89f19a1b/config/paseo.providers.example.json#L1-L34),
  [Tool filtering](https://github.com/Minnyat/paseo-team-orchestration/blob/1a8fbb642ece4e8b5efe46d2b58e4ace89f19a1b/extensions/paseo-team-policy.ts#L550-L575),
  [Call guard](https://github.com/Minnyat/paseo-team-orchestration/blob/1a8fbb642ece4e8b5efe46d2b58e4ace89f19a1b/extensions/paseo-team-policy.ts#L703-L745).

### Observer hoặc bridge ở phía daemon/plugin

- **hoangnb24/paseo-supervision:** observer subscribe lifecycle, capture rồi
  xử lý qua queue riêng; SDK gửi alert tới Supervisor. Dedupe/case là in-memory;
  mark-before-send và không retry send mơ hồ để tránh duplicate. Đây là alert
  observer, không phải replacement bảo đảm mọi Peer handback được chuyển tới
  Lead. [Registration](https://github.com/hoangnb24/paseo-supervision/blob/1bad19b8ee6c58482494f56a3d8c6edb4f969ee1/server/observer.ts#L417-L425),
  [State](https://github.com/hoangnb24/paseo-supervision/blob/1bad19b8ee6c58482494f56a3d8c6edb4f969ee1/server/observer.ts#L45-L65),
  [Ambiguous-send policy](https://github.com/hoangnb24/paseo-supervision/blob/1bad19b8ee6c58482494f56a3d8c6edb4f969ee1/server/observer.ts#L378-L392).
- **cuongntr/paseo-room:** base setup cho native tools ở Lead/Supervisor, Peer
  off; opt-in runtime thêm riêng assignment-scoped `ask`/`handoff`. Bridge dùng
  correlation và generation capability ẩn, không forward generic native calls.
  Reports persist trước notify, identical retry replay receipt. Turn cuối thiếu
  explicit report bị block/uncertain, không suy ra success từ prose/idle.
  Owner notices persist stable IDs, inspect recipient timeline và retry qua
  recovery/idle/permission events. Đây là at-least-once delivery; không bảo đảm
  exactly once. [Bridge identity](https://github.com/cuongntr/paseo-room/blob/67d28ff219efd3ceddc7c30c6cb08910c883eb3c/src/runtime-plugin/server/bridge/bridge.mjs#L1-L8),
  [Persist report trước notify](https://github.com/cuongntr/paseo-room/blob/67d28ff219efd3ceddc7c30c6cb08910c883eb3c/src/runtime-plugin/server/handlers/peer.ts#L129-L205),
  [Missing report](https://github.com/cuongntr/paseo-room/blob/67d28ff219efd3ceddc7c30c6cb08910c883eb3c/src/runtime-plugin/server/handlers/turns.ts#L89-L117),
  [Notice delivery](https://github.com/cuongntr/paseo-room/blob/67d28ff219efd3ceddc7c30c6cb08910c883eb3c/src/runtime-plugin/server/notices.ts#L1-L20),
  [Recovery](https://github.com/cuongntr/paseo-room/blob/67d28ff219efd3ceddc7c30c6cb08910c883eb3c/src/runtime-plugin/server/recovery.ts#L54-L114).
- **duongvm57/paseo-slp-plugin:** desk bridge cấp stdio MCP qua create hook,
  kết nối Unix socket bằng minted handle; server resolve handle → membership →
  agent ID và kiểm tra epoch/live SDK identity ở mỗi dispatch. Lifecycle event
  chỉ reconcile positively correlated send: matching agent/membership và exact
  message ID; không tự granting authority hoặc acceptance. Đây là bridge có
  identity riêng, không phải giữ native identity bằng parent labels.
  [Trust model](https://github.com/duongvm57/paseo-slp-plugin/blob/5a77b5854b62601842969eea23915ab5fd5526b2/plugin/server/desk-bridge.ts#L1-L24),
  [Turn reconciliation](https://github.com/duongvm57/paseo-slp-plugin/blob/5a77b5854b62601842969eea23915ab5fd5526b2/plugin/server/desk-bridge.ts#L1233-L1288).
- **webplode/paseo-slp:** plugin định nghĩa role allowlists; daemon intersect
  ceiling này với host/provider policy. Peer không có control tool; Lead có
  dispatch, Supervisor có observation/send. Attention trigger dùng lifecycle
  event và SDK wake Watcher/Supervisor; không nên gọi attention alert là toàn bộ
  completion transport. [Allowlists](https://github.com/webplode/paseo-slp/blob/29ff5e6a8d3972dfc8150a2d90602550d26f7cd3/slp/plugin/server/configure-role.ts#L198-L246),
  [Attention hook](https://github.com/webplode/paseo-slp/blob/29ff5e6a8d3972dfc8150a2d90602550d26f7cd3/slp/plugin/server/attention-trigger.ts#L363-L391).

### Durable delivery trong runtime riêng hoặc daemon fork

- **webplode/paseo-doctrine-downstream:** sửa ở daemon: coordination signals và
  finish notifications dùng pending queue trên persisted agent record, shared
  per-record serialization, deliver ở idle boundary, bounded retry, resume khi
  restart. Code nói rõ dispatched không chứng minh recipient đã đọc/accept.
  Transport throw/crash vẫn không cho unconditional exactly-once guarantee.
  Đây là downstream implementation, không mặc định có trên upstream 0.11.2.
  [Delivery contract](https://github.com/webplode/paseo-doctrine-downstream/blob/20b717f0c6101ff7ea07a6a7d963cfacb09097b1/packages/server/src/server/agent/coordinated-delivery.ts#L6-L18),
  [Retry và restart resume](https://github.com/webplode/paseo-doctrine-downstream/blob/20b717f0c6101ff7ea07a6a7d963cfacb09097b1/packages/server/src/server/agent/coordinated-delivery.ts#L238-L292).
- **sting8k/piggery:** Go/SQLite runtime riêng. Inbox ghi delivery gắn current
  run/batch; completion đóng batch và ack đúng các delivery còn mở của caller.
  Message chỉ được ack một lần dù batch khác đã ack trước. Đây là durable team
  mailbox/turn acknowledgment, không phải Jira-style Paseo plugin hay native
  finish callback fix. Kênh reserved `notify` riêng lại là post-commit hook,
  không có inbox/ack, nên không gán bảo đảm mailbox cho nó.
  [Inbox](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/mail.go#L269-L332),
  [Completion/ack](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/mail.go#L377-L452),
  [Notify boundary](https://github.com/sting8k/piggery/blob/c51499299462ac5fe7766de869f2c69d6fd94f64/internal/core/notify.go#L9-L20).

### Thu kết quả và recovery bằng heartbeat/wait

- **hanh9898/matt-with-paseo:** detect plugin/version để chọn message path;
  message path `notifyOnFinish=false`, heartbeat fallback `true`. Khi orchestrator
  session thay thế, callback cũ vẫn về spawning session; heartbeat bù tới khi
  re-arm bằng prompt mới. ADR ghi chưa test plugin thật cho quyết định này.
  Đây là contract của skills; không kiểm tra source của external event plugin.
  [ADR](https://github.com/hanh9898/matt-with-paseo/blob/18ed60b34215acd44bba3db16c5d50d40e7e94f5/docs/adr/0012-supervise-from-the-plugins-messages-with-the-heartbeat-as-fallback.md#L7-L25),
  [Session recovery](https://github.com/hanh9898/matt-with-paseo/blob/18ed60b34215acd44bba3db16c5d50d40e7e94f5/plugins/matt-with-paseo/skills/matt-with-paseo-streams/HEARTBEAT-PATH.md#L20-L43).
- **duchm1606/paseo-room:** CLI `paseo wait`, rồi logs; restart làm wait chết thì
  inspect/resume/re-arm một wait. Claude Stop hook chọn Supervisor/transcript
  theo heuristic, swallow send error, không durable receipt/outbox trong hook.
  [Wait/recovery](https://github.com/duchm1606/paseo-room/blob/5b8dfe1a87be3cccc3e317d74a15bc1423e3b46e/protocol/lead-operations.md#L17-L58),
  [Stop hook](https://github.com/duchm1606/paseo-room/blob/5b8dfe1a87be3cccc3e317d74a15bc1423e3b46e/hooks/notify-on-stop.sh#L1-L47).
- **duongvm57/herdr-orchestrator-skill:** native Herdr wait/read rồi active Lead
  validate structured handback có exact assignment ID. Source nói detached Lead
  không tự được wake; không làm notification subsystem riêng trong helper.
  Đây là Herdr transport, không chứng minh compatibility callback Paseo.
  [Peer lifecycle](https://github.com/duongvm57/herdr-orchestrator-skill/blob/a76775859e1aa188909508c4cc371f3338ff3ec5/skills/herdr-orchestrator/references/lead/peer-lifecycle.md#L21-L47).

## Phạm vi và giới hạn

12 repo trên đã kiểm tra HEAD và các đường source liên quan. Không chạy test
suite của các repo bên ngoài. Các claim về production/live setup của tác giả
vẫn chưa kiểm chứng. `sting8k/paseo-mascot` không được dùng làm evidence cho
control/callback; `linhban150612/epistex` không có source accessible trong audit
trước và không được đưa vào kết luận hiện tại. Không coi policy/provider/tool
catalog khác nhau là tương thích mặc định giữa các phiên bản.
