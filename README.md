# patternity

Learns coding patterns from how you actually work — corrections, repeated
commit fixes, confirmations — and turns them into agent instructions,
automatically, instead of waiting for you to type them out explicitly every
time.

Works alongside Claude Code, Cursor, and GitHub Copilot. It does not replace
your existing CLAUDE.md / `.cursor/rules` / Copilot instructions — it feeds
them.

## Why

Most agent-instruction workflows are explicit: you notice a recurring
correction, and *you* write it into CLAUDE.md yourself. That's tedious, and
most of the signal (what you just corrected, what you just confirmed) gets
thrown away the moment the session ends. patternity captures that signal,
tracks how often it recurs, and once it's recurred enough to be trustworthy,
reflects it into every tool's instructions on its own.

## How it works

```mermaid
stateDiagram-v2
    [*] --> observed

    observed --> suspect: recurs again
    suspect --> proven: recurs again
    observed --> proven: explicit "always" / "never"
    suspect --> proven: explicit "always" / "never"
    proven --> [*]: compiled automatically

    note right of observed
        signal captured once
        (hook or git-history mining)
    end note

    note right of suspect
        seen twice, trending
        not compiled yet
    end note

    note right of proven
        3rd+ occurrence, or an explicit
        standing statement.
        compile.py runs immediately,
        no manual approval step.
    end note

    classDef observedStyle fill:#dbe9fb,stroke:#5c8fc9,color:#1f3a5c
    classDef suspectStyle fill:#fde8b8,stroke:#c9932e,color:#5c4110
    classDef provenStyle fill:#c7e8d3,stroke:#3f9c66,color:#1c4a30
    class observed observedStyle
    class suspect suspectStyle
    class proven provenStyle
```

1. **Capture** — one shared hook script (`hooks/capture.py`) appends raw
   session signal to `.patternity/signal.jsonl` in the project you're working
   in, wired into whichever host you use: Claude Code's `Stop` hook (full
   user/assistant exchange via the transcript), Cursor's `beforeSubmitPrompt`
   hook (`.cursor/hooks.json`), or Copilot's `userPromptSubmitted` hook
   (`.github/hooks/patternity-capture.json`). All three write the same
   record shape, just tagged with a different `source`.
   `scripts/mine_git_history.py` adds a second, tool-independent source by
   mining commit messages/diffs. Cursor and Copilot hook config files ship
   with a `<path-to-patternity-clone>` placeholder since neither host has a
   Claude-Code-style plugin-root variable — fill in where you cloned this
   repo, or copy `hooks/capture.py` directly into the target project.
2. **Distill** — the `patternity` skill (`skills/patternity/SKILL.md`) reads
   `.patternity/signal.jsonl` and matches it against your personal pattern
   store at `${PATTERNITY_HOME:-~/.patternity}/patterns/` (outside any repo's
   git history — this is about you, not one project). Matching signal bumps
   a pattern's `occurrences`; new signal creates one at `state: observed`.
3. **Promote** — patterns climb `observed` (1) → `suspect` (2) → `proven`
   (3+) purely by recurrence. An explicit standing statement ("always...",
   "never...") skips straight to `proven` — it isn't an inference that needs
   corroborating. There's no manual approval step; the safety net is that
   every promotion lands as a visible, revertible git diff on the *compiled*
   files, not a pre-compile review queue.
4. **Compile** — the instant a pattern reaches `proven`, the skill runs
   `scripts/compile.py`, which renders every proven pattern into each tool's
   native format for the current project: `AGENTS.md`, `CLAUDE.md`,
   `.cursor/rules/patternity-learned.mdc`,
   `.github/instructions/patternity-learned.instructions.md`. Deterministic
   templating, no AI, idempotent (re-running just replaces the marked
   section) — so instructions/skills/agents stay dynamically in sync with
   what's actually been learned, instead of stale until someone remembers to
   run a script.

## The walking doc

`${PATTERNITY_HOME:-~/.patternity}/patterns/WALKING_DOC.md` is the running
index — one line per pattern, its state, and occurrence count — regenerated
every time the skill touches a pattern. See `patterns/_SCHEMA.md` for the
full frontmatter and the state ladder.

## Backing up your pattern store

`${PATTERNITY_HOME:-~/.patternity}` is treated like dotfiles: its own local
git repo from the start, so every promotion is a revertible commit, but
nothing is ever pushed automatically. One-time setup:

```bash
scripts/init_store.sh   # git init's the store if it isn't already a repo
```

The `patternity` skill commits there itself after every distill run
(`git -C ~/.patternity add -A && git commit -m "..."`). To back it up or
sync across machines, add a remote whenever you want — e.g. a private
personal repo, kept separate from any project's code:

```bash
gh repo create <you>/patterns --private --source ~/.patternity --remote origin --push
```

## Visualizing the store

Every `compile.py` run also regenerates
`${PATTERNITY_HOME:-~/.patternity}/patterns/index.html` — a Kanban-style
board (Noticed | Recurring | Adopted — display labels only, the underlying
`state` values are still `observed`/`suspect`/`proven`) of every pattern in
the store, at every state, across every project. It's a single
self-contained file with the data embedded inline (no server, no
fetch/CORS issue — just open it), searchable, and paginated per column so
it doesn't turn into a wall of cards:

```bash
open ~/.patternity/patterns/index.html   # macOS; xdg-open on Linux
```

`index.json` next to it is the same data in plain structured form, for
anything else you want to build on top (a CLI summary, a different view).
The board is dark-only (no light theme) — chrome, ink, and state colors all
come from the dataviz skill's validated dark-surface reference palette
rather than hand-picked values: page/surface/text from its "chart chrome &
ink" steps, and each state's wash from its dark categorical/status hues
(blue for observed, warning-amber for suspect, good-green for proven),
blended onto the surface at area-fill opacity rather than flattened into
pastel HSL. `type: override` patterns get a small solid badge in a fourth,
reserved accent (violet) instead of a recolored card, so it never gets
confused for a state and stays legible regardless of which state's
background it sits on. Occurrence count shows as three small dots, filled
up to the pattern's count. `cluster` shows as a small chip on the card
itself. Clicking a card (or Enter/Space when it's focused) opens a detail
view with the full body text, not just the truncated first line — useful
once a pattern's "why" runs longer than one line, or for reading an
override's full suppressed-text target.

The header title, column/profile headings, card/dialog titles, and cluster
chips use Caveat (a handwriting webfont) as a one-off flourish; everything
else read as data — body/"why" text, state and scope chips, occurrence
counts — stays in Inter, a plain, small-size-legible sans. Both load from
Google Fonts with a system-font fallback if offline.

If `${PATTERNITY_HOME:-~/.patternity}/patterns/PROFILE.md` exists, it's
rendered as a summary panel above the board — the skill's synthesis of
proven patterns grouped by `cluster` (tooling, code-style, workflow, ...),
e.g. "you default to uv over pip/venv, stated across multiple projects".
That's the "who is this user" digest; the board underneath stays the
detailed ledger.

## Fine-grained scoping

The store is global, but a pattern doesn't have to apply everywhere:
`applies_to.project` scopes a pattern to the repo(s) it's actually been seen
in, and only widens to `"*"` once it's shown up across more than one
project. `applies_to.tool`/`glob` scope by host and file pattern the same
way.

## Overrides

A pattern can target and suppress a rule from another plugin/instruction
file that's annoying you, instead of only adding new rules. Set
`type: override` and `target` to the literal line/snippet you want gone.
The compiler removes that exact text from the file it appears in once the
override reaches `proven`; if the text isn't found verbatim (the source
file changed), it's flagged under a `## Overrides (needs manual check)`
section instead of silently failing. Copilot in particular resolves
conflicting instructions non-deterministically, so removing the offending
text directly is the only reliable way to suppress it there.

## Install

Clone this repo once (`git clone https://github.com/domudev/patternity`),
then wire it into whichever host(s) you use, per project:

**Claude Code** — real plugin install, no file copying needed:
```
/plugin marketplace add domudev/patternity
/plugin install patternity@patternity
```
This repo is private, so `/plugin marketplace add` needs GitHub access to
your account — if it can't fetch the marketplace, flip the repo to public
or fall back to referencing `skills/patternity/SKILL.md` and
`hooks/capture-hooks.json` directly from your clone.

**Cursor** and **GitHub Copilot** don't have an install command — their
hooks are just files in the target repo, so `scripts/install.sh` copies and
path-fills them for you:
```bash
# from your patternity clone
scripts/install.sh /path/to/target-project        # both Cursor + Copilot
scripts/install.sh /path/to/target-project cursor  # just one
scripts/install.sh /path/to/target-project copilot
```
It skips (and prints instead) any file that already exists in the target,
so it won't clobber hooks/instructions you've already customized.

## Quickstart

```bash
# in the project you want patternity to learn from
uv run /path/to/patternity/scripts/mine_git_history.py
# ... use Claude Code/Cursor/Copilot for a while; hooks log signal automatically ...

# ask your agent to run the patternity skill, e.g.:
#   /patternity-distill
# proven patterns compile automatically; check `git diff` in your project
```

## Scope of v0

- Patterns are personal to the user (global store, outside any repo's git
  history) — not tied to one project. Compiled *output* is still per-project
  (CLAUDE.md etc. live in each repo), and `applies_to.project` keeps
  single-project observations from leaking everywhere by default.
- Capture sources: Claude Code `Stop` hook, Cursor `beforeSubmitPrompt` hook,
  Copilot `userPromptSubmitted` hook, and git history mining.
- Adapters cover Claude Code, Cursor, and Copilot. Adding another tool means
  adding one render function in `scripts/compile.py`.

## Repo layout

- `skills/patternity/SKILL.md` — canonical distillation/promotion logic
- `commands/` — `/patternity-distill`, `/patternity-compile` slash commands
- `hooks/` — shared capture hook wired into Claude Code, Cursor, and Copilot
- `scripts/` — `mine_git_history.py`, `compile.py`, shared `_lib.py` parser (plain `uv run` scripts, no project/deps needed), plus `install.sh` (wires Cursor/Copilot into a target project) and `init_store.sh` (git-inits the personal pattern store)
- `patterns/` — schema doc + reference example (the real store is `${PATTERNITY_HOME:-~/.patternity}/patterns/`)
- `viz/template.html` — the visualization `compile.py` fills in and writes to the store as `index.html`
- `.claude-plugin/` — `plugin.json` + `marketplace.json` so this repo installs directly via `/plugin marketplace add domudev/patternity`
- `.cursor/rules/`, `.github/`, `.cursor/hooks.json` — static pointers so Cursor/Copilot know patternity exists, plus where the compiled learned-pattern files land
