# 12 — Decision log

Đây là log các quyết định đã hình thành qua quá trình setup. Các mục lịch sử cũ được ghi để hiểu vì sao config hiện tại có hình dạng này; không phải mọi trạng thái cũ còn active.

## D1 — Chọn topology Supervisor → Lead → Peer

Mục tiêu là Human có một front door và không phải quản lý các engineering worker trực tiếp.

Quyết định:

- Supervisor là governance/portfolio/lifecycle assistant;
- Lead là engineering owner của workspace;
- Peer là bounded worker/reviewer;
- Paseo là control plane.

## D2 — Supervisor là người nói chuyện với Human

Human không cần biết Lead/Peer là ai trong vận hành thường ngày. Supervisor relay objective và báo outcome. Lead/Peer không được biết implementation/provider của Supervisor qua prompt contract.

## D3 — Đổi nomenclature `root` thành `lead`

Tài liệu/upload ban đầu dùng `codex-root`/Root. Sau khi làm rõ ownership, role engineering owner được gọi là Lead. Config hiện tại dùng `codex-lead` và launcher role `lead`; `root` chỉ còn trong history.

## D4 — Supervisor không làm project management

Supervisor không chia task, chọn Peer, chọn architecture, review/accept code hoặc prioritize engineering. Supervisor chỉ quản lý workflow quality, ownership, lifecycle, decision/evidence flow và advice governance.

## D5 — Thêm shared dissent protocol

Dissent phải có current direction, claim, evidence, counterevidence, risk, requested resolution. Lead đóng bằng đúng một outcome; không vote/loop vô hạn.

## D6 — Tách role runtime bằng `codex-room`

Một Codex baseline được materialize thành ba `CODEX_HOME` khác nhau. Native Codex collaboration metadata bị loại khỏi model catalog để tránh hai control plane.

## D7 — MCP

Paseo `0.2.5` chỉ có global `injectIntoAgents`; `injectIntoProviders` không có implementation. Global injection được tắt. Supervisor/Lead nhận role-aware `paseo-room-mcp`; Peer không nhận control MCP. OpenCode permissions, CLI wrapper và ACP capability flag bổ sung boundary. Baseline Codex MCP vẫn được runtime role kế thừa.

## D8 — Rút gọn OpenCode Peer

OpenCode Peer chỉ giữ AI Box DeepSeek V4 Flash và GLM 5.2, cả hai Max. Claude/OpenCode native vẫn tồn tại cho direct/manual use nhưng không tự thành internal role route.

## D9 — Thêm Luna

Lead/Peer có Luna; Supervisor hiện cũng có Sol và Luna. Supervisor dùng Sol Medium mặc định; Luna Max là option cho governance khó.

## D10 — Sửa stock `gpt-5.4` routing

Trace `<redacted-agent-id>` cho thấy chain đã fallback vào `codex/gpt-5.4`. Fix:

- custom provider map;
- orchestration preferences;
- post-create provider/model verification;
- preserve legacy history, không tiếp tục chain misrouted.

## D11 — Search dùng Luna Low

Direct `rg`/GitNexus không tạo model mới. Delegated codebase search dùng `codex-peer/gpt-5.6-luna` với Low, vì Low là option nhẹ nhất đang được catalog khai báo.

## D12 — Implementation split DeepSeek/Luna

- DeepSeek Flash Max cho normal/mechanical implementation;
- Luna Max cho hard/cross-cutting implementation và audit;
- không thêm option thinking không được provider hỗ trợ.

## D13 — Gemini UI qua ACP

Thêm `gemini-ui` với `antigravity-acp`, giới hạn model catalog về Gemini 3.6/3.5/3.1. UI route mặc định Gemini 3.6 Flash Medium. Auth/TOS risk được ghi ở [08-provider-integrations.md](08-provider-integrations.md).

## D14 — Không tự restart daemon

Paseo skill quy định restart daemon có thể kill agent đang chạy. Config có thể ghi trước; reload/restart là operation cần Human approval nếu còn active work.

## D15 — Deterministic role guard và Lead lease

Thêm `room-role-guard.py`, Lead lease registry và sau đó đặt guard sau role-aware MCP proxy:

- Supervisor chỉ tạo `planning` Lead;
- Lead chỉ tạo Peer bằng declared route đúng provider/thinking;
- Peer bị deny Paseo MCP/CLI;
- target mutation phải đi xuống đúng parent→child;
- Lead creation reserve một lease theo workspace trước khi gọi Paseo.

Native lifecycle chỉ là runtime state. Peer phải trả `Task outcome`; Lead mới được đặt `ACCEPTED` sau validation.

Codex `app-server` direct/nested MCP path đã được live test và không phát lifecycle hook ổn định. Vì vậy `PreToolUse` không còn được coi là enforcement boundary; proxy gọi guard script trực tiếp ở server boundary.

## D16 — Explicit final handback thay vì poll/heartbeat

Live smoke test cho thấy `notifyOnFinish` là per-turn: Lead kết thúc turn đầu trong lúc chờ Peer nên Supervisor nhận callback sớm; Peer callback sau đó mở turn thứ hai của Lead nhưng không tự propagate lần nữa lên Supervisor.

Thêm Lead-only `handback_to_parent` trong role proxy. Tool:

- không nhận Supervisor ID;
- resolve exact parent từ `paseo.parent-agent-id`;
- chỉ chấp nhận parent active có `role=supervisor` hoặc canonical provider `codex-supervisor`/`claude-supervisor`;
- gửi final report background với reverse notification tắt;
- không xuất hiện cho Supervisor/Peer.

Đây là explicit event-driven handback, không phải polling, schedule hoặc heartbeat.

## D17 — Sonnet 5 Lead pilot với working context 300K

Giữ `planning` stable ở `codex-lead/gpt-5.6-sol`. Thêm route owner-explicit `planning_pilot` tới `claude-lead/claude-sonnet-5[1m]` Max. Lead pilot dùng cùng lease, authority, Peer routing và final handback contract.

Biến thể 1M chỉ là headroom. Claude runtime đặt `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000`; Lead phải giữ trạng thái chính xác trong artifact bền vững và không xem compact summary là source of truth. Guard chỉ chấp nhận pilot khi creation có `lead_profile=pilot`; nếu không, stable route vẫn là bắt buộc.
