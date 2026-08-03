# 05 — Dissent, counterevidence và heartbeat

## Dissent là gì?

Dissent là một evidence-bearing disagreement giữa Lead và Peer, không phải lỗi giao tiếp và không phải cơ chế bỏ phiếu.

Peer không được silently đổi direction. Lead không được silently suppress material counterevidence.

## Structured handback bắt buộc

Khi Peer không đồng ý direction hiện tại, handback phải có:

| Trường | Nội dung |
|---|---|
| `Current direction` | hướng đang được thực hiện |
| `Claim` | điểm Peer cho là sai/rủi ro |
| `Evidence` | code reference, test, log, experiment hoặc fact quan sát được |
| `Counterevidence` | fact làm yếu claim hoặc phần chưa chắc |
| `Risk` | hậu quả nếu giữ direction hiện tại |
| `Requested resolution` | quyết định hoặc verification nhỏ nhất cần Lead làm |

Peer dừng trước irreversible choice nếu authority không rõ và handback về Lead.

## Lead đóng dissent bằng đúng một outcome

### `RESOLVED_BY_LEAD`

Vấn đề nằm trong engineering authority. Lead ghi rationale/evidence, trả next action cho Peer.

### `NEEDS_MORE_EVIDENCE`

Chỉ cho phép một bounded verification/rebuttal round. Sau round đó Lead phải đóng tiếp, không mở debate vô hạn.

### `ESCALATED_TO_HUMAN`

Vấn đề vượt engineering authority: objective, accepted decision, product trade-off, authority, ownership hoặc irreversible risk.

Supervisor chỉ kiểm tra process có tôn trọng evidence và authority hay không; Supervisor không phán technical content.

## Dissent lifecycle

```text
Peer nhận direction
  → Peer phát hiện claim/risk
  → Peer handback structured evidence
  → Lead so sánh evidence + counterevidence
  → Lead chọn một outcome
  → Lead gửi outcome + next action về Peer
  → Peer tiếp tục hoặc dừng theo outcome
```

## Heartbeat không thay dissent

Heartbeat chỉ tạo nhịp kiểm tra/nhắc việc. Nó không được dùng để:

- override Lead;
- gọi trực tiếp Peer để bypass Lead;
- biến Supervisor thành project manager;
- coi agent còn sống là đang tiến đúng;
- thay cho handback có evidence.

Nếu cần giám sát, Supervisor xem structured state, recent bounded activity và ownership; không poll transcript vô hạn.

## Các lỗi dễ gặp

- “Peer nói khác nên phải vote”: sai, không có majority vote.
- “Supervisor thấy dissent nên tự chốt”: sai, Supervisor không có technical acceptance authority.
- “Lead im lặng nghĩa là resolved”: sai, phải có outcome rõ.
- “Peer đã xong task nghĩa là engineering result accepted”: sai, Lead vẫn là người acceptance.
