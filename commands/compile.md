---
description: Recompile adopted patternity patterns into CLAUDE.md/AGENTS.md/.cursor/.github for this project
---

From the project root, run:

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/compile.py"
```

`${CLAUDE_PLUGIN_ROOT}` is set by Claude Code to this plugin's install
directory, so do not search the filesystem for the repo. This is normally
done automatically by the `patternity` skill right after a pattern reaches
`adopted`; use this command to force a re-sync, e.g. after manually editing a
pattern file.
