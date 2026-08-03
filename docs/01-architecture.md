# 01 — Kiến trúc tổng thể

## Mô hình điều khiển

```text
Human
  │ objective, accepted decisions, product trade-offs, final authority
  ▼
Paseo UI / current human-facing channel
  ▼
Supervisor
  │ front door, relay, lifecycle, governance/portfolio observation
  ▼
Lead
  │ sole engineering owner in one workspace
  ├── Peer: bounded implementation/research/search/review/UI work
  └── Peer: optional second opinion or counterevidence
```

Paseo daemon là control plane của agent lifecycle. Các CLI bên dưới là execution plane:

```text
Paseo daemon
  ├── codex-supervisor → codex-room supervisor → Codex runtime
  ├── codex-lead       → codex-room lead       → Codex runtime
  ├── codex-peer       → codex-room peer       → Codex runtime
  ├── opencode-peer    → opencode-paseo-peer   → OpenCode ACP
  └── gemini-ui        → antigravity-acp       → agy/Antigravity CLI
```

## Ba lớp cần phân biệt

### 1. Human/governance layer

Human đặt objective, quyết định product trade-off, accepted decisions, authority boundary và các thay đổi protocol/topology có tính chính sách.

### 2. Engineering layer

Lead phân rã engineering, chọn cách làm trong accepted decisions, giao bounded work cho Peer, đánh giá evidence và chấp nhận engineering result.

### 3. Execution layer

Peer thực hiện hoặc kiểm tra một assignment cụ thể. Peer không tạo Lead, không staff thêm người, không tự chọn product architecture và không acceptance toàn bộ result.

## Provider boundary

Paseo không phải model gateway. Nó launch và quản lý các external CLI/provider. Vì vậy:

- provider ID quyết định executable/profile;
- model ID quyết định model bên trong provider;
- `thinkingOptionId`/effort quyết định mức reasoning khi provider hỗ trợ;
- parent-child agent relation quyết định ownership/lifecycle;
- `workspaceId`/cwd quyết định placement, không thay đổi parentage.

Một agent có thể được đặt trong workspace khác nhưng vẫn là child của agent tạo nó. Vì vậy phải kiểm tra cả `ParentAgentId` và `Cwd`.

## Nguồn dữ liệu theo tầng

```text
~/.paseo/config.json
  ├── daemon settings
  ├── custom provider registry
  └── Paseo MCP injection policy

~/.paseo/orchestration-preferences.json
  └── semantic routing: impl/ui/research/planning/audit + custom routes

~/.codex/config.toml
  └── Codex baseline: MCP, trusted projects, features, plugins, defaults

~/.codex/{supervisor,lead,peer}.config.toml
  └── role overlay: model, permissions, developer instructions

~/.local/bin/codex-room*
  └── materialize role runtime and exec external Codex

~/.config/room-workflow/
  └── shared protocol, authority and durable governance notes
```

## Invariant cốt lõi

1. Một workspace chỉ có một engineering owner khỏe mạnh tại một thời điểm.
2. Supervisor không trở thành Lead thứ hai.
3. Lead không được tạo một Lead khác.
4. Peer không dispatch hoặc route agent.
5. Không tạo internal Lead/Peer bằng stock provider nếu custom provider tương ứng đã được cấu hình.
6. Finish/error/permission notification là attention event, không phải acceptance.
7. Dissent phải đóng bằng một outcome bounded, không có debate vô hạn.
8. Mọi identity-sensitive operation phải đọc lại agent ID và provider hiện tại trước khi viết.
