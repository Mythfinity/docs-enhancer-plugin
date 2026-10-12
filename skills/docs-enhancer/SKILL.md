---
name: docs-enhancer
description: Audit a project's root index (CLAUDE.md, or README.md if that is the index) and the docs it links to or @imports, plus the project's MEMORY.md, for documentation hygiene — above all a changelog-style file (recent-changes.md, CHANGELOG.md, HISTORY.md, an activity log) that keeps growing past its own retention rule and should be split into a current window plus a dated archive, and an index that has drifted from a lean set of links into embedded detail. Use when asked to review, audit, or clean up documentation or CLAUDE.md structure; when a changelog-style file is described as large, long, old, or unwieldy; when a session started with a "[docs-enhancer] Documentation overdue for a split" notice; or when you are already in a project for another reason and notice a linked log has clearly outgrown its stated rule.
---

# Docs Enhancer

Audit a project's documentation structure — the root index and the files it points at — for the drift that quietly costs future sessions: an index that has stopped being an index, and a rolling log that never stops growing.

## Why this matters

Two kinds of file cost something every session:

- **Auto-loaded files**: the root `CLAUDE.md`, anything it `@imports`, and the project's `MEMORY.md`. These are read into context at session start, every time. Detail that creeps into them — a long command reference, a changelog, an explanation that belongs in a topic doc — is paid for on every turn of every session.
- **Linked files** (plain markdown links) cost nothing until opened. But a rolling log that is linked from the index *is* opened whenever someone wants recent history, and a reader who wants the last few weeks pays for the whole file.

Projects often state their own intent — "move entries out once older than ~3 months" — and then nothing enforces it. This skill, and the session-start check that ships with it, are the enforcement.

## Tooling

Everything mechanical is done by the bundled script, not by hand. It lives in this skill's `scripts/` directory; the base directory is given at the top of this skill when it loads.

```bash
python3 "<base directory>/scripts/split_changelog.py" check <file>   # overdue or not, and why
python3 "<base directory>/scripts/split_changelog.py" plan  <file>   # exactly what a split would move; writes nothing
python3 "<base directory>/scripts/split_changelog.py" apply <file>   # do it, then verify nothing was lost
python3 "<base directory>/scripts/split_changelog.py" scan  <dir>    # what the session-start hook runs
```

Options for `check`/`plan`/`apply`: `--months N` (age window; default is the file's own stated rule, else 3) or `--lines N` (size cutoff for files without dated entries; default 1500).

The script recognises `## 2026-07-17 …`, `## May 2026 …`, `## [1.4.0] - 2026-09-20` and year-only grouping headers (`## 2026` with dated `###` entries beneath), ignores headers inside code fences, and detects whether the file is newest-first or oldest-first. Do not eyeball split points in a long file — that is exactly the mechanical task that goes subtly wrong by hand.

## Step 1 — find the index and its candidates

Read the project's root index: `CLAUDE.md` (and `.claude/CLAUDE.md` if present); fall back to `README.md`; ask if it is genuinely unclear which file is the index. Collect every markdown file it links to or `@imports`, and the project's `MEMORY.md` (`~/.claude/projects/<cwd with / as ->/memory/MEMORY.md`) if one exists. `scan <dir>` does this collection and runs `check` on each — use it as the first pass.

## Step 2 — which of them are rolling logs

Among the candidates, the ones that behave like a log rather than a stable reference doc: names like `recent-changes.md`, `CHANGELOG.md`, `HISTORY.md`, `activity.md`, or any file whose body is a sequence of dated or numbered entries. A long reference doc about one stable feature is not a candidate; the signal is *entries that accumulate*, not length.

## Step 3 — the file's own rule, or the default

The script reads a stated "N months" rule from the first lines of the file and uses it. If the rule is phrased some other way ("keep the last quarter", "archive each January"), translate it yourself and pass `--months`. With no rule at all, the default is 3 months, or 1,500 lines for a file with no parseable dates. Honouring the project's own rule is safer than imposing an outside one.

## Step 4 — is it actually overdue

`check` says overdue only when the file is **still active** (newest entry inside the window) **and** has entries outside it. A file whose newest entry is itself old is dormant — a closed historical record, not a hygiene problem — and `check` says so. A file that merely looks long is not overdue. If nothing is overdue, say so plainly in the report and stop; don't restructure a file because you were asked to look at it.

## Step 5 — show the plan

Run `plan` and put its output in your report: the boundary line and header, how many lines and entries move, whether an archive already exists (the moved entries are prepended to it, or appended for an oldest-first file), and any undated sections caught in the moved range (a trailing "See also" or "License" section should probably stay — if so, stop and ask rather than apply).

## Step 6 — apply, after confirmation

Run `apply`. It writes `<name>-archive.md` next to the original with a one-line header linking back, trims the original and adds a one-line pointer to the archive, then **reads both files back and verifies** that current + archive reproduce the original exactly apart from those pointer lines. If verification fails it says `ABORTED` and exits 2; report that verbatim. When the split lands inside a year group, the `## 2026` heading is repeated on the other side so the moved entries keep their year.

## Step 7 — update the index's link

If the index links to the file you split, adjust its one-line description so it still makes sense — current file holds recent entries, the archive the rest. Keep it to a line; the index is not a summary.

## Step 8 — the index itself

Skim the index for content that has stopped being an index: an embedded command reference, a long explanation, anything duplicating a linked topic file. Flag it in the report; don't rewrite it unasked. Unlike the split (mechanical, verified, nothing deleted), deciding what belongs in an index is a judgement call worth the user's input.

## Report structure

Report before writing anything; write only after the user confirms (unless they pre-approved this change for the current task).

```
## Doc hygiene audit — <project>

**Index:** <path> — <clean | drifted: brief reason>

**Candidates checked:**
- <file>: <N> lines, newest <date>, oldest <date>, rule: <"quoted" | none → default> → **<clean | dormant | overdue — split at line <N> "<header>", <M> entries move>**
(one line per candidate)

**Proposed action:** <split <file> → <file> + <file>-archive.md, update the index link | none needed>
```

## What not to do

- Don't invent a retention rule for a file that states none and isn't unwieldy — a few hundred lines going back a year is fine.
- Don't split a dormant file; it buys nothing.
- Don't act before reporting. The split is low-risk, but files other people and future sessions rely on should not change by surprise.
- Don't hand-edit the split. Use `apply`; it is the only path with verification.
- Don't assume the index is `CLAUDE.md`; ask when it is ambiguous.
