# UI specialists

UI work defaults to `ui` → `antigravity-cli/gemini-3.8-flash`, High, `accept-edits`. This requires the Antigravity CLI provider plugin (`paseo-plugin-antigravity-cli`, verified locally at 0.9.3); the room-kit installer does not install it. The disabled `gemini-ui` ACP provider is legacy and is not the active route. Check live provider availability and model catalog after `paseo reload` before dispatch. Missing capability is a blocker, never a reason to route silently to Codex.

`ui_opus` → `claude-ui/claude-opus-5-5`, High, `acceptEdits` is an explicit alternative. Lead must record a non-empty `labels.ui_choice_reason` naming the Human request or its deliberate choice. No automatic retry, model switch, or extra Peer after failure. This is a writable engineering Peer with its own Claude instructions/settings, not the read-only `claude-reviewer` seat.

Both routes use the existing task reservations, assignment/epoch correlation, callback relay, report and settlement flow in LP or SLP. Lead owns engineering acceptance; Human acceptance remains separate. Scope UI changes to named frontend paths, preserve other writers, request Lead decisions for backend/API changes, and include rendered evidence at wide/compact widths and light/dark themes when available. A screenshot alone is not a functional test.

Paseo MCP injection stays disabled globally and for both UI providers. Antigravity's native tool and subagent constraints are cooperative prompt rules, not runtime hooks or OS isolation; the provider does not expose the same deterministic local hooks as Claude. Do not claim parity. Its own browser/MCP availability must be verified per launch. Claude UI uses the bounded Peer Bash guard and denies Agent/Task/Workflow while allowing Edit/Write. Never reuse the implementation Peer as its own independent Reviewer.

## Trial

The first bounded trial targets the Jira snapshot plugin list and detail UI, preserving snapshot-only reads, safe links, search/filter, freshness/coverage notices and backend behavior. It runs in a separate Git worktree with one Antigravity Peer. Runtime and visual results are recorded after the trial; configured models alone are not completion evidence.

## Headless permissions and callback admission

Before the first UI turn, inspect the selected Antigravity account's permissions. Workspace files are implicitly allowed, but external protocol/skill/preview paths and shell commands may be soft-denied in headless mode. Prepare exact `read_file(path)` and `command(command-prefix)` allow rules for the approved task, preserve existing settings, and remove temporary rules afterward. Never enable skip-all-permissions to make a smoke test pass. Follow the [official headless permission contract](https://www.antigravity.google/docs/cli/headless/) and [permission syntax](https://www.antigravity.google/docs/permissions?tab=cli).

The callback plugin explicitly admits `antigravity-cli` and `claude-ui` lifecycle events; the owner CLI still validates role, canonical assignment, epoch and recipient. Provider names alone grant no authority. An empty successful CLI response is not a handoff and must surface as NEEDS_LEAD_DECISION.
