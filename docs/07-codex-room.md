# 07 — `codex-room` và runtime isolation

## Vai trò

`codex-room` không phải tính năng native của Codex. Nó là launcher custom để Paseo khởi động cùng một Codex binary với ba role-specific runtime:

```text
Paseo
  → ~/.local/bin/codex-room <role>
  → ~/.local/bin/codex-room-sync <role>
  → ~/.codex-runtime/<role>/config.toml
  → CODEX_HOME=~/.codex-runtime/<role>
  → exec codex <arguments do Paseo truyền>
```

Role hiện tại chỉ có:

- `supervisor`;
- `lead`;
- `peer`.

Tên `root` trong một số tài liệu/upload cũ là nomenclature trước khi chốt Lead; không dùng `root` cho setup hiện tại.

## Hai nguồn config

`codex-room-sync` lấy:

```text
~/.codex/config.toml                 baseline chung
~/.codex/supervisor.config.toml      role overlay
~/.codex/lead.config.toml            role overlay
~/.codex/peer.config.toml            role overlay
```

Overlay override các scalar key:

- `model`;
- `model_instructions_file`;
- `model_reasoning_effort`;
- `personality`;
- `model_verbosity`;
- `model_reasoning_summary`;
- `service_tier`;
- `sandbox_mode`;
- `approval_policy`;
- `approvals_reviewer`.

Developer instruction block của role overlay được đưa lên config runtime. Phần table/baseline còn lại được giữ từ `~/.codex/config.toml`.

## Shared resources

Runtime role dùng `CODEX_HOME` khác nhau để tách config/state role. Các resource dùng chung được launcher symlink về canonical Codex home khi tồn tại:

- `auth.json`;
- `model-instructions.md`;
- `AGENTS.md`;
- `skills`;
- `plugins`.

`hooks.json` là ngoại lệ: `codex-room-sync` copy canonical hooks rồi thêm `room-role-guard.py --role <role>` vào `PreToolUse` và `PostToolUse`. Runtime hooks là file riêng, không còn là symlink. Tuy nhiên Codex `app-server` có tool path có thể opt out khỏi lifecycle hooks, nên hook không phải enforcement boundary chính.

Với Supervisor/Lead, sync còn materialize:

```toml
[mcp_servers.paseo]
command = "$HOME/.local/bin/paseo-room-mcp"
args = ["supervisor"] # hoặc "lead"
```

Peer không có table này. Namespace Paseo được ép direct-only trong code mode. Authority chính chạy trong MCP proxy trước khi request tới daemon.

## Tắt native Codex collaboration

Mỗi lần sync, script chạy:

```text
codex debug models --bundled
```

Sau đó set `multi_agent_version = null` trên model metadata và ghi:

```text
~/.codex-runtime/<role>/model-catalog.no-native-agents.json
```

Runtime config trỏ `model_catalog_json` vào catalog này. Mục tiêu là để Paseo là control plane duy nhất, tránh Codex native subagent/team capability cạnh tranh với Supervisor → Lead → Peer topology.

## Profile contract

### Supervisor

- Human-facing front door.
- Sol Medium/High hoặc Luna Max.
- Governance/portfolio/lifecycle, không engineering acceptance.

### Lead

- Engineering owner.
- Sol hoặc Luna Max.
- Được tạo bounded Peer theo routing preference.

### Peer

- Bounded worker/reviewer.
- Không dispatch; không được cấp Paseo MCP và direct CLI bị wrapper/permission deny.
- Không biết/điều khiển governance channel.

Xem source trực tiếp tại supervisor.config.toml, lead.config.toml, peer.config.toml.

## Failure modes của launcher

- đổi canonical config nhưng session đang chạy không tự materialize lại;
- role command gọi sai `root`/`lead`;
- runtime model catalog không được tạo;
- `CODEX_HOME` trỏ nhầm canonical home;
- provider identity hiển thị custom nhưng child bên trong thực tế là stock Codex;
- config baseline chứa MCP/secret không nên expose cho role đó.
- runtime vô tình có `[mcp_servers.paseo]` ở Peer;
- global `injectIntoAgents` bị bật lại và bypass role proxy;
- runtime `hooks.json` vô tình trở lại symlink và làm mất defense-in-depth guard.

Sau khi sửa overlay, kiểm tra runtime mới bằng một agent/session mới; không suy luận từ agent cũ.
