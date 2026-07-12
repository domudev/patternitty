"""Shared pattern-file parsing for compile.py — one frontmatter parser, not
one per script. No PyYAML dependency: the schema is small and controlled
(patterns/_SCHEMA.md), so a hand-rolled parser is a few lines vs. a new dep.
"""
import os
import subprocess
from pathlib import Path


def patterns_dir() -> Path:
    home = os.environ.get("PATTERNITY_HOME", str(Path.home() / ".patternity"))
    return Path(home) / "patterns"


def git_author() -> str:
    """Who to attribute a pattern to: the git identity if there is one, else
    'anon'. email over name (more stable); never raises."""
    for key in ("user.email", "user.name"):
        try:
            out = subprocess.run(["git", "config", key], check=False,
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            out = ""
        if out:
            return out
    return "anon"


def ensure_store() -> Path:
    """Make the store exist on first write — no separate `init` step. Creates
    the patterns dir and, best-effort, git-inits the store root so promotions
    are versioned (silent if git is missing; the store works without it).
    Called by every write path; read paths never create anything."""
    directory = patterns_dir()
    directory.mkdir(parents=True, exist_ok=True)
    root = directory.parent
    if not (root / ".git").exists():
        try:
            subprocess.run(["git", "init", "-q", str(root)], check=False,
                           capture_output=True, timeout=5)
        except Exception:
            pass  # ponytail: versioning is a bonus; the store is usable without git
    return directory


def parse_pattern(path: Path) -> dict:
    text = path.read_text()
    _, fm, body = text.split("---", 2)
    data: dict = {}
    applies_to: dict = {}
    in_applies_to = False
    for line in fm.splitlines():
        if not line.strip():
            continue
        if line.startswith("applies_to:"):
            in_applies_to = True
            continue
        if in_applies_to and line.startswith("  "):
            k, _, v = line.strip().partition(":")
            applies_to[k.strip()] = v.strip().strip('"')
            continue
        in_applies_to = False
        k, _, v = line.partition(":")
        data[k.strip()] = v.strip().strip('"')
    data["applies_to"] = applies_to
    data["body"] = body.strip()
    data["name"] = path.stem
    return data


def in_scope(p: dict, project: str) -> bool:
    project_scope = p["applies_to"].get("project", "*")
    return project_scope == "*" or project in project_scope.split(",")


def set_field(path: Path, key: str, value: str | None) -> None:
    """Set/replace a top-level frontmatter field in place, or remove it when
    value is None. Order-preserving (replaces where the key already is,
    otherwise appends at the end of the frontmatter block); the parser is
    order-independent, but keeping edits stable makes the git diffs clean.
    Top-level keys only — nested applies_to.* is left to hand-editing."""
    _, fm, body = path.read_text().split("---", 2)
    lines, replaced = [], False
    for line in fm.split("\n"):
        if line.strip().startswith(f"{key}:"):
            if value is not None and not replaced:
                lines.append(f"{key}: {value}")
                replaced = True
            continue  # drop the old line (and any dupes; drop entirely if removing)
        lines.append(line)
    if value is not None and not replaced:
        end = len(lines)
        while end > 0 and lines[end - 1].strip() == "":
            end -= 1  # insert before the block's trailing blank line(s)
        lines.insert(end, f"{key}: {value}")
    path.write_text("---" + "\n".join(lines) + "---" + body)


def load_all() -> list[dict]:
    """Every pattern in the store, any state — for the visualization, which
    shows the whole personal store rather than one project's compiled slice."""
    directory = patterns_dir()
    if not directory.exists():
        return []
    return [
        parse_pattern(path)
        for path in sorted(directory.glob("*.md"))
        if not path.name.startswith("_") and path.name not in ("WALKING_DOC.md", "PROFILE.md")
    ]
