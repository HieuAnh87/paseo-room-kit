# Room Flow: Model & effort preview

An interactive browser harness for the actual React Native settings component. UI authored by `claude-ui/claude-opus-5-5`, High, in one bounded trial. The harness renders the same component with `react-native-web`; it does not emulate the native Paseo host.

```sh
cd preview/model-effort
npm install
npm start
```

Open http://127.0.0.1:4318/ and use `?theme=light` for light mode. Resize below 760px for compact layout. Optional fixtures: `?saveError=1` simulates a failed save; `?unavailable=1` marks the Claude UI route unavailable. Rebuild with `npm run build` after source edits, then refresh.

Catalog data is a static snapshot captured from the machine's provider catalog on 2026-10-15; initial routes are illustrative defaults from the UI-routing branch. Saving affects component memory only. Reloading resets the preview. No daemon config, leases, active agents, or actual launch defaults are changed.

Source: `plugin/client/models/model-settings.tsx`. Shared fixtures: `plugin/shared/models/fixture.ts`. Research: `docs/research/model-effort-ui.md`.
