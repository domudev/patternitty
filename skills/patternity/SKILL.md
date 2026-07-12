---
name: patternity
description: >
  Distills captured session signal (.patternity/signal.jsonl, from the Stop/
  prompt-submit hooks and git-history mining) into a personal, cross-project
  pattern store at ${PATTERNITY_HOME:-~/.patternity}/patterns/, promotes
  patterns through observed -> suspect -> proven as they recur, and compiles
  proven ones into CLAUDE.md/AGENTS.md/.cursor/.github instructions right
  away. Use when the user says "patternity", "/patternity-distill", "learn my
  patterns", "distill patterns", or asks what patternity has observed/proven.
  Also use proactively at the start of a session if .patternity/signal.jsonl
  has grown substantially since the walking doc was last updated. Do NOT use
  for one-off requests already stated explicitly — this is for signal that
  was never said explicitly.
license: MIT
---

# patternity

You are turning implicit signal into explicit rules, personal to the user
across every project they work in — not just this repo. A user who corrects
the same thing three times didn't want to type a CLAUDE.md entry, they
wanted the agent to notice.

## Input

Read `.patternity/signal.jsonl` in the current project (one JSON object per
line). Three kinds of records:

- `source: "claude-stop-hook"` — `{user, assistant}` text from a completed
  Claude Code turn. Look for corrections ("no, don't...", "stop doing X",
  "actually use Y"), and confirmations (user accepts an unusual choice
  without pushback, or says "yes exactly", "perfect").
- `source: "cursor-prompt-hook"` / `"copilot-prompt-hook"` — `{user}` text
  captured at prompt-submit time (no assistant reply attached yet). Same
  correction/confirmation signal to look for, just one-sided.
- `source: "git-history"` — `{sha, subject, body, shortstat}` per commit.
  Look for repeated fix/revert themes — a signal the agent should have
  caught it upfront.

## The pattern store

Read/write `${PATTERNITY_HOME:-~/.patternity}/patterns/` — global, not this
project's `patterns/` directory (that one is just the schema reference).
Schema: `patterns/_SCHEMA.md`. Index: `WALKING_DOC.md` in the same
directory, regenerated every time you touch a pattern.

For each piece of signal:

1. Check whether it matches an existing pattern file (same underlying
   preference, possibly worded differently). If yes, bump `occurrences` and
   re-derive `state`: 1 -> `observed`, 2 -> `suspect`, 3+ -> `proven`. An
   explicit standing statement ("always...", "never...", "from now on...")
   goes straight to `proven` regardless of count — it isn't an inference
   that needs corroborating.
2. If no, and the signal is a genuine correction/confirmation (not a one-off
   already fully explicit in that same message), create a new pattern file
   at `state: observed`, `occurrences: 1`.
3. If the signal targets suppressing another plugin's rule the user finds
   annoying (a different SKILL.md, a `.cursor/rules/*.mdc` line, a
   `.github/copilot-instructions.md` line), set `type: override` and copy
   the exact offending text into `target` verbatim — the compiler does
   literal text matching, not fuzzy matching, so precision here matters more
   than for additive patterns. Explicit override requests go straight to
   `proven` too, same rule as above.
4. Use `applies_to.project` to scope narrowly (the observing project's name)
   until a pattern has shown up in more than one project — don't default a
   single-project observation to `project: "*"`.
5. Rewrite `WALKING_DOC.md` to reflect the current state of every pattern.
6. If `${PATTERNITY_HOME:-~/.patternity}` isn't a git repo yet, run
   `<patternity-repo>/scripts/init_store.sh` once (idempotent, safe to call
   every time). Then commit the change there: `git -C "${PATTERNITY_HOME:-$HOME/.patternity}" add -A && git -C "${PATTERNITY_HOME:-$HOME/.patternity}" commit -m "<name>: <observed|suspect|proven> (n=<occurrences>)"`.
   Local commit only — never push, that's a separate, user-initiated step
   (see README "Backing up your pattern store").

## Dynamic reflection

If any pattern newly reached `proven` in this pass, immediately run
`uv run <patternity-repo>/scripts/compile.py` from the current project's
root — don't wait for the user to ask, and don't ask them to approve first.
That's what keeps CLAUDE.md/AGENTS.md/`.cursor/rules`/`.github/instructions`
in sync with what's actually been learned instead of stale. Then tell the
user in one line what changed and where (which files, which pattern) so they
can look at the diff — informing them after the fact, not gating on
approval before.
