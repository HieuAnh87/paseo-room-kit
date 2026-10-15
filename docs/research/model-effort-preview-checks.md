# Model & effort preview checks — 2026-10-15

## Candidate and proof boundary

Branch `feat/model-effort-preview`, based on UI-routing branch `f00e542`. UI authored by one Opus 5.5 High agent, followed by one same-agent review batch and a mechanical compact footer sizing correction. No additional paid reviewers, fallback providers, live model probes, or installed runtime changes.

The browser harness renders the actual React Native component using react-native-web. These checks do not prove native Paseo registration, actual launch-policy persistence, private-host accessibility or real agent launches. The incumbent Room Flow package still targets Paseo 0.9.x; migrating that package to the installed 0.11.2 API remains outside this preview. The standalone preview is usable now.

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
- Browser exposed aria-selected for selected role tabs and aria-checked for model/effort radios. Native-host semantics remain unverified.

Preview process: http://127.0.0.1:4318/ (loopback only). `?theme=light` switches to light fixtures. Reload resets saved preview values.
