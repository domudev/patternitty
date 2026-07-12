#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compile adopted patterns into each tool's native format, for whichever
project you run this from.

Patterns are personal to the user (${PATTERNITY_HOME:-~/.patternity}/patterns/),
not the repo — this script reads that global store but writes compiled
output into the current working directory's project files. Deterministic
templating, no AI. Idempotent: re-running only replaces the marked section
it owns, everything else in the target file is left alone. No frontmatter
YAML parser dependency — the schema is small and controlled
(patterns/_SCHEMA.md), so a hand-rolled parser is a few lines vs. a new dep.

Also regenerates the store-wide visualization (index.json + index.html) in
${PATTERNITY_HOME:-~/.patternity}/patterns/, covering every pattern at any
state — not just what got compiled for this project.

Run from the project you want compiled patternity patterns applied to:
    uv run /path/to/patternity/scripts/compile.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ensure_store, in_scope, load_all, patterns_dir  # noqa: E402

BEGIN = "<!-- patternity:begin -->"
END = "<!-- patternity:end -->"
REPO_ROOT = Path(__file__).resolve().parent.parent


def current_project() -> str:
    return Path.cwd().name


def is_effective_adopted(p: dict) -> bool:
    """A pattern compiles if the user explicitly accepted it (pin, regardless
    of occurrence count) or it reached `adopted` on its own — but an explicit
    reject always wins and excludes it. Manual accept/reject (set in the
    frontmatter's `decision` field, e.g. via scripts/decide.py) overrides the
    automatic occurrence-driven state."""
    decision = p.get("decision", "")
    if decision == "rejected":
        return False
    if decision == "accepted":
        return True
    return p.get("state") == "adopted"


def load_adopted(project: str) -> tuple[list[dict], list[dict]]:
    additive, overrides = [], []
    for p in load_all():
        if not is_effective_adopted(p) or not in_scope(p, project):
            continue
        (overrides if p.get("type") == "override" else additive).append(p)
    return additive, overrides


def bullet(p: dict) -> str:
    first_line = p["body"].splitlines()[0] if p["body"] else p["name"]
    return f"- {first_line} _({p['name']})_"


def replace_marked_section(path: Path, section_body: str, header: str) -> None:
    block = f"{BEGIN}\n{header}\n\n{section_body}\n{END}"
    if path.exists():
        text = path.read_text()
        if BEGIN in text and END in text:
            text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
    else:
        text = block + "\n"
    path.write_text(text)


def write_markdown_targets(additive: list[dict]) -> list[Path]:
    body = "\n".join(bullet(p) for p in additive) if additive else "_(none adopted yet)_"
    written = []
    for target in (Path("AGENTS.md"), Path("CLAUDE.md")):
        replace_marked_section(target, body, "## Learned patterns (patternity)")
        written.append(target)
    return written


def write_cursor_rule(additive: list[dict]) -> Path:
    globs = ",".join(sorted({p["applies_to"].get("glob", "**/*") for p in additive})) or "**/*"
    always = any(p["applies_to"].get("tool") in ("*", "cursor") for p in additive)
    body = "\n".join(bullet(p) for p in additive) if additive else "_(none adopted yet)_"
    content = (
        "---\n"
        f"description: Patterns learned by patternity\n"
        f"alwaysApply: {'true' if always else 'false'}\n"
        f"globs: {globs}\n"
        "---\n\n"
        "## Learned patterns (patternity)\n\n"
        f"{body}\n"
    )
    path = Path(".cursor/rules/patternity-learned.mdc")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def write_copilot_instructions(additive: list[dict]) -> Path:
    globs = ",".join(sorted({p["applies_to"].get("glob", "**/*") for p in additive})) or "**/*"
    body = "\n".join(bullet(p) for p in additive) if additive else "_(none adopted yet)_"
    content = (
        "---\n"
        f"applyTo: \"{globs}\"\n"
        "---\n\n"
        "## Learned patterns (patternity)\n\n"
        f"{body}\n"
    )
    path = Path(".github/instructions/patternity-learned.instructions.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def apply_overrides(overrides: list[dict]) -> tuple[list[str], list[str]]:
    search_paths = [
        Path("CLAUDE.md"), Path("AGENTS.md"), Path(".github/copilot-instructions.md"),
        *Path(".cursor/rules").glob("*.mdc"), *Path(".github/instructions").glob("*.instructions.md"),
    ]
    applied, unresolved = [], []
    for o in overrides:
        target = o.get("target")
        if not target or target == "null":
            unresolved.append(f"{o['name']}: no target text set")
            continue
        found = False
        for path in search_paths:
            if not path.exists():
                continue
            text = path.read_text()
            if target in text:
                path.write_text(text.replace(target + "\n", "").replace(target, ""))
                applied.append(f"{o['name']}: removed from {path}")
                found = True
                break
        if not found:
            unresolved.append(f"{o['name']}: target text not found verbatim — {target!r}")
    return applied, unresolved


def write_overrides_report(unresolved: list[str]) -> None:
    body = "\n".join(f"- {u}" for u in unresolved) if unresolved else "_(none pending)_"
    replace_marked_section(Path("AGENTS.md"), body, "## Overrides (needs manual check)")


def write_viz(all_patterns: list[dict]) -> list[Path]:
    """Regenerate the whole-store visualization: index.json (raw data) and
    index.html (the same data + PROFILE.md embedded, so it opens via file://
    with no server and no fetch/CORS gotcha)."""
    slim = [
        {k: p.get(k, "") for k in ("name", "type", "state", "occurrences", "cluster", "decision", "agent", "author", "applies_to", "target", "body")}
        for p in all_patterns
    ]
    json_path = patterns_dir() / "index.json"
    json_path.write_text(json.dumps(slim, indent=2))

    profile_path = patterns_dir() / "PROFILE.md"
    profile_text = profile_path.read_text() if profile_path.exists() else ""

    def embed(value) -> str:
        # each placeholder sits inside its own <script type="application/json">
        # tag, parsed client-side with JSON.parse — dump once (array for data,
        # string for profile text) and escape "<" so a literal "</script>" in
        # a pattern body or the profile can't break out of the tag.
        return json.dumps(value).replace("<", "\\u003c")

    template = (REPO_ROOT / "viz" / "template.html").read_text()
    html_path = patterns_dir() / "index.html"
    html_path.write_text(
        template
        .replace("/*__PATTERNITY_DATA__*/", embed(slim))
        .replace("/*__PATTERNITY_PROFILE__*/", embed(profile_text))
    )
    return [json_path, html_path]


def main() -> None:
    ensure_store()  # self-init on first run — no separate `init` step
    project = current_project()
    all_pats = load_all()

    # always refresh the store-local dashboard so it's never a dead end...
    written = write_viz(all_pats)
    # ...but don't touch this project's CLAUDE.md/etc until there's actually
    # something in the store — no point stamping empty blocks into a repo.
    if not all_pats:
        print(f"store is empty ({patterns_dir()}) — dashboard refreshed, nothing to compile yet")
        return

    additive, overrides = load_adopted(project)
    applied, unresolved = apply_overrides(overrides)
    written += write_markdown_targets(additive)
    written += [write_cursor_rule(additive), write_copilot_instructions(additive)]
    if unresolved:
        write_overrides_report(unresolved)

    print(f"[{project}] compiled {len(additive)} pattern(s), {len(applied)} override(s) applied, {len(unresolved)} unresolved")
    for w in written:
        print(f"  wrote {w}")


if __name__ == "__main__":
    main()
