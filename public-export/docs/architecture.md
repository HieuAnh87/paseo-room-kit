# Reusable architecture

The public example separates authority from execution:

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
- The Supervisor is the front door and relays a faithful brief.
- The Lead decomposes engineering work, chooses an approach within those
  decisions, validates evidence, and accepts or rejects the result.
- The Peer owns only the assignment given by the Lead and returns evidence,
  uncertainty, and counterevidence.

The control plane may manage lifecycle events, but a finish notification is not
engineering acceptance. The data plane remains the project workspace and its
normal review tools. A role-aware boundary should deny an operation before it
reaches the control plane when the caller lacks that role's authority.

Prefer a managed workspace when more than one engineering room may mutate a
checkout. Keep credentials, local identities, and provider-specific settings in
machine-local configuration rather than in reusable examples.
