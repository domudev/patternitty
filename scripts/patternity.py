#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""patternity — the agent-facing query/edit surface over the pattern store.

This is an accelerator, not the only door: the store is plain markdown, so an
agent with no Python can grep/read/write the files directly (see
patterns/_SCHEMA.md) and get the same result. The file format is the API; this
CLI is sugar over it.

Read:   search <query> [--regex] [--limit N] [--json]   (BM25 by default)
        get <name> [--json]
        list [--state S] [--cluster C] [--json]
Write:  add <name> [--type T] [--cluster C] [--tool T] [--project P] [--body "…"]
        set <name> <field> <value>           (or --clear to remove the field)
        bump <name>                          (occurrences +1, re-derive state)
View:   dashboard                            (regenerate + open index.html)

All commands operate on ${PATTERNITY_HOME:-~/.patternity}/patterns/.
"""
import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ensure_store, load_all, parse_pattern, patterns_dir, set_field  # noqa: E402

LADDER = [(3, "adopted"), (2, "recurring"), (0, "noticed")]  # occurrences -> state


def searchable(p: dict) -> str:
    at = p.get("applies_to", {})
    return " ".join(str(x) for x in [p.get("name"), p.get("body"), p.get("cluster"),
                                     p.get("type"), at.get("tool"), at.get("project")] if x)


def tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def bm25(query: str, docs: list[tuple[str, list[str]]], k1: float = 1.5, b: float = 0.75) -> list[tuple[float, str]]:
    # ponytail: no index, tokenize+score the whole store per query. Fine for a
    # personal store (dozens–hundreds of tiny files); add a cached index only
    # if the corpus ever grows into the thousands.
    n = len(docs)
    if not n:
        return []
    avgdl = sum(len(t) for _, t in docs) / n
    df: Counter = Counter()
    for _, toks in docs:
        df.update(set(toks))
    scores = []
    for name, toks in docs:
        tf, dl, s = Counter(toks), len(toks), 0.0
        for term in tokenize(query):
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / avgdl))
        if s > 0:
            scores.append((s, name))
    return sorted(scores, reverse=True)


def cmd_search(args) -> int:
    pats = {p["name"]: p for p in load_all()}
    if args.regex:
        rx = re.compile(args.query, re.I)
        hits = [(1.0, p["name"]) for p in pats.values() if rx.search(searchable(p))]
    else:
        hits = bm25(args.query, [(p["name"], tokenize(searchable(p))) for p in pats.values()])
    hits = hits[: args.limit]
    if args.json:
        print(json.dumps([{"name": n, "score": round(s, 3), **{k: pats[n].get(k, "") for k in ("state", "cluster", "decision", "type")}} for s, n in hits], indent=2))
    else:
        for s, n in hits:
            first = (pats[n].get("body", "").splitlines() or [""])[0]
            print(f"{s:6.2f}  {n:28} {first}")
        if not hits:
            print("(no matches)")
    return 0


def cmd_get(args) -> int:
    path = patterns_dir() / f"{args.name}.md"
    if not path.exists():
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    print(json.dumps(parse_pattern(path), indent=2) if args.json else path.read_text())
    return 0


def cmd_list(args) -> int:
    pats = load_all()
    if args.state:
        pats = [p for p in pats if p.get("state") == args.state]
    if args.cluster:
        pats = [p for p in pats if p.get("cluster") == args.cluster]
    if args.json:
        print(json.dumps([{k: p.get(k, "") for k in ("name", "state", "cluster", "decision", "occurrences", "type")} for p in pats], indent=2))
    else:
        for p in pats:
            print(f"{p.get('state',''):9} {p.get('cluster',''):14} {p['name']}")
    return 0


def cmd_add(args) -> int:
    ensure_store()
    path = patterns_dir() / f"{args.name}.md"
    if path.exists():
        print(f"already exists: {args.name} (use `set`/`bump` to edit)", file=sys.stderr)
        return 1
    body = args.body or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    fm = [
        f"name: {args.name}", f"type: {args.type}", "state: noticed", "occurrences: 1",
        *([f"cluster: {args.cluster}"] if args.cluster else []),
        "applies_to:", f"  tool: \"{args.tool}\"", "  glob: \"**/*\"", f"  project: \"{args.project}\"",
        *(["target: null"] if args.type == "override" else []),
    ]
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n")
    print(f"added {args.name} (noticed)")
    return 0


def cmd_set(args) -> int:
    path = patterns_dir() / f"{args.name}.md"
    if not path.exists():
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    if not args.clear and args.value is None:
        print("set needs a value, or --clear to remove the field", file=sys.stderr)
        return 1
    set_field(path, args.field, None if args.clear else args.value)
    print(f"{args.name}: {args.field} = {'(cleared)' if args.clear else args.value}")
    return 0


def cmd_bump(args) -> int:
    path = patterns_dir() / f"{args.name}.md"
    if not path.exists():
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    p = parse_pattern(path)
    occ = (int(p.get("occurrences", 0) or 0)) + 1
    state = next(s for threshold, s in LADDER if occ >= threshold)
    set_field(path, "occurrences", str(occ))
    set_field(path, "state", state)
    print(f"{args.name}: occurrences={occ}, state={state}")
    return 0


def cmd_dashboard(args) -> int:
    # first run has no store yet — create it and render an empty board rather
    # than dead-ending, so there's always something to open.
    ensure_store()
    import compile as compile_mod  # regenerate the viz from the store (no project needed)
    _, html = compile_mod.write_viz(load_all())
    opener = {"darwin": "open", "win32": "start"}.get(sys.platform, "xdg-open")
    print(f"opening {html}")
    subprocess.run([opener, str(html)], shell=(opener == "start"), check=False)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="patternity", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--regex", action="store_true"); s.add_argument("--limit", type=int, default=10); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_search)
    g = sub.add_parser("get"); g.add_argument("name"); g.add_argument("--json", action="store_true"); g.set_defaults(fn=cmd_get)
    ls = sub.add_parser("list"); ls.add_argument("--state"); ls.add_argument("--cluster"); ls.add_argument("--json", action="store_true"); ls.set_defaults(fn=cmd_list)
    a = sub.add_parser("add"); a.add_argument("name"); a.add_argument("--type", default="feedback"); a.add_argument("--cluster"); a.add_argument("--tool", default="*"); a.add_argument("--project", default="*"); a.add_argument("--body"); a.set_defaults(fn=cmd_add)
    st = sub.add_parser("set"); st.add_argument("name"); st.add_argument("field"); st.add_argument("value", nargs="?"); st.add_argument("--clear", action="store_true"); st.set_defaults(fn=cmd_set)
    b = sub.add_parser("bump"); b.add_argument("name"); b.set_defaults(fn=cmd_bump)
    d = sub.add_parser("dashboard"); d.set_defaults(fn=cmd_dashboard)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
