---
description: Open the patternity dashboard (live server with accept/reject write-back)
---

Start the dashboard server **in the background** (it blocks, so never run it
in the foreground or it will hang this turn); it opens itself in the browser:

```
nohup uv run "${CLAUDE_PLUGIN_ROOT}/scripts/patternity.py" dashboard --serve >/dev/null 2>&1 &
```

`${CLAUDE_PLUGIN_ROOT}` is set by Claude Code to this plugin's install
directory, so do not search the filesystem for the repo. The server picks a
random free localhost port and opens itself in the browser; accept/reject
persists instantly and a `↻ recompile` button applies adopted patterns to
the current repo.

(To view without the write-back server, `dashboard` alone opens the static
`index.html` file instead.)
