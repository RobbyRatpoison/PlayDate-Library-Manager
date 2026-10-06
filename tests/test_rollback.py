"""Update rollback (rollback.py): snapshot/restore, health marker, and the
watchdog end to end with a stand-in "app" that crashes or starts."""
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import textwrap
import time

import pytest

import rollback


def _make_db(path, rows):
    c = sqlite3.connect(path)
    c.execute('create table games (name text)')
    c.executemany('insert into games values (?)', [(r,) for r in rows])
    c.commit()
    c.close()


def _names(path):
    c = sqlite3.connect(path)
    try:
        return [r[0] for r in c.execute('select name from games order by name')]
    finally:
        c.close()


def test_data_roundtrip_drops_stale_wal(tmp_path):
    base = str(tmp_path)
    _make_db(os.path.join(base, 'games.db'), ['old'])
    (tmp_path / 'config.json').write_text('{"v": 1}')
    rollback.backup_data(base)
    # the "new version" migrates the db and rewrites settings
    c = sqlite3.connect(os.path.join(base, 'games.db'))
    c.execute('insert into games values (?)', ('new',))
    c.commit()
    c.close()
    (tmp_path / 'config.json').write_text('{"v": 2}')
    (tmp_path / 'games.db-wal').write_bytes(b'junk')
    rollback.restore_data(base)
    assert _names(os.path.join(base, 'games.db')) == ['old']
    assert json.loads((tmp_path / 'config.json').read_text()) == {'v': 1}
    assert not (tmp_path / 'games.db-wal').exists()


def test_source_snapshot_restores_changed_and_removes_created(tmp_path):
    base = str(tmp_path)
    (tmp_path / 'a.py').write_text('old a')
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'b.py').write_text('old b')
    (tmp_path / 'keep.db').write_text('user data, not in the zip')
    rollback.snapshot_source(base, ['a.py', 'sub/b.py', 'new.py'])
    (tmp_path / 'a.py').write_text('new a')
    (tmp_path / 'sub' / 'b.py').write_text('new b')
    (tmp_path / 'new.py').write_text('new file')
    rollback.restore_source(base)
    assert (tmp_path / 'a.py').read_text() == 'old a'
    assert (tmp_path / 'sub' / 'b.py').read_text() == 'old b'
    assert not (tmp_path / 'new.py').exists()
    assert (tmp_path / 'keep.db').read_text() == 'user data, not in the zip'


def test_mark_healthy_ignores_the_process_that_started_the_update(tmp_path, monkeypatch):
    base = str(tmp_path)
    rollback.begin(base, 'source', '1.0.0', '1.1.0')
    assert rollback.mark_healthy(base) is False          # same pid: the old app
    assert rollback.read_pending(base)
    pend = rollback.read_pending(base)
    pend['old_pid'] = -1                                  # a different process
    rollback._write_json(rollback._p(base, 'pending.json'), pend)
    os.makedirs(rollback._p(base, 'code'))
    assert rollback.mark_healthy(base) is True
    assert rollback.read_pending(base) is None
    assert not os.path.exists(rollback._p(base, 'code'))  # heavy snapshot freed


def test_housekeeping_records_failed_version_once(tmp_path):
    base = str(tmp_path)
    rollback._write_json(rollback._p(base, 'rolled_back.json'),
                         {'from_version': '1.1.0', 'to_version': '1.0.0'})
    rollback.housekeeping(base)
    rollback.housekeeping(base)
    assert rollback.failed_versions(base) == ['1.1.0']
    assert rollback.read_notice(base)                     # still shown until dismissed
    rollback.clear_notice(base)
    assert rollback.failed_versions(base) == ['1.1.0']    # but remembered


def test_housekeeping_clears_stale_pending(tmp_path):
    base = str(tmp_path)
    rollback.begin(base, 'source', '1.0.0', '1.1.0')
    pend = rollback.read_pending(base)
    pend['started'] = time.time() - rollback.PENDING_MAX_AGE - 10
    rollback._write_json(rollback._p(base, 'pending.json'), pend)
    rollback.housekeeping(base)
    assert rollback.read_pending(base) is None


# ── Watchdog, end to end ──────────────────────────────────────────────────────

FAKE_APP = textwrap.dedent('''
    import os, sys
    base = os.path.dirname(os.path.abspath(__file__))
    marker = open(os.path.join(base, 'version.txt')).read().strip()
    open(os.path.join(base, 'ran.log'), 'a').write(marker + '\\n')
    if marker == 'new-broken':
        sys.exit(1)                                        # crashes on startup
    # a healthy start: render a page, which drops pending.json
    os.remove(os.path.join(base, '.rollback', 'pending.json'))
''')


def _setup(tmp_path, new_version_text):
    base = str(tmp_path)
    (tmp_path / 'version.txt').write_text('old')
    (tmp_path / 'main.py').write_text(FAKE_APP)
    _make_db(os.path.join(base, 'games.db'), ['mine'])
    rollback.backup_data(base)
    rollback.snapshot_source(base, ['version.txt'])
    shutil.copy2(rollback.__file__, os.path.join(rollback.rb_dir(base), 'watchdog.py'))
    rollback.begin(base, 'source', 'old', 'new')
    (tmp_path / 'version.txt').write_text(new_version_text)   # the "update"
    return base


def _run_watchdog(base):
    launch = json.dumps([sys.executable, os.path.join(base, 'main.py')])
    subprocess.run([sys.executable, os.path.join(rollback.rb_dir(base), 'watchdog.py'), 'watch',
                    '--base-dir', base, '--kind', 'source', '--launch', launch], timeout=60, check=True)


def _wait_for(pred, secs=15):
    t = time.time()
    while time.time() - t < secs:
        if pred():
            return True
        time.sleep(0.2)
    return False


def test_watchdog_rolls_back_a_version_that_crashes_twice(tmp_path):
    base = _setup(tmp_path, 'new-broken')
    _run_watchdog(base)
    assert _wait_for(lambda: (tmp_path / 'ran.log').read_text().split().count('old') == 1)
    ran = (tmp_path / 'ran.log').read_text().split()
    assert ran[:2] == ['new-broken', 'new-broken']          # tried twice
    assert (tmp_path / 'version.txt').read_text() == 'old'  # restored, then started
    assert _names(os.path.join(base, 'games.db')) == ['mine']
    notice = rollback.read_notice(base)
    assert notice['from_version'] == 'new' and notice['to_version'] == 'old'
    assert rollback.read_pending(base) is None


def test_watchdog_leaves_a_healthy_update_alone(tmp_path):
    base = _setup(tmp_path, 'new-ok')
    _run_watchdog(base)
    assert (tmp_path / 'ran.log').read_text().split() == ['new-ok']
    assert (tmp_path / 'version.txt').read_text() == 'new-ok'
    assert rollback.read_notice(base) is None


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX sh script')
def test_flatpak_watchdog_script_rolls_back(tmp_path):
    base = tmp_path / 'data'
    bindir = tmp_path / 'bin'
    base.mkdir()
    bindir.mkdir()
    _make_db(str(base / 'games.db'), ['mine'])
    rollback.backup_data(str(base))
    (base / '.rollback' / 'old.flatpak').write_text('bundle')
    rollback.begin(str(base), 'flatpak', 'old', 'new')
    # the new version's database change is undone from the snapshot
    c = sqlite3.connect(str(base / 'games.db'))
    c.execute('insert into games values (?)', ('migrated',))
    c.commit()
    c.close()
    calls = tmp_path / 'calls.log'
    fake = bindir / 'flatpak'
    fake.write_text(textwrap.dedent(f'''\
        #!/bin/sh
        echo "$@" >> {calls}
        case "$1" in
          run) exit 1 ;;      # the new version always crashes
          ps) exit 0 ;;
          install) exit 0 ;;
        esac
    '''))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    script = base / '.rollback' / 'watchdog.sh'
    script.write_text(rollback.FLATPAK_WATCHDOG_SH)
    env = dict(os.environ, PATH=f'{bindir}:{os.environ["PATH"]}')
    subprocess.run(['sh', str(script), str(base), 'org.x.App', 'child', 'exec flatpak run org.x.App',
                    'new', 'old'], env=env, timeout=60, check=True)
    assert _wait_for(lambda: calls.read_text().count('run org.x.App') >= 3)
    log = calls.read_text()
    assert log.count('run org.x.App') == 3                  # 2 failed starts + the restored one
    assert '--reinstall' in log and 'old.flatpak' in log
    assert _names(str(base / 'games.db')) == ['mine']
    notice = json.loads((base / '.rollback' / 'rolled_back.json').read_text())
    assert notice['from_version'] == 'new'
    assert not (base / '.rollback' / 'pending.json').exists()


def test_failed_beta_does_not_block_later_betas_or_the_final(tmp_path, monkeypatch):
    import updater
    monkeypatch.setattr(updater, 'BASE_DIR', str(tmp_path))
    rollback._write_json(rollback._p(str(tmp_path), 'failed.json'), ['1.12.1-beta.2'])
    assert updater._is_failed_version('1.12.1-beta.2')
    assert not updater._is_failed_version('1.12.1-beta.3')
    assert not updater._is_failed_version('1.12.1')
    # and the reverse: a failed final doesn't hide a later patch or a beta of it
    rollback._write_json(rollback._p(str(tmp_path), 'failed.json'), ['1.12.1'])
    assert updater._is_failed_version('1.12.1')
    assert not updater._is_failed_version('1.12.2-beta.1')


def test_frozen_snapshot_and_restore_swap_the_whole_tree(tmp_path):
    base = str(tmp_path)
    (tmp_path / 'PlayDate.exe').write_text('old exe')
    (tmp_path / '_internal').mkdir()
    (tmp_path / '_internal' / 'lib.dll').write_text('old dll')
    (tmp_path / 'games.db').write_text('user data, must be left alone')
    assert rollback.snapshot_frozen(base)
    assert (tmp_path / '.rollback' / 'code' / rollback.WATCHDOG_EXE).read_text() == 'old exe'
    # the installer lays down the new version, adding and replacing files
    (tmp_path / 'PlayDate.exe').write_text('new exe')
    (tmp_path / '_internal' / 'lib.dll').write_text('new dll')
    (tmp_path / '_internal' / 'extra.dll').write_text('only in new')
    assert rollback.restore_frozen(base)
    assert (tmp_path / 'PlayDate.exe').read_text() == 'old exe'
    assert (tmp_path / '_internal' / 'lib.dll').read_text() == 'old dll'
    assert not (tmp_path / '_internal' / 'extra.dll').exists()
    assert (tmp_path / 'games.db').read_text() == 'user data, must be left alone'
    leftovers = [n for n in os.listdir(base) if n.endswith(('.restoring', '.failed'))]
    assert leftovers == []


def test_frozen_snapshot_declines_an_unexpected_layout(tmp_path):
    (tmp_path / 'PlayDate.exe').write_text('exe')       # no _internal next to it
    assert rollback.snapshot_frozen(str(tmp_path)) is False
    assert not (tmp_path / '.rollback' / 'code').exists()


def _observe_setup(tmp_path, new_instance_lifetime):
    """Fake host for the Game Mode watchdog: the OLD version's sandbox (111) is
    listed for the whole test, as it was on the Deck, and launching starts a
    new instance (222) that lives `new_instance_lifetime` seconds."""
    base, bindir, state = tmp_path / 'data', tmp_path / 'bin', tmp_path / 'state'
    for d in (base, bindir, state):
        d.mkdir()
    _make_db(str(base / 'games.db'), ['mine'])
    rollback.backup_data(str(base))
    (base / '.rollback' / 'old.flatpak').write_text('bundle')
    rollback.begin(str(base), 'flatpak', 'old', 'new')
    calls = tmp_path / 'calls.log'
    fake = bindir / 'flatpak'
    fake.write_text(textwrap.dedent(f'''\
        #!/bin/sh
        echo "$@" >> {calls}
        case "$1" in
          ps) printf '111\\torg.x.App\\n'; [ -f {state}/new ] && printf '222\\torg.x.App\\n'; exit 0 ;;
          install) exit 0 ;;
        esac
    '''))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    launch = bindir / 'launch.sh'
    launch.write_text(textwrap.dedent(f'''\
        #!/bin/sh
        echo launch >> {calls}
        touch {state}/new
        ( sleep {new_instance_lifetime}; rm -f {state}/new ) &
    '''))
    launch.chmod(launch.stat().st_mode | stat.S_IEXEC)
    script = base / '.rollback' / 'watchdog.sh'
    script.write_text(rollback.FLATPAK_WATCHDOG_SH)
    env = dict(os.environ, PATH=f'{bindir}:{os.environ["PATH"]}')
    return base, script, launch, calls, env


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX sh script')
def test_observe_mode_detects_a_crash_despite_a_lingering_old_instance(tmp_path):
    base, script, launch, calls, env = _observe_setup(tmp_path, new_instance_lifetime=2)
    subprocess.run(['sh', str(script), str(base), 'org.x.App', 'observe', str(launch), 'new', 'old'],
                   env=env, timeout=90, check=True)
    assert _wait_for(lambda: calls.read_text().count('launch') >= 3)
    assert '--reinstall' in calls.read_text()
    assert (base / '.rollback' / 'rolled_back.json').exists()
    assert _names(str(base / 'games.db')) == ['mine']


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX sh script')
def test_observe_mode_does_not_roll_back_a_healthy_start(tmp_path):
    base, script, launch, calls, env = _observe_setup(tmp_path, new_instance_lifetime=25)
    # the new version proves itself shortly after it starts
    proc = subprocess.Popen(['sh', str(script), str(base), 'org.x.App', 'observe', str(launch), 'new', 'old'], env=env)
    assert _wait_for(lambda: calls.exists() and 'launch' in calls.read_text(), 20)
    os.remove(base / '.rollback' / 'pending.json')
    assert proc.wait(timeout=30) == 0
    assert '--reinstall' not in calls.read_text()
    assert not (base / '.rollback' / 'rolled_back.json').exists()
    subprocess.run(['rm', '-f', str(tmp_path / 'state' / 'new')])
