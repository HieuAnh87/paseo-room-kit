# 13 — History và legacy

## Legacy nomenclature

Các upload cũ mô tả:

```text
codex-root
~/.codex/root.config.toml
codex-room root
Root → Peer
```

Đó là thiết kế trước khi role engineering owner được chốt tên Lead. Setup hiện tại dùng:

```text
codex-supervisor → codex-lead → codex-peer/opencode-peer/gemini-ui
```

Không tạo provider `codex-root` mới.

## Legacy provider/config

Backup `config.json.pre-supervisor-<redacted-agent>` là mốc trước khi hoàn thiện Supervisor. Uploaded config cũ còn có `codex-root`, `agy`, Kimi và một số daemon feature khác. Nó chỉ dùng để hiểu migration, không copy trở lại nguyên trạng.

## Legacy agent records

Daemon vẫn giữ closed records để audit. Một số record lịch sử dùng:

- `codex/gpt-5.4`;
- `opencode/openai/gpt-5.6-luna`;
- `opencode/opencode/deepseek-v4-flash-free`;
- `opencode/opencode-go/glm-5.2`.

Đây là history của các phiên trước, không phải route mới trong `orchestration-preferences.json`.

## Trace cũ gpt-5.4

Chuỗi cũ Supervisor → stock Codex Lead → stock Codex Peer được giữ để phân tích nguyên nhân. Không archive/delete chỉ để làm dashboard “sạch”; khi debug routing cần nhìn cả closed records.

## Uploaded material không phải Paseo core

Các file `Shop.dc.html`, `Product.dc.html`, `Cart.dc.html`, `Home.dc.html`, `support.js` trong upload là product/UI artifacts. Chúng không thuộc setup control plane và không được đưa vào bộ tài liệu này ngoài việc ghi nhận inventory.

`message _3_.txt` chứa Test Discipline/HARD CUT Rules cho một project (NOVA), có thể ảnh hưởng engineering behavior nhưng không thay thế room authority protocol. Nó được ghi trong [references/uploaded-materials.md](references/uploaded-materials.md).
