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
Path('project/CLAUDE.md').write_text("""# Gateway

Edge gateway for the public API.

## Docs

- [Changelog](docs/changelog.md) — newest first; entries older than ~3 months are archived
""")
Path('project/docs/changelog.md').write_text(f"""# Changelog

Newest first. Entries older than ~3 months are moved to changelog-archive.md.

## {d(5)} — Docs: header examples

Documented the header format we use in this file. Example of an entry header:

```md
## 2020-01-01 — sample header

Body text.
```

Nothing else changed.

## {d(40)} — Cache warmup

Warm the route cache on deploy instead of on first request.

## {d(140)} — Rate limiter rewrite

Token bucket per client key; old fixed-window limiter removed.

## {d(220)} — Bootstrap

Initial gateway skeleton.
""")
PY
