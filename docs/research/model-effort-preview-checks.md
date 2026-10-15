# Model & effort preview checks — 2026-10-15

## Candidate and proof boundary

Branch `feat/model-effort-preview`, based on UI-routing branch `f00e542`. UI authored by one Opus 5.5 High agent, followed by one same-agent review batch and a mechanical compact footer sizing correction. No additional paid reviewers, fallback providers, or live model probes.

The initial browser checks below used the actual React Native component through react-native-web at commit `6a6a671`. The subsequent installed-desktop checks are recorded separately. Saving remains an in-memory preview: neither stage proves launch-policy persistence or real agent launches.

## Checks run

- Plugin server/shared and client TypeScript checks: PASS.
- Existing Room Flow tests: 10 PASS.
- Build of standalone actual-component browser preview: PASS.
- Impeccable mechanical detector: no findings at the scan point.
- Desktop 1280×900 dark and light: rendered, roles fixed at240px, model area uses remaining space.
- Compact390×844 dark and light: rendered, document scrollWidth390; Save/Discard targets44px. Footer status sizing corrected and re-rendered.
- Lead effort XHigh→High, Peer Luna→Sol, UI Gemini→Opus: drafts preserved across role switches, three changes in review summary.
- Save preview: changes become in-memory baseline, explicit no-agent-application message, save/discard disabled until next edit.
- Discard: restored saved model selection and cleared unsaved state.
- Search no-match and Clear filters: PASS.
- Role isolation: Lead only codex-lead; Peer only codex-peer; UI only antigravity-cli/claude-ui; Advisor only claude-reviewer. Provider filter reset on role switch is implemented.
- `?unavailable=1`: Claude UI row visibly unavailable and disabled.
- `?saveError=1`: simulated save failure retained Lead Max draft and allowed retry/discard.
- Browser exposed aria-selected for selected role tabs and aria-checked for model/effort radios.

Preview process: http://127.0.0.1:4318/ (loopback only). `?theme=light` switches to light fixtures. Reload resets saved preview values.

## Installed Paseo desktop follow-up

- Migrated the plugin entry from legacy surface/sidebar registrations to `addScreen` and `addSidebarHeaderItem` with host `SidebarRow` components.
- Pinned the local SDK to 0.11.2 and declared Paseo `>=0.11.2 <0.12.0` compatibility. Server/shared and client typechecks and all 10 existing tests passed after migration.
- Installed runtime ID `room-flow` from `/Users/hieuda/Documents/paseo-room-kit-models/plugin`; the daemon reports it enabled and running.
- Invoked the installed `room-flow.snapshot` RPC through the local daemon SDK: returned a present lease source and 36 rooms at `2026-10-15T07:01:12.330Z`. Only aggregate metadata was printed. Plugin logs showed loading/ready without errors.
- Opened **Model & effort** directly in the actual Paseo desktop app. The screen title is **Room Flow · Model & effort**; Lead, Peer, UI specialist and Advisor tabs render.
- Selected UI specialist, changed Gemini to Opus, and used Save preview. The native app displayed **Preview saved · settings are not applied to agents** and disabled Save/Discard after saving.
- The desktop accessibility tree exposed selected role/model/effort states. A native desktop screenshot was inspected.
- Native compact/mobile and native light theme were not exercised; the earlier browser fixture checks cover only their browser boundary. Human design acceptance remains the owner's decision.
- No launch-policy write, agent mutation, global MCP injection change, or daemon restart was performed.
- The daemon retained PID 1363, worker PID 1367 and start time `2026-10-12T11:41:03.402Z`; `daemon.mcp.injectIntoAgents` remains false.
