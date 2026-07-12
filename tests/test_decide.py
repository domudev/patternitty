#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for scripts/decide.py: accept/reject set the frontmatter
`decision` field, clear removes it, and the pattern body survives intact."""
import importlib.util
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("decide_mod", REPO_ROOT / "scripts" / "decide.py")
decide_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decide_mod)


def field(text: str, key: str) -> str | None:
    _, fm, _ = text.split("---", 2)
    for line in fm.splitlines():
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def main() -> None:
    with tempfile.TemporaryDirectory() as home:
        os.environ["PATTERNITY_HOME"] = home
        patterns = Path(home) / "patterns"
        patterns.mkdir()
        (patterns / "foo.md").write_text("""---
name: foo
type: feedback
state: noticed
occurrences: 1
---

Body line that must survive edits.
""")

        decide_mod.main(["accept:foo"])
        text = (patterns / "foo.md").read_text()
        assert field(text, "decision") == "accepted", "accept should set decision: accepted"
        assert "Body line that must survive edits." in text, "body must be preserved"
        assert field(text, "state") == "noticed", "other frontmatter fields must be preserved"

        decide_mod.main(["reject:foo"])
        assert field((patterns / "foo.md").read_text(), "decision") == "rejected", "reject should overwrite decision"
        # no duplicate decision lines
        assert (patterns / "foo.md").read_text().count("decision:") == 1, "must not stack duplicate decision lines"

        decide_mod.main(["clear:foo"])
        assert field((patterns / "foo.md").read_text(), "decision") is None, "clear should remove decision"

        decide_mod.main(["reject:does-not-exist"])  # should not raise

        print("all checks passed")


if __name__ == "__main__":
    main()
