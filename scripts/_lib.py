"""Shared pattern-file parsing for compile.py — one frontmatter parser, not
one per script. No PyYAML dependency: the schema is small and controlled
(patterns/_SCHEMA.md), so a hand-rolled parser is a few lines vs. a new dep.
"""
import os
import subprocess
from pathlib import Path


def patterns_dir() -> Path:
    """The per-USER store: personal, global, follows you across repos."""
    home = os.environ.get("PATTERNITTY_HOME", str(Path.home() / ".patternitty"))
    return Path(home) / "patterns"


def repo_root() -> Path | None:
    """The current git repository's top level, or None outside a repo. The one
    canonical answer to "where's the project root": signal writers and the
    pattern store must resolve it the same way, or signals written from a
    subdir land somewhere the store never looks."""
    try:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=False,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        root = ""
    return Path(root) if root else None


def repo_patterns_dir() -> Path | None:
    """The per-REPO store: team/project conventions committed with the code,
    at <git-root>/.patternitty/patterns/. None when not inside a git repo.
    (Signal lives at <git-root>/.patternitty/signal.jsonl and stays gitignored;
    only patterns/ is meant to be committed — see README.)"""
    root = repo_root()
    return root / ".patternitty" / "patterns" if root else None


def signal_file() -> Path:
    """Where captured signal lands and is read from: <git-root>/.patternitty/
    signal.jsonl, or ./.patternitty/signal.jsonl outside a repo. Gitignored.
    The hook appends, mine_git_history.py appends, the skill + dashboard read."""
    return (repo_root() or Path(".")) / ".patternitty" / "signal.jsonl"


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


# Sensible defaults so a hand-authored pattern needs only `name` + body — the
# reader fills the rest. Keeps "the file format is the API" cheap to write by
# hand, and keeps every consumer (compile/viz/CLI) from special-casing blanks.
DEFAULTS = {
    "type": "feedback", "state": "noticed", "occurrences": "1", "cluster": "",
    "decision": "", "agent": "unknown", "author": "anon", "target": "null",
}
APPLIES_DEFAULTS = {"tool": "*", "glob": "**/*", "project": "*"}


def parse_pattern(path: Path) -> dict:
    text = path.read_text()
    # tolerate a body-only file (no frontmatter) — treat the whole thing as body
    parts = text.split("---", 2)
    fm, body = (parts[1], parts[2]) if len(parts) == 3 else ("", text)
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
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    for k, v in APPLIES_DEFAULTS.items():
        applies_to.setdefault(k, v)
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


def _load_dir(directory: Path | None, tier: str) -> list[dict]:
    if not directory or not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_") or path.name in ("WALKING_DOC.md", "PROFILE.md"):
            continue
        p = parse_pattern(path)
        p["tier"] = tier  # "user" (personal) or "repo" (team, committed) — derived from location
        out.append(p)
    return out


def load_all() -> list[dict]:
    """Every pattern relevant here: the per-repo store (team) merged over the
    per-user store (personal). Repo wins on a name clash — a repo can override
    a personal default. Each dict carries its `tier`."""
    repo = _load_dir(repo_patterns_dir(), "repo")
    repo_names = {p["name"] for p in repo}
    user = [p for p in _load_dir(patterns_dir(), "user") if p["name"] not in repo_names]
    return repo + user
