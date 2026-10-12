---
type: llm
---

The fixture is project/ with CLAUDE.md linking docs/activity-log.md (about 5,000 lines of numbered "## Entry N — …" sections, newest first, with no dates anywhere and no stated retention rule) and docs/architecture.md (a short stable reference doc).

PASS only if ALL of these hold:
1. The response reports docs/activity-log.md as oversized (on the order of 5,000 lines) and proposes splitting it at an entry boundary, keeping roughly the first ~1,500 lines current and archiving the rest.
2. It says explicitly that the file has no dated entries and no stated rule, so a size-based fallback (about 1,500 lines) is being applied rather than a rule the project stated.
3. It does not propose splitting docs/architecture.md.
4. It has not performed the split — it reports and asks first.

FAIL if any of: it invents dates for the entries or claims the file states a retention rule; it says the file is fine as it is; it proposes splitting, archiving or trimming architecture.md; it reports having already written an archive.
