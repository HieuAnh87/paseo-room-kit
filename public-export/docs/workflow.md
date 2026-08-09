# Reusable workflow

Use one bounded assignment at a time. A Lead brief should name the objective,
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

When there is material disagreement, include `Current direction`, `Claim`,
`Evidence`, `Counterevidence`, `Risk`, and `Requested resolution`. Do not make
an irreversible choice while authority is unclear.

## Review gates

- inspect the diff and staged file list;
- validate examples without provider credentials;
- scan the assembled public artifact;
- record unresolved uncertainty before publication.
