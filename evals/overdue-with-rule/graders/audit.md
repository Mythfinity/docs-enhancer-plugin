---
type: llm
---

The fixture is project/ with CLAUDE.md linking docs/architecture.md (a stable reference doc) and docs/changelog.md (newest-first, states "Move entries out once older than ~3 months"). Two changelog entries are older than three months: "Legacy export removed" and "Initial import". The three newer entries ("Resize retry fix", "WebP output", "Cache index rebuild") are inside the window.

PASS only if ALL of these hold:
1. The response says docs/changelog.md is overdue under its own ~3-month rule and proposes splitting it so that "Legacy export removed" and "Initial import" move to an archive file while "Cache index rebuild" and the newer entries stay. Noting that the file is small and the gain modest is fine, as long as the split is still proposed as the action.
2. It does not propose splitting, archiving, or trimming docs/architecture.md.
3. It has not performed the split: it reports and asks for confirmation (an audit report ending in a question is correct).

FAIL if any of: it proposes archiving "Cache index rebuild" or a newer entry; it proposes splitting, archiving or trimming architecture.md; it says no action is needed; it reports having already created an archive or rewritten the changelog.
