#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for scripts/compile.py: proven patterns render, observed/suspect
patterns don't, project scoping is respected, overrides remove exact-match
text, and re-running is idempotent (no duplicate marked sections)."""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("compile_mod", REPO_ROOT / "scripts" / "compile.py")
compile_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compile_mod)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as project:
        os.environ["PATTERNITY_HOME"] = home
        patterns = Path(home) / "patterns"

        write(patterns / "proven-one.md", """---
name: proven-one
type: feedback
state: proven
occurrences: 3
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Use uv for python scripts.
""")
        write(patterns / "observed-one.md", """---
name: observed-one
type: feedback
state: observed
occurrences: 1
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Should never appear in compiled output.
""")
        write(patterns / "scoped-elsewhere.md", """---
name: scoped-elsewhere
type: feedback
state: proven
occurrences: 5
applies_to:
  tool: "*"
  glob: "**/*"
  project: some-other-repo
target: null
---

Should not leak into a project it wasn't scoped to.
""")
        write(patterns / "override-one.md", """---
name: override-one
type: override
state: proven
occurrences: 1
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: "Always use tabs, never spaces."
---

Suppress the annoying tabs rule.
""")
        write(patterns / "script-breakout.md", """---
name: script-breakout
type: feedback
state: observed
occurrences: 1
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Mentions a literal </script> tag in prose, which must not break index.html.
""")

        project_dir = Path(project)
        os.chdir(project_dir)
        write(project_dir / "CLAUDE.md", "# Project\n\nAlways use tabs, never spaces.\n")

        compile_mod.main()

        agents = Path("AGENTS.md").read_text()
        assert "Use uv for python scripts" in agents, "proven pattern missing from AGENTS.md"
        assert "Should never appear" not in agents, "observed pattern leaked into compiled output"
        assert "Should not leak" not in agents, "out-of-scope project pattern leaked in"

        claude = Path("CLAUDE.md").read_text()
        assert "Always use tabs, never spaces." not in claude, "override did not remove target text"

        cursor_rule = Path(".cursor/rules/patternity-learned.mdc").read_text()
        assert "Use uv for python scripts" in cursor_rule

        copilot = Path(".github/instructions/patternity-learned.instructions.md").read_text()
        assert "applyTo" in copilot

        index_json = json.loads((Path(home) / "patterns" / "index.json").read_text())
        assert {p["name"] for p in index_json} == {
            "proven-one", "observed-one", "scoped-elsewhere", "override-one", "script-breakout",
        }, "index.json should include every pattern regardless of state or project scope"

        index_html = (Path(home) / "patterns" / "index.html").read_text()
        assert "__PATTERNITY_DATA__" not in index_html, "template placeholder was not substituted"
        assert "observed-one" in index_html, "embedded data missing from index.html"
        data_tag_content = index_html.split('id="patternity-data"', 1)[1].split(">", 1)[1].split("</script>", 1)[0]
        assert "</script>" not in data_tag_content, "a literal </script> in pattern body must not close the data tag early"
        assert "\\u003c/script" in data_tag_content, "pattern body's </script> should be escaped, not passed through raw"

        # idempotency: compiling twice must not duplicate the marked section
        compile_mod.main()
        agents_twice = Path("AGENTS.md").read_text()
        assert agents_twice.count(compile_mod.BEGIN) == 1, "marker duplicated on re-run"

        print("all checks passed")


if __name__ == "__main__":
    main()
