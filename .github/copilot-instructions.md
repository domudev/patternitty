# patternitty

This project uses patternitty to distill recurring corrections and commit
patterns into a personal store at `${PATTERNITTY_HOME:-~/.patternitty}/patterns/`
(schema in the patternitty repo's `patterns/_SCHEMA.md`) — not into this
repo. Patterns that reached `state: adopted` are already compiled into
`.github/instructions/patternitty-learned.instructions.md` — no need to read
the pattern store for those during normal work.

A `userPromptSubmitted` hook (`.github/hooks/patternitty-capture.json`)
already logs every prompt to `.patternitty/signal.jsonl` if its path
placeholder has been pointed at a patternitty clone. If asked to "run
patternitty" here: also mine `.patternitty/signal.jsonl` via
`uv run <patternitty-repo>/scripts/mine_git_history.py`, then match that plus
recent conversation against existing patterns (bump `occurrences`/`state`)
or create new `noticed` ones. If anything
newly reached `adopted`, immediately run
`uv run <patternitty-repo>/scripts/compile.py` and report what changed.

Note: Copilot resolves conflicting instructions non-deterministically, so an
override pattern here isn't a second instruction layered on top of the
annoying one — `scripts/compile.py` removes the literal offending text from
this file (or the relevant `*.instructions.md`) directly when it can find an
exact match.
