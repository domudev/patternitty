# Dashboard

Every `compile.py` run regenerates
`${PATTERNITTY_HOME:-~/.patternitty}/patterns/index.html` — a Kanban board
(**Noticed | Recurring | Adopted**) of every pattern, at every state, across
every project. Open it:

```bash
open ~/.patternitty/patterns/index.html   # macOS; xdg-open on Linux
# or, for interactive accept/reject:
uv run scripts/patternitty.py dashboard --serve
```

It's a single self-contained file with data embedded inline (no server
needed to view), searchable, and paginated per column. Design notes: dark
only; state is carried by a crisp accent (glowing left bar + dots + tinted
cluster chip), not a full-card tint — slate (noticed) → amber (recurring) →
green (adopted). `type: override` patterns get a violet badge (a reserved
fourth accent, matching the logo). Clicking a card opens a bottom drawer with
the full, markdown-rendered body. Titles/headings/clusters use Caveat
(handwriting); data stays in Ubuntu.

## Accept / reject

Both `state` and `decision` live in the pattern's frontmatter — nothing is
tracked only in the browser. `state` is the automatic ladder; `decision` is
your manual override:

- **accept** — pins a pattern to Adopted / compiled regardless of count
- **reject** — tombstones it: dropped to the collapsed "Rejected" tray, never
  compiled, and the skill won't re-propose it

Three ways to apply a decision, least friction first:

1. **Tell your agent** — "reject the tabs pattern", "accept uv-pref". The
   skill sets `decision` and recompiles. This is the normal plugin flow.
2. **`dashboard --serve`** — serves the board on `127.0.0.1` with write-back,
   so clicking ✓/✕ **persists instantly**, plus a `↻ recompile` button that
   applies adopted patterns to the current repo. Blocks until Ctrl-C; run it
   from a terminal, not via the agent (it would hang the turn).
3. **Static `file://` fallback** — a plain double-click can't write to disk,
   so clicks stage pending decisions and show a `decide.py accept:… reject:…`
   command to run.

All three set the same `decision` field; the next compile honors it
(`is_effective_adopted`). Clearing a decision hands the pattern back to the
automatic ladder.

## The profile panel

If `${PATTERNITTY_HOME:-~/.patternitty}/patterns/PROFILE.md` exists, it renders
as a summary panel above the board — the skill's narrative synthesis of
adopted patterns grouped by cluster ("you default to uv over pip/venv, stated
across multiple projects"). That's the "who is this user" digest; the board
below is the detailed ledger.
