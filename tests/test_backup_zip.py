"""Backup zip contents (art stored, data deflated) and restoring from a path."""
import logging
import os
import sqlite3
import threading
import zipfile

import pytest

import backup

log = logging.getLogger('test')


def _make_install(base):
    """A small fake install: data files plus art, badge and background images."""
    base.mkdir(parents=True, exist_ok=True)
    for name in ('config.json', 'state.json', 'theme.json'):
        (base / name).write_text('{"k": "%s"}' % name)
    con = sqlite3.connect(base / 'games_1.db')
    con.execute('create table games (appid integer, name text)')
    con.execute("insert into games values (1, 'Alpha')")
    con.commit()
    con.close()
    lib = base / 'static' / 'img' / 'library' / 'vertical'
    lib.mkdir(parents=True)
    (lib / '1.jpg').write_bytes(os.urandom(3000))
    (lib / '2.jpg').write_bytes(os.urandom(2000))
    (base / 'static' / 'img' / 'badges').mkdir(parents=True)
    (base / 'static' / 'img' / 'badges' / 'b.png').write_bytes(os.urandom(500))
    (base / 'static' / 'img' / 'backgrounds').mkdir(parents=True)
    (base / 'static' / 'img' / 'backgrounds' / 'background.jpg').write_bytes(os.urandom(800))


def _build_backup(tmp_path, monkeypatch, include_art=True):
    src = tmp_path / 'src'
    _make_install(src)
    monkeypatch.setattr(backup, 'BASE_DIR', str(src))
    zpath = tmp_path / 'backup.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        backup._fill_backup_zip(zf, include_art)
    return src, zpath


def test_images_are_stored_and_data_is_deflated(tmp_path, monkeypatch):
    _, zpath = _build_backup(tmp_path, monkeypatch)
    with zipfile.ZipFile(zpath) as zf:
        kinds = {i.filename: i.compress_type for i in zf.infolist()}
    assert kinds['static/img/library/vertical/1.jpg'] == zipfile.ZIP_STORED
    assert kinds['static/img/library/vertical/2.jpg'] == zipfile.ZIP_STORED
    assert kinds['static/img/badges/b.png'] == zipfile.ZIP_STORED
    assert kinds['static/img/backgrounds/background.jpg'] == zipfile.ZIP_STORED
    assert kinds['config.json'] == zipfile.ZIP_DEFLATED
    assert kinds['games_1.db'] == zipfile.ZIP_DEFLATED


def test_art_is_left_out_unless_asked_for(tmp_path, monkeypatch):
    _, zpath = _build_backup(tmp_path, monkeypatch, include_art=False)
    with zipfile.ZipFile(zpath) as zf:
        assert not [n for n in zf.namelist() if n.startswith('static/img/library/')]


@pytest.mark.parametrize('as_path', [True, False])
def test_restore_round_trip_from_a_path_or_bytes(tmp_path, monkeypatch, as_path):
    src, zpath = _build_backup(tmp_path, monkeypatch)
    dest = tmp_path / 'dest'
    dest.mkdir()
    monkeypatch.setattr(backup, 'BASE_DIR', str(dest))
    source = str(zpath) if as_path else zpath.read_bytes()
    restored, _ = backup._extract_backup_zip(source, log)
    assert '2 cover image(s)' in restored
    for rel in ('static/img/library/vertical/1.jpg', 'static/img/library/vertical/2.jpg',
                'static/img/badges/b.png', 'static/img/backgrounds/background.jpg',
                'config.json', 'state.json'):
        assert (dest / rel).read_bytes() == (src / rel).read_bytes(), rel
    con = sqlite3.connect(dest / 'games_1.db')
    assert con.execute('select name from games').fetchall() == [('Alpha',)]
    con.close()


def test_a_corrupt_zip_reports_an_invalid_backup(tmp_path, monkeypatch):
    bad = tmp_path / 'bad.zip'
    bad.write_bytes(b'this is not a zip file at all')
    monkeypatch.setattr(backup, 'BASE_DIR', str(tmp_path))
    backup._restore_state.update({'status': 'running', 'error': None})
    backup._do_restore(str(bad), log)
    assert backup._restore_state['status'] == 'error'
    assert 'Invalid zip file' in backup._restore_state['error']


def test_restore_from_path_hands_over_the_path_not_the_file_contents(tmp_path, monkeypatch):
    from flask import Flask
    zpath = tmp_path / 'b.zip'
    zpath.write_bytes(b'PK-not-read-by-this-test')
    seen, done = {}, threading.Event()

    def fake_run(source, logger):
        seen['source'] = source
        done.set()

    monkeypatch.setattr(backup, 'validate_user_path', lambda p: p)
    monkeypatch.setattr(backup, '_run_restore_thread', fake_run)
    backup._restore_state.update({'status': 'idle', 'error': None})
    app = Flask(__name__)
    app.register_blueprint(backup.backup_bp)
    r = app.test_client().post('/api/restore-from-path', json={'path': str(zpath)})
    assert r.status_code == 200 and r.get_json()['status'] == 'started'
    assert done.wait(5)
    assert seen['source'] == str(zpath)          # a path, not the bytes
    backup._restore_state.update({'status': 'idle'})


def _post_backup(tmp_path, monkeypatch, body):
    from flask import Flask
    src = tmp_path / 'src'
    _make_install(src)
    monkeypatch.setattr(backup, 'BASE_DIR', str(src))
    monkeypatch.setattr(backup, 'validate_user_path', lambda p: p)
    monkeypatch.setattr(backup, 'save_state', lambda *a, **k: None)
    out = tmp_path / 'out.zip'
    app = Flask(__name__)
    app.register_blueprint(backup.backup_bp)
    r = app.test_client().post('/api/backup-to-path', json={'path': str(out), **body})
    assert r.status_code == 200, r.get_json()
    with zipfile.ZipFile(out) as zf:
        return [n for n in zf.namelist() if n.startswith('static/img/library/')]


def test_a_backup_includes_cover_art_unless_told_otherwise(tmp_path, monkeypatch):
    assert len(_post_backup(tmp_path, monkeypatch, {})) == 2                      # default: art in
    assert _post_backup(tmp_path / 'b', monkeypatch, {'include_art': False}) == []   # opted out
