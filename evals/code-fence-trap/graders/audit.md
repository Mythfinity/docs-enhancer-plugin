---
type: llm
---

The fixture is project/docs/changelog.md, newest first, with a stated ~3-month rule. The entry "Docs: header examples" is recent and contains a fenced code block holding the text "## 2020-01-01 — sample header" — that line is an example inside a code block, not an entry. "Cache warmup" is also recent. "Rate limiter rewrite" and "Bootstrap" are older than three months.

PASS only if the response proposes the split at the "Rate limiter rewrite" entry (so that it and "Bootstrap" move to the archive) and keeps "Docs: header examples" and "Cache warmup" in the current file.

FAIL if the proposed split point is at, or inside, the "Docs: header examples" entry; if the "2020-01-01 sample header" line is treated as an entry; or if "Cache warmup" is proposed for archiving.
