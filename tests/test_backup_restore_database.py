import os
import sqlite3

import pytest

import backup


def _make(path, rows, wal=False, page_size=None):
    c = sqlite3.connect(path)
    if page_size:
        c.execute(f'PRAGMA page_size={page_size}')
    if wal:
        c.execute('PRAGMA journal_mode=wal')
    c.execute('CREATE TABLE g(id INTEGER PRIMARY KEY, name TEXT)')
    c.executemany('INSERT INTO g VALUES(?,?)', rows)
    c.commit()
    return c


def _backup_bytes(tmp_path, rows, **kw):
    p = tmp_path / 'from-backup.db'
    _make(str(p), rows, **kw).close()
    return p.read_bytes()


ORIG = [(i, f'orig{i}') for i in range(1, 51)]


def test_a_restore_replaces_a_live_database_without_the_stale_log(tmp_path):
    data = _backup_bytes(tmp_path, ORIG)
    live_path = str(tmp_path / 'live.db')
    live = _make(live_path, ORIG, wal=True)
    live.execute("INSERT INTO g VALUES(999, 'added after the backup')")
    live.commit()
    assert os.path.exists(live_path + '-wal')   # the app still has a log with that change in it

    backup._write_database(data, live_path)

    fresh = sqlite3.connect(live_path)
    assert fresh.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 50
    assert fresh.execute('SELECT COUNT(*) FROM g WHERE id = 999').fetchone()[0] == 0
    assert fresh.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    # the connection the app already had open sees the restored content too
    assert live.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 50
    assert not os.path.exists(live_path + '.restore')
    fresh.close()
    live.close()


def test_the_old_overwrite_brought_the_change_back(tmp_path):
    """Documents the bug the helper fixes: writing the file in place leaves the stale log to be replayed."""
    data = _backup_bytes(tmp_path, ORIG)
    live_path = str(tmp_path / 'live.db')
    live = _make(live_path, ORIG, wal=True)
    live.execute("INSERT INTO g VALUES(999, 'added after the backup')")
    live.commit()
    with open(live_path, 'wb') as f:
        f.write(data)
    fresh = sqlite3.connect(live_path)
    assert fresh.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 51   # not the 50 the backup holds
    fresh.close()
    live.close()


def test_a_missing_destination_is_simply_created(tmp_path):
    data = _backup_bytes(tmp_path, ORIG)
    dest = str(tmp_path / 'new.db')
    backup._write_database(data, dest)
    c = sqlite3.connect(dest)
    assert c.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 50
    c.close()
    assert not os.path.exists(dest + '.restore')


def test_a_damaged_backup_is_refused_and_the_library_is_left_alone(tmp_path):
    live_path = str(tmp_path / 'live.db')
    _make(live_path, ORIG).close()
    good = _backup_bytes(tmp_path, ORIG)
    damaged = good[:4096] + b'\x00' * (len(good) - 4096)
    with pytest.raises(Exception):
        backup._write_database(damaged, live_path)
    c = sqlite3.connect(live_path)
    assert c.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 50
    c.close()
    assert not os.path.exists(live_path + '.restore')


def test_another_page_size_restores_when_nothing_else_has_the_library_open(tmp_path):
    data = _backup_bytes(tmp_path, ORIG, page_size=1024)
    live_path = str(tmp_path / 'live.db')
    _make(live_path, [(1, 'x')], wal=True).close()
    backup._write_database(data, live_path)
    c = sqlite3.connect(live_path)
    assert c.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 50
    assert c.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'   # back to what the app uses
    c.close()


def test_another_page_size_while_the_library_is_in_use_is_refused_cleanly(tmp_path):
    data = _backup_bytes(tmp_path, ORIG, page_size=1024)
    live_path = str(tmp_path / 'live.db')
    live = _make(live_path, [(1, 'x')], wal=True)
    with pytest.raises(RuntimeError, match='different page size'):
        backup._write_database(data, live_path)
    assert live.execute('SELECT COUNT(*) FROM g').fetchone()[0] == 1   # the library was not touched
    assert not os.path.exists(live_path + '.restore')
    live.close()
