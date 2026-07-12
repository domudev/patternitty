<p align="center">
  <img src="viz/logo.svg" width="300" alt="patternity">
  <br><br>
  <b>DRY for your preferences.</b>
  <br>
  <sub>Scream at your agent once; patternity does the nagging from then on.</sub>
</p>

# You are lazy. That's the feature.

You've corrected your AI the same way a dozen times this week ("use uv, not
pip", "smaller modules", "stop explaining, just do it"), and you have never
once opened `CLAUDE.md` to write any of it down. Because that's work, and you
have a senior-engineer-grade allergy to work a tool should be doing for you.

It gets worse. Half the time you can't even be bothered to *tell* your agent
to update its own instructions, let alone edit them yourself. So you just
re-correct it next session. And the session after. Forever.

patternity ends the loop. It watches the corrections and preferences you keep
repeating, waits until it's sure you mean it, then quietly teaches every AI
assistant you use (Claude Code, Cursor, Copilot) to stop making you say it
again.

The arrangement is simple: you keep being lazy, patternity keeps the notes.
Nobody hand-maintains a `CLAUDE.md` ever again. You're welcome.

## What you get

- **Zero-effort memory.** Corrections and confirmations are captured
  automatically as you work. No "remember this" ritual, no prompting the
  agent to write anything down.
- **It waits before it trusts you.** A preference has to recur (or be stated
  as a flat "always/never") before it becomes a rule. One grumpy one-off
  won't calcify into law.
- **One brain, every tool.** Learned rules compile into `CLAUDE.md`,
  `AGENTS.md`, Cursor rules, and Copilot instructions, from a single source.
- **You stay in charge (lazily).** Accept or reject from a dashboard, or just
  tell your agent "reject that". It's all plain, git-tracked markdown you can
  eyeball or revert.
- **Personal + team.** Your preferences follow you across repos; team
  conventions live committed in the repo.

## Install

### Claude Code

Add the marketplace:

```
/plugin marketplace add domudev/patternity
```

Install the plugin:

```
/plugin install patternity@patternity
```

Then just work. After a few sessions, run `/patternity` and watch it write
the `CLAUDE.md` you were never going to.

### Cursor

From your patternity clone, wire the hooks into a project:

```
scripts/install.sh /path/to/your/project cursor
```

### GitHub Copilot

```
scripts/install.sh /path/to/your/project copilot
```

Full setup, git-history seeding, and backing up your store:
**[docs/install.md](docs/install.md)**.

## How it works (10-second version)

```
capture  ->  noticed -> recurring -> adopted  ->  compile into your tools
```

It notices a preference, waits for it to recur, and once **adopted** compiles
it into your assistants' instructions. No approval gate; every change is a
git diff you can revert. Full walkthrough: **[docs/how-it-works.md](docs/how-it-works.md)**.

## Docs

- **[How it works](docs/how-it-works.md)**: capture, the noticed/recurring/adopted ladder, compilation
- **[Install & hosts](docs/install.md)**: Claude Code, Cursor, Copilot, git-history mining, backing up your store
- **[Dashboard](docs/dashboard.md)**: the board, accept/reject, the profile panel
- **[CLI & server](docs/cli.md)**: `patternity.py` commands and the localhost API
- **[Patterns & the store](docs/patterns.md)**: schema, two tiers, scoping, clusters, provenance, overrides
- **[Development](docs/development.md)**: tests, conventional commits, releases, repo layout
