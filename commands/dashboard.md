---
description: Open the patternity dashboard (regenerates and opens index.html)
---

Run `uv run <patternity-repo>/scripts/patternity.py dashboard` — it
regenerates the visualization from the current pattern store and opens it in
the browser. Ask the user for the patternity repo path if it isn't known.

For interactive accept/reject that persists instantly (no copy-a-command
step), the user runs `patternity.py dashboard --serve` themselves from a
terminal — it serves on localhost with write-back and blocks until Ctrl-C,
so don't launch `--serve` from here (it would hang this turn).
