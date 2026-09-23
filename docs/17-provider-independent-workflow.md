# 17 — Workflow và authority độc lập provider

Thay đổi này áp dụng trong source kit; chưa xác nhận bằng session Paseo live. Không thêm lifecycle ledger, không thay provider sang Pi. Paseo giữ identity/session/workspace/parentage/events; proxy và guard dùng chung authority/evidence contracts; repo quyết định tactics; adapter nạp instructions và chuyển tool/report.

Ý tưởng tham chiếu từ [SLP](https://github.com/duongvm57/paseo-slp) và [architecture gốc](https://github.com/duongvm57/pi-paseo-orchestration/blob/main/docs/architecture.md): Lead giữ technical judgment; Supervisor quan sát bằng evidence; role, project protocol và assignment tách biệt. Đây là triển khai trong room-kit, không phải tuyên bố hai repo có cùng API.

## Hai cách bắt đầu

- Human tạo/chọn một root Lead bằng adapter hiện có, bind trực tiếp. Kết quả vào Human decision queue.
- Human chọn root Lead và root Supervisor riêng, bind Supervisor làm observer. Kết quả gửi đúng observer; Lead vẫn không có native parent. Đường Supervisor tạo child Lead cũ vẫn tương thích.

Binding không tạo agent, không reparent, không suy quyền từ tên/provider. Một workspace chỉ có một Lead active/pending. Supervisor không nhận quyền engineering của Lead. Human giữ objective, product trade-off, external effects và authority changes.

## Chuẩn bị tactics trước khi bind

Chạy từ owner shell sau khi cài kit đã cập nhật:

```bash
paseo-room-workflow init /path/to/project
paseo-room-workflow init /path/to/project --apply
```

Lệnh preview mặc định; apply chỉ tạo file còn thiếu. Đọc và sửa `.orchestration/workspace-protocol.md` cho scope, ownership, checks, owner-reserved decisions và cost limits thực tế. `.orchestration/workflow.json` version 1 định nghĩa gates. Mặc định:

| Class | Candidate | Review độc lập | Lead self-work có thể được giao |
|---|---|---|---|
| read_only | không | không | có (inspection) |
| tiny | có | không | có |
| bounded | có | không | không |
| sensitive | có | có | không |
| foundation | có | có | không |

Self-work gate là quyền trong workflow instructions, không phải OS write sandbox. Repo có thể định nghĩa class khác với ba boolean gates tường minh. Omission không cấp quyền. Repo thiếu policy giữ đường legacy và không bật candidate/review gates. Policy lỗi hoặc symlink bị từ chối.

```bash
paseo-room-workflow bind --lead-id LEAD_ID --task-class bounded
paseo-room-workflow bind --lead-id LEAD_ID --task-class bounded --apply
# Nếu cần observer, thêm --supervisor-id SUPERVISOR_ID vào hai lệnh trên.
paseo-room-workflow bindings
paseo-room-workflow decisions
```

Lead đọc `inspect_work_context` và toàn bộ protocol trước dispatch. Dùng topology nhỏ nhất đáp ứng gates, ownership rõ cho từng writer, brief trung lập và câu hỏi có thể thay đổi quyết định. Không buộc mọi task phải có Architect/Reviewer. Peer được yêu cầu report correlation qua initial assignment trên các adapter hiện có.

## Candidate và report

Lead dùng `inspect_work_candidate`; owner có thể dùng `snapshot /path/to/project`. Digest gồm HEAD, staged index, tracked/nonignored untracked files, deletion, mode, symlink target. Không commit hoặc stage. HEAD chưa có commit được hỗ trợ. Ignored artifacts không nằm trong proof; submodules bị từ chối và cần phạm vi riêng. Pause writers khi snapshot/review; đây không phải atomic filesystem snapshot.

Report JSON version 1 có `reportId`, `peerAgentId`, `parentLeadId`, `workspaceId`, `workEpoch`, `assignmentId`, `kind`, `payload.evidence`. REVIEW thêm `payload.candidateDigest` và `verdict=APPROVE|FINDINGS`. Guard tạo assignment identity; disposition và write_mode không được đổi sau dispatch. Engineer không được chuyển nhãn thành Reviewer để approve chính assignment đó. Lead ghi `record_peer_report` trước archive Peer. Report correlation, receipt dedup và verdict được lưu trong lease hiện có.

Gates review yêu cầu Reviewer approve đúng candidate và không còn findings cho candidate đó. Report là evidence do Lead cung cấp để kiểm tra, không phải chứng minh cryptographic rằng một test đã chạy hoặc bảo đảm reviewer reasoning độc lập. Lead vẫn phải đọc checks, uncertainty và counterevidence. Tests không được tự định nghĩa API chưa có quyết định.

Lead gọi `submit_work_result` với message và candidateDigest khi gated. Proxy kiểm tra lại lúc handback, Human ACCEPTED và archive accepted result. Thay đổi file làm proof cũ không còn dùng được. Acceptance của Human, technical judgment và delivery receipt là các sự kiện khác nhau.

## Human decisions và drift

`decide`, `reopen`, `resolve`, `archive` nhận file JSON với arguments của protected operations trong [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md), preview mặc định; `--apply` thực thi. Epoch/revision/evidenceDigest/correlation phải lấy từ queue hiện tại. Chỉ accept sau khi xem evidence. Bounded follow-up dùng reopen; delivery không chắc chắn phải resolve trước, không tự retry.

Provider/model/settings, placement và bytes của protocol/policy được pin vào binding. Đây là metadata từ record Paseo, không phải live attestation của model đang chạy. Drift yêu cầu checkpoint và replacement rõ ràng; Lead/Supervisor không tự rebind. Human có thể withdrawal sau khi descendants đã settled:

```json
{
  "agentId": "LEAD_ID",
  "expectedWorkEpoch": 1,
  "expectedRevision": 1,
  "settlementEvidence": "Checkpoint saved; all descendants settled; owner withdraws old authority."
}
```

Lấy version thực tế từ `bindings`, ghi request file rồi chạy `withdraw REQUEST.json`, sau đó `--apply`. Unarchived descendants và uncertain delivery chặn withdrawal. Withdrawal không kill/archive runtime, không accept kết quả. Bind lại cùng root Lead tăng epoch; proof cũ không được mang sang. Với child Lead legacy, checkpoint/archive/replacement đi theo đường supervised hiện có.

## Cài đặt và giới hạn hiện tại

Installer cài proxy, CLI và module chung cùng nhau; doctor kiểm tra source và installed copies. Không restart daemon tự động. Gói public chứa cùng enforcement code và tests. Routing provider/catalog hiện có vẫn được giữ; chưa có repository-specific routing pools. Role shells không được chạy owner CLI control, nhưng đây là cooperative isolation và không thay OS authentication hoặc permissions.
