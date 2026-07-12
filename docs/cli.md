# CLI & server

## `patternitty.py` — the tool surface

An agent or skill queries and edits the store through one CLI, called via
Bash — no MCP server, no daemon, identical across Claude Code / Cursor /
Copilot:

```bash
uv run scripts/patternitty.py search "testing style"       # BM25, relevance-ranked
uv run scripts/patternitty.py search "TODO|FIXME" --regex   # structural / exact
uv run scripts/patternitty.py get uv-pref --json
uv run scripts/patternitty.py list --state adopted --json
uv run scripts/patternitty.py list --tier repo             # team-tier only
uv run scripts/patternitty.py add lint-on-save --cluster workflow --body "…"
uv run scripts/patternitty.py add team-rule --repo --body "…"   # committed team store
uv run scripts/patternitty.py bump uv-pref                  # +1 occurrence, re-derive state
uv run scripts/patternitty.py set uv-pref decision accepted # (--clear to remove)
uv run scripts/patternitty.py dashboard [--serve]
```

**The file format is the API; this CLI is sugar.** The store is plain
markdown — no Python? grep and edit the files directly, same result. The CLI
exists to keep frontmatter valid, keep the occurrence ladder consistent, and
give relevance-ranked search (BM25) raw grep can't. Search is computed on
demand — no index, no dependency (fine for a personal store; a cached index
only matters in the thousands).

Only `name` is required for `add`; every other field defaults on read (see
[patterns](patterns.md)).

## The localhost server

`dashboard --serve` runs a stdlib `http.server` on `127.0.0.1` (zero deps)
and routes every action through it, so the board is live instead of a
snapshot. It blocks until Ctrl-C — run it from a terminal.

| Method | Route | Does |
|---|---|---|
| GET | `/` | the dashboard HTML |
| GET | `/search?q=&regex=1&limit=` | relevance/regex search |
| GET | `/list?state=&cluster=&tier=` | filtered list |
| GET | `/get?name=` | one pattern |
| POST | `/decide` `{name, decision}` | persist accept/reject/clear |
| POST | `/add` `{name, …}` | create a pattern |
| POST | `/bump` `{name}` | bump occurrences |
| POST | `/compile` | apply adopted patterns to the repo the server started in |

Mutating routes return the refreshed index so the page re-renders in one
round-trip. Routes are a `(method, path) → handler` table dispatched once;
each handler reuses the same core functions the CLI does, so a command and
its route can't drift.

Localhost-only, no auth — fine for a personal tool. If this ever becomes
multi-user/hosted, that's the first thing to lock down (and the point where a
real framework would replace stdlib).
