#!/bin/bash
# SessionStart hook: scan the project's linked/imported docs (and its MEMORY.md)
# for changelog-style files that are overdue for a split. Prints one line per
# overdue file, which Claude Code adds to the session context; prints nothing
# when everything is fine. Never blocks the session: any failure exits 0 silently.
#
# Tuning (set in your shell):
#   DOCS_ENHANCER_MONTHS=6   age window used when a file states no rule (default 3)
#   DOCS_ENHANCER_LINES=1000 size limit for auto-loaded files without dates (default 1500)
#   DOCS_ENHANCER_SKIP=1     disable the check entirely

[ -n "${DOCS_ENHANCER_SKIP:-}" ] && exit 0
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

project="${CLAUDE_PROJECT_DIR:-$PWD}"
script="${CLAUDE_PLUGIN_ROOT}/skills/docs-enhancer/scripts/split_changelog.py"
[ -f "$script" ] || exit 0

python3 -I "$script" scan "$project" 2>/dev/null || true
exit 0
