# Lead–Peer dissent protocol

Dissent is evidence, not a veto and not a failure. A Peer must surface material disagreement instead of silently changing direction or silently complying with a risky brief. The Lead owns the engineering decision inside accepted authority.

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

Lead closes each material dissent with exactly one outcome:

- `RESOLVED_BY_LEAD`: Lead decides within engineering authority and records rationale/evidence.
- `NEEDS_MORE_EVIDENCE`: Lead assigns one bounded verification or rebuttal round, then re-evaluates.
- `ESCALATED_TO_HUMAN`: the issue crosses objective, accepted decision, product trade-off, authority, ownership, or irreversible-risk boundaries.

After closing the dissent, Lead sends the outcome and next action back to Peer. No majority vote, endless debate, or silent evidence suppression. Supervisor may inspect the process for ignored evidence or repeated unresolved dissent, but does not decide the technical content.
