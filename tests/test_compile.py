#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for scripts/compile.py: adopted patterns render, noticed/recurring
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
        os.environ["PATTERNITTY_HOME"] = home
        patterns = Path(home) / "patterns"

        write(patterns / "adopted-one.md", """---
name: adopted-one
type: feedback
state: adopted
occurrences: 3
cluster: tooling
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Use uv for python scripts.
""")
        write(patterns / "PROFILE.md", """## Tooling

You default to uv over pip/venv, stated across multiple projects.

Mentions a literal </script> tag too, which must not break index.html.
""")
        write(patterns / "noticed-one.md", """---
name: noticed-one
type: feedback
state: noticed
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
state: adopted
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
state: adopted
occurrences: 1
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: "Always use tabs, never spaces."
---

Suppress the annoying tabs rule.
""")
        write(patterns / "accepted-noticed.md", """---
name: accepted-noticed
type: feedback
state: noticed
occurrences: 1
decision: accepted
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Accepted despite only being noticed once.
""")
        write(patterns / "rejected-adopted.md", """---
name: rejected-adopted
type: feedback
state: adopted
occurrences: 9
decision: rejected
applies_to:
  tool: "*"
  glob: "**/*"
  project: "*"
target: null
---

Rejected even though it reached adopted.
""")
        write(patterns / "script-breakout.md", """---
name: script-breakout
type: feedback
state: noticed
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

        # per-repo (team) store: make the project a git repo and drop a repo
        # pattern scoped to a *different* project — it must still compile here,
        # because repo-tier patterns belong to this repo regardless of scope.
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=project_dir, check=False)
        write(project_dir / ".patternitty" / "patterns" / "team-convention.md", """---
name: team-convention
type: project
state: adopted
occurrences: 9
applies_to:
  tool: "*"
  glob: "**/*"
  project: some-other-repo
---

Team rule that lives in the repo store.
""")

        compile_mod.main()

        all_cluster_text = "".join(p.read_text() for p in Path("patternitty").glob("*.md"))
        assert "Team rule that lives in the repo store" in all_cluster_text, "repo-tier pattern must compile regardless of project scope"

        # rules now live in patternitty/<cluster>.md; the tool files reference them
        tooling = Path("patternitty/tooling.md").read_text()
        assert "Use uv for python scripts" in tooling, "adopted pattern missing from its cluster file"
        agents = Path("AGENTS.md").read_text()
        assert "patternitty/tooling.md" in agents, "AGENTS.md should reference the cluster file"
        assert "Use uv for python scripts" not in agents, "AGENTS.md should reference, not inline, the rule"
        all_clusters = "".join(p.read_text() for p in Path("patternitty").glob("*.md"))
        assert "Should never appear" not in all_clusters, "noticed pattern leaked into compiled output"
        assert "Should not leak" not in all_clusters, "out-of-scope project pattern leaked in"
        assert "Accepted despite only being noticed" in all_clusters, "decision:accepted should compile even at noticed"
        assert "Rejected even though it reached adopted" not in all_clusters, "decision:rejected must never compile"

        claude = Path("CLAUDE.md").read_text()
        assert "Always use tabs, never spaces." not in claude, "override did not remove target text"

        cursor_rule = Path(".cursor/rules/patternitty-learned.mdc").read_text()
        assert "patternitty/tooling.md" in cursor_rule, "cursor rule should reference the cluster file"

        copilot = Path(".github/instructions/patternitty-learned.instructions.md").read_text()
        assert "applyTo" in copilot

        index_json = json.loads((Path(home) / "patterns" / "index.json").read_text())
        assert {p["name"] for p in index_json} == {
            "adopted-one", "noticed-one", "scoped-elsewhere", "override-one", "script-breakout",
            "accepted-noticed", "rejected-adopted", "team-convention",
        }, "index.json should include every pattern (both tiers) regardless of state/decision/scope"
        assert next(p for p in index_json if p["name"] == "adopted-one")["cluster"] == "tooling", \
            "cluster field should pass through to index.json"
        assert next(p for p in index_json if p["name"] == "rejected-adopted")["decision"] == "rejected", \
            "decision field should pass through to index.json"
        assert next(p for p in index_json if p["name"] == "team-convention")["tier"] == "repo", \
            "repo-tier patterns should be tagged tier=repo"

        index_html = (Path(home) / "patterns" / "index.html").read_text()
        assert "__PATTERNITTY_DATA__" not in index_html, "template placeholder was not substituted"
        assert "__PATTERNITTY_PROFILE__" not in index_html, "profile placeholder was not substituted"
        assert "noticed-one" in index_html, "embedded data missing from index.html"
        assert "You default to uv" in index_html, "PROFILE.md content missing from index.html"

        def tag_content(tag_id: str) -> str:
            return index_html.split(f'id="{tag_id}"', 1)[1].split(">", 1)[1].split("</script>", 1)[0]

        for tag_id in ("patternitty-data", "patternitty-profile"):
            content = tag_content(tag_id)
            assert "</script>" not in content, f"a literal </script> in source text must not close {tag_id} early"
        assert "\\u003c/script" in tag_content("patternitty-data"), "pattern body's </script> should be escaped"
        assert "\\u003c/script" in tag_content("patternitty-profile"), "PROFILE.md's </script> should be escaped"

        # idempotency: compiling twice must not duplicate the marked section
        compile_mod.main()
        agents_twice = Path("AGENTS.md").read_text()
        assert agents_twice.count(compile_mod.BEGIN) == 1, "marker duplicated on re-run"

        print("all checks passed")


if __name__ == "__main__":
    main()
