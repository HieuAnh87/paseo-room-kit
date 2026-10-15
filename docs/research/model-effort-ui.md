# Model & effort UI research — 2026-10-15

This is an interactive preview for the existing Room Flow visual system. It does not change installed routing, active agents or launch policy.

## References reviewed

- [Paseo plugin directory](https://paseo.sh/plugins), including Orchestration and Utils. No dedicated role-based model/effort editor was identified among the reviewed listings; this is not an exhaustive absence claim.
- [Model Pricing](https://paseo.sh/plugins/gpambrozio/model-pricing): searchable model pricing/capability table. Useful comparison screen, but does not edit role routes or effort. No pricing claims are added to our snapshot preview.
- [Bots](https://paseo.sh/plugins/oliexe/bots): separate identity/model/permission settings and visible review of proposed changes. Borrow the separation of responsibilities, not its runtime or daemon-wide tool setting.
- [Agent Crew](https://paseo.sh/plugins/omercnet/agent-crew): compact parent/child roster, clear native agent states and user-directed operations. Borrow role scanability.
- [Workboard](https://paseo.sh/plugins/fxbing/workboard): grouped views, compact layout and keyboard controls. Borrow density and responsive structure.
- [Firstmate](https://paseo.sh/plugins/gpambrozio/firstmate): crew board adjacent to the supervising chat. Broader orchestration than this screen needs.
- [Cafe](https://paseo.sh/plugins/paseo-cafe/cafe): searchable plugin directory with a pinned artifact review before install. A store browser, not a model-policy editor.
- [Alliance model settings source](https://github.com/haohao3k/alliance-work/blob/84541c92560ea8d47702312169a57df8550ab381/client/model-settings.tsx): room allowlist, effort and difficulty priorities in a modal. Keep explicit supported efforts; reduce the number of simultaneous decisions.

## Trial direction

A settings surface inside Room Flow: role navigation with model/effort summaries; searchable model list; supported effort choices; inspectable draft changes and explicit save/discard. Follow Paseo theme tokens and compact layout. Keep provider aliases visible because two aliases with the same model can carry different permissions.

Catalog entries are a read-only snapshot from list_models on this machine. Initial routes follow the UI-routing branch's defaults. Advisor is an illustrative mapping to the read-only reviewer route. Do not treat this as an installed launch configuration.

Only approved role providers are selectable for each role. No automatic fallback or active-session mutation. Preview saving records an in-memory draft only, and the UI states this boundary.
