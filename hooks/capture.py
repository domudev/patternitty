#!/usr/bin/env python3
"""Shared capture hook for Claude Code, Cursor, and Copilot.

Deliberately dumb — no classification here, just append raw signal to
.patternitty/signal.jsonl. The patternitty skill (an LLM call) does the
interpretation later. Never raises: a broken hook must not block the agent.

One script instead of three near-identical ones: the three hosts differ only
in what their stdin payload looks like, not in what we do with it.

- Claude Code `Stop`: payload has transcript_path -> pull last user/assistant text.
- Cursor `beforeSubmitPrompt`: payload has prompt + workspace_roots.
- Copilot `userPromptSubmitted`: payload has prompt + cwd/sessionId.

Unlike the other scripts (which run via `uv` with requires-python>=3.11), this
hook is invoked with the machine's bare `python3` — which can be old (3.9 on
stock macOS). Keep it broadly compatible: `from __future__ import annotations`
so PEP-604 (`X | None`) type hints don't get evaluated at def time, and no
other 3.10+ syntax.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


# junk we must never treat as user signal: slash-command / skill / tool /
# system-injected turns. Claude Code flags these with `isMeta: true`; the tag
# list is a cheap backup for injected content that isn't flagged.
JUNK_TAGS = (
    "<command-name>", "<command-message>", "<command-args>", "<local-command",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>", "<task-notification>",
    "<system-reminder>", "Base directory for this skill:",
)


def _text(entry: dict) -> str:
    content = (entry.get("message", {}) or {}).get("content")
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


def from_claude_transcript(transcript_path: str):
    entries = []
    for line in Path(transcript_path).read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    assistant_text = next((_text(e) for e in reversed(entries)
                           if ((e.get("message", {}) or {}).get("role") == "assistant") and _text(e)), "")

    # The turn's trigger is the most recent user entry with real text (tool
    # results are role=user but textless, so they're skipped). If that trigger
    # is meta/injected, this whole turn is noise — skip it, don't reach back to
    # an earlier real message and mis-pair it.
    for e in reversed(entries):
        role = (e.get("message", {}) or {}).get("role") or e.get("type")
        if role != "user":
            continue
        text = _text(e).strip()
        if not text:
            continue
        if e.get("isMeta") or text.startswith(JUNK_TAGS):
            return None
        return {"user": text[:2000], "assistant": assistant_text[:2000]}
    return None


def build_record(payload: dict):
    if "transcript_path" in payload:
        transcript_path = payload["transcript_path"]
        if not transcript_path or not Path(transcript_path).exists():
            return None
        turn = from_claude_transcript(transcript_path)
        if turn is None:
            return None
        return {"source": "claude-stop-hook", "cwd": payload.get("cwd"), **turn}

    if "prompt" in payload and "workspace_roots" in payload:
        roots = payload.get("workspace_roots") or ["."]
        return {"source": "cursor-prompt-hook", "cwd": roots[0], "user": payload["prompt"][:2000], "assistant": ""}

    if "prompt" in payload:
        return {"source": "copilot-prompt-hook", "cwd": payload.get("cwd", "."), "user": payload["prompt"][:2000], "assistant": ""}

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        record = build_record(payload)
        if record is None:
            return 0
        record["ts"] = time.time()

        out_dir = Path(record.pop("cwd") or ".") / ".patternitty"
        out_dir.mkdir(exist_ok=True)
        with open(out_dir / "signal.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # ponytail: never let capture break the session; silent best-effort
    return 0


if __name__ == "__main__":
    sys.exit(main())
