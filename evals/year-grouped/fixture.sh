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
Path('project/CLAUDE.md').write_text("""# Photo Pipeline

Ingests, tags and serves photos.

## Docs

- [Changelog](docs/changelog.md) — grouped by year, newest first; keep ~3 months current
""")
entries = [(10, "Payment webhook retry", "Retry webhook delivery with backoff."),
           (60, "Image CDN", "Serve derived images from the CDN."),
           (150, "Old importer removed", "The v1 importer is gone."),
           (300, "Initial", "First cut of the pipeline.")]
out = ["# Changelog\n", "\nGrouped by year, newest first. Keep ~3 months current; archive the rest.\n"]
year = None
for days, title, body in entries:
    day = t - timedelta(days=days)
    if day.year != year:
        year = day.year
        out.append(f"\n## {year}\n")
    out.append(f"\n### {day.isoformat()} — {title}\n\n{body}\n")
Path('project/docs/changelog.md').write_text("".join(out))
PY
