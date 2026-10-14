# Room callback

Server-only trusted local plugin for Paseo 0.11.2 and room-kit. It subscribes to
`agent.turn_ended` and invokes the installed room workflow CLI. No UI, vendor API,
credentials, or model polling is used.

The proxy chooses native callbacks when the scoped catalog supports them.
Otherwise it requires a fresh private plugin heartbeat and labels newly created
Peers `callback_transport=room-callback-v1`. Relay requests suppress native
notifications. The CLI validates the canonical Lead binding, active workspace,
epoch and exact assignment before notifying that Lead. Reviewer seats are also
Peers for this purpose.

Receipts live in the existing lease. Delivery never records engineering or Human
acceptance. Uncertain delivery is never automatically retried, including after
restart or new activity. Inspect `paseo-room-workflow asks --lead-id UUID`; use the
existing explicit Peer recovery/report/settlement procedure after Human review.
An ended turn without a current handback produces `NEEDS_LEAD_DECISION`.

Only new opted-in Peers are handled. Installation does not migrate old leases,
revive archived agents, change models/effort, or restart the daemon. Startup
performs one reconciliation of at most 64 canonical assignments. Lifecycle
hooks are best effort; this is not a durable daemon event subscription. There is
no continuous progress poll or guaranteed replay after an arbitrary lost event.

Requirements: installed `~/.local/bin/paseo-room-mcp`, `paseo-room-workflow` and
shared room-kit Python modules, an owner-writable lease directory, and the same
daemon host/user as the room proxy. The heartbeat is capability evidence, not
OS authentication or authority. This follows room-kit's cooperative owner-shell
boundary. A crash after reserving delivery leaves an `UNCERTAIN` receipt.

```sh
npm ci --ignore-scripts
npm test
npm run typecheck
paseo plugin install /absolute/path/to/paseo-room-kit/callback-plugin
paseo plugin reload room-callback
```

Changing source requires typecheck and plugin reload. Keep the manifest version
range accurate before upgrading Paseo. No `injectIntoAgents` configuration change
is required.
