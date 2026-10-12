#!/usr/bin/env bash
# Builds this case's fixture project in the run's empty workspace.
# Dates are generated relative to today so the case does not rot as the calendar moves.
set -euo pipefail
mkdir -p project/docs
python3 - <<'PY'
from datetime import date, timedelta
from pathlib import Path
t = date.today()
d = lambda days: (t - timedelta(days=days)).isoformat()
COMMANDS = """Each command takes `--env` unless the environment is given positionally.

- `tool sync <env>` — pull the latest state for an environment
- `tool diff <a> <b>` — compare two environments
- `tool apply <plan>` — apply a saved plan; refuses if the plan is stale
- `tool plan <env>` — compute the changes needed to reach the desired state
- `tool lock <env>` — take the environment lock; released automatically after apply
- `tool unlock <env>` — force-release a lock (ask the owner first)
- `tool status` — show locks, pending plans and the last apply per environment
- `tool history <env>` — list applies with who/when/what
- `tool rollback <env> <id>` — re-apply the state from a previous apply
- `tool validate <file>` — check a desired-state file without planning
- `tool fmt <file>` — normalise a desired-state file in place
- `tool export <env>` — dump the live state as a desired-state file
"""
Path('project/docs/commands.md').write_text("# Commands\n\n" + COMMANDS)
Path('project/CLAUDE.md').write_text("""# Fleet Tool

Keeps environment state in sync.

## Docs

- [Commands](docs/commands.md) — command reference
- [Changelog](docs/changelog.md) — newest first; ~3 months kept current

## Commands

""" + COMMANDS + """
## Conventions

- Plans are immutable once saved.
- Never unlock an environment you don't own.
""")
Path('project/docs/changelog.md').write_text(f"""# Changelog

Newest first. Entries older than ~3 months are archived.

## {d(12)} — Rollback command

`tool rollback` re-applies a previous state.

## {d(50)} — Lock timeouts

Locks expire after 2 hours.
""")
PY
