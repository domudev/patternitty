# patternity

This project uses patternity to distill recurring corrections and commit
patterns into a personal store at `${PATTERNITY_HOME:-~/.patternity}/patterns/`
(schema in the patternity repo's `patterns/_SCHEMA.md`) — not into this
repo. Patterns that reached `state: adopted` are already compiled into
`.github/instructions/patternity-learned.instructions.md` — no need to read
the pattern store for those during normal work.

A `userPromptSubmitted` hook (`.github/hooks/patternity-capture.json`)
already logs every prompt to `.patternity/signal.jsonl` if its path
placeholder has been pointed at a patternity clone. If asked to "run
patternity" here: also mine `.patternity/signal.jsonl` via
`uv run <patternity-repo>/scripts/mine_git_history.py`, then match that plus
recent conversation against existing patterns (bump `occurrences`/`state`)
or create new `noticed` ones. If anything
newly reached `adopted`, immediately run
`uv run <patternity-repo>/scripts/compile.py` and report what changed.

Note: Copilot resolves conflicting instructions non-deterministically, so an
override pattern here isn't a second instruction layered on top of the
annoying one — `scripts/compile.py` removes the literal offending text from
this file (or the relevant `*.instructions.md`) directly when it can find an
exact match.
