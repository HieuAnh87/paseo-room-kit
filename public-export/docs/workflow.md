# Reusable workflow

> Authority update: Supervisor is optional. Direct Human→root Lead and an independently bound root Supervisor observer use the same canonical lease and protected epoch operations as the compatible parented bootstrap. Parentage alone is not authority. `submit_work_result` resolves the active binding; direct mode persists a Human-queue receipt. See the shared [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) for repository gates, correlated reports, candidate review and owner-shell commands.


Give each Peer one bounded assignment; concurrent writers need disjoint ownership or separate worktrees. A Lead brief should name the objective,
ownership boundary, expected handback, and validation evidence.

## Assignment

1. The Lead states the smallest change or inspection that is in scope.
2. The Peer checks the surrounding code and preserves unrelated work.
3. The Peer implements or inspects only that slice.
4. The Peer runs focused validation and reports the exact commands and results.

## Handback

Every terminal handback begins with one outcome:

```text
Task outcome: DONE|BLOCKED_PERMISSION|NEEDS_LEAD_DECISION|FAILED
```

It then records what changed or was inspected, validation evidence, remaining
uncertainty, counterevidence, and any requested resolution. A `DONE` callback
means the bounded turn ended; the Lead still decides whether the engineering
result is accepted.

Managed Peers carry the same `room_kind` and current `work_epoch` as their
Lead. Native callbacks are primary. If one expected callback does not render,
the Lead may invoke `recover_peer_callbacks` once; the proxy validates
parent/workspace/epoch and stores a digest-deduplicated receipt instead of
normalizing repeated activity reads.

Final handback, Human accept/abandon, bounded reopen, uncertain-delivery
resolution, and archive are protected epoch/revision operations. Generic prompt
and archive paths cannot bypass those fences. Legacy Lead cleanup uses an
authority digest derived from workspace, Paseo-owned parentage, and lease
binding—not native idle status.

When there is material disagreement, include `Current direction`, `Claim`,
`Evidence`, `Counterevidence`, `Risk`, and `Requested resolution`. Do not make
an irreversible choice while authority is unclear.

## Review gates

- inspect the diff and staged file list;
- validate examples without provider credentials;
- scan the assembled public artifact;
- record unresolved uncertainty before publication.

## Project gates and evidence

Choose the smallest topology satisfying repository gates. Neutral briefs must permit reopen, dependency and blocker reports; tests verify established contracts rather than decide unknown APIs. Lead reads `inspect_work_context` and the repository protocol before dispatch.

Assignments carry immutable identity, disposition and write_mode. Lead records version-1 correlated JSON with `record_peer_report` before archiving Peer. REVIEW requires a Reviewer assignment, candidate digest, verdict and evidence. For gated work, pause writers and use `inspect_work_candidate`; changes to HEAD, index or included files invalidate prior candidate approval. Independent review requires approval with no unresolved findings. Acceptance and accepted archive recheck the candidate.

`submit_work_result` delivers via the bound observer or persists a direct Human-queue receipt. Owner-shell `bindings` and `decisions` expose versions and choices. JSON-file `decide`, `reopen`, `resolve`, `archive`, `withdraw` commands preview unless `--apply` is supplied. Drift requires checkpoint and explicit replacement, not self-rebinding. Missing repository policy preserves legacy behavior without enabling candidate gates. The contracts validate metadata/correlation, not actual test execution, model attestation or OS write permissions.

## Attention and optional Git land

Runtime pins use version 2 and normalize native configured/effective model, thinking and mode, rejecting missing or conflicting values. Unversioned pins remain explicitly unverified for the current epoch; no automatic upgrade or new epoch is permitted. Owner-shell `rebind-runtime` previews a digest-bound replacement at a handback checkpoint with settled tasks, quiescent checks and archived descendants; applying it requires independent launch evidence and exact epoch/revision/digest. Rebinding never grants Human acceptance. A null Peer self-ID can be filled only from one matching canonical post-create assignment and native record, with an explicit correlation receipt.

Human may authorize an exact Peer instruction through owner-shell `authorize-peer-steering REQUEST.json --apply`, binding Lead, Peer, assignment, instruction and current epoch/revision. Bound Supervisor consumes it with `steer_room_peer`; Human uses `steer-peer`. Lead notice precedes Peer delivery, and completion stays routed to Lead. No generic Supervisor-to-Peer permission is added. Uncertain delivery needs Human evidence and owner-shell `resolve-peer-steering`, never automatic retry. See `protocols/WORKFLOW_PROTOCOL.md` for fields and states.

Lead records material `REOPEN_REQUEST` reports, then uses `resolve_peer_report` with decision/evidence/next action. Pending evidence blocks handback; explicit Human escalation stays in the final outcome. Changed-work evidence is bound to the final candidate, including legacy repositories. Generic ACK does not close dissent. Read-only `list_room_observations` or owner-shell `observations --lead-id LEAD_ID` joins dispatch brief, report, disposition and steering receipts. Missing/truncated context is unknown, never an artifact or acceptance verdict. Flow exposes pending reopen and uncertain steering from that same lease.

Lead can record a bounded question for the bound Supervisor or direct Human with `open_room_ask`. A Peer `DEPENDENCY_REQUEST` recorded by Lead becomes a question to Lead. Owner shell uses `paseo-room-workflow asks --lead-id LEAD_ID` and previews `answer-ask REQUEST.json` before `--apply`. Reminders, escalation and possible missing Peer handback are read-only attention signals; they neither send prompts nor decide a result.

`land-prepare --lead-id LEAD_ID --target-branch BRANCH` previews a local fast-forward for an already Human-accepted, clean, committed candidate. `land-apply PLAN.json --approve-plan-digest DIGEST --apply` separately approves and applies that exact plan after rechecking lease, candidate, review, source and base SHAs, clean worktrees and idle writers. A checked-out base needs `--target-worktree PATH` at prepare. Land does not commit, push or run a test command. Human acceptance alone never lands a branch; archive the room afterward if its active lease is needed for land.

## Scoped tasks and check receipts

For multiple Peer writers or prerequisite-sensitive work, define the optional task ledger before creating any Peer in that epoch. Use `inspect_work_tasks` for current epoch/revision, then `define_work_task` with objective, literal scope, write disposition, existing prerequisites and required repository recipes. Create each Peer with matching `task_id` and `task_revision` labels. Use scout disposition for inspection-only search/research. A ledger cannot be introduced around already-dispatched Peers.

Only dispatch a prerequisite-ready task. After quiescing its Peer, run fixed repository recipes through `run_work_check`, inspect the candidate-bound receipts, and explicitly `settle_work_task` as ACCEPTED or CANCELLED with evidence. Idle/callback does not accept a task. Reopen failed prerequisites through `reopen_work_task`; hold descendant dispatch/acceptance and quiesce their existing writers without silently releasing scope. Final handback requires all current tasks settled. An interrupted RUNNING check requires owner inspection and owner-shell `resolve-check`; never retry uncertain execution or manufacture a passing receipt. These are dispatch/evidence contracts, not filesystem sandboxes or Human acceptance.

## Execution mode

New owner-shell root bindings support --mode L (tiny self-work; no Peer), LP (bounded direct Human; default), and SLP (requires --supervisor-id). Repository gates still apply. Preview bind before --apply. Existing bindings are not migrated. The optional callback-plugin supplies fenced ended-turn notifications when native scoped tools are unavailable; install it after its tests/typecheck and the shared CLI. See callback-plugin/OVERVIEW.md. Delivery and acceptance remain separate.
