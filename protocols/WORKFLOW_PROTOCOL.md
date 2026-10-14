# Paseo room workflow protocol

This protocol defines the governance state that Paseo's native lifecycle does not provide. Native `running`, `idle`, `error`, `closed`, attention, and permission events remain transport/runtime facts; they are never engineering acceptance.

## Authority bindings

Human owns objectives, product trade-offs, accepted decisions and authority changes. Lead is the sole engineering owner of a workspace; Peer owns one bounded assignment. Supervisor is optional governance observation and relay, with no project engineering authority.

Valid arrangements are `Human → Lead → Peer`, an independently bound root Supervisor observing a root Lead, and the compatible `Human → Supervisor → Lead → Peer` bootstrap path. Paseo parentage describes session ancestry. An explicit lease grants authority; a provider name, display title or parent relation alone does not grant it.

The owner-shell `paseo-room-workflow bind` binds an existing root Lead without creating or reparenting agents. `authority_mode=direct` has no Supervisor; `observed` names an independently bound Supervisor; legacy leases default to `parented`. At most one active or pending Lead owns a workspace. Supervisor may act only on its binding; Human may use the same protected operations directly.

## Shared contracts and repository tactics

Four layers remain separate: Paseo identity/session/lifecycle; common proxy/guard authority and evidence contracts; role invariants plus repository tactics and assignment; provider-specific instruction loading and tool transport. All supported adapters use the same common contracts.

An optional `.orchestration/workflow.json` defines version-1 task classes with explicit boolean `candidate`, `independent_review` and `lead_self_work` gates. It requires `.orchestration/workspace-protocol.md`, which records project-specific scope, owner-reserved decisions, ownership, review tactics and proof requirements. The protocol and policy bytes, Lead placement and persisted provider/model/settings are pinned to the binding. Drift blocks managed work until an explicit checkpoint and replacement. Missing policy preserves legacy behavior; it does not supply candidate review gates.

New bindings carry `runtime_binding_version=2`. The pin normalizes persisted `config`/`settings` and effective `runtimeInfo`; missing provider/model/thinking/mode or conflicting configured/effective values fail closed. Stable settings and feature values are digest-bound; display metadata and runtime session IDs are excluded. This is persisted metadata validation, not model attestation.

Unversioned runtime pins remain legacy v1 for their current epoch, including null pins. They are surfaced as `LEGACY_UNVERIFIED` in room attention and are never silently upgraded. Existing work/handback can close under the original v1 checks; opening another epoch requires v2. Human may release and bind afresh, or use owner-shell `rebind-runtime REQUEST.json` at a `HANDBACK_READY` checkpoint with all tasks settled, checks quiescent and descendants archived. Request fields are `agentId`, `expectedWorkEpoch`, `expectedRevision`, `runtimeBindingDigest`, and independent launch-verification `evidence`. Preview returns the exact proposed digest without writing; `--apply` rechecks that digest and CAS before changing only the runtime pin/revision with a history receipt. It does not accept work, alter candidate/report evidence, change parentage or reopen an epoch.

`paseo-room-workflow init REPOSITORY` previews missing files; `--apply` creates only missing files. Human adapts tactics before binding. Lead starts with `inspect_work_context`, reads the full repository protocol, and chooses the smallest topology that satisfies those gates. Neutral briefs and evidence-backed reopen/dependency requests are expected. Tests verify established contracts rather than silently deciding new APIs.

For candidate-gated work, `inspect_work_candidate` returns a digest of Git HEAD (including unborn HEAD), staged index and tracked/nonignored untracked file contents, deletions, modes and symlink targets. Pause writers during review. The snapshot does not commit or stage changes; ignored artifacts and submodules are outside this proof (submodules are rejected). Acceptance and accepted archive recheck the candidate. A changed candidate invalidates the review.

Peer assignments carry immutable `assignment_id`, `disposition=engineer|architect|reviewer|scout` and `write_mode`. Only engineer assignments request writing; the other dispositions inspect. These are cooperative workflow ceilings, not OS filesystem permissions. A Reviewer cannot be relabeled from an Engineer to approve its own assignment.

Lead records structured reports with `record_peer_report` before archiving the Peer. A version-1 envelope contains `reportId`, `peerAgentId`, `parentLeadId`, `workspaceId`, `workEpoch`, `assignmentId`, `kind` and `payload`. `payload.evidence` is a non-empty string naming actual artifacts, checks and their limits; arrays and objects are rejected. Kinds are `HANDOFF`, `REVIEW`, `REOPEN_REQUEST`, `DEPENDENCY_REQUEST`, `BLOCKED`, `PROGRESS`. A REVIEW needs a Reviewer assignment, `candidateDigest` and `verdict=APPROVE|FINDINGS`. Reports are correlated to current durable identity/assignment/epoch; identical report IDs deduplicate, changed content is denied. Independent-review gates require current-candidate approval and no unresolved findings. The envelope validates correlation, not whether a claimed check actually ran; Lead must inspect that evidence.

## Required labels

Supervisor creates a Lead with:

- `role=lead`
- `route=planning`
- `lead_profile=stable|claude`
- `stack_profile=standard`
- `room_kind=managed_slp`
- `work_epoch=1`
- `task_state=LEASED`

After a successful final handback, the proxy changes the Lead to:

- `task_state=HANDBACK_READY`

Lead creates a Peer with:

- `role=peer`
- `route=impl|impl_deep|search|ui|research|audit`
- `stack_profile=standard`
- `room_kind=managed_slp`
- `work_epoch=<current Lead epoch>`
- `task_state=ASSIGNED`
- `assignment_id=<guard-generated identity>`
- `disposition=engineer|architect|reviewer|scout`
- `write_mode=write|read_only`

The role-aware MCP proxy invokes the guard and canonicalizes these labels. Managed Lead creation uses `notifyOnFinish=false`; explicit epoch handback is its only completion report. Peer creation uses `notifyOnFinish=true`. Paseo owns `paseo.parent-agent-id`.

`room_kind=managed_slp` distinguishes rooms governed by this protocol from ad-hoc Paseo sessions. Ad-hoc sessions do not acquire a managed lease, do not enter the Human decision queue, and cannot use managed epoch operations.

## Lead lease

`lead-leases.json` is the deterministic lease and work-epoch registry. A workspace may have at most one `pending` or `active` Lead lease. New managed leases start with `work_epoch=1`, `handback_epoch=0`, `revision=1`, and `decision_state=WORKING`. Existing version-1 and version-2 leases lazily gain `revision=1`; the registry format remains version 2. A legacy ready lease without a stored report receives a deterministic missing-evidence digest and may be abandoned or reopened, but cannot be accepted until a new epoch supplies evidence.

```text
none → pending → active → released
                 └──────→ failed
```

- The Supervisor proxy reserves `pending` before it forwards `create_agent` to Paseo.
- The proxy activates the lease with the returned Lead agent ID.
- Archiving or killing that Lead releases the lease.
- Archiving the workspace releases its pending or active Lead lease. Reconciliation also releases a stale active lease when its Lead record is missing/archived or its workspace record is missing/archived.
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

The proxy requires a working finish notification transport before Peer dispatch: native scoped callbacks, or the trusted room-callback lifecycle plugin for newly labelled Peers. The relay sends ended-turn evidence once to the canonical Lead with reverse notification disabled. It never accepts work. Missing current handback yields NEEDS_LEAD_DECISION; uncertain send is not retried. Native permission notifications depend on daemon support; inspect permission attention through the explicit bounded path when needed. Lead must not poll. If the Peer cannot access its own identity, it may report `peerAgentId=null` rather than guess or probe. The owning Lead's `record_peer_report` can correlate only one matching durable post-create brief and active native Peer record, preserving assignment/epoch/workspace/parentage and recording the correlation method. Ambiguity or missing creation evidence returns `NEEDS_LEAD_DECISION`; incorrect non-null IDs are never repaired. This does not establish a cause for a missing callback or missing environment variable.

If an expected Peer callback does not render, Lead may invoke `recover_peer_callbacks`
once as a bounded recovery action. The proxy reads durable Paseo status and curated
activity, requires exact parent/workspace/current-epoch authority, persists the
terminal handback plus an evidence digest in the active lease, and updates the
Peer's display state. Repeated recovery reads the stored receipt instead of
re-reading activity. This is an exception path, not a status loop or replacement
for the selected callback transport.

After receiving the callback, Lead updates the Peer label to the reported terminal outcome. Lead then chooses:

- `ACCEPTED`: evidence is sufficient and Lead accepts the bounded result;
- `REWORK`: Lead sends one bounded follow-up and sets `task_state=ASSIGNED`;
- `NEEDS_LEAD_DECISION`: Lead resolves within engineering authority;
- `ESCALATED_TO_HUMAN`: only for objective, accepted-decision, product, ownership, authority, or irreversible-risk boundaries.

`DONE` means the Peer completed its turn. Only `ACCEPTED` means Lead accepted the engineering result.

## Lead final handback

Paseo's native `notifyOnFinish` is scoped to the created or prompted turn. It notifies Lead when Peer completes, but a later Lead turn started by that callback does not inherit the original Lead-to-Supervisor callback.

After required callbacks and validation, Lead calls `submit_work_result` (compatible alias: `handback_to_parent`) once for the epoch, supplying the report and `candidateDigest` when gated. The proxy resolves governance from the active binding. Observed/parented bindings deliver to the bound active Supervisor with reverse notification disabled. Direct bindings persist a local delivery receipt and expose the report in the Human decision queue, without prompting another agent. Lead never supplies a governance recipient.

The final report includes:

- accepted engineering outcome;
- validation evidence;
- remaining risk or uncertainty;
- any decision that crosses into Human authority.

Before delivery, the proxy durably reserves `decision_state=HANDBACK_SENDING`, a unique correlation ID, and a monotonic lease revision. Successful correlated delivery must still match the reserved epoch, revision, and correlation ID before it records `handback_epoch=work_epoch`, changes the Lead label from `LEASED` to `HANDBACK_READY`, and enters `decision_state=HANDBACK_READY`. Stale completion is rejected. A timeout, crash, empty response, or uncorrelated response leaves the reserved state and is never automatically retried, so uncertain upstream completion cannot duplicate the report.

Supervisor uses `list_slp_decisions`; Human can use owner-shell `paseo-room-workflow decisions` and JSON-file `decide`, `reopen`, `resolve`, `archive` commands over the same deterministic decision queue. Mutating CLI commands preview by default and require `--apply`. Each item includes the current epoch, revision, delivery correlation ID when unresolved, immutable epoch-report `evidence_digest`, and delivered report. An unreadable Lead or workspace authority record fails closed. Each ready item requires exactly one Human choice:

- accept and archive;
- abandon and archive;
- request bounded follow-up.

For acceptance or abandonment, Supervisor calls `record_slp_decision` with the queue's expected epoch, revision, and evidence digest after the Human decides. Decisions are one-shot per epoch; changed evidence, epoch, revision, or an existing decision rejects a stale/silent override. The queue then exposes only `archive`, and Supervisor uses `archive_slp_workspace` with the new expected epoch/revision. Generic managed workspace archive is denied. The protected operation reserves `ARCHIVE_SENDING`; uncertain completion enters the same explicit Human resolution path instead of being retried.

For bounded follow-up, Supervisor uses `reopen_work_epoch` with the queue's expected epoch and revision; the protected operation durably reserves `REOPEN_SENDING` with a correlation ID, advances `work_epoch`, invalidates any prior acceptance, changes `HANDBACK_READY → LEASED`, and prompts the same Lead with native reverse notification disabled. A new explicit handback is then allowed once for the new epoch. Generic prompting of any managed Lead and direct lifecycle-label mutation are denied so epoch advancement cannot be bypassed.

`list_slp_decisions` also surfaces interrupted `HANDBACK_SENDING`, `REOPEN_SENDING`, or `ARCHIVE_SENDING` delivery. After Human inspection, Supervisor uses `resolve_slp_delivery` with `DELIVERED` or `NOT_DELIVERED` plus the queue's expected epoch, revision, and correlation ID; the proxy never guesses or automatically retries an uncertain operation.

`slp-decision-history.jsonl` is append-only receipt and decision evidence. Each event records epoch, revision, operation, actor/authority class, UTC timestamp, correlation ID, result, and uncertainty. History and registry files are flushed and fsynced, including the registry parent directory after atomic replacement. Append failure fails the operation before external delivery. Malformed/unreadable canonical registry data—including malformed nested lease entries or explicit invalid revisions—fails closed instead of becoming an empty/default registry. Handback and reopen also require an active workspace authority record immediately before reservation. The JSONL file is not replayed and never overrides `lead-leases.json`; an event without a matching registry transition is audit counterevidence, not lifecycle truth.

Human acceptance or abandonment remains required before Supervisor archives the workspace, which releases the lease while preserving history and local directories.

This explicit handback is event-driven. It does not use polling, schedules, or heartbeats.

## Legacy and orphaned Lead retirement

Native `idle` is not ownership truth, and archiving a workspace does not prove
that every persisted agent record gained `archivedAt`. Supervisor uses
`inspect_slp_ownership` to classify custom Lead records by workspace registry,
Paseo-owned parentage, and managed lease binding. Unparented and foreign-parent
records remain visible but do not grant mutation authority. A missing `role`
label alone does not make a custom Lead safe to ignore.

After an explicit Human-authorized checkpoint/replacement or orphan cleanup,
Supervisor may call `retire_legacy_lead` with the exact workspace and authority
digest returned by the inspection. The protected operation soft-archives only a
parent-owned custom Lead that is not the current managed lease holder. A stale
digest, unreadable authority, foreign parent, or managed lease holder fails
closed. The retirement is recorded in decision history. Generic archive remains
denied, and a new Lead must not be created until the old authority has been
retired or reconciled.

Plugins and UI may visualize `list_slp_decisions` output or invoke these protected bounded operations. Every managed operation requires `room_kind=managed_slp`; an ad-hoc lease cannot be promoted implicitly. Plugins and UI must not infer or persist an independent lifecycle state machine.

## Bounded attention

`open_room_ask` records a Lead question for the bound Supervisor, or for Human in direct mode. A Peer `DEPENDENCY_REQUEST` report creates a Peer-to-Lead question when Lead records the report. Ask IDs are deduplicated against their sender, recipient, epoch and question; `answer_room_ask` requires the responsible recipient, current epoch and expected revision. The existing Lead lease carries bounded ask records. `list_room_attention` computes 30-minute reminder and two-hour escalation signals without sending a prompt or changing authority. The owner shell may list and answer Human-addressed asks through `paseo-room-workflow asks` and `answer-ask` (preview by default).

`inspect_peer_attention` may signal a pending permission, a terminal Peer without handback, or a possible missing handback after an idle turn. These are read-only suspicions for Lead to inspect. They never set `DONE`, `ACCEPTED`, or a Human decision; `recover_peer_callbacks` remains the bounded evidence-recovery operation.

An independent Watcher may read the active agent/workspace lists and current room attention for any managed Lead. It has no decision, lifecycle, agent mutation, or engineering authority. Its hourly scheduled run reports observed signals only; it never infers acceptance, sends prompts, or changes a lease.

## Human steering and communication evidence

Human may authorize an exact Peer instruction from the owner shell using `authorize-peer-steering REQUEST.json --apply`. The request binds `leadAgentId`, `peerAgentId`, `assignmentId`, unique `grantId`, `humanInstruction`, exact `prompt` and current `expectedWorkEpoch`/`expectedRevision`. No agent tool can create a grant. A grant preserves the assignment's disposition/write mode and expires for execution when the room revision changes before its first reservation; cancel it and authorize a new grant. It does not transfer ownership, widen write scope or accept work.

The bound Supervisor consumes the grant via `steer_room_peer`, or Human via `steer-peer REQUEST.json --apply`, with only Lead/grant IDs and current epoch/revision. The proxy durably reserves each delivery, informs Lead of the exact intervention first, then sends to Peer with completion routed to Lead. The generic Supervisor-to-Peer mutation guard remains closed. Delivery receipts prove transport only; the Peer report and Lead disposition must show any effect on work.

Peer delivery requires the Lead-scoped upstream tool. It never falls back to an unscoped send, which loses native completion routing. An unavailable caller-scoped method is a rejected send, not a successful steering receipt; runtime compatibility must be checked before relying on this path.

`UNCERTAIN`, `NOTICE_SENDING` and `PEER_SENDING` never retry automatically. Human inspects exact message evidence and uses owner-shell `resolve-peer-steering` with Lead/grant IDs, `resolution=DELIVERED|NOT_DELIVERED`, evidence and current epoch/revision. Resolving a notice as delivered permits an explicit subsequent send to Peer, without sending the notice twice. Human may cancel a not-yet-sent or notice-only grant with `resolution=CANCELLED`. These resolution operations send nothing. Pending steering blocks final handback and binding withdrawal.

`REOPEN_REQUEST` reports create obligations under [the dissent protocol](DISSENT_PROTOCOL.md). Only Lead records their evidence-backed disposition through `resolve_peer_report`; unresolved and evidence-pending requests block handback, while explicit Human escalation remains in the final outcome. Changed-work disposition must match the final candidate, including legacy repositories without optional review gates.

Lead, bound Supervisor and read-only Watcher may call `list_room_observations`; Human may use `observations --lead-id`. The view joins current-epoch reports to dispatch briefs by exact Peer/assignment/epoch, plus Lead handling and Human steering receipts, inside the existing lease. Successful guarded dispatch captures a digest and bounded brief excerpt; missing hook/response correlation is `UNKNOWN`. The newest 64 reports are ordered by recorded time; omitted counts and truncated handback/brief context are explicit. This is evidence for a task-relative audit, never a score of reasoning, code quality or acceptance. Ordinary handbacks with no explicit handling record stay `UNKNOWN`.

## Optional local Git land

Human `ACCEPTED` does not authorize an automatic merge. The owner-shell `land-prepare` creates a read-only plan for an already accepted, clean, fully committed candidate in a managed room with candidate proof. `land-apply` requires a separate exact plan-digest approval and `--apply`. Before fast-forwarding a local target branch it rechecks authority epoch/revision, candidate/review evidence, source and target commit IDs, clean worktrees, and idle room writers; any drift requires a new plan. The target branch may be checked out in an explicitly named clean worktree. The operation does not commit, push, run a test command, or override a red gate. Archive after land if the same active lease is needed for the check. Manual Git processes outside managed rooms are cooperative writers and must stay quiescent during land.

## Routing

Provider/model routing comes from `~/.paseo/orchestration-preferences.json`.

- Codex/Claude Supervisor chooses `planning` with `lead_profile=stable` or `planning_claude` with `lead_profile=claude` at the start of a bounded objective. An explicit Human preference wins; otherwise the Supervisor selects from the approved routes, defaulting to `planning` when neither has a clear task advantage. Both use `stack_profile=standard`. The chosen provider/model/settings remain pinned to the Lead binding; changing them requires an explicit checkpoint and replacement.
- One Lead owns one bounded objective or workstream in one workspace. Same-objective follow-ups use the work epoch protocol; unrelated objectives use separate isolated workspaces. Concurrent work in the same repository requires disjoint write scope and contracts, otherwise the Supervisor serializes it. The one-Lead-per-workspace guard is deterministic; the cross-workspace scope check is a Supervisor workflow rule, not a filesystem-enforced invariant.
- Lead must declare the Peer `route` label. The role-aware MCP proxy checks the exact provider/model, propagates the stack profile, and normalizes required thinking.
- Standard `impl`, `impl_deep`, and `search` use GPT-6 Luna High (default), XHigh or Max. The guard preserves the selected supported level. Standard `audit` uses a fresh Claude Opus 5.5 High Reviewer in Plan Mode with `disposition=reviewer` and read-only scope.
- Codex/Claude Leads offer High, XHigh (default) and Max thinking. Preserve the selected supported level and pin it for the work epoch.
- Stock providers are invalid for internal Lead or Peer seats.
- Room launchers shadow the direct Paseo CLI; internal orchestration must use the role-aware MCP proxy.

The MCP proxy is the deterministic operational boundary. Codex hooks remain defense in depth only because app-server tool paths may bypass lifecycle hooks. None of these mechanisms is a hostile-process security sandbox; Human/top-level daemon administration remains outside the room-agent authority chain.

## Workspace isolation

Use a Paseo-managed worktree for engineering objectives that may mutate a repository, especially when more than one room can touch the same project concurrently. Use local isolation only for explicitly read-only work or work that the Human has chosen to serialize. Logical workspace separation does not isolate a shared local checkout.

## Explicit binding withdrawal

`paseo-room-workflow bindings` exposes canonical epoch/revision, including WORKING rooms. Human may `withdraw REQUEST.json --apply` after checkpointing and settling every unarchived descendant. The request requires `agentId`, `expectedWorkEpoch`, `expectedRevision` and `settlementEvidence`. Uncertain deliveries must first be resolved. Withdrawal releases authority; it neither archives runtime nor asserts acceptance. Rebinding the same released root Lead advances its epoch and pins new context, preserving history and preventing old assignment correlation from being reused.

## Scoped tasks and check receipts

For multiple Peer writers or prerequisite-sensitive work, define the optional task ledger before creating any Peer in that epoch. Use `inspect_work_tasks` for current epoch/revision, then `define_work_task` with objective, literal scope, write disposition, existing prerequisites and required repository recipes. Create each Peer with matching `task_id` and `task_revision` labels. Use scout disposition for inspection-only search/research. A ledger cannot be introduced around already-dispatched Peers.

Only dispatch a prerequisite-ready task. After quiescing its Peer, run fixed repository recipes through `run_work_check`, inspect the candidate-bound receipts, and explicitly `settle_work_task` as ACCEPTED or CANCELLED with evidence. Idle/callback does not accept a task. Reopen failed prerequisites through `reopen_work_task`; hold descendant dispatch/acceptance and quiesce their existing writers without silently releasing scope. Final handback requires all current tasks settled. An interrupted RUNNING check requires owner inspection and owner-shell `resolve-check`; never retry uncertain execution or manufacture a passing receipt. These are dispatch/evidence contracts, not filesystem sandboxes or Human acceptance.
