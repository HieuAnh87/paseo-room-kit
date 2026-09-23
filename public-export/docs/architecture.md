# Reusable architecture

> Authority update: Supervisor is optional. Direct Human→root Lead and an independently bound root Supervisor observer use the same canonical lease and protected epoch operations as the compatible parented bootstrap. Parentage alone is not authority. `submit_work_result` resolves the active binding; direct mode persists a Human-queue receipt. See the shared [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) for repository gates, correlated reports, candidate review and owner-shell commands.


The compatible bootstrap below is one arrangement. Direct Human→Lead and independently bound Supervisor observation are also valid. The architecture separates authority from execution:

```text
Human
  │ objective, accepted decisions, final authority
  ▼
Supervisor
  │ relay and lifecycle observation
  ▼
Lead
  │ engineering ownership and validation
  └── Peer: one bounded implementation, search, or review assignment
```

## Boundaries

- The Human sets the objective, accepted decisions, and product constraints.
- An optional bound Supervisor observes governance and relays a faithful brief. Human may bind a root Lead directly.
- The Lead decomposes engineering work, chooses an approach within those
  decisions, validates evidence, and accepts or rejects the result.
- The Peer owns only the assignment given by the Lead and returns evidence,
  uncertainty, and counterevidence.

The control plane may manage lifecycle events, but a finish notification is not
engineering acceptance. The data plane remains the project workspace and its
normal review tools. A role-aware boundary should deny an operation before it
reaches the control plane when the caller lacks that role's authority.

Managed lifecycle authority lives in a version-2 lease registry with
`room_kind`, work epoch, revision, evidence digest, and reserved delivery
transitions. Paseo 0.8 native tools are disabled per internal custom provider;
the role-aware proxy is the only control surface. A future plugin may be a thin
UI over protected operations, never a second lifecycle state machine.

Prefer a managed workspace when more than one engineering room may mutate a
checkout. Keep credentials, local identities, and provider-specific settings in
machine-local configuration rather than in reusable examples.

## Four layers

Paseo provides identity, sessions, placement and native lifecycle/events. Common proxy/guard contracts enforce authority binding, correlation, epochs and candidate proof. Role invariants, repository tactics and assignments shape the workflow. Provider adapters load instructions and transport tools/reports; changing an adapter does not change project authority.

Repository tactics live in `.orchestration/workspace-protocol.md` with machine gates in `.orchestration/workflow.json`. `paseo-room-workflow init` previews missing files, and `bind` previews authority for an existing root Lead. Both require `--apply` to mutate. Optional `--supervisor-id` binds observation without reparenting. Read [workflow protocol](../protocols/WORKFLOW_PROTOCOL.md) before choosing gates or using the Human queue.
