# 10 — Troubleshooting và trace

## Thứ tự chẩn đoán

```text
1. paseo status
2. provider ls/models
3. inspect agent identity
4. inspect parent/cwd/model/thinking
5. recent logs của đúng agent
6. daemon.log bounded slice
7. provider CLI/ACP smoke test
8. mới xem code/project behavior
```

Đừng bắt đầu bằng cách đọc toàn bộ daemon log hoặc poll tất cả transcript.

## Lỗi từng xảy ra: Lead/Peer chạy `gpt-5.4`

Trace chính: `<redacted-agent-id>`.

Observed chain trong history:

```text
Supervisor custom
  → created Lead with stock codex/gpt-5.4
  → Lead created Peer with stock codex/gpt-5.4
```

Root cause:

- orchestration preference chưa có/không được resolve đúng;
- workflow fallback về stock provider;
- không có post-create provider guard.

Fix hiện tại:

- tạo `orchestration-preferences.json`;
- map `planning` → `codex-lead/gpt-5.6-sol`;
- map Peer routes → custom provider;
- thêm explicit provider verification sau create;
- stock chain cũ giữ history, không tiếp tục chain misrouted.

## Provider unknown sau khi thêm config

Triệu chứng:

```text
Error: Unknown provider: gemini-ui
```

Nguyên nhân thường là daemon snapshot cũ chưa đọc `config.json`. Kiểm tra:

```bash
jq '.agents.providers["gemini-ui"]' ~/.paseo/config.json
paseo provider ls
paseo provider models gemini-ui
```

Nếu file đúng nhưng daemon chưa thấy, cần một lần reload/restart theo approval của Human. Tại snapshot hiện tại `gemini-ui` đã available nên không còn lỗi này.

## Provider đúng nhưng model sai

Phân biệt:

- provider catalog static/dynamic;
- `settings.model` lúc tạo agent;
- model mặc định của role overlay;
- model ID bên trong ACP/CLI;
- model của agent cũ.

Dùng:

```bash
paseo inspect <agent-id> --json
paseo provider models <provider>
```

Không suy luận model từ label UI.

## `codex-room` lỗi

Kiểm tra:

```bash
command -v codex
ls -l ~/.local/bin/codex-room ~/.local/bin/codex-room-sync
~/.local/bin/codex-room supervisor
rg -n 'model_catalog_json|multi_agent_version' ~/.codex-runtime/supervisor
```

Nếu chạy wrapper trực tiếp, nó sẽ exec Codex nên không dùng lúc agent đang có active session nếu không cần.

## Gemini ACP lỗi

Kiểm tra:

```bash
ls -l ~/.local/share/antigravity-acp/dist/agy-acp-darwin-arm64
ls -l ~/.local/share/antigravity-acp/dist/agy
~/.local/share/antigravity-acp/dist/agy --version
~/.local/share/antigravity-acp/dist/agy models
~/.local/share/antigravity-acp/dist/agy-acp-darwin-arm64 --version
```

ACP smoke test tối thiểu phải nhận JSON-RPC `initialize`. Prompt thật có thể còn yêu cầu authentication của `agy`.

## MCP không thấy

Xem [06-mcp-and-visibility.md](06-mcp-and-visibility.md). Đừng nhầm:

- MCP baseline từ Codex `config.toml`;
- Paseo control MCP injection;
- MCP riêng của OpenCode/Antigravity;
- quyền của service account/database.

## Peer xong nhưng Supervisor không nhận final Lead result

Đây không nhất thiết là mất event. `notifyOnFinish` của Paseo `0.2.5` gắn với turn được create/prompt:

```text
Supervisor prompts Lead
  → Lead creates Peer và kết thúc turn đầu
  → callback sớm về Supervisor
  → Peer callback tạo turn thứ hai cho Lead
  → turn thứ hai không tự kế thừa callback lên Supervisor
```

Lead phải gọi `handback_to_parent` sau validation. Nếu tool báo không tìm thấy parent governance seat:

1. xác nhận Lead có label `paseo.parent-agent-id`;
2. xác nhận parent chưa archive;
3. parent mới nên có `role=supervisor`; Supervisor legacy được nhận bằng provider canonical `codex-supervisor`, `claude-supervisor` hoặc `opencode-supervisor`;
4. reload riêng Lead để stdio MCP process nạp proxy mới; không cần restart toàn daemon;
5. chỉ retry khi lần trước được xác nhận chưa deliver.

## Dissent loop

Nếu Lead/Peer tranh luận nhiều vòng:

1. yêu cầu structured handback;
2. bắt Lead chọn `RESOLVED_BY_LEAD`, `NEEDS_MORE_EVIDENCE` hoặc `ESCALATED_TO_HUMAN`;
3. nếu `NEEDS_MORE_EVIDENCE`, giới hạn đúng một verification round;
4. Supervisor chỉ advice process nếu evidence bị bỏ qua/ownership bị ép;
5. không tạo Peer mới để “đếm phiếu”.

## Logs và secret hygiene

Daemon logs/agent timeline có thể chứa prompt, path, command và thông tin vận hành. Chỉ lấy bounded lines cần thiết; không paste nguyên log vào issue/chat công khai.
