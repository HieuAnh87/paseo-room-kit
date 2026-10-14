# Room Flow plugin

Optional, read-only Paseo 0.9.x sidebar view for managed `paseo-room-kit` rooms.
It joins the daemon's paged workspace and agent directory with the kit's
existing `lead-leases.json`. The lease remains the source of room authority;
Paseo remains the source of session status. The plugin creates no lane ledger,
agent, decision, prompt, Git operation, reminder, or automatic mutation.

The view shows active room bindings, work epoch/revision, Lead/Supervisor/Peer
status, decision state, report count, recorded candidate presence, and open
current-epoch asks. Health highlights missing Paseo authority, uncertain
delivery, pending Human review and permissions. The first shadow hint marks an
idle Peer with an open assignment and no report. That hint does **not** mean
the Peer finished or the Lead accepted its work. Released rooms are hidden by
default and can be expanded.

## Requirements and local checks

- Paseo daemon **and app** version `>=0.9.0 <0.10.0`.
- Node.js 22 or later for the local test command.
- The room-kit lease registry on the same machine as the daemon. The path is
  `ROOM_GUARD_LEASES_PATH`, then `PASEO_ROOM_LEASES_PATH`, then
  `~/.config/room-workflow/lead-leases.json`, matching the kit proxy.

From this directory:

```bash
npm ci
npm run typecheck
npm test
```

`@getpaseo/plugin` is a development dependency pinned to 0.9.0 for checking
the API. Paseo supplies SDK, React, React Native and Zod host modules at
runtime. The plugin uses no external service.

## Installation

Paseo plugins are trusted code. Its backend runs with the daemon user's file
access, and the client surface runs inside the app. Review this directory
before installing. The kit installer does not install or enable this plugin.

When using a matching Paseo 0.9.x CLI, daemon and app, check that the daemon's
global plugin switch is already enabled. If it is not, get the machine owner's
authorization before enabling it. Then install this directory as an absolute
path on the daemon host:

```bash
paseo plugin install /absolute/path/to/paseo-room-kit/plugin
paseo plugin ls room-flow
```

Open **Room Flow** in the Paseo sidebar. The screen refreshes every 15 seconds
and has a manual Refresh button. An absent lease file is shown explicitly;
malformed lease data or an incomplete Paseo directory makes the RPC fail
instead of presenting a misleading empty or partial view.

Source changes require `npm run typecheck` followed by
`paseo plugin reload room-flow` on a host where it is already installed.
