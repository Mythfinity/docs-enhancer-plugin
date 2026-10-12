#!/usr/bin/env python3
"""Check, plan, and perform the split of a changelog-style markdown file.

Usage:
  split_changelog.py check <file> [--months N | --lines N] [--json]
  split_changelog.py plan  <file> [--months N | --lines N]
  split_changelog.py apply <file> [--months N | --lines N]
  split_changelog.py scan  <project-dir> [--json]

check  — is the file overdue for a split? One-line verdict; exit 0 either way,
         exit 1 if the file can't be assessed.
plan   — show exactly what a split would move, without writing anything.
apply  — write <name>-archive.md and trim the original, then verify that
         current + archive reproduces the original byte-for-byte apart from
         the pointer lines this script adds. Aborts on any mismatch.
scan   — find the docs a project's CLAUDE.md links to or @imports (plus the
         project's MEMORY.md), run `check` on each, print the overdue ones.
         Used by the plugin's SessionStart hook; silent when everything is fine.

Entry headers recognised (level 2 or 3, i.e. "## " / "### "):
  ## 2026-07-17 — Short title        ISO date
  ## May 2026 — Short title          month + year (treated as the 1st)
  ## [1.4.0] - 2026-09-20            Keep-a-Changelog style
  ## 2026                            year-only grouping header (not an entry;
                                     its dated ### children are the entries)

Headers inside fenced code blocks are ignored. Both newest-first and
oldest-first files are handled; the order is detected from the dates.
"""
import argparse
import calendar
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_MONTHS = 3
DEFAULT_LINES = 1500
RULE_HEAD_LINES = 10  # how far into a file to look for a stated retention rule

HEADER_RE = re.compile(r'^(#{2,3})\s+(.*?)\s*$')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
ISO_DATE_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
MONTH_NAMES = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
]
MONTH_YEAR_RE = re.compile(r'(' + '|'.join(MONTH_NAMES) + r')\s+(\d{4})', re.IGNORECASE)
RULE_MONTHS_RE = re.compile(r'(\d+)\s*months?', re.IGNORECASE)
YEAR_START_RE = re.compile(r'^\s*(\d{4})(?!\d)')
YEAR_MIN, YEAR_MAX = 1970, 2100


# --- header classification -------------------------------------------------

def classify_header(text: str):
    """Classify the text of a "## " or "### " header line.

    Returns one of:
      ("entry", date)  — a dated changelog entry
      ("group", year)  — a year-only grouping header such as "2026"; the dated
                         "###" headers beneath it are the real entries
      None             — no date found; not something the split logic cares about

    A year-only group header is never an entry on its own: it must not be read
    as "1 January", or a file grouped by year would archive this year's newest
    entries along with the group.
    """
    m = ISO_DATE_RE.search(text)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return ('entry', date(y, mo, d))
        except ValueError:
            return None

    m = MONTH_YEAR_RE.search(text)
    if m:
        mo = MONTH_NAMES.index(m.group(1).lower()) + 1
        return ('entry', date(int(m.group(2)), mo, 1))

    # A header that *starts* with a plausible year and carries no fuller date is a
    # grouping header: "2026", "2025 — older entries". The range keeps a ticket
    # number like "1234 — fix" from being read as a year.
    m = YEAR_START_RE.match(text)
    if m and YEAR_MIN <= int(m.group(1)) <= YEAR_MAX:
        return ('group', int(m.group(1)))

    return None


# --- parsing ---------------------------------------------------------------

@dataclass
class Header:
    line: int                     # 1-based line number
    level: int                    # 2 or 3
    kind: str                     # 'entry' | 'group'
    text: str                     # header text without the leading hashes
    date: Optional[date] = None   # entries only
    year: Optional[int] = None    # groups only


def parse_headers(lines: List[str]) -> List[Header]:
    """Return the dated headers of a file in document order, skipping code fences."""
    out = []
    in_fence = False
    fence_marker = None
    for i, raw in enumerate(lines, start=1):
        fm = FENCE_RE.match(raw)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, None
            continue
        if in_fence:
            continue
        m = HEADER_RE.match(raw)
        if not m:
            continue
        kind = classify_header(m.group(2))
        if kind is None:
            continue
        level = len(m.group(1))
        if kind[0] == 'entry':
            out.append(Header(i, level, 'entry', m.group(2), date=kind[1]))
        else:
            out.append(Header(i, level, 'group', m.group(2), year=kind[1]))
    return out


def entries_of(headers: List[Header]) -> List[Header]:
    return [h for h in headers if h.kind == 'entry']


def detect_order(headers: List[Header]) -> Optional[str]:
    """'newest-first' or 'oldest-first', judged from the first and last dated entries."""
    ents = entries_of(headers)
    if not ents:
        return None
    if ents[0].date >= ents[-1].date:
        return 'newest-first'
    return 'oldest-first'


# --- dates and rules -------------------------------------------------------

def months_before(d: date, n: int) -> date:
    """The same calendar day n months before d, clamped to the month's length."""
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def stated_rule_months(lines: List[str]) -> Optional[int]:
    """A retention window the file states about itself ("… older than 3 months"), if any."""
    for raw in lines[:RULE_HEAD_LINES]:
        m = RULE_MONTHS_RE.search(raw)
        if m:
            return int(m.group(1))
    return None


# --- check -----------------------------------------------------------------

@dataclass
class Verdict:
    path: str
    line_count: int
    dated: bool
    order: Optional[str] = None
    newest: Optional[date] = None
    oldest: Optional[date] = None
    stated_months: Optional[int] = None
    window_months: Optional[int] = None
    cutoff: Optional[date] = None
    stale_entries: int = 0
    dormant: bool = False
    size_limit: Optional[int] = None
    overdue: bool = False
    reason: str = ''

    def as_dict(self):
        d = self.__dict__.copy()
        for k in ('newest', 'oldest', 'cutoff'):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        return d


def read_lines(path) -> List[str]:
    with open(path, encoding='utf-8', newline='') as f:
        return f.read().splitlines(keepends=True)


def check(path, months: Optional[int] = None, lines: Optional[int] = None,
          today: Optional[date] = None) -> Verdict:
    """Decide whether a file is overdue for a split.

    Dated file: overdue only if it is still active (newest entry inside the
    window) AND has entries outside it. A file whose newest entry is itself
    outside the window is dormant — a closed record, not a hygiene problem.
    Undated file: overdue if it has at least `lines` lines (default 1500).
    """
    today = today or date.today()
    path = Path(path)
    content = read_lines(path)
    headers = parse_headers(content)
    ents = entries_of(headers)
    v = Verdict(path=str(path), line_count=len(content), dated=bool(ents))

    if not ents:
        v.size_limit = lines or DEFAULT_LINES
        v.overdue = v.line_count >= v.size_limit
        v.reason = (f'{v.line_count} lines, no dated entries; size limit {v.size_limit}'
                    + (' exceeded' if v.overdue else ' not reached'))
        return v

    v.order = detect_order(headers)
    dates = [e.date for e in ents]
    v.newest, v.oldest = max(dates), min(dates)
    v.stated_months = stated_rule_months(content)
    v.window_months = months or v.stated_months or DEFAULT_MONTHS
    v.cutoff = months_before(today, v.window_months)
    v.stale_entries = sum(1 for d in dates if d < v.cutoff)
    v.dormant = v.newest < v.cutoff
    v.overdue = (not v.dormant) and v.stale_entries > 0

    rule = (f'stated {v.stated_months}-month rule' if v.stated_months and not months
            else f'{v.window_months}-month window')
    if v.dormant:
        v.reason = f'dormant: newest entry {v.newest.isoformat()} is itself older than the {rule}; nothing to split'
    elif v.overdue:
        v.reason = (f'{v.stale_entries} entr{"y" if v.stale_entries == 1 else "ies"} older than the {rule} '
                    f'(oldest {v.oldest.isoformat()}); newest {v.newest.isoformat()}')
    else:
        v.reason = f'all {len(ents)} entries within the {rule}'
    return v


# --- plan ------------------------------------------------------------------

POINTER_NEWEST = '> Older entries: [{a}]({a})\n'
POINTER_OLDEST = '> Earlier entries: [{a}]({a})\n'
POINTER_PREFIXES = ('> Older entries: [', '> Earlier entries: [')
ARCHIVE_HEADER = '> **Archive** of [{c}]({c}) — entries moved out of the current window. {order} first.\n'
ARCHIVE_HEADER_PREFIX = '> **Archive** of ['


def archive_name(path: Path) -> Path:
    return path.with_name(f'{path.stem}-archive{path.suffix}')


@dataclass
class Plan:
    path: Path
    archive_path: Path
    verdict: Verdict
    order: Optional[str] = None
    boundary_line: Optional[int] = None
    preamble: List[str] = field(default_factory=list)   # lines before the first dated header
    kept: List[str] = field(default_factory=list)       # body that stays in the current file
    moved: List[str] = field(default_factory=list)      # body that goes to the archive
    trailing_pointer: List[str] = field(default_factory=list)  # an earlier split's pointer, re-added after
    group_header_copy: Optional[str] = None             # a "## 2026" line the other side needs a copy of
    moved_entries: int = 0
    undated_in_moved: List[str] = field(default_factory=list)
    added_final_newline: bool = False
    reason: str = ''

    @property
    def actionable(self) -> bool:
        return self.boundary_line is not None

    def reassembled(self) -> str:
        """The original file, rebuilt from the plan's slices. Must equal the input exactly."""
        if self.order == 'oldest-first':
            body = self.moved + self.kept
        else:
            body = self.kept + self.moved
        return ''.join(self.preamble + body + self.trailing_pointer)


def _strip_trailing_pointer(lines: List[str]) -> Tuple[List[str], List[str]]:
    """Split off a pointer line this script added at the end of the file in an earlier split."""
    i = len(lines)
    while i > 0 and lines[i - 1].strip() == '':
        i -= 1
    if i > 0 and lines[i - 1].startswith(POINTER_PREFIXES):
        j = i - 1
        while j > 0 and lines[j - 1].strip() == '':
            j -= 1
        return lines[:j], lines[j:]
    return lines, []


def _boundary_by_date(headers: List[Header], order: str, cutoff: date) -> Optional[Header]:
    """The first header (in document order) from which everything belongs on the other side."""
    ents = entries_of(headers)
    if order == 'oldest-first':
        pivot = next((e for e in ents if e.date >= cutoff), None)
    else:
        pivot = next((e for e in ents if e.date < cutoff), None)
    if pivot is None:
        return None
    # If the pivot is the first entry under a group header, the boundary is the group header.
    idx = headers.index(pivot)
    if idx > 0 and headers[idx - 1].kind == 'group':
        return headers[idx - 1]
    return pivot


def _enclosing_group(headers: List[Header], h: Header) -> Optional[Header]:
    """The group header h sits under, if any (ignored when h is itself a group)."""
    if h.kind == 'group':
        return None
    for prev in reversed(headers[:headers.index(h)]):
        if prev.kind == 'group':
            return prev
    return None


def _boundary_by_lines(lines: List[str], n: int) -> Optional[int]:
    """The first level-2 header at or after line n, else the last one before it."""
    level2 = []
    in_fence = False
    for i, raw in enumerate(lines, start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if not in_fence and raw.startswith('## '):
            level2.append(i)
    after = [i for i in level2 if i >= n]
    if after:
        return after[0]
    return level2[-1] if level2 else None


def plan(path, months: Optional[int] = None, lines: Optional[int] = None,
         today: Optional[date] = None) -> Plan:
    path = Path(path)
    v = check(path, months=months, lines=lines, today=today)
    pl = Plan(path=path, archive_path=archive_name(path), verdict=v, reason=v.reason)
    content = read_lines(path)
    if content and not content[-1].endswith('\n'):
        content[-1] += '\n'
        pl.added_final_newline = True
    content, pl.trailing_pointer = _strip_trailing_pointer(content)
    headers = parse_headers(content)

    if lines is not None or not v.dated:
        # Size mode: no dates to go by, so the file is taken as newest-first and the tail moves.
        if not v.overdue:
            return pl
        b = _boundary_by_lines(content, lines or DEFAULT_LINES)
        if b is None:
            pl.reason = f'{v.reason}; but no "## " headers to split at'
            return pl
        pl.order = 'newest-first'
        pl.preamble, pl.kept, pl.moved = [], content[:b - 1], content[b - 1:]
        pl.boundary_line = b
        pl.moved_entries = sum(1 for raw in _unfenced(pl.moved) if raw.startswith('## '))
        pl.reason = f'{v.reason}; splitting at the "## " header on line {b}'
        return pl

    pl.order = v.order
    if not v.overdue:
        return pl

    boundary = _boundary_by_date(headers, v.order, v.cutoff)
    if boundary is None:  # can't happen when overdue, but don't crash on it
        return pl
    first = headers[0].line
    b = boundary.line
    pl.preamble = content[:first - 1]
    if v.order == 'oldest-first':
        pl.moved, pl.kept = content[first - 1:b - 1], content[b - 1:]
    else:
        pl.kept, pl.moved = content[first - 1:b - 1], content[b - 1:]
    pl.boundary_line = b

    group = _enclosing_group(headers, boundary)
    if group is not None:
        pl.group_header_copy = content[group.line - 1]

    moved_lo, moved_hi = (first, b - 1) if v.order == 'oldest-first' else (b, len(content))
    pl.moved_entries = sum(1 for e in entries_of(headers) if moved_lo <= e.line <= moved_hi)
    dated_lines = {h.line for h in headers}
    pl.undated_in_moved = [
        f'{raw.rstrip()} (line {i})'
        for i, raw in enumerate(content, start=1)
        if moved_lo <= i <= moved_hi and raw.startswith('## ') and i not in dated_lines
    ]
    pl.reason = f'{v.reason}; split at line {b} ("{boundary.text}")'
    return pl


# --- apply -----------------------------------------------------------------

class SplitError(Exception):
    """Raised when a split would not reproduce the original content exactly."""


@dataclass
class Rendered:
    original: str      # the file as read (plus a final newline if one was missing)
    current: str       # new content of the current file
    archive: str       # new content of the archive file
    existing_archive: str = ''  # the archive's previous content, kept verbatim inside `archive`


def _ends_blank(lines: List[str]) -> bool:
    return bool(lines) and lines[-1].strip() == ''


def _existing_archive_parts(path: Path) -> Tuple[List[str], List[str]]:
    """(header block, body) of an existing archive; header is empty if it isn't ours."""
    if not path.exists():
        return [], []
    lines = read_lines(path)
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    if lines and lines[0].startswith(ARCHIVE_HEADER_PREFIX):
        head = lines[:1]
        if len(lines) > 1 and lines[1].strip() == '':
            head = lines[:2]
        return head, lines[len(head):]
    return [], lines


def render(pl: Plan) -> Rendered:
    """Build the two files' new contents from a plan, and prove the plan loses nothing."""
    if not pl.actionable:
        raise SplitError('nothing to split')
    original = read_lines(pl.path)
    original_text = ''.join(original)
    if pl.added_final_newline:
        original_text += '\n'
    if pl.reassembled() != original_text:
        raise SplitError('plan does not reproduce the original file; refusing to write')

    cur_name, arc_name = pl.path.name, pl.archive_path.name
    order_word = 'Oldest' if pl.order == 'oldest-first' else 'Newest'
    header = [ARCHIVE_HEADER.format(c=cur_name, order=order_word), '\n']
    _, existing_body = _existing_archive_parts(pl.archive_path)
    existing_text = ''.join(existing_body)
    group = [pl.group_header_copy, '\n'] if pl.group_header_copy else []

    if pl.order == 'oldest-first':
        pointer = [POINTER_OLDEST.format(a=arc_name), '\n']
        pre = list(pl.preamble)
        if pre and not _ends_blank(pre):
            pre.append('\n')
        current = pre + pointer + group + pl.kept
        archive = header + existing_body
        if existing_body and not _ends_blank(existing_body):
            archive.append('\n')
        archive += pl.moved
    else:
        pointer = [POINTER_NEWEST.format(a=arc_name)]
        body = pl.preamble + pl.kept
        if body and not _ends_blank(body):
            body = body + ['\n']
        current = body + pointer
        archive = header + group + list(pl.moved)
        if existing_body:
            if not _ends_blank(archive):
                archive.append('\n')
            archive += existing_body

    return Rendered(original=original_text, current=''.join(current),
                    archive=''.join(archive), existing_archive=existing_text)


def _atomic_write(path: Path, text: str):
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, path)


def verify_written(pl: Plan, out: Rendered):
    """Read both files back and check they hold exactly what was planned."""
    with open(pl.path, encoding='utf-8', newline='') as f:
        cur = f.read()
    with open(pl.archive_path, encoding='utf-8', newline='') as f:
        arc = f.read()
    if cur != out.current:
        raise SplitError(f'{pl.path} does not contain the planned content after writing')
    if arc != out.archive:
        raise SplitError(f'{pl.archive_path} does not contain the planned content after writing')
    if out.existing_archive and out.existing_archive not in arc:
        raise SplitError(f'{pl.archive_path} lost its previous content')
    moved = ''.join(pl.moved)
    if moved not in arc:
        raise SplitError('moved entries are not present verbatim in the archive')
    kept = ''.join(pl.preamble) + ''.join(pl.kept) if pl.order != 'oldest-first' else ''.join(pl.kept)
    if kept not in cur:
        raise SplitError('kept entries are not present verbatim in the current file')


@dataclass
class ApplyResult:
    plan: Plan
    applied: bool
    verified: bool = False


def apply(path, months: Optional[int] = None, lines: Optional[int] = None,
          today: Optional[date] = None) -> ApplyResult:
    pl = plan(path, months=months, lines=lines, today=today)
    if not pl.actionable:
        return ApplyResult(plan=pl, applied=False)
    out = render(pl)
    _atomic_write(pl.archive_path, out.archive)
    _atomic_write(pl.path, out.current)
    verify_written(pl, out)
    return ApplyResult(plan=pl, applied=True, verified=True)


# --- scan ------------------------------------------------------------------

LINK_RE = re.compile(r'\[[^\]]*\]\(([^)\s]+?\.md)(?:#[^)]*)?\)')
IMPORT_RE = re.compile(r'(?<!\S)@([^\s`]+\.md)\b')


@dataclass
class Candidate:
    path: Path
    auto_loaded: bool   # read into context every session (@import, MEMORY.md) vs. merely linked


def _unfenced(lines: List[str]) -> List[str]:
    out, in_fence = [], False
    for raw in lines:
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(raw)
    return out


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def memory_file(project_dir: Path, config_dir: Optional[Path] = None) -> Path:
    """Claude Code's per-project MEMORY.md: <config>/projects/<cwd with / as ->/memory/MEMORY.md."""
    config_dir = Path(config_dir or os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
    escaped = str(project_dir).replace('/', '-')
    return config_dir / 'projects' / escaped / 'memory' / 'MEMORY.md'


def find_candidates(project_dir, config_dir=None) -> List[Candidate]:
    project_dir = Path(project_dir)
    indexes = [p for p in (project_dir / 'CLAUDE.md', project_dir / '.claude' / 'CLAUDE.md') if p.is_file()]
    if not indexes and (project_dir / 'README.md').is_file():
        indexes = [project_dir / 'README.md']

    found = {}  # resolved path -> Candidate
    def add(path: Path, auto_loaded: bool):
        path = Path(os.path.normpath(path))
        if not path.is_file() or path.suffix.lower() != '.md':
            return
        key = path.resolve()
        if key in found:
            found[key].auto_loaded = found[key].auto_loaded or auto_loaded
        else:
            found[key] = Candidate(path=path, auto_loaded=auto_loaded)

    for index in indexes:
        base = index.parent
        for raw in _unfenced(read_lines(index)):
            for m in LINK_RE.finditer(raw):
                p = base / m.group(1)
                if _inside(p, project_dir):
                    add(p, auto_loaded=False)
            for m in IMPORT_RE.finditer(raw):
                target = m.group(1)
                p = Path(target).expanduser() if target.startswith(('~', '/')) else base / target
                if _inside(p, project_dir):
                    add(p, auto_loaded=True)

    mem = memory_file(project_dir, config_dir)
    if mem.is_file():
        add(mem, auto_loaded=True)
    return list(found.values())


@dataclass
class Finding:
    path: Path
    auto_loaded: bool
    verdict: Verdict


def scan(project_dir, config_dir=None, months: Optional[int] = None,
         lines: Optional[int] = None, today: Optional[date] = None) -> List[Finding]:
    """Check every candidate; return the overdue ones.

    Dated files get the retention check. Files without dated entries get the
    size check only if they are auto-loaded — a linked reference doc is allowed
    to be long; an @imported one costs tokens every session.
    """
    out = []
    for c in find_candidates(project_dir, config_dir):
        try:
            v = check(c.path, months=months, lines=lines, today=today)
        except (OSError, UnicodeDecodeError):
            continue
        if not v.dated and not c.auto_loaded:
            continue
        if v.overdue:
            out.append(Finding(path=c.path, auto_loaded=c.auto_loaded, verdict=v))
    return out


def format_findings(findings: List[Finding], project_dir) -> str:
    if not findings:
        return ''
    project_dir = Path(project_dir)
    lines = ['[docs-enhancer] Documentation overdue for a split:']
    for f in findings:
        try:
            shown = f.path.relative_to(project_dir).as_posix()
        except ValueError:
            shown = str(f.path)
        note = ' (loaded into context every session)' if f.auto_loaded else ''
        lines.append(f'- {shown}{note}: {f.verdict.reason}')
    lines.append('Run /docs-enhancer to review and split. Nothing is changed without confirmation.')
    return '\n'.join(lines)


# --- CLI -------------------------------------------------------------------

def describe_plan(pl: Plan) -> str:
    v = pl.verdict
    out = [f'{"OVERDUE" if v.overdue else "ok"}: {pl.path} — {v.reason}']
    if not pl.actionable:
        out.append('Nothing to split.')
        return '\n'.join(out)
    side = 'head' if pl.order == 'oldest-first' else 'tail'
    out.append(f'Order: {pl.order}. Split at line {pl.boundary_line}; the {side} from there '
               f'({len(pl.moved)} lines, {pl.moved_entries} entries) moves to {pl.archive_path.name}.')
    out.append(f'Current file keeps {len(pl.preamble) + len(pl.kept)} lines.')
    if pl.group_header_copy:
        out.append(f'The split lands inside the "{pl.group_header_copy.strip()}" group; '
                   f'that header is repeated on the other side so the entries keep their year.')
    if pl.archive_path.exists():
        out.append(f'{pl.archive_path.name} already exists; the moved entries will be '
                   f'{"appended to" if pl.order == "oldest-first" else "prepended to"} it.')
    if pl.undated_in_moved:
        out.append('Note — undated sections in the moved range (check they belong in an archive): '
                   + ', '.join(pl.undated_in_moved))
    if pl.added_final_newline:
        out.append('Note — the file has no final newline; one will be added.')
    return '\n'.join(out)


def cmd_plan(args):
    pl = plan(args.file, months=args.months, lines=args.lines)
    print(describe_plan(pl))
    return 0


def cmd_check(args):
    v = check(args.file, months=args.months, lines=args.lines)
    if args.json:
        print(json.dumps(v.as_dict()))
    else:
        print(f'{"OVERDUE" if v.overdue else "ok"}: {v.path} — {v.reason}')
    return 0


def cmd_apply(args):
    try:
        res = apply(args.file, months=args.months, lines=args.lines)
    except SplitError as e:
        print(f'ABORTED: {e}', file=sys.stderr)
        return 2
    pl = res.plan
    if not res.applied:
        print(describe_plan(pl))
        return 0
    print(f'Split {pl.path}: {len(pl.moved)} lines ({pl.moved_entries} entries) moved to {pl.archive_path}.')
    print(f'Verified: current + archive reproduce the original exactly, apart from the pointer lines added.')
    print(f'Current file: {len(pl.preamble) + len(pl.kept)} lines of original content kept.')
    return 0


def _env_int(name: str) -> Optional[int]:
    val = os.environ.get(name, '').strip()
    return int(val) if val.isdigit() else None


def cmd_scan(args):
    findings = scan(args.project_dir,
                    months=args.months or _env_int('DOCS_ENHANCER_MONTHS'),
                    lines=args.lines or _env_int('DOCS_ENHANCER_LINES'))
    if args.json:
        print(json.dumps([{'path': str(f.path), 'auto_loaded': f.auto_loaded, **f.verdict.as_dict()}
                          for f in findings]))
    else:
        msg = format_findings(findings, args.project_dir)
        if msg:
            print(msg)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def add_window(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument('--months', type=int, help=f'age cutoff in months (default: the file\'s stated rule, else {DEFAULT_MONTHS})')
        g.add_argument('--lines', type=int, help=f'size cutoff for files without dated entries (default {DEFAULT_LINES})')

    p = sub.add_parser('check', help='report whether a file is overdue for a split')
    p.add_argument('file')
    add_window(p)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_check)

    p = sub.add_parser('plan', help='show what a split would move, without writing anything')
    p.add_argument('file')
    add_window(p)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser('apply', help='perform the split and verify nothing was lost')
    p.add_argument('file')
    add_window(p)
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser('scan', help="check every doc a project's index links to; print the overdue ones")
    p.add_argument('project_dir')
    add_window(p)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_scan)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
