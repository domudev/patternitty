#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Record manual accept/reject decisions on patterns in the personal store.

The visualization can't write the store itself (it's a static file:// page),
so its accept/reject buttons just build the command that runs this. Accept
pins a pattern to compiled regardless of occurrence count; reject tombstones
it (never compiled, and the skill won't re-propose it); clear removes the
decision and lets the automatic state ladder take over again.

Usage (token form, as the viz emits it):
    uv run scripts/decide.py accept:uv-pref reject:tabs-not-spaces clear:foo

Edits the `decision` frontmatter field in ${PATTERNITTY_HOME:-~/.patternitty}/
patterns/<name>.md. Re-run compile.py afterwards to reflect it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import patterns_dir, set_field  # noqa: E402

VERBS = {"accept": "accepted", "reject": "rejected", "clear": None}


def set_decision(path: Path, value: str | None) -> None:
    """Set/clear the `decision` field. Thin wrapper over the shared frontmatter
    editor so decide.py and patternitty.py `set` never drift apart."""
    set_field(path, "decision", value)


def main(argv: list[str]) -> int:
    directory = patterns_dir()
    if not directory.exists():
        print(f"no pattern store at {directory}")
        return 1
    if not argv:
        print(__doc__)
        return 1

    changed = 0
    for token in argv:
        verb, _, name = token.partition(":")
        if verb not in VERBS or not name:
            print(f"skipping malformed token: {token!r} (want accept:NAME / reject:NAME / clear:NAME)")
            continue
        path = directory / f"{name}.md"
        if not path.exists():
            print(f"no such pattern: {name}")
            continue
        set_decision(path, VERBS[verb])
        print(f"{name}: {verb}")
        changed += 1

    if changed:
        print(f"\n{changed} decision(s) recorded — re-run compile.py to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
