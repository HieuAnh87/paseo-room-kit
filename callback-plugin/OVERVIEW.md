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

New room bindings save handbacks in an outbox in the existing lease before
notification. Saved READY messages can resume after restart; an interrupted
SENDING becomes UNCERTAIN and requires Human inspection. Delivery never records
engineering or Human acceptance. Use `paseo-room-workflow callback-outbox
--lead-id UUID` to read saved handbacks and `resolve-callback` for an evidence-
backed resolution or explicit retry of a rejected message. An ended turn without
a current handback produces `NEEDS_LEAD_DECISION`.

Existing bindings keep their v1 relay until a fresh binding checkpoint.
Only opted-in Peers are handled. Installation does not migrate old leases,
revive archived agents, change models/effort, or restart the daemon. Startup
performs one reconciliation of at most 64 canonical assignments. Lifecycle
hooks are best effort; this is not a durable daemon event subscription. There is
no continuous progress poll or guaranteed replay after an arbitrary lost event.

Requirements: installed `~/.local/bin/paseo-room-mcp`, `paseo-room-workflow` and
shared room-kit Python modules, an owner-writable lease directory, and the same
daemon host/user as the room proxy. The heartbeat is capability evidence, not
OS authentication or authority. This follows room-kit's cooperative owner-shell
boundary. Outbox payloads are limited to 64 KiB. A stored message ID prevents
duplicate local dispatch; ambiguous network delivery still needs inspection.

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
