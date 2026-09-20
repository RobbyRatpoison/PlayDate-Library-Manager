"""Game names must sort case-insensitively ("Backpack Hero" before "BROK the
InvestiGator"). SQLite's default BINARY collation puts every capital before every
lowercase letter, so any `ORDER BY name` over game names needs COLLATE NOCASE
(reported by Mayanaise). A source scan rather than a DB test: the queries are
spread across routes that need Flask, but the mistake is always the same."""
import glob
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), '..')

# Not game names: imports.py lists SQLite table names from sqlite_master.
ALLOWED = {('imports.py', "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def test_no_case_sensitive_name_sorts():
    bad = []
    for path in sorted(glob.glob(os.path.join(ROOT, '*.py'))):
        src = open(path, encoding='utf-8').read()
        for m in re.finditer(r'ORDER BY name(?! COLLATE NOCASE)', src, re.IGNORECASE):
            line_start = src.rfind('\n', 0, m.start()) + 1
            line = src[line_start:src.find('\n', m.end())]
            if not any(os.path.basename(path) == f and frag in line for f, frag in ALLOWED):
                bad.append(f'{os.path.basename(path)}: {line.strip()}')
    assert not bad, 'ORDER BY name without COLLATE NOCASE:\n' + '\n'.join(bad)
