# 11 — Security, secrets và boundary

## Authority hiện tại

Custom Codex role profile hiện dùng:

- `sandbox_mode = danger-full-access`;
- `approval_policy = never`;
- `service_tier = default`.

Đây là cấu hình mạnh. Nó phù hợp với workflow local mà Human đã chốt nhưng không nên coi là secure-by-default. Baseline canonical Codex hiện có permission khác, nhưng role overlay custom thắng trên runtime role.

## Secret-bearing sources

`~/.codex/config.toml` hiện có các nhóm secret/credential có thể có:

- `auth.json`/provider auth;
- database URI cho prod/staging/dev;
- Kibana credentials;
- Morph API key;
- SigNoz API key;
- ZRead auth header;
- Sentry auth token;
- environment key cho external search/AI service.

Folder docs này không sao chép các giá trị đó. Khi backup config, phải dùng bản redacted hoặc secret manager, không commit raw config vào Git.

## MCP least privilege

Một số MCP có quyền rộng, bao gồm database `unrestricted` ở source config. Khuyến nghị vận hành:

- dùng read-only/service account riêng cho inspect;
- tách prod/staging/dev credential;
- không expose database MCP cho Peer nếu assignment không cần;
- không coi URL/command visible là authorization;
- rotate secret nếu credential từng bị paste vào chat/log/issue công khai.

## Role opacity

Supervisor/Lead/Peer không được tiết lộ topology control trong prompt thường ngày. Đây là boundary để giảm coupling và tránh Peer bypass Lead.

Giới hạn:

- người có filesystem/process access vẫn có thể đọc config;
- daemon logs có thể chứa metadata;
- external CLI có thể có behavior riêng;
- prompt instruction không thay thế OS isolation.

## Antigravity ACP risk

`antigravity-acp` README cảnh báo việc dùng third-party ACP tool để drive Antigravity OAuth có thể bị Google coi là vi phạm Terms và có rủi ro account suspension/termination. Nếu cần giảm rủi ro, dùng Vertex AI hoặc AI Studio API key theo hướng dẫn upstream. Xem [antigravity-acp README](https://github.com/shubzkothekar/antigravity-acp#readme).

## Backup policy

Có backup cấu hình Paseo trước khi chốt Supervisor tại:

`~/.paseo/config.json.pre-supervisor-<redacted-agent>`

Backup đó là historical reference, không phải source of truth. Nó còn dùng provider nomenclature/feature set cũ hơn.

## Không được làm khi debug

- không gửi `auth.json`;
- không paste nguyên `config.toml` vào chat;
- không commit raw `$HOME/.paseo` hoặc `$HOME/.codex`;
- không chạy destructive command để “dọn” agent/workspace mà chưa resolve target;
- không restart daemon khi còn agent cần giữ;
- không dùng Supervisor để lách product/ownership authority.
