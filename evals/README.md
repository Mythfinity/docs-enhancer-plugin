# Evals

Behavioural tests for the `docs-enhancer` skill, run with Claude Code's plugin eval runner. Each case scaffolds a small fixture project (dates generated relative to today, so cases don't rot), asks for a docs audit, and grades the answer.

| Case | What it checks |
|---|---|
| `overdue-with-rule` | Honours the file's own 3-month rule, proposes the right split point, leaves the stable reference doc alone, asks before writing |
| `overdue-no-rule-large` | Undated 5,000-line log: applies the size fallback and says so; invents no dates or rules |
| `closed-historical` | A changelog with no entries since 2022 is a closed record — no split proposed (the false-positive trap) |
| `code-fence-trap` | A `## 2020-01-01` line inside a code block is not an entry; the split lands at the first real old entry |
| `year-grouped` | `## 2026` / `### date` layout: the split lands at an entry, not at a year heading with current entries under it |
| `index-drift` | CLAUDE.md embedding a command reference that duplicates a linked doc is flagged, not rewritten |

Every case also checks that the skill fired and (where relevant) that the bundled script was used rather than the file eyeballed, and that no archive file was written during the audit.

## Running

Each run is a real Claude session on your account, so it costs money. By default each case runs 3 times in two arms (with and without the plugin). Start small:

```bash
claude plugin eval . --case overdue-with-rule --scaffold --allow-tools Bash --runs 1 --ablation none
```

Whole suite:

```bash
claude plugin eval . --scaffold --allow-tools Bash --threshold 0.8
```

- `--scaffold` is required: it runs each case's `fixture.sh`, which creates the fixture project. Scripts run as you; read them first if you didn't write them.
- `--allow-tools Bash` lets the skill run `split_changelog.py`; without it the "used-script" graders can't pass.
- Results land in `evals/results/` (gitignored). `--keep-temp` keeps the scaffolded workspaces for debugging.
- Requires Claude Code 2.1.269+ and git 2.31+.
