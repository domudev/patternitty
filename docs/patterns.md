# Patterns & the store

Patterns are plain markdown with YAML frontmatter. The full schema —
frontmatter fields, the state ladder, and authoring rules — lives in
[`patterns/_SCHEMA.md`](../patterns/_SCHEMA.md). This page covers the
concepts around it.

Only `name` is required; every other field (`type`, `state`, `occurrences`,
`applies_to`, `agent`, `author`, …) defaults on read, so the minimal pattern
is a name + a body.

## Two tiers: personal + team

| Tier | Location | For |
|---|---|---|
| **Personal** (default) | `${PATTERNITTY_HOME:-~/.patternitty}/patterns/` | your preferences, global across every repo |
| **Team** | `<git-root>/.patternitty/patterns/` (committed) | conventions that belong to *this project*, shared with whoever clones it |

Add a team pattern with `patternitty.py add <name> --repo`. `compile.py`
merges both: repo-tier patterns are always in scope for their repo; personal
ones are narrowed by `applies_to.project`; a repo pattern wins on a name
clash.

**Gitignore for a repo using the team tier:** commit `.patternitty/patterns/`
and the generated `patternitty/`, but ignore the transient capture log
(`.patternitty/signal.jsonl`, `.patternitty/state.json`).

## Provenance

Every pattern records `agent` (which harness captured it — `claude-code` /
`cursor` / `copilot`) and `author` (the git identity it was learned from, or
`anon`). Informational, not used for compilation — but in a shared team store
they show who/what each pattern came from (surfaced in the dashboard drawer).

## Fine-grained scoping

`applies_to.project` keeps a personal pattern from leaking everywhere: it
scopes to the repo(s) it's actually been seen in, widening to `"*"` only once
it's shown up across more than one project. `applies_to.tool` / `glob` scope
by host and file pattern. (Repo-tier patterns skip this — implicitly scoped
to their repo.)

## Clusters → a profile

`cluster` groups patterns by theme (tooling, code-style, workflow, …). The
skill reuses an existing cluster when a pattern fits one and mints a new one
only when nothing does, keeping the set small. Clusters drive both the
per-cluster compiled files (`patternitty/<cluster>.md`) and the synthesized
`PROFILE.md` narrative.

## Overrides

A pattern can *suppress* an annoying rule from another plugin/instruction
file instead of only adding rules: set `type: override` and `target` to the
literal snippet to remove. Once the override is `adopted`, `compile.py`
deletes that exact text from wherever it appears; if it's not found verbatim
(the source changed), it's flagged under `## Overrides (needs manual check)`
rather than silently failing. This is the only reliable way to suppress a
rule in Copilot, which resolves conflicting instructions non-deterministically.
