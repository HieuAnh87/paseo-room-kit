# Paseo room workflow protocol

This protocol defines the governance state that Paseo's native lifecycle does not provide. Native `running`, `idle`, `error`, `closed`, attention, and permission events remain transport/runtime facts; they are never engineering acceptance.

## Authority chain

```text
Human → Supervisor → Lead → Peer
```

- Human owns objective, accepted decisions, product trade-offs, protocol changes, and Lead replacement.
- Supervisor is the Human-facing governance and lifecycle owner. It creates or resumes exactly one Lead per project workspace and communicates only with that Lead during normal operation.
- Lead is the sole engineering owner. It decomposes work, selects routes, assigns Peers, validates evidence, resolves dissent, and accepts or rejects engineering results.
- Peer executes or reviews one bounded assignment and hands evidence back to its parent Lead. Peer cannot use Paseo orchestration tools or the Paseo CLI.

## Required labels

Supervisor creates a Lead with:

- `role=lead`
- `route=planning`
- `task_state=LEASED`

After a successful final handback, the proxy changes the Lead to:

- `task_state=HANDBACK_READY`

Lead creates a Peer with:

- `role=peer`
- `route=impl|impl_deep|search|ui|research|audit`
- `task_state=ASSIGNED`

The role-aware MCP proxy invokes the guard, canonicalizes these labels, and forces `notifyOnFinish=true`. Paseo owns `paseo.parent-agent-id`.

## Lead lease

`lead-leases.json` is the deterministic lease registry. A workspace may have at most one `pending` or `active` Lead lease.

```text
none → pending → active → released
                 └──────→ failed
```

- The Supervisor proxy reserves `pending` before it forwards `create_agent` to Paseo.
- The proxy activates the lease with the returned Lead agent ID.
- Archiving or killing that Lead releases the lease.
- Archiving the workspace releases its pending or active Lead lease and reconciles any lease whose Lead was already archived.
- A pending reservation expires after five minutes if creation never completes.
- A new Lead is denied while an unarchived `role=lead` agent or live lease exists for the workspace.
- Replacement order is checkpoint → handoff → archive old Lead → verify lease released → create new Lead → reconcile.

## Peer terminal handback

Every Peer response that ends its bounded turn starts with exactly one line:

```text
Task outcome: DONE|BLOCKED_PERMISSION|NEEDS_LEAD_DECISION|FAILED
```

Then include:

- work changed or inspected;
- validation evidence;
- remaining uncertainty;
- counterevidence;
- dissent fields when applicable.

Paseo automatically notifies Lead when the Peer finishes, errors, or needs permission. Lead must not poll.

After receiving the callback, Lead updates the Peer label to the reported terminal outcome. Lead then chooses:

- `ACCEPTED`: evidence is sufficient and Lead accepts the bounded result;
- `REWORK`: Lead sends one bounded follow-up and sets `task_state=ASSIGNED`;
- `NEEDS_LEAD_DECISION`: Lead resolves within engineering authority;
- `ESCALATED_TO_HUMAN`: only for objective, accepted-decision, product, ownership, authority, or irreversible-risk boundaries.

`DONE` means the Peer completed its turn. Only `ACCEPTED` means Lead accepted the engineering result.

## Lead final handback

Paseo's native `notifyOnFinish` is scoped to the created or prompted turn. It notifies Lead when Peer completes, but a later Lead turn started by that callback does not inherit the original Lead-to-Supervisor callback.

After all required Peer callbacks are resolved and the engineering result is validated, Lead calls `handback_to_parent` exactly once. The proxy resolves the exact active parent Supervisor from Paseo-owned metadata and sends the final report in the background with reverse notification disabled. Lead supplies only the report, never a Supervisor ID.

The final report includes:

- accepted engineering outcome;
- validation evidence;
- remaining risk or uncertainty;
- any decision that crosses into Human authority.

Successful delivery changes the Lead label from `LEASED` to `HANDBACK_READY` and rejects duplicate final handback attempts. Human acceptance remains a Human decision; after acceptance or explicit abandonment, Supervisor archives the workspace, which releases the lease while preserving history and local directories.

This explicit handback is event-driven. It does not use polling, schedules, or heartbeats.

## Routing

Provider/model routing comes from `~/.paseo/orchestration-preferences.json`.

- Supervisor may create only the `planning` route.
- Lead must declare the Peer `route` label. The role-aware MCP proxy checks the exact provider/model and normalizes required thinking.
- Stock `codex/...` is invalid for internal Lead or Peer seats.
- Room launchers shadow the direct Paseo CLI; internal orchestration must use the role-aware MCP proxy.

The MCP proxy is the deterministic operational boundary. Codex hooks remain defense in depth only because app-server tool paths may bypass lifecycle hooks. None of these mechanisms is a hostile-process security sandbox; Human/top-level daemon administration remains outside the room-agent authority chain.

## Workspace isolation

Use a Paseo-managed worktree for engineering objectives that may mutate a repository, especially when more than one room can touch the same project concurrently. Use local isolation only for explicitly read-only work or work that the Human has chosen to serialize. Logical workspace separation does not isolate a shared local checkout.
