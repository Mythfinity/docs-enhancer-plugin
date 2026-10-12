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
Path('project/CLAUDE.md').write_text("""# Ledger Importer

Pulls bank statements and reconciles them against the ledger.

## Docs

- [Activity log](docs/activity-log.md) — running log of what changed, newest first
- [Architecture](docs/architecture.md) — system overview
""")
Path('project/docs/architecture.md').write_text("""# Architecture

Ledger Importer pulls bank statements and reconciles them against the ledger.

## Components

- **fetcher** — talks to each bank adapter, downloads statements on a schedule, stores them raw.
- **parser** — turns raw statements (CSV, MT940, CAMT.053) into normalised transactions.
- **reconciler** — matches transactions against ledger entries; unmatched ones go to the review queue.

## Data flow

1. `fetcher` downloads a statement and writes it to the raw store keyed by bank, account and period.
2. `parser` reads it, emits one normalised transaction per line, and marks the statement parsed.
3. `reconciler` matches by amount, date window and reference; matches are posted, the rest are queued for review.

## Failure handling

Every step is idempotent on (bank, account, period): re-running a fetch or parse replaces the previous result.
A statement that fails to parse three times is flagged and left for a human; nothing downstream runs on it.

## Invariants

- A transaction is posted to the ledger at most once, keyed by (bank, account, statement line id).
- The review queue only holds transactions with no match; a later match removes them.
""")
titles = ["Reconcile tweak", "Parser fix", "New bank adapter", "Retry policy", "Schema bump",
          "Dashboard tile", "Timeout raised", "Cleanup", "Audit trail", "Perf pass"]
out = ["# Activity log\n", "\nNewest first.\n"]
for n in range(420, 0, -1):
    out.append(f"\n## Entry {n} — {titles[n % len(titles)]}\n\n")
    out.append("What changed and why, in a few lines:\n")
    for i in range(8):
        out.append(f"- note {i + 1} for entry {n}: adjusted behaviour, checked the dashboards, nothing else affected\n")
Path('project/docs/activity-log.md').write_text("".join(out))
PY
