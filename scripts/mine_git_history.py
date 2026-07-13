#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mine commit messages + diffstat since the last run into .patternitty/signal.jsonl.

Run from inside the project you want patternitty to learn from:
    uv run /path/to/patternitty/scripts/mine_git_history.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import repo_root  # noqa: E402

_ROOT = repo_root() or Path(".")
STATE_FILE = _ROOT / ".patternitty" / "state.json"
SIGNAL_FILE = _ROOT / ".patternitty" / "signal.jsonl"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main() -> None:
    SIGNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    since_sha = state.get("last_mined_sha")

    rev_range = f"{since_sha}..HEAD" if since_sha else "-n 200"
    log = git("log", rev_range, "--pretty=format:%H\x1f%s\x1f%b\x1e", "--shortstat")

    if not log.strip():
        return

    commits = []
    for chunk in log.split("\x1e"):
        chunk = chunk.strip()
        if not chunk:
            continue
        header, _, shortstat = chunk.partition("\n")
        parts = header.split("\x1f")
        if len(parts) < 2:
            continue
        sha, subject, *body = parts
        commits.append({"sha": sha, "subject": subject, "body": (body[0] if body else "").strip(), "shortstat": shortstat.strip()})

    if not commits:
        return

    with open(SIGNAL_FILE, "a") as f:
        for c in commits:
            f.write(json.dumps({"source": "git-history", **c}) + "\n")

    STATE_FILE.write_text(json.dumps({"last_mined_sha": commits[0]["sha"]}))
    print(f"mined {len(commits)} commit(s) into {SIGNAL_FILE}")


if __name__ == "__main__":
    main()
