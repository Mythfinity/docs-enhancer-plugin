"""Tests for skills/docs-enhancer/scripts/split_changelog.py.

Run from the plugin root:  python3 -m unittest discover -s tests
"""
import importlib.util
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills' / 'docs-enhancer' / 'scripts' / 'split_changelog.py'

spec = importlib.util.spec_from_file_location('split_changelog', SCRIPT)
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

TODAY = date(2026, 10, 12)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, text):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p


# --- header classification -------------------------------------------------

class ClassifyHeader(unittest.TestCase):
    def test_iso_date_header_is_an_entry(self):
        self.assertEqual(sc.classify_header('2026-10-01 — Fixed checkout'), ('entry', date(2026, 10, 1)))

    def test_month_year_header_is_an_entry_on_the_first(self):
        self.assertEqual(sc.classify_header('May 2026 — Short title'), ('entry', date(2026, 5, 1)))

    def test_keep_a_changelog_header_is_an_entry(self):
        self.assertEqual(sc.classify_header('[1.3.0] - 2026-03-02'), ('entry', date(2026, 3, 2)))

    def test_year_only_header_is_a_group(self):
        self.assertEqual(sc.classify_header('2026'), ('group', 2026))

    def test_year_with_a_title_is_a_group(self):
        self.assertEqual(sc.classify_header('2025 — older entries'), ('group', 2025))

    def test_four_digit_number_that_is_not_a_plausible_year_is_not_dated(self):
        self.assertIsNone(sc.classify_header('1234 — fix ticket'))

    def test_unreleased_header_is_not_dated(self):
        self.assertIsNone(sc.classify_header('[Unreleased]'))

    def test_invalid_iso_date_is_not_dated(self):
        self.assertIsNone(sc.classify_header('2026-13-45 bogus'))


# --- parsing ---------------------------------------------------------------

class ParseHeaders(unittest.TestCase):
    def test_skips_headers_inside_fenced_code_blocks(self):
        lines = [
            '# Log\n', '\n',
            '## 2026-10-01 docs\n', '\n',
            '```md\n', '## 2020-01-01 sample header\n', '```\n', '\n',
            '## 2026-09-01 other\n',
        ]
        headers = sc.parse_headers(lines)
        self.assertEqual([h.line for h in headers], [3, 9])

    def test_records_header_level(self):
        lines = ['## 2026\n', '### 2026-10-01 fix\n']
        headers = sc.parse_headers(lines)
        self.assertEqual([(h.level, h.kind) for h in headers], [(2, 'group'), (3, 'entry')])

    def test_ignores_undated_headers(self):
        lines = ['## Overview\n', '## 2026-10-01 fix\n']
        headers = sc.parse_headers(lines)
        self.assertEqual([h.line for h in headers], [2])


class DetectOrder(unittest.TestCase):
    def _headers(self, text):
        return sc.parse_headers(text.splitlines(keepends=True))

    def test_newest_first(self):
        h = self._headers('## 2026-10-01 a\n## 2026-01-01 b\n')
        self.assertEqual(sc.detect_order(h), 'newest-first')

    def test_oldest_first(self):
        h = self._headers('## 2025-01-10 a\n## 2026-10-05 b\n')
        self.assertEqual(sc.detect_order(h), 'oldest-first')

    def test_single_entry_defaults_to_newest_first(self):
        h = self._headers('## 2026-10-01 a\n')
        self.assertEqual(sc.detect_order(h), 'newest-first')

    def test_no_entries_is_none(self):
        self.assertIsNone(sc.detect_order([]))


# --- dates and rules -------------------------------------------------------

class MonthsBefore(unittest.TestCase):
    def test_same_day_n_months_earlier(self):
        self.assertEqual(sc.months_before(date(2026, 10, 12), 3), date(2026, 7, 12))

    def test_crosses_year_boundary(self):
        self.assertEqual(sc.months_before(date(2026, 2, 10), 3), date(2025, 11, 10))

    def test_clamps_day_to_month_length(self):
        self.assertEqual(sc.months_before(date(2026, 5, 31), 3), date(2026, 2, 28))


class StatedRule(unittest.TestCase):
    def test_reads_months_from_file_head(self):
        lines = ['# Recent changes\n', 'Move entries out once older than ~3 months.\n', '## 2026-10-01 x\n']
        self.assertEqual(sc.stated_rule_months(lines), 3)

    def test_reads_six_months(self):
        lines = ['Entries are archived after 6 months.\n']
        self.assertEqual(sc.stated_rule_months(lines), 6)

    def test_none_when_no_rule(self):
        lines = ['# Changelog\n', '## 2026-10-01 x\n']
        self.assertIsNone(sc.stated_rule_months(lines))

    def test_only_looks_at_the_head_of_the_file(self):
        lines = ['# Changelog\n'] + ['filler\n'] * 20 + ['took 3 months to land\n']
        self.assertIsNone(sc.stated_rule_months(lines))


# --- check -----------------------------------------------------------------

class Check(TempDirCase):
    def test_active_file_with_old_entries_is_overdue(self):
        p = self.write('log.md', '# Log\n\n## 2026-10-01 new\n\n## 2026-09-01 ok\n\n## 2026-02-01 old\n\n## 2025-11-01 older\n')
        v = sc.check(p, months=3, today=TODAY)
        self.assertTrue(v.overdue)
        self.assertFalse(v.dormant)
        self.assertEqual(v.stale_entries, 2)
        self.assertEqual(v.cutoff, date(2026, 7, 12))

    def test_dormant_file_is_not_overdue(self):
        p = self.write('log.md', '# Log\n\n## 2022-03-01 a\n\n## 2021-06-01 b\n')
        v = sc.check(p, months=3, today=TODAY)
        self.assertFalse(v.overdue)
        self.assertTrue(v.dormant)

    def test_everything_within_window_is_not_overdue(self):
        p = self.write('log.md', '# Log\n\n## 2026-10-01 a\n\n## 2026-09-01 b\n')
        v = sc.check(p, months=3, today=TODAY)
        self.assertFalse(v.overdue)
        self.assertEqual(v.stale_entries, 0)

    def test_stated_rule_overrides_default_window(self):
        p = self.write('log.md', '# Log\nArchive after 12 months.\n\n## 2026-10-01 a\n\n## 2026-02-01 b\n')
        v = sc.check(p, today=TODAY)
        self.assertEqual(v.window_months, 12)
        self.assertEqual(v.stated_months, 12)
        self.assertFalse(v.overdue)

    def test_explicit_months_overrides_stated_rule(self):
        p = self.write('log.md', '# Log\nArchive after 12 months.\n\n## 2026-10-01 a\n\n## 2026-02-01 b\n')
        v = sc.check(p, months=3, today=TODAY)
        self.assertEqual(v.window_months, 3)
        self.assertTrue(v.overdue)

    def test_undated_file_falls_back_to_size(self):
        p = self.write('log.md', '# Log\n' + 'line\n' * 1600)
        v = sc.check(p, lines=1500, today=TODAY)
        self.assertFalse(v.dated)
        self.assertTrue(v.overdue)
        self.assertEqual(v.line_count, 1601)

    def test_small_undated_file_is_fine(self):
        p = self.write('log.md', '# Log\n' + 'line\n' * 100)
        v = sc.check(p, lines=1500, today=TODAY)
        self.assertFalse(v.dated)
        self.assertFalse(v.overdue)

    def test_year_grouped_file_judges_by_nested_entries(self):
        p = self.write('log.md', '# Log\n\n## 2026\n\n### 2026-10-01 new\n\n### 2026-02-01 old\n\n## 2025\n\n### 2025-12-01 older\n')
        v = sc.check(p, months=3, today=TODAY)
        self.assertTrue(v.overdue)
        self.assertFalse(v.dormant)
        self.assertEqual(v.newest, date(2026, 10, 1))
        self.assertEqual(v.stale_entries, 2)


if __name__ == '__main__':
    unittest.main()


# --- plan ------------------------------------------------------------------

NEWEST_FIRST = (
    '# Recent changes\n'
    'Move entries out once older than ~3 months.\n'
    '\n'
    '## 2026-10-01 — new\n'
    'body a\n'
    '\n'
    '## 2026-09-01 — ok\n'
    'body b\n'
    '\n'
    '## 2026-02-01 — old\n'
    'body c\n'
    '\n'
    '## 2025-11-01 — older\n'
    'body d\n'
)

OLDEST_FIRST = (
    '# Log\n'
    '\n'
    '## 2025-11-01 — older\n'
    'body d\n'
    '\n'
    '## 2026-02-01 — old\n'
    'body c\n'
    '\n'
    '## 2026-09-01 — ok\n'
    'body b\n'
    '\n'
    '## 2026-10-01 — new\n'
    'body a\n'
)

YEAR_GROUPED = (
    '# Log\n'
    '\n'
    '## 2026\n'
    '\n'
    '### 2026-10-01 — new\n'
    'body a\n'
    '\n'
    '### 2026-02-01 — old\n'
    'body c\n'
    '\n'
    '## 2025\n'
    '\n'
    '### 2025-12-01 — older\n'
    'body d\n'
)


class PlanSplit(TempDirCase):
    def plan(self, text, name='log.md', **kw):
        p = self.write(name, text)
        kw.setdefault('today', TODAY)
        return sc.plan(p, **kw)

    def test_newest_first_moves_the_tail_from_the_first_old_entry(self):
        pl = self.plan(NEWEST_FIRST)
        self.assertEqual(pl.boundary_line, 10)
        self.assertEqual(''.join(pl.moved), '## 2026-02-01 — old\nbody c\n\n## 2025-11-01 — older\nbody d\n')
        self.assertEqual(''.join(pl.preamble), '# Recent changes\nMove entries out once older than ~3 months.\n\n')
        self.assertEqual(pl.moved_entries, 2)

    def test_oldest_first_moves_the_head_up_to_the_first_current_entry(self):
        pl = self.plan(OLDEST_FIRST)
        self.assertEqual(pl.order, 'oldest-first')
        self.assertEqual(pl.boundary_line, 9)
        self.assertEqual(''.join(pl.moved), '## 2025-11-01 — older\nbody d\n\n## 2026-02-01 — old\nbody c\n\n')
        self.assertEqual(''.join(pl.kept), '## 2026-09-01 — ok\nbody b\n\n## 2026-10-01 — new\nbody a\n')

    def test_kept_plus_moved_reproduces_the_original(self):
        for text in (NEWEST_FIRST, OLDEST_FIRST):
            pl = self.plan(text)
            self.assertEqual(pl.reassembled(), text)

    def test_nothing_to_do_when_not_overdue(self):
        pl = self.plan('# Log\n\n## 2026-10-01 a\n\n## 2026-09-01 b\n')
        self.assertIsNone(pl.boundary_line)
        self.assertFalse(pl.actionable)

    def test_nothing_to_do_when_dormant(self):
        pl = self.plan('# Log\n\n## 2022-03-01 a\n\n## 2021-06-01 b\n')
        self.assertFalse(pl.actionable)
        self.assertIn('dormant', pl.reason)

    def test_split_inside_a_year_group_copies_the_group_header_to_the_archive(self):
        pl = self.plan(YEAR_GROUPED)
        self.assertEqual(pl.boundary_line, 8)
        self.assertEqual(pl.group_header_copy, '## 2026\n')
        self.assertEqual(''.join(pl.kept), '## 2026\n\n### 2026-10-01 — new\nbody a\n\n')
        self.assertTrue(''.join(pl.moved).startswith('### 2026-02-01 — old\n'))
        self.assertEqual(pl.reassembled(), YEAR_GROUPED)

    def test_split_at_the_first_entry_of_a_group_moves_the_group_header_too(self):
        text = ('# Log\n\n## 2026\n\n### 2026-10-01 — new\nbody a\n\n'
                '## 2025\n\n### 2025-12-01 — older\nbody d\n')
        pl = self.plan(text)
        self.assertEqual(pl.boundary_line, 8)
        self.assertIsNone(pl.group_header_copy)
        self.assertTrue(''.join(pl.moved).startswith('## 2025\n'))

    def test_oldest_first_split_inside_a_group_copies_the_header_to_current(self):
        text = ('# Log\n\n## 2025\n\n### 2025-06-01 — older\nbody d\n\n'
                '## 2026\n\n### 2026-02-01 — old\nbody c\n\n### 2026-10-01 — new\nbody a\n')
        pl = self.plan(text)
        self.assertEqual(pl.order, 'oldest-first')
        self.assertEqual(pl.group_header_copy, '## 2026\n')
        self.assertTrue(''.join(pl.moved).startswith('## 2025\n'))
        self.assertEqual(''.join(pl.kept), '### 2026-10-01 — new\nbody a\n')

    def test_header_inside_code_fence_is_not_a_boundary(self):
        text = ('# Log\n\n## 2026-10-01 docs\n\nExample:\n```md\n## 2020-01-01 sample header\n```\n\n'
                '## 2026-09-01 other\n\n## 2026-01-01 old\n')
        pl = self.plan(text)
        self.assertEqual(pl.boundary_line, 12)

    def test_lines_mode_snaps_to_the_next_level_2_header(self):
        text = '# Log\n' + ''.join(f'## Section {i}\nline\nline\nline\n' for i in range(1, 6))
        # headers at lines 2, 6, 10, 14, 18
        pl = self.plan(text, lines=8)
        self.assertEqual(pl.boundary_line, 10)
        self.assertEqual(pl.order, 'newest-first')

    def test_lines_mode_counts_moved_sections_by_header(self):
        text = '# Log\n' + ''.join(f'## Section {i}\nline\nline\nline\n' for i in range(1, 6))
        pl = self.plan(text, lines=8)
        self.assertEqual(pl.moved_entries, 3)

    def test_warns_about_undated_sections_in_the_moved_range(self):
        text = NEWEST_FIRST + '\n## See also\n- links\n'
        pl = self.plan(text)
        self.assertEqual(pl.undated_in_moved, ['## See also (line 16)'])

    def test_missing_final_newline_is_added_and_recorded(self):
        text = NEWEST_FIRST.rstrip('\n')
        pl = self.plan(text)
        self.assertTrue(pl.added_final_newline)
        self.assertEqual(pl.reassembled(), text + '\n')

    def test_existing_pointer_at_the_end_is_not_moved_into_the_archive(self):
        text = NEWEST_FIRST + '\n> Older entries: [log-archive.md](log-archive.md)\n'
        pl = self.plan(text)
        self.assertNotIn('Older entries', ''.join(pl.moved))
        self.assertEqual(pl.trailing_pointer, ['\n', '> Older entries: [log-archive.md](log-archive.md)\n'])
        self.assertEqual(pl.reassembled(), text)


# --- apply -----------------------------------------------------------------

HEADER_NEWEST = '> **Archive** of [log.md](log.md) — entries moved out of the current window. Newest first.\n'
HEADER_OLDEST = '> **Archive** of [log.md](log.md) — entries moved out of the current window. Oldest first.\n'
POINTER_NEWEST = '> Older entries: [log-archive.md](log-archive.md)\n'
POINTER_OLDEST = '> Earlier entries: [log-archive.md](log-archive.md)\n'


class ApplySplit(TempDirCase):
    def apply(self, text, today=TODAY, **kw):
        p = self.write('log.md', text)
        return p, sc.apply(p, today=today, **kw)

    def archive(self):
        return (self.dir / 'log-archive.md').read_text(encoding='utf-8')

    def test_writes_archive_and_trims_current(self):
        p, res = self.apply(NEWEST_FIRST)
        self.assertTrue(res.applied)
        self.assertEqual(p.read_text(encoding='utf-8'),
                         '# Recent changes\nMove entries out once older than ~3 months.\n\n'
                         '## 2026-10-01 — new\nbody a\n\n## 2026-09-01 — ok\nbody b\n\n' + POINTER_NEWEST)
        self.assertEqual(self.archive(),
                         HEADER_NEWEST + '\n## 2026-02-01 — old\nbody c\n\n## 2025-11-01 — older\nbody d\n')

    def test_oldest_first_puts_the_pointer_after_the_preamble(self):
        p, res = self.apply(OLDEST_FIRST)
        self.assertEqual(p.read_text(encoding='utf-8'),
                         '# Log\n\n' + POINTER_OLDEST + '\n## 2026-09-01 — ok\nbody b\n\n## 2026-10-01 — new\nbody a\n')
        self.assertEqual(self.archive(),
                         HEADER_OLDEST + '\n## 2025-11-01 — older\nbody d\n\n## 2026-02-01 — old\nbody c\n\n')

    def test_blank_line_is_added_before_the_pointer_when_needed(self):
        p, res = self.apply('# Log\n## 2026-10-01 a\nbody\n## 2026-01-01 b\nbody\n')
        self.assertEqual(p.read_text(encoding='utf-8'), '# Log\n## 2026-10-01 a\nbody\n\n' + POINTER_NEWEST)

    def test_prepends_to_an_existing_archive(self):
        self.write('log-archive.md', HEADER_NEWEST + '\n## 2025-01-01 — ancient\nbody z\n')
        self.apply(NEWEST_FIRST)
        self.assertEqual(self.archive(),
                         HEADER_NEWEST + '\n## 2026-02-01 — old\nbody c\n\n## 2025-11-01 — older\nbody d\n'
                         '\n## 2025-01-01 — ancient\nbody z\n')

    def test_appends_to_an_existing_archive_when_oldest_first(self):
        self.write('log-archive.md', HEADER_OLDEST + '\n## 2024-01-01 — ancient\nbody z\n')
        self.apply(OLDEST_FIRST)
        self.assertEqual(self.archive(),
                         HEADER_OLDEST + '\n## 2024-01-01 — ancient\nbody z\n'
                         '\n## 2025-11-01 — older\nbody d\n\n## 2026-02-01 — old\nbody c\n\n')

    def test_keeps_a_foreign_archive_intact_below_the_moved_entries(self):
        self.write('log-archive.md', '# Old archive\n\n## 2025-01-01 — ancient\n')
        self.apply(NEWEST_FIRST)
        arc = self.archive()
        self.assertTrue(arc.startswith(HEADER_NEWEST))
        self.assertTrue(arc.endswith('body d\n\n# Old archive\n\n## 2025-01-01 — ancient\n'))

    def test_archive_repeats_the_group_header(self):
        p, res = self.apply(YEAR_GROUPED)
        self.assertEqual(p.read_text(encoding='utf-8'),
                         '# Log\n\n## 2026\n\n### 2026-10-01 — new\nbody a\n\n' + POINTER_NEWEST)
        self.assertEqual(self.archive(),
                         HEADER_NEWEST + '\n## 2026\n\n### 2026-02-01 — old\nbody c\n\n## 2025\n\n### 2025-12-01 — older\nbody d\n')

    def test_does_nothing_when_not_overdue(self):
        text = '# Log\n\n## 2026-10-01 a\n'
        p, res = self.apply(text)
        self.assertFalse(res.applied)
        self.assertEqual(p.read_text(encoding='utf-8'), text)
        self.assertFalse((self.dir / 'log-archive.md').exists())

    def test_second_split_keeps_one_pointer_and_prepends(self):
        p, _ = self.apply(NEWEST_FIRST)
        res = sc.apply(p, today=date(2026, 12, 15))
        self.assertTrue(res.applied)
        cur = p.read_text(encoding='utf-8')
        self.assertEqual(cur.count('> Older entries:'), 1)
        self.assertEqual(cur, '# Recent changes\nMove entries out once older than ~3 months.\n\n'
                              '## 2026-10-01 — new\nbody a\n\n' + POINTER_NEWEST)
        self.assertEqual(self.archive(),
                         HEADER_NEWEST + '\n## 2026-09-01 — ok\nbody b\n\n'
                         '## 2026-02-01 — old\nbody c\n\n## 2025-11-01 — older\nbody d\n')

    def test_verification_catches_a_corrupted_write(self):
        p = self.write('log.md', NEWEST_FIRST)
        pl = sc.plan(p, today=TODAY)
        out = sc.render(pl)
        p.write_text(out.current, encoding='utf-8')
        (self.dir / 'log-archive.md').write_text(out.archive[:-5], encoding='utf-8')
        with self.assertRaises(sc.SplitError):
            sc.verify_written(pl, out)

    def test_verification_catches_a_plan_that_drops_lines(self):
        p = self.write('log.md', NEWEST_FIRST)
        pl = sc.plan(p, today=TODAY)
        pl.moved = pl.moved[1:]
        with self.assertRaises(sc.SplitError):
            sc.render(pl)


# --- scan ------------------------------------------------------------------

class FindCandidates(TempDirCase):
    def cands(self):
        found = sc.find_candidates(self.dir, config_dir=self.dir / 'cfg')
        return sorted((c.path.relative_to(self.dir).as_posix(), c.auto_loaded) for c in found)

    def test_collects_linked_and_imported_docs_from_claude_md(self):
        self.write('CLAUDE.md', '# P\n- [Changes](docs/changes.md)\n- [Site](https://x.y/z.md)\n'
                                '- [Missing](docs/nope.md)\n- [Script](run.sh)\n- [Anchored](docs/arch.md#top)\n'
                                '@docs/notes.md\nSee @README.md too\nmail me@example.md\n')
        for f in ('docs/changes.md', 'docs/notes.md', 'docs/arch.md', 'README.md', 'run.sh'):
            self.write(f, 'x\n')
        self.assertEqual(self.cands(), [('README.md', True), ('docs/arch.md', False),
                                        ('docs/changes.md', False), ('docs/notes.md', True)])

    def test_ignores_links_inside_code_fences(self):
        self.write('CLAUDE.md', '```\n[x](docs/a.md)\n@docs/b.md\n```\n[y](docs/c.md)\n')
        for f in ('docs/a.md', 'docs/b.md', 'docs/c.md'):
            self.write(f, 'x\n')
        self.assertEqual(self.cands(), [('docs/c.md', False)])

    def test_skips_files_outside_the_project(self):
        self.write('CLAUDE.md', '[out](../outside.md)\n')
        (self.dir.parent / 'outside.md').write_text('x\n')
        self.addCleanup(lambda: (self.dir.parent / 'outside.md').unlink())
        self.assertEqual(self.cands(), [])

    def test_also_reads_dot_claude_claude_md(self):
        self.write('.claude/CLAUDE.md', '@../notes.md\n')
        self.write('notes.md', 'x\n')
        self.assertEqual(self.cands(), [('notes.md', True)])

    def test_readme_is_the_index_when_there_is_no_claude_md(self):
        self.write('README.md', '[Changes](docs/changes.md)\n')
        self.write('docs/changes.md', 'x\n')
        self.assertEqual(self.cands(), [('docs/changes.md', False)])

    def test_same_file_linked_and_imported_is_listed_once_as_auto_loaded(self):
        self.write('CLAUDE.md', '[n](notes.md)\n@notes.md\n')
        self.write('notes.md', 'x\n')
        self.assertEqual(self.cands(), [('notes.md', True)])

    def test_memory_md_path_is_derived_from_the_project_path(self):
        escaped = str(self.dir).replace('/', '-')
        mem = self.write(f'cfg/projects/{escaped}/memory/MEMORY.md', '# mem\n')
        found = sc.find_candidates(self.dir, config_dir=self.dir / 'cfg')
        self.assertIn((mem, True), [(c.path, c.auto_loaded) for c in found])


class Scan(TempDirCase):
    def scan(self, **kw):
        kw.setdefault('today', TODAY)
        return sc.scan(self.dir, config_dir=self.dir / 'cfg', **kw)

    def test_reports_only_overdue_dated_files(self):
        self.write('CLAUDE.md', '- [Changes](docs/changes.md)\n- [Arch](docs/arch.md)\n- [Fine](docs/fine.md)\n')
        self.write('docs/changes.md', NEWEST_FIRST)
        self.write('docs/arch.md', '# Arch\n' + 'line\n' * 2000)   # undated, not auto-loaded: not judged by size
        self.write('docs/fine.md', '# Fine\n\n## 2026-10-01 a\n')
        findings = self.scan()
        self.assertEqual([f.path for f in findings], [self.dir / 'docs/changes.md'])

    def test_size_checks_auto_loaded_undated_files(self):
        self.write('CLAUDE.md', '@docs/big.md\n')
        self.write('docs/big.md', '# Big\n' + 'line\n' * 2000)
        findings = self.scan()
        self.assertEqual([f.path for f in findings], [self.dir / 'docs/big.md'])

    def test_silent_when_everything_is_fine(self):
        self.write('CLAUDE.md', '@docs/small.md\n[c](docs/changes.md)\n')
        self.write('docs/small.md', '# Small\n')
        self.write('docs/changes.md', '# C\n\n## 2026-10-01 a\n')
        self.assertEqual(self.scan(), [])

    def test_window_overrides_apply_to_every_file(self):
        self.write('CLAUDE.md', '[c](docs/changes.md)\n')
        self.write('docs/changes.md', '# C\n\n## 2026-10-01 a\n\n## 2026-08-01 b\n')
        self.assertEqual(self.scan(), [])
        self.assertEqual(len(self.scan(months=1)), 1)

    def test_message_names_the_file_the_reason_and_the_fix(self):
        self.write('CLAUDE.md', '[c](docs/changes.md)\n')
        self.write('docs/changes.md', NEWEST_FIRST)
        msg = sc.format_findings(self.scan(), self.dir)
        self.assertIn('docs/changes.md', msg)
        self.assertIn('stated 3-month rule', msg)
        self.assertIn('/docs-enhancer', msg)

    def test_no_message_when_nothing_found(self):
        self.assertEqual(sc.format_findings([], self.dir), '')
