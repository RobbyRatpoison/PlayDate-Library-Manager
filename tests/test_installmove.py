import json
import os
import shutil
import sqlite3

import installmove


def _old_install(tmp_path):
    old = tmp_path / 'PlayDate'
    (old / '_internal').mkdir(parents=True)
    (old / '_internal' / 'lib.dll').write_text('code')
    (old / 'PlayDate.exe').write_text('exe')
    (old / 'static' / 'img' / 'library' / 'vertical').mkdir(parents=True)
    (old / 'static' / 'img' / 'library' / 'vertical' / '1.jpg').write_bytes(b'jpg1')
    (old / 'plugins' / 'gog').mkdir(parents=True)
    (old / 'plugins' / 'gog' / 'plugin.json').write_text('{"id": "gog"}')
    (old / 'steamgifts_wins_1.json').write_text('{"a": 1}')
    db = old / 'games_1.db'
    con = sqlite3.connect(db)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE games (appid INTEGER, install_path TEXT, runner_path TEXT)')
    con.execute('INSERT INTO games VALUES (1, ?, NULL)', (str(old / 'Games' / 'x'),))
    con.commit()   # stays open: its write-ahead log is live
    (old / 'config.json').write_text(json.dumps({'prefix': str(old / 'pfx'), 'k': 1}))
    return old, con


def test_copies_data_not_code_and_repoints_paths(tmp_path):
    old, live = _old_install(tmp_path)
    new = tmp_path / 'Zest'
    new.mkdir()
    (new / 'Zest.exe').write_text('new exe')
    assert installmove.move_install_data(str(old), str(new)) == 'done'
    live.close()
    assert not (new / 'PlayDate.exe').exists() and not (new / '_internal').exists()
    assert (new / 'Zest.exe').read_text() == 'new exe'
    assert (new / 'static' / 'img' / 'library' / 'vertical' / '1.jpg').read_bytes() == b'jpg1'
    assert (new / 'plugins' / 'gog' / 'plugin.json').exists()
    assert json.loads((new / 'config.json').read_text())['prefix'] == str(new / 'pfx')
    con = sqlite3.connect(new / 'games_1.db')
    assert con.execute('SELECT install_path FROM games').fetchone()[0] == str(new / 'Games' / 'x')
    con.close()
    assert (old / 'config.json').exists() and (old / 'PlayDate.exe').exists()   # the old folder is untouched


def test_second_run_and_existing_data_are_left_alone(tmp_path):
    old, live = _old_install(tmp_path)
    live.close()
    new = tmp_path / 'Zest'
    assert installmove.move_install_data(str(old), str(new)) == 'done'
    assert installmove.move_install_data(str(old), str(new)) == 'none'
    other = tmp_path / 'Other'
    other.mkdir()
    (other / 'config.json').write_text('{}')
    assert installmove.move_install_data(str(old), str(other)) == 'none'


def test_a_locked_file_fails_cleanly_and_leaves_no_trace(tmp_path, monkeypatch):
    old, live = _old_install(tmp_path)
    live.close()
    new = tmp_path / 'Zest'
    new.mkdir()
    real = shutil.copy2

    def locked(src, dst, *a, **k):
        if str(src).endswith('1.jpg'):
            raise PermissionError('being used by another process')
        return real(src, dst, *a, **k)
    monkeypatch.setattr(shutil, 'copy2', locked)
    status = installmove.move_install_data(str(old), str(new))
    assert status.startswith('failed')
    assert os.listdir(new) == []   # everything copied so far was removed
    assert (old / 'config.json').exists() and (old / 'games_1.db').exists()
    monkeypatch.setattr(shutil, 'copy2', real)
    assert installmove.move_install_data(str(old), str(new)) == 'done'   # a later start can retry


def test_a_bad_copy_is_caught(tmp_path, monkeypatch):
    old, live = _old_install(tmp_path)
    live.close()
    new = tmp_path / 'Zest'
    real = shutil.copy2

    def short(src, dst, *a, **k):
        real(src, dst, *a, **k)
        if str(src).endswith('1.jpg'):
            with open(dst, 'wb') as f:
                f.write(b'j')   # silently truncated
    monkeypatch.setattr(shutil, 'copy2', short)
    assert installmove.move_install_data(str(old), str(new)).startswith('failed')
    assert not (new / 'config.json').exists()


def test_cleanup_leaves_only_what_is_locked(tmp_path, monkeypatch):
    old, live = _old_install(tmp_path)
    live.close()
    real = os.remove

    def locked(path, *a, **k):
        if str(path).endswith('steamgifts_wins_1.json'):
            raise PermissionError('in use')
        return real(path, *a, **k)
    monkeypatch.setattr(os, 'remove', locked)
    left = installmove.remove_old_data(str(old))
    assert left == ['steamgifts_wins_1.json']
    assert not (old / 'config.json').exists() and not (old / 'plugins').exists()
    assert (old / 'PlayDate.exe').exists()   # program files are the installer's business


def test_old_install_dir_only_for_a_zest_folder_next_to_playdate(tmp_path):
    (tmp_path / 'PlayDate').mkdir()
    (tmp_path / 'Zest').mkdir()
    (tmp_path / 'Other').mkdir()
    assert installmove.old_install_dir(str(tmp_path / 'Zest')) == str(tmp_path / 'PlayDate')
    assert installmove.old_install_dir(str(tmp_path / 'Other')) is None
    (tmp_path / 'PlayDate').rmdir()
    assert installmove.old_install_dir(str(tmp_path / 'Zest')) is None


def test_finish_move_clears_the_old_update_marker_and_the_data(tmp_path):
    old, live = _old_install(tmp_path)
    live.close()
    (old / '.rollback').mkdir()
    (old / '.rollback' / 'pending.json').write_text(json.dumps({'old_token': 'someone-else'}))
    new = tmp_path / 'Zest'
    assert installmove.move_install_data(str(old), str(new)) == 'done'
    assert installmove.moved_from(str(new)) == str(old)
    assert installmove.finish_move(str(new)) == []
    assert not (old / '.rollback' / 'pending.json').exists()   # the old version's watchdog stops waiting
    assert not (old / 'config.json').exists() and not (old / 'plugins').exists()
    assert (old / 'PlayDate.exe').exists()
    assert not (old / '.rollback').exists()
    shutil.rmtree(old / '_internal'); (old / 'PlayDate.exe').unlink()   # as if the installer had removed them
    assert installmove.finish_move(str(new)) == []
    assert old.is_symlink() and os.path.samefile(old, new)   # the old name leads to the new folder
    assert installmove.finish_move(str(new)) == []   # idempotent
    assert (new / 'config.json').exists()


def test_remove_old_data_refuses_to_go_through_a_link(tmp_path):
    new = tmp_path / 'Zest'
    new.mkdir()
    (new / 'config.json').write_text('{}')
    link = tmp_path / 'PlayDate'
    os.symlink(new, link, target_is_directory=True)
    assert installmove.remove_old_data(str(link)) == []
    assert (new / 'config.json').exists()
