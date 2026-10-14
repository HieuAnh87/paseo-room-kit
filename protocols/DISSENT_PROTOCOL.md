# Lead–Peer dissent protocol

Dissent is evidence, not a veto and not a failure. A Peer must surface material disagreement instead of silently changing direction or silently complying with a risky brief. The Lead owns the engineering decision inside accepted authority. Do not require disagreement for its own sake. Distinguish the goal, mandatory constraints and provisional design choices in the brief; a narrow write boundary does not forbid questioning a premise outside it.

## Peer handback

When dissenting, return:

- `Current direction`: what the current brief or Lead direction says.
- `Claim`: the specific point of disagreement.
- `Evidence`: observed facts, tests, code references, or experiment results.
- `Counterevidence`: facts that weaken the Peer claim or remain unresolved.
- `Risk`: consequence if the current direction is retained.
- `Requested resolution`: the smallest decision or verification needed from Lead.

Do not bypass Lead to contact Human or the governance channel. Stop before an irreversible choice when authority is unclear.

## Lead outcomes

Lead gives each material dissent one current disposition:

- `RESOLVED_BY_LEAD`: Lead decides within engineering authority and records rationale/evidence.
- `NEEDS_MORE_EVIDENCE`: Lead assigns one bounded verification or rebuttal round with an owner and checkpoint, then re-evaluates. The obligation remains open.
- `ESCALATED_TO_HUMAN`: the issue crosses objective, accepted decision, product trade-off, authority, ownership, or irreversible-risk boundaries. Identify the owner and decision checkpoint; this is an unresolved owner decision, not engineering success.

After closing the dissent, Lead sends the outcome and next action back to Peer. No majority vote, endless debate, or silent evidence suppression. Supervisor may inspect the process for ignored evidence or repeated unresolved dissent, but does not decide the technical content.

## Durable disposition

Record the correlated `REOPEN_REQUEST` using `record_peer_report`. This creates a Peer-to-Lead obligation in the existing lease. Lead uses `resolve_peer_report` with `reportId`, `outcome`, non-empty `decision`, `evidence`, `nextAction`, boolean `changesWork`, and current `expectedWorkEpoch`/`expectedRevision`. Pending and escalated outcomes also require `owner` and `checkpoint`. A generic ACK through `answer_room_ask` cannot close it.

Use `changesWork=true` after a correction has changed the candidate, with `candidateDigest` from the current snapshot and fresh verification evidence. Later integration invalidates that proof: reverify the same decision on the new candidate, or record a new report for a changed decision. This check also applies to repositories without the optional candidate gate. `changesWork=false` records a decision without claiming a code change; the proxy cannot prove the truth or completeness of supplied evidence.

Final handback is blocked by an unhandled request or `NEEDS_MORE_EVIDENCE`. Explicit escalation may accompany final handback, with its decision/evidence/next action automatically preserved in the outcome for Human. An old receipt without an ask remains pending and can be resolved by Lead after the Peer is archived. Prior-epoch receipts remain history, never evidence of current acceptance.

`list_room_observations` exposes brief, handback and disposition receipts read-only. Missing or truncated context limits the observation; it does not prove a violation, a sound design or acceptance.
