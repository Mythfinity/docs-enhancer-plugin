---
type: llm
---

The fixture is project/. CLAUDE.md links docs/commands.md and docs/changelog.md, but ALSO embeds the entire command reference (a "## Commands" section listing a dozen commands) that duplicates docs/commands.md line for line. The changelog has two recent entries and is within its stated window.

PASS only if ALL of these hold:
1. The response reports that CLAUDE.md has drifted from being an index: it embeds the command reference that already lives in docs/commands.md, and recommends moving or removing that duplication.
2. It reports docs/changelog.md as fine / within its rule and proposes no split for it.
3. It does not rewrite CLAUDE.md itself; it recommends and asks.

FAIL if it misses the duplicated command reference; if it proposes splitting or archiving the changelog; or if it reports having edited CLAUDE.md.
