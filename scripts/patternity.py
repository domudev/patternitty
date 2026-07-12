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
View:   dashboard [--serve]                  (open index.html; --serve adds
                                             instant accept/reject write-back)

All commands operate on ${PATTERNITY_HOME:-~/.patternity}/patterns/.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ensure_store, git_author, load_all, parse_pattern, patterns_dir, repo_patterns_dir, set_field  # noqa: E402


def resolve_path(name: str) -> Path | None:
    """Locate a pattern file across both tiers (repo takes precedence)."""
    for directory in (repo_patterns_dir(), patterns_dir()):
        if directory and (directory / f"{name}.md").exists():
            return directory / f"{name}.md"
    return None

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
    # search both tiers (repo takes precedence, same as load_all)
    p = next((x for x in load_all() if x["name"] == args.name), None)
    if p is None:
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(p, indent=2))
    else:
        tier_dir = repo_patterns_dir() if p.get("tier") == "repo" else patterns_dir()
        print((tier_dir / f"{args.name}.md").read_text())
    return 0


def cmd_list(args) -> int:
    pats = load_all()
    if args.state:
        pats = [p for p in pats if p.get("state") == args.state]
    if args.cluster:
        pats = [p for p in pats if p.get("cluster") == args.cluster]
    if args.tier:
        pats = [p for p in pats if p.get("tier") == args.tier]
    if args.json:
        print(json.dumps([{k: p.get(k, "") for k in ("name", "tier", "state", "cluster", "decision", "occurrences", "type")} for p in pats], indent=2))
    else:
        for p in pats:
            print(f"{p.get('tier',''):5} {p.get('state',''):9} {p.get('cluster',''):14} {p['name']}")
    return 0


def cmd_add(args) -> int:
    # --repo targets the committed team store (<git-root>/.patternity/patterns);
    # default is the personal per-user store.
    if args.repo:
        directory = repo_patterns_dir()
        if directory is None:
            print("--repo needs a git repo (no git root found here)", file=sys.stderr)
            return 1
        directory.mkdir(parents=True, exist_ok=True)
    else:
        ensure_store()
        directory = patterns_dir()
    path = directory / f"{args.name}.md"
    if path.exists():
        print(f"already exists: {args.name} (use `set`/`bump` to edit)", file=sys.stderr)
        return 1
    body = args.body or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    agent = args.agent or os.environ.get("PATTERNITY_AGENT") or "unknown"
    fm = [
        f"name: {args.name}", f"type: {args.type}", "state: noticed", "occurrences: 1",
        *([f"cluster: {args.cluster}"] if args.cluster else []),
        f"agent: {agent}", f"author: {git_author()}",   # provenance: which harness / which user
        "applies_to:", f"  tool: \"{args.tool}\"", "  glob: \"**/*\"", f"  project: \"{args.project}\"",
        *(["target: null"] if args.type == "override" else []),
    ]
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n")
    print(f"added {args.name} to {'repo' if args.repo else 'user'} store (noticed, agent={agent}, author={git_author()})")
    return 0


def cmd_set(args) -> int:
    path = resolve_path(args.name)
    if path is None:
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    if not args.clear and args.value is None:
        print("set needs a value, or --clear to remove the field", file=sys.stderr)
        return 1
    set_field(path, args.field, None if args.clear else args.value)
    print(f"{args.name}: {args.field} = {'(cleared)' if args.clear else args.value}")
    return 0


def cmd_bump(args) -> int:
    path = resolve_path(args.name)
    if path is None:
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    p = parse_pattern(path)
    occ = (int(p.get("occurrences", 0) or 0)) + 1
    state = next(s for threshold, s in LADDER if occ >= threshold)
    set_field(path, "occurrences", str(occ))
    set_field(path, "state", state)
    print(f"{args.name}: occurrences={occ}, state={state}")
    return 0


def _open(url_or_path) -> None:
    if os.environ.get("PATTERNITY_NO_OPEN"):
        return  # headless / tests
    opener = {"darwin": "open", "win32": "start"}.get(sys.platform, "xdg-open")
    subprocess.run([opener, str(url_or_path)], shell=(opener == "start"), check=False)


def cmd_dashboard(args) -> int:
    # first run has no store yet — create it and render an empty board rather
    # than dead-ending, so there's always something to open.
    ensure_store()
    import compile as compile_mod  # regenerate the viz from the store (no project needed)
    compile_mod.write_viz(load_all())
    html_path = patterns_dir() / "index.html"

    if not args.serve:
        # non-blocking: just open the static file (safe for the plugin command).
        # accept/reject falls back to the copy-a-command tray.
        print(f"opening {html_path}")
        _open(html_path)
        return 0

    # interactive: serve on 127.0.0.1 with a write-back endpoint, so accept/
    # reject persists to the store instantly (no copy). Blocks until Ctrl-C —
    # run this from a terminal, not via the agent's dashboard command.
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, html_path.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path == "/decide":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length) or b"{}")
                path = resolve_path(data.get("name", ""))
                if path:
                    set_field(path, "decision", data.get("decision") or None)
                compile_mod.write_viz(load_all())  # refresh embedded data
                self._send(200, (patterns_dir() / "index.json").read_bytes(), "application/json")
            elif self.path == "/compile":
                # apply adopted patterns to the repo the server was started in
                compile_mod.main()
                self._send(200, b'{"ok":true}', "application/json")
            else:
                self._send(404, b"not found", "text/plain")

        def log_message(self, *a):
            pass  # quiet

    server = HTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"serving patternity dashboard at {url}  (Ctrl-C to stop)", flush=True)
    _open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="patternity", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--regex", action="store_true"); s.add_argument("--limit", type=int, default=10); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_search)
    g = sub.add_parser("get"); g.add_argument("name"); g.add_argument("--json", action="store_true"); g.set_defaults(fn=cmd_get)
    ls = sub.add_parser("list"); ls.add_argument("--state"); ls.add_argument("--cluster"); ls.add_argument("--tier", choices=["user", "repo"]); ls.add_argument("--json", action="store_true"); ls.set_defaults(fn=cmd_list)
    a = sub.add_parser("add"); a.add_argument("name"); a.add_argument("--type", default="feedback"); a.add_argument("--cluster"); a.add_argument("--tool", default="*"); a.add_argument("--project", default="*"); a.add_argument("--agent"); a.add_argument("--body"); a.add_argument("--repo", action="store_true", help="write to the committed per-repo store instead of the personal one"); a.set_defaults(fn=cmd_add)
    st = sub.add_parser("set"); st.add_argument("name"); st.add_argument("field"); st.add_argument("value", nargs="?"); st.add_argument("--clear", action="store_true"); st.set_defaults(fn=cmd_set)
    b = sub.add_parser("bump"); b.add_argument("name"); b.set_defaults(fn=cmd_bump)
    d = sub.add_parser("dashboard"); d.add_argument("--serve", action="store_true", help="serve on localhost with instant accept/reject write-back (blocks; run from a terminal)"); d.set_defaults(fn=cmd_dashboard)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
