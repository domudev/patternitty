#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""patternitty — the agent-facing query/edit surface over the pattern store.

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

All commands operate on ${PATTERNITTY_HOME:-~/.patternitty}/patterns/.
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


# ── core operations (return plain data) — shared by the CLI and the server,
#    so a route and its command can never drift ────────────────────────────

def search_patterns(query: str, regex: bool = False, limit: int = 10) -> list[dict]:
    pats = {p["name"]: p for p in load_all()}
    if regex:
        rx = re.compile(query, re.I)
        hits = [(1.0, n) for n, p in pats.items() if rx.search(searchable(p))]
    else:
        hits = bm25(query, [(n, tokenize(searchable(p))) for n, p in pats.items()])
    return [
        {"name": n, "score": round(s, 3), **{k: pats[n].get(k, "") for k in ("state", "cluster", "decision", "type", "tier")}}
        for s, n in hits[:limit]
    ]


def get_pattern(name: str) -> dict | None:
    return next((x for x in load_all() if x["name"] == name), None)


def list_patterns(state=None, cluster=None, tier=None) -> list[dict]:
    pats = load_all()
    if state:
        pats = [p for p in pats if p.get("state") == state]
    if cluster:
        pats = [p for p in pats if p.get("cluster") == cluster]
    if tier:
        pats = [p for p in pats if p.get("tier") == tier]
    return [{k: p.get(k, "") for k in ("name", "tier", "state", "cluster", "decision", "occurrences", "type")} for p in pats]


def add_pattern(name, type="feedback", cluster=None, tool="*", project="*", agent=None, body="", repo=False) -> dict:
    if repo:
        directory = repo_patterns_dir()
        if directory is None:
            raise ValueError("--repo needs a git repo (no git root found here)")
        directory.mkdir(parents=True, exist_ok=True)
    else:
        ensure_store()
        directory = patterns_dir()
    path = directory / f"{name}.md"
    if path.exists():
        raise FileExistsError(name)
    agent = agent or os.environ.get("PATTERNITTY_AGENT") or "unknown"
    author = git_author()
    fm = [
        f"name: {name}", f"type: {type}", "state: noticed", "occurrences: 1",
        *([f"cluster: {cluster}"] if cluster else []),
        f"agent: {agent}", f"author: {author}",   # provenance: which harness / which user
        "applies_to:", f"  tool: \"{tool}\"", "  glob: \"**/*\"", f"  project: \"{project}\"",
        *(["target: null"] if type == "override" else []),
    ]
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n")
    return {"name": name, "tier": "repo" if repo else "user", "state": "noticed", "agent": agent, "author": author}


def bump_pattern(name: str) -> dict:
    path = resolve_path(name)
    if path is None:
        raise FileNotFoundError(name)
    p = parse_pattern(path)
    occ = (int(p.get("occurrences", 0) or 0)) + 1
    state = next(s for threshold, s in LADDER if occ >= threshold)
    set_field(path, "occurrences", str(occ))
    set_field(path, "state", state)
    return {"name": name, "occurrences": occ, "state": state}


def set_decision(name: str, decision: str | None) -> bool:
    path = resolve_path(name)
    if path is None:
        return False
    set_field(path, "decision", decision or None)
    return True


# ── CLI wrappers (format the core results for a terminal) ──────────────────

def cmd_search(args) -> int:
    results = search_patterns(args.query, args.regex, args.limit)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['score']:6.2f}  {r['name']}")
        if not results:
            print("(no matches)")
    return 0


def cmd_get(args) -> int:
    p = get_pattern(args.name)
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
    rows = list_patterns(args.state, args.cluster, args.tier)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r.get('tier',''):5} {r.get('state',''):9} {r.get('cluster',''):14} {r['name']}")
    return 0


def cmd_add(args) -> int:
    body = args.body or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    try:
        r = add_pattern(args.name, args.type, args.cluster, args.tool, args.project, args.agent, body, args.repo)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    except FileExistsError:
        print(f"already exists: {args.name} (use `set`/`bump` to edit)", file=sys.stderr)
        return 1
    print(f"added {args.name} to {r['tier']} store (noticed, agent={r['agent']}, author={r['author']})")
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
    try:
        r = bump_pattern(args.name)
    except FileNotFoundError:
        print(f"no such pattern: {args.name}", file=sys.stderr)
        return 1
    print(f"{args.name}: occurrences={r['occurrences']}, state={r['state']}")
    return 0


# ── server routes: a table of small handlers, dispatched by (method, path).
#    each takes a params dict and returns (status, json-able). Mutations return
#    the refreshed index so the page can re-render in one round-trip. ──────────

def _refresh_index() -> list:
    import compile as compile_mod
    compile_mod.write_viz(load_all())  # keep index.json (the embedded data) current
    return json.loads((patterns_dir() / "index.json").read_text())


def _route_search(p): return 200, search_patterns(p.get("q", ""), p.get("regex") == "1", int(p.get("limit") or 10))
def _route_list(p): return 200, list_patterns(p.get("state"), p.get("cluster"), p.get("tier"))
def _route_get(p): return ((200, x) if (x := get_pattern(p.get("name", ""))) else (404, {"error": "not found"}))
def _route_add(p):
    add_pattern(p.get("name", ""), p.get("type", "feedback"), p.get("cluster"), p.get("tool", "*"),
                p.get("project", "*"), p.get("agent"), p.get("body", ""), bool(p.get("repo")))
    return 200, _refresh_index()


def _route_decide(p):
    set_decision(p.get("name", ""), p.get("decision") or None)
    return 200, _refresh_index()


def _route_bump(p):
    bump_pattern(p.get("name", ""))
    return 200, _refresh_index()


def _route_compile(p):
    import compile as compile_mod
    compile_mod.main()  # apply adopted patterns to the repo the server started in
    return 200, {"ok": True}


ROUTES = {
    ("GET", "/search"): _route_search, ("GET", "/list"): _route_list, ("GET", "/get"): _route_get,
    ("POST", "/decide"): _route_decide, ("POST", "/add"): _route_add,
    ("POST", "/bump"): _route_bump, ("POST", "/compile"): _route_compile,
}


def _open(url_or_path) -> None:
    if os.environ.get("PATTERNITTY_NO_OPEN"):
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
    from urllib.parse import parse_qs, urlparse

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            body = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self, method):
            u = urlparse(self.path)
            if method == "GET" and u.path in ("/", "/index.html"):
                return self._send(200, html_path.read_bytes(), "text/html; charset=utf-8")
            fn = ROUTES.get((method, u.path))
            if fn is None:
                return self._send(404, {"error": "not found"})
            if method == "GET":
                params = {k: v[0] for k, v in parse_qs(u.query).items()}
            else:
                params = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            try:
                code, data = fn(params)
            except (ValueError, FileExistsError, FileNotFoundError) as e:
                code, data = 400, {"error": str(e) or type(e).__name__}
            self._send(code, data)

        def do_GET(self): self._dispatch("GET")
        def do_POST(self): self._dispatch("POST")
        def log_message(self, *a): pass  # quiet

    # random free port by default (0 = OS picks) so it never clashes with
    # whatever's already running; the server opens the browser itself, so the
    # port doesn't need to be known ahead of time. Override with PATTERNITTY_PORT.
    port = int(os.environ.get("PATTERNITTY_PORT", "0"))
    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"serving patternitty dashboard at {url}  (Ctrl-C to stop)", flush=True)
    _open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="patternitty", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
