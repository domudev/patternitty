---
description: Open the patternity dashboard (regenerates and opens index.html)
---

Run:

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/patternity.py" dashboard
```

`${CLAUDE_PLUGIN_ROOT}` is set by Claude Code to this plugin's install
directory, so do not search the filesystem for the repo. It regenerates the
visualization from the current pattern store and opens it in the browser.

For interactive accept/reject that persists instantly (no copy-a-command
step), the user runs `dashboard --serve` themselves from a terminal (it
serves on localhost with write-back and blocks until Ctrl-C). Do not launch
`--serve` from here, it would hang this turn.
