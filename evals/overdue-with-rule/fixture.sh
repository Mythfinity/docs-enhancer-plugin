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
Path('project/CLAUDE.md').write_text("""# Widget Service

Internal service that resizes widget images.

## Documentation map

- [Architecture](docs/architecture.md) — how the pieces fit together
- [Changelog](docs/changelog.md) — rolling log of changes, newest first
""")
Path('project/docs/architecture.md').write_text('# Architecture\n\nWidget Service resizes widget images on demand and caches the results.\n\n## Components\n\n- **api** — HTTP front door. Validates requests, looks up the cache, enqueues misses.\n- **worker** — pulls resize jobs from the queue, runs the resize pipeline, writes to storage.\n- **storage** — object store with a content-addressed layout; the cache is a thin index over it.\n\n## Request flow\n\n1. A client requests `/resize?w=…&h=…&src=…`.\n2. `api` hashes the parameters, checks the cache index, and returns the stored object on a hit.\n3. On a miss it enqueues a job and returns 202 with a poll URL.\n4. `worker` processes the job and writes the result; the next poll returns it.\n\n## Failure handling\n\nJobs are idempotent: a duplicate enqueue produces the same object key, so retries are safe.\nThe queue has a dead-letter topic; anything that fails three times lands there for inspection.\n\n## Invariants\n\n- The cache index never references an object that does not exist in storage.\n- Object keys are derived only from request parameters, never from time or request id.\n')
Path('project/docs/changelog.md').write_text(f"""# Changelog

Newest first. Move entries out once older than ~3 months.

## {d(10)} — Resize retry fix

Retries on 502 from the storage backend, with jitter.

## {d(45)} — WebP output

Serve WebP when the client accepts it; JPEG kept as the fallback.

## {d(70)} — Cache index rebuild

Nightly full rebuild replaced by incremental updates.

## {d(130)} — Legacy export removed

The CSV export of resize stats is gone; use the reports API.

## {d(200)} — Initial import

Imported the service from the monorepo.
""")
PY
