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
Path('project/CLAUDE.md').write_text("""# Badge Printer

Prints visitor badges. No longer actively developed.

## Docs

- [Changelog](docs/changelog.md) — history of changes
- [Operations](docs/operations.md) — how to run it
""")
Path('project/docs/operations.md').write_text("""# Operations

Start with `badge-printer serve`. Logs go to /var/log/badge-printer.
The printer must be on the same VLAN; see the network team for the port.
""")
Path('project/docs/changelog.md').write_text("""# Changelog

## 2022-11-03 — Final release

Pinned dependencies; no further development planned.

## 2022-06-17 — Printer driver update

Supports the ZD421.

## 2022-02-02 — Badge template v3

Larger name field, QR code moved to the bottom.

## 2021-09-20 — Visitor photo

Optional photo on the badge.

## 2021-03-08 — Initial release

First version used at reception.
""")
PY
