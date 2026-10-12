---
type: llm
---

The fixture is project/docs/changelog.md: entries are grouped under year headings ("## <year>") with dated "### <date> — <title>" entries beneath, newest first, and a stated ~3-month rule. "Payment webhook retry" and "Image CDN" are inside the window; "Old importer removed" and "Initial" are older than three months.

PASS only if the response proposes a split that moves "Old importer removed" and "Initial" to the archive while "Payment webhook retry" and "Image CDN" stay current — i.e. the split lands at an entry, not at a year heading that still has current entries under it.

FAIL if the response proposes moving an entire year group that contains "Payment webhook retry" or "Image CDN"; if it proposes archiving either of those entries; or if it treats a bare year heading as an entry dated 1 January.
