---
name: patternitty
description: >
  Learns the user's standing coding preferences so they stop repeating
  themselves, then compiles them into CLAUDE.md/AGENTS.md/.cursor/.github.
  Fire proactively (no command needed) whenever the user states a standing
  preference or repeats a correction ("always", "never", "stop doing", "use A
  not B"); also on "patternitty" / "/patternitty" / "distill my patterns" and at
  session start. You judge: durable prefs yes, one-offs no.
license: MIT
---

# patternitty

The user is lazy, proudly. They will not hand-write a CLAUDE.md, so you notice
for them.

## When to act

Proactively, mid-conversation, the moment the user states a standing
preference or repeats a correction. Record it then; don't wait for a command.
Restraint is the job: durable, generalizable prefs only. Skip one-offs,
task-specific asks, and anything already fully explicit. When unsure, leave it
at `noticed` rather than calcify a wrong rule (accept/reject and the git diff
are the safety net).

## Distilling captured signal

The live conversation is one source; the other is the **capture log** the hooks
append to `<git-root>/.patternitty/signal.jsonl` (one JSON object per turn:
`user`, `assistant`, `source`, `ts`). It's the safety net for preferences
stated when this skill wasn't invoked — but it does nothing until you read it.
At session start and on `/patternitty`, drain it:

1. Read `<git-root>/.patternitty/state.json` → `last_distilled_ts` (0 if absent).
2. Read `signal.jsonl`; consider only rows with `ts > last_distilled_ts`.
3. Apply the same restraint as live capture — durable prefs become
   `patternitty.py add`/`bump`, one-offs are dropped.
4. Write the max `ts` you processed back to `state.json` as `last_distilled_ts`,
   so the same rows are never re-distilled.

## Store & tools

Personal store: `${PATTERNITTY_HOME:-~/.patternitty}/patterns/`. Team store (if
the repo has one): `<git-root>/.patternitty/patterns/`. Prefer the CLI (keeps
frontmatter valid); run from the plugin dir Claude Code exposes as
`${CLAUDE_PLUGIN_ROOT}`:

- `patternitty.py search "<topic>"` : dedupe before creating.
- `patternitty.py add <name> --cluster <c> --agent <claude-code|cursor|copilot> --body "…"` (`--repo` for the team store).
- `patternitty.py bump <name>` : +1 occurrence, re-derives state.
- `patternitty.py set <name> <field> <value>` (or `--clear`).

Only `name` is required; other fields default. No Python? edit the markdown
directly, same result. Full schema: `patterns/_SCHEMA.md`.

## Ladder & decisions

`occurrences` 1 = `noticed`, 2 = `recurring`, 3+ = `adopted` (compiled). An
explicit "always/never" jumps straight to `adopted`. `decision: accepted`
pins a pattern; `decision: rejected` tombstones it (never compile, never
re-propose, don't resurrect it). To suppress another tool's rule: `type:
override` with `target` set to the verbatim text to remove.

## Reflect

When a pattern reaches `adopted`, run
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/compile.py"` from the project root
without asking. Give each pattern a `cluster`, and refresh `PROFILE.md` (a
sentence or two of synthesis per cluster, not a re-listing). Commit the store
locally, never push. `index.json`/`index.html` regenerate themselves.

## Reporting

Ledger, not essay. One line per pattern touched (`name: state, n=N`), one line
for what compiled. No preamble, no narrating the files you read, no restating
this. Nothing to do? Say so in one sentence.
