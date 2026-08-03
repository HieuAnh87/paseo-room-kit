# Uploaded materials và cách xử lý

## Đã dùng để reconstruct setup

| File | Nội dung | Trạng thái |
|---|---|---|
| `message _1_.txt` | giải thích `codex-room` bản cũ dùng `root` | historical; đã chuyển thành Lead |
| `message _2_.txt` | Supervisor profile cũ, còn gọi engineering owner là Root | historical; đã thay bằng Supervisor/Lead contract hiện tại |
| `message _3_.txt` | Test Discipline/NOVA hard-cut rules | project-specific; không thay thế Paseo room law |
| `model-instructions.md` | global Codex communication/operation instructions | shared source hiện tại |
| `codex-room` | launcher shell script reference | đối chiếu với `~/.local/bin/codex-room` |
| `codex-room-sync` | runtime materializer reference | đối chiếu với `~/.local/bin/codex-room-sync` |
| `config.json` | Paseo config cũ có `codex-root`, `agy`, Kimi | historical; không phải source hiện tại |
| `models_cache.json` | model cache cũ | chỉ dùng metadata/count, không chép nguyên file |

## Không đưa vào nội dung core

Các artifact sau được upload nhưng không phải Paseo control-plane setup:

- `Home.dc.html`;
- `Shop.dc.html`;
- `Product.dc.html`;
- `Cart.dc.html`;
- `support.js`.

Chúng được giữ nguyên ở upload location, không copy vào docs để tránh trộn product artifact với orchestration design.

## Lưu ý về khác biệt old/current

Các file cũ có thể nói `root`, `/root/.local/bin`, `codex-root`, browserTools disabled hoặc provider `agy`. Local setup hiện tại trên macOS dùng `$HOME`, role `lead`, provider `gemini-ui` và binary path dưới `~/.local/share/antigravity-acp`.
