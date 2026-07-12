#!/usr/bin/env python3
"""Shared capture hook for Claude Code, Cursor, and Copilot.

Deliberately dumb — no classification here, just append raw signal to
.patternity/signal.jsonl. The patternity skill (an LLM call) does the
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


def from_claude_transcript(transcript_path: str) -> dict:
    lines = Path(transcript_path).read_text().splitlines()
    user_text = assistant_text = ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message", {})
        role = msg.get("role") or entry.get("type")
        content = msg.get("content")
        text = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        ) if isinstance(content, list) else (content or "")
        if role == "assistant" and not assistant_text:
            assistant_text = text
        elif role == "user" and not user_text:
            user_text = text
        if user_text and assistant_text:
            break
    return {"user": user_text[:2000], "assistant": assistant_text[:2000]}


def build_record(payload: dict) -> dict | None:
    if "transcript_path" in payload:
        transcript_path = payload["transcript_path"]
        if not transcript_path or not Path(transcript_path).exists():
            return None
        return {"source": "claude-stop-hook", "cwd": payload.get("cwd"), **from_claude_transcript(transcript_path)}

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

        out_dir = Path(record.pop("cwd") or ".") / ".patternity"
        out_dir.mkdir(exist_ok=True)
        with open(out_dir / "signal.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # ponytail: never let capture break the session; silent best-effort
    return 0


if __name__ == "__main__":
    sys.exit(main())
