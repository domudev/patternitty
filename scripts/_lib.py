"""Shared pattern-file parsing for compile.py — one frontmatter parser, not
one per script. No PyYAML dependency: the schema is small and controlled
(patterns/_SCHEMA.md), so a hand-rolled parser is a few lines vs. a new dep.
"""
import os
from pathlib import Path


def patterns_dir() -> Path:
    home = os.environ.get("PATTERNITY_HOME", str(Path.home() / ".patternity"))
    return Path(home) / "patterns"


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


def load_all() -> list[dict]:
    """Every pattern in the store, any state — for the visualization, which
    shows the whole personal store rather than one project's compiled slice."""
    directory = patterns_dir()
    if not directory.exists():
        return []
    return [
        parse_pattern(path)
        for path in sorted(directory.glob("*.md"))
        if not path.name.startswith("_") and path.name != "WALKING_DOC.md"
    ]
