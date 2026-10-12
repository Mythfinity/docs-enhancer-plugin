# docs-enhancer

A Claude Code plugin that keeps a project's changelog-style docs from growing forever.

Many projects keep a rolling log — `docs/recent-changes.md`, `CHANGELOG.md`, `HISTORY.md`, an activity log — linked from `CLAUDE.md`. Some even state a rule ("move entries out once older than ~3 months"). Nothing enforces it, so the file grows, and every reader who wants the last few weeks pays for the whole history. This plugin notices when a log has outgrown its rule and splits it into a current window plus a dated archive — moving content, never deleting it, and verifying the result.

## What you get

| Piece | What it does |
|---|---|
| **Session-start check** (hook) | At the start of each session, checks the docs your `CLAUDE.md` links to or `@imports`, plus the project's `MEMORY.md`. Prints one line per overdue file; silent when everything is fine. Takes milliseconds, uses no tokens. |
| **`/docs-enhancer`** (skill) | Audits the index and its linked docs, reports findings, and — only after you confirm — performs the split and updates the index link. Also flags an index that has drifted into holding detail that belongs in topic files. |
| **`split_changelog.py`** (script) | The deterministic core: finds the split point, writes the archive, trims the original, and verifies that current + archive reproduce the original byte-for-byte. Usable outside Claude too. |

## Install

```bash
claude plugin marketplace add Mythfinity/docs-enhancer-plugin
```

```bash
claude plugin install docs-enhancer@docs-enhancer
```

Restart Claude Code afterwards so the session-start hook loads. Requires `python3` (3.8+) on `PATH`; without it the hook stays silent and the skill tells you.

Skill only, no hook: copy `skills/docs-enhancer` into `~/.claude/skills/`.

## What you'll see

When a log is overdue, the session starts with a notice like:

```
[docs-enhancer] Documentation overdue for a split:
- docs/recent-changes.md: 2 entries older than the stated 3-month rule (oldest 2026-01-15); newest 2026-10-02
Run /docs-enhancer to review and split. Nothing is changed without confirmation.
```

Run `/docs-enhancer` (or just ask Claude to review the docs). You get an audit report first: which files were checked, which rule applied, where the split would land and how many entries move. Nothing is written until you say so.

## What "overdue" means

A file is flagged only when it is **still active** (its newest entry is inside the window) **and** has entries outside it. A log whose newest entry is itself old is a closed historical record and is left alone. A file that is merely long is not flagged.

The window comes from, in order: `--months` if given, a rule stated in the file's first lines ("… older than 3 months"), else 3 months. Files with no parseable dates are judged by size (1,500 lines) — and only if they are auto-loaded (`@import` or `MEMORY.md`), since a long linked reference doc is allowed to be long.

## What the split does

For `docs/recent-changes.md`:

- Creates `docs/recent-changes-archive.md` with a one-line header linking back to the current file, followed by the moved entries. If an archive already exists, the moved entries are prepended to it (appended, for an oldest-first log).
- Trims the current file to the entries inside the window and adds a one-line pointer to the archive.
- Reads both files back and checks that current + archive equal the original apart from those pointer lines. On any mismatch it prints `ABORTED` and exits 2.

Handled correctly: newest-first and oldest-first files (order is detected), year-grouped files (`## 2026` with dated `###` entries — the year heading is repeated on the other side so moved entries keep their year), `## [1.4.0] - 2026-09-20` Keep-a-Changelog headers, `## May 2026` month headers, and `##` lines inside code fences (ignored). Undated sections caught in the moved range (a trailing "See also") are called out in the plan so you can stop before applying.

## The script on its own

```bash
python3 skills/docs-enhancer/scripts/split_changelog.py check docs/CHANGELOG.md
```

```bash
python3 skills/docs-enhancer/scripts/split_changelog.py plan docs/CHANGELOG.md --months 6
```

```bash
python3 skills/docs-enhancer/scripts/split_changelog.py apply docs/CHANGELOG.md
```

`scan <project-dir>` is what the hook runs. `check` and `scan` take `--json`.

## Tuning

Environment variables, read by the session-start check:

- `DOCS_ENHANCER_MONTHS=6` — default window for files that state no rule
- `DOCS_ENHANCER_LINES=1000` — size limit for auto-loaded files without dates
- `DOCS_ENHANCER_SKIP=1` — disable the check

The better fix is to state the rule in the file itself: a line like `Entries older than ~3 months are moved to recent-changes-archive.md.` near the top is picked up automatically and documents the convention for humans too.

## Development

```bash
python3 -m unittest discover -s tests
```

Evals live in `evals/` and run with `claude plugin eval .` — see `evals/README.md`.

## License

MIT — see [LICENSE](LICENSE).
