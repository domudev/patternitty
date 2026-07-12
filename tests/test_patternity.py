#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for scripts/patternity.py: BM25 ranks by relevance, regex
matches structurally, and add/set/bump edit the store correctly."""
import importlib.util
import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("patternity_mod", REPO_ROOT / "scripts" / "patternity.py")
pat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pat)


def run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        pat.main(argv)
    return buf.getvalue()


def main() -> None:
    with tempfile.TemporaryDirectory() as home:
        os.environ["PATTERNITY_HOME"] = home
        patterns = Path(home) / "patterns"
        patterns.mkdir()

        def write(name, body, extra=""):
            (patterns / f"{name}.md").write_text(
                f"---\nname: {name}\ntype: feedback\nstate: adopted\noccurrences: 3\n{extra}"
                "applies_to:\n  tool: \"*\"\n  glob: \"**/*\"\n  project: \"*\"\n---\n\n" + body + "\n"
            )

        write("uv-tooling", "Use uv for python package management, never pip.", "cluster: tooling\n")
        write("small-modules", "Keep modules small with low cyclomatic complexity.", "cluster: code-style\n")
        write("test-naming", "Name tests descriptively; uv is unrelated here.", "cluster: testing\n")

        # BM25: a query about packaging should rank the uv/pip pattern first
        out = run(["search", "python package pip", "--limit", "3"])
        assert out.splitlines()[0].split()[1] == "uv-tooling", f"BM25 mis-ranked:\n{out}"

        # regex: structural match, not relevance
        out = run(["search", r"cyclomatic", "--regex"])
        assert "small-modules" in out and "uv-tooling" not in out, f"regex over-matched:\n{out}"

        # add creates a valid noticed pattern
        run(["add", "new-thing", "--cluster", "workflow", "--agent", "claude-code", "--body", "A freshly added pattern."])
        added = (patterns / "new-thing.md").read_text()
        assert "state: noticed" in added and "occurrences: 1" in added and "cluster: workflow" in added
        assert "agent: claude-code" in added, "add should record the capturing agent"
        assert "author:" in added, "add should record an author (git identity or anon)"

        # bump walks the ladder: 1 -> noticed already, bump to 2 -> recurring, 3 -> adopted
        run(["bump", "new-thing"])
        assert "state: recurring" in (patterns / "new-thing.md").read_text(), "bump to 2 should be recurring"
        run(["bump", "new-thing"])
        assert "state: adopted" in (patterns / "new-thing.md").read_text(), "bump to 3 should be adopted"
        assert "occurrences: 3" in (patterns / "new-thing.md").read_text()

        # set + clear
        run(["set", "new-thing", "decision", "rejected"])
        assert "decision: rejected" in (patterns / "new-thing.md").read_text()
        run(["set", "new-thing", "decision", "--clear"])
        assert "decision:" not in (patterns / "new-thing.md").read_text(), "--clear should remove the field"

        # list filter
        out = run(["list", "--cluster", "code-style"])
        assert "small-modules" in out and "uv-tooling" not in out

        print("all checks passed")


if __name__ == "__main__":
    main()
