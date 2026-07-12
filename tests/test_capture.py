#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for hooks/capture.py's build_record branching across the three
host payload shapes (Claude Code, Cursor, Copilot)."""
import importlib.util
import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("capture_mod", REPO_ROOT / "hooks" / "capture.py")
capture_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture_mod)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        transcript = Path(tmp) / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"message": {"role": "user", "content": [{"text": "stop using classes for this"}]}}) + "\n"
            + json.dumps({"message": {"role": "assistant", "content": [{"text": "ok, switched to a function"}]}}) + "\n"
        )
        claude_record = capture_mod.build_record({"transcript_path": str(transcript), "cwd": tmp})
        assert claude_record["source"] == "claude-stop-hook"
        assert "stop using classes" in claude_record["user"]
        assert "switched to a function" in claude_record["assistant"]

        # a turn triggered by a slash-command/skill (isMeta) must be skipped,
        # not logged as user signal — and it must not reach back to the earlier
        # real message and mis-pair it.
        meta_tx = Path(tmp) / "meta.jsonl"
        meta_tx.write_text(
            json.dumps({"message": {"role": "user", "content": [{"text": "real earlier message"}]}}) + "\n"
            + json.dumps({"message": {"role": "assistant", "content": [{"text": "reply"}]}}) + "\n"
            + json.dumps({"isMeta": True, "message": {"role": "user", "content": [{"text": "Run `uv run scripts/patternitty.py dashboard`"}]}}) + "\n"
            + json.dumps({"message": {"role": "assistant", "content": [{"text": "opening dashboard"}]}}) + "\n"
        )
        assert capture_mod.build_record({"transcript_path": str(meta_tx), "cwd": tmp}) is None, \
            "isMeta-triggered turn (slash command/skill) must not be captured"

        # tool-output echo (tagged) also skipped
        tag_tx = Path(tmp) / "tag.jsonl"
        tag_tx.write_text(
            json.dumps({"message": {"role": "user", "content": [{"text": "<bash-stdout>(no output)</bash-stdout>"}]}}) + "\n"
            + json.dumps({"message": {"role": "assistant", "content": [{"text": "done"}]}}) + "\n"
        )
        assert capture_mod.build_record({"transcript_path": str(tag_tx), "cwd": tmp}) is None, \
            "tagged tool-output turn must not be captured"

        cursor_record = capture_mod.build_record({"prompt": "always use uv", "workspace_roots": ["/tmp/proj"]})
        assert cursor_record["source"] == "cursor-prompt-hook"
        assert cursor_record["cwd"] == "/tmp/proj"

        copilot_record = capture_mod.build_record({"prompt": "never touch main.py", "cwd": "/tmp/proj2"})
        assert copilot_record["source"] == "copilot-prompt-hook"

        assert capture_mod.build_record({"unrelated": "field"}) is None

        print("all checks passed")


if __name__ == "__main__":
    main()
