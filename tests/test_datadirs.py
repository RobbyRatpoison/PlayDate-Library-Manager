import json
import os
import sqlite3

import datadirs


def _make(tmp_path, with_games=True):
    parent = tmp_path / 'share'
    old = parent / 'PlayDate'
    (old / 'epic' / 'drive_c').mkdir(parents=True)
    (old / 'epic' / 'drive_c' / 'marker.txt').write_text('hi')
    (parent / 'PlayDateX').mkdir()
    db = tmp_path / 'games.db'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE games (appid INTEGER, install_path TEXT, runner_path TEXT)')
    if with_games:
        con.executemany('INSERT INTO games VALUES (?,?,?)', [
            (1, f'{old}/epic/drive_c/Game', None),
            (2, f'{old}', f'{parent}/PlayDateX/proton'),   # root itself; a sibling that only shares the prefix
            (3, '/elsewhere/Game', f'{old}/runner'),
            (4, None, ''),
        ])
    con.commit(); con.close()
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({'launchers': {'epic_games': {'prefix': f'{old}/epic'}},
                               'list': [f'{old}/a', 'plain', 3], 'other': f'{parent}/PlayDateX/keep'}))
    return parent, old, db, cfg


def _rows(db):
    con = sqlite3.connect(db)
    try:
        return con.execute('SELECT appid, install_path, runner_path FROM games ORDER BY appid').fetchall()
    finally:
        con.close()


def test_noop_when_names_match(tmp_path):
    parent, old, db, cfg = _make(tmp_path)
    assert datadirs.migrate([str(db)], str(cfg), parent=str(parent), name='PlayDate', legacy='PlayDate') == 'none'
    assert old.is_dir() and not old.is_symlink()


def test_move_rewrites_paths_and_leaves_a_link(tmp_path):
    parent, old, db, cfg = _make(tmp_path)
    new = parent / 'Zest'
    assert datadirs.migrate([str(db)], str(cfg), parent=str(parent), name='Zest', legacy='PlayDate') == 'done'
    assert new.is_dir() and not new.is_symlink()
    assert old.is_symlink() and os.path.samefile(old, new)
    assert (old / 'epic' / 'drive_c' / 'marker.txt').read_text() == 'hi'   # the old name still works
    assert _rows(db) == [
        (1, f'{new}/epic/drive_c/Game', None),
        (2, f'{new}', f'{parent}/PlayDateX/proton'),   # PlayDateX is not under PlayDate
        (3, '/elsewhere/Game', f'{new}/runner'),
        (4, None, ''),
    ]
    data = json.loads(cfg.read_text())
    assert data['launchers']['epic_games']['prefix'] == f'{new}/epic'
    assert data['list'] == [f'{new}/a', 'plain', 3]
    assert data['other'] == f'{parent}/PlayDateX/keep'


def test_second_run_does_nothing(tmp_path):
    parent, old, db, cfg = _make(tmp_path)
    kw = dict(parent=str(parent), name='Zest', legacy='PlayDate')
    assert datadirs.migrate([str(db)], str(cfg), **kw) == 'done'
    assert datadirs.migrate([str(db)], str(cfg), **kw) == 'none'


def test_skips_when_both_exist_or_in_use(tmp_path):
    parent, old, db, cfg = _make(tmp_path)
    kw = dict(parent=str(parent), name='Zest', legacy='PlayDate')
    assert datadirs.migrate([str(db)], str(cfg), in_use=lambda p: True, **kw).startswith('skipped: in use')
    assert old.is_dir() and not old.is_symlink()
    (parent / 'Zest').mkdir()
    assert datadirs.migrate([str(db)], str(cfg), **kw).startswith('skipped: both')


def test_failure_puts_everything_back(tmp_path, monkeypatch):
    parent, old, db, cfg = _make(tmp_path)
    before_cfg = cfg.read_text()
    before_rows = _rows(db)
    real_replace = os.replace

    def boom(src, dst):
        if str(dst) == str(cfg):
            raise OSError('disk full')
        return real_replace(src, dst)
    monkeypatch.setattr(os, 'replace', boom)
    status = datadirs.migrate([str(db)], str(cfg), parent=str(parent), name='Zest', legacy='PlayDate')
    assert status.startswith('rolled back')
    assert old.is_dir() and not old.is_symlink() and not (parent / 'Zest').exists()
    assert (old / 'epic' / 'drive_c' / 'marker.txt').read_text() == 'hi'
    assert cfg.read_text() == before_cfg
    assert _rows(db) == before_rows


def test_data_root_prefers_new_then_legacy_then_new(tmp_path):
    p = str(tmp_path)
    assert datadirs.data_root(p, 'Zest', 'PlayDate') == os.path.join(p, 'Zest')          # fresh install
    os.mkdir(os.path.join(p, 'PlayDate'))
    assert datadirs.data_root(p, 'Zest', 'PlayDate') == os.path.join(p, 'PlayDate')      # not migrated yet
    os.mkdir(os.path.join(p, 'Zest'))
    assert datadirs.data_root(p, 'Zest', 'PlayDate') == os.path.join(p, 'Zest')
