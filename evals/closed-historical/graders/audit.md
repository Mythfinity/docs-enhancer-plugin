---
type: llm
---

The fixture is project/ for a tool that is no longer developed. docs/changelog.md has five entries, all from 2021–2022, newest first, with no entries since. A naive "older than 3 months" check would flag every entry; the right conclusion is that this changelog is a closed historical record.

PASS only if the response concludes that docs/changelog.md is dormant / a closed historical record (nothing has been added in years) and proposes NO split or archive for it. Flagging other, genuine issues is fine.

FAIL if the response proposes splitting docs/changelog.md, moving its entries to an archive file, or otherwise restructuring it because the entries are old.
