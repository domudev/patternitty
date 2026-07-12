---
description: Open the patternitty dashboard (live server, accept/reject write-back)
---

Launch the server in the background (it blocks; never foreground it or this
turn hangs). It opens itself in the browser on a random localhost port:

```
nohup uv run "${CLAUDE_PLUGIN_ROOT}/scripts/patternitty.py" dashboard --serve >/dev/null 2>&1 &
```

Accept/reject persists live; `↻ recompile` applies adopted patterns to this
repo. (`dashboard` without `--serve` just opens the static file.)
