---
name: patternity
description: >
  Distills captured session signal (.patternity/signal.jsonl, from the Stop/
  prompt-submit hooks and git-history mining) into a personal, cross-project
  pattern store at ${PATTERNITY_HOME:-~/.patternity}/patterns/, promotes
  patterns through observed -> suspect -> proven as they recur, clusters them
  into a synthesized PROFILE.md, and compiles proven ones into
  CLAUDE.md/AGENTS.md/.cursor/.github instructions right away. Use when the
  user says "patternity", "/patternity", "learn my patterns",
  "distill patterns", or asks what patternity has observed/proven/learned
  about them. Also use proactively at the start of a session if
  .patternity/signal.jsonl has grown substantially since the walking doc was
  last updated. Do NOT use for one-off requests already stated explicitly —
  this is for signal that was never said explicitly.
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

**Prefer the `patternity.py` CLI over hand-editing files** when it fits — it
keeps frontmatter valid and the occurrence ladder consistent:
- `patternity.py search "<topic>"` (BM25, relevance-ranked) or `--regex` —
  check whether a matching pattern already exists before creating a new one.
- `patternity.py get <name> --json`, `list [--state/--cluster] --json`.
- `patternity.py add <name> --type … --cluster … --body "…"` to create a new
  `observed` pattern; `bump <name>` to increment occurrences and re-derive
  state; `set <name> <field> <value>` for other frontmatter edits.
If Python isn't available, the files are plain markdown — read/grep/edit them
directly (same result; the CLI is just sugar over the file format). Whichever
you use, the store is the single source of truth — never keep pattern state
anywhere else.

For each piece of signal:

1. Check whether it matches an existing pattern file (same underlying
   preference, possibly worded differently). If yes, bump `occurrences` and
   re-derive `state`: 1 -> `observed`, 2 -> `suspect`, 3+ -> `proven`. An
   explicit standing statement ("always...", "never...", "from now on...")
   goes straight to `proven` regardless of count — it isn't an inference
   that needs corroborating. **Exception:** if the matched pattern has
   `decision: rejected`, leave it alone entirely — don't bump `occurrences`,
   don't change `state`, don't resurrect it. The user tombstoned it on
   purpose; re-proposing it defeats the reject. (A pattern with
   `decision: accepted` stays accepted; you may still bump its `occurrences`
   for the record, but never demote it.)
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
5. Set/update `cluster` on the pattern: reuse an existing cluster name from
   the store if the pattern fits one thematically, mint a new short one only
   if nothing fits. This is what turns a pile of rules into a profile — see
   "Clustering into a profile" in `patterns/_SCHEMA.md`.
6. Rewrite `WALKING_DOC.md` to reflect the current state of every pattern,
   and `PROFILE.md` to reflect the current clusters (group proven patterns
   under a `## <cluster>` heading each, with a sentence or two of synthesis,
   not just a re-listing of pattern bullets).
7. The store self-initializes — `patternity.py add`/`compile.py`/etc. create
   the directory and git-init it on first write, so there's no separate init
   step and no "store not initialized" dead-end. After writing, commit the
   change there: `git -C "${PATTERNITY_HOME:-$HOME/.patternity}" add -A && git -C "${PATTERNITY_HOME:-$HOME/.patternity}" commit -m "<name>: <observed|suspect|proven> (n=<occurrences>)"`.
   Local commit only — never push, that's a separate, user-initiated step
   (see README "Backing up your pattern store").

## Dynamic reflection

If any pattern newly reached `proven` in this pass, immediately run
`uv run <patternity-repo>/scripts/compile.py` from the current project's
root — don't wait for the user to ask, and don't ask them to approve first.
That's what keeps CLAUDE.md/AGENTS.md/`.cursor/rules`/`.github/instructions`
in sync with what's actually been learned instead of stale.

## Reporting — short, poignant, no BS

Report like a ledger, not an essay. Rules:
- One line per pattern touched: `name — state (n=N)` plus at most a short
  clause of why. One line for what compiled/where.
- No preamble, no restating these instructions, no narrating the files you
  read, no justifying inaction beyond a brief clause.
- Nothing to distill? Say it in one sentence and stop.
- Never pad to sound thorough. If the whole report is one line, ship one line.
