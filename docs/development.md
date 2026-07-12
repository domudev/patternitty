# Development

## Tests

Four self-checks, plain `uv run` scripts (no framework, no deps):

```bash
for t in tests/test_*.py; do uv run "$t"; done
```

- `test_compile` — adopted patterns compile, non-adopted don't, scoping,
  overrides, two-tier merge, idempotency, `</script>` escaping
- `test_patternitty` — BM25 ranking, regex, add/bump/set, provenance
- `test_decide` — accept/reject/clear frontmatter surgery
- `test_capture` — the three host payload shapes + meta/junk filtering

CI runs these on every push and PR (`.github/workflows/ci.yml`).

## Contributing (trunk-based)

`main` is protected: changes land via PR with a passing `test` check, a
Conventional-Commit-shaped PR title (`lint` check), and code-owner review.
The repo is squash-merge only, so **the PR title becomes the commit** on
`main`.

Use [Conventional Commits](https://www.conventionalcommits.org/) for PR
titles: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `chore:`, … — a `feat:`
bumps the minor version, `fix:` the patch, `feat!:`/`BREAKING CHANGE` the
major.

## Releases (release-please)

Releases are automated by [release-please](https://github.com/googleapis/release-please)
(`.github/workflows/release-please.yml`). It reads Conventional Commits on
`main` and maintains a rolling **release PR** that bumps the version
(`.claude-plugin/plugin.json` via a JSON updater) and updates `CHANGELOG.md`.
Merging that PR tags `vX.Y.Z` and cuts the GitHub Release.

So the release flow is: **merge conventional PRs → merge the release PR when
you want to ship.** No manual version bumping or tagging. Consumers can pin a
version via the marketplace `source` ref (`domudev/patternitty#vX.Y.Z`).

## Repo layout

- `skills/patternitty/SKILL.md` — the distillation/promotion logic (the skill)
- `commands/` — `/patternitty:compile`, `/patternitty:dashboard` (distillation is the `patternitty` skill, `/patternitty`)
- `hooks/` — the shared capture hook + per-host hook configs
- `scripts/` — `patternitty.py` (CLI + server), `compile.py`, `mine_git_history.py`, `decide.py`, shared `_lib.py`; plus `install.sh` and `init_store.sh`
- `patterns/` — `_SCHEMA.md` + reference example (the real store is `${PATTERNITTY_HOME:-~/.patternitty}/patterns/`)
- `viz/` — `template.html` (compiled into the store as `index.html`) + `logo.svg`
- `.claude-plugin/` — `plugin.json` + `marketplace.json`
- `tests/` — the four self-checks
