"""Move a user's data from an old install folder into a new one (the Windows PlayDate -> Zest folder change).

Windows won't rename a folder that holds a running exe or an open file, so the new app is installed into a
fresh folder and, on its first start, copies the user data across: copy, verify, re-point stored paths, and
only then remove the old copies. Nothing here depends on a rename or a delete succeeding. A failure while
copying removes what was copied and leaves the old folder exactly as it was; a file that can't be deleted
afterwards is only left behind.

Everything that is not program code counts as user data, so files and folders this module has never heard of
(plugins, art, per-feature json) come along."""
import json
import logging
import os
import shutil
import sqlite3

import datadirs

log = logging.getLogger(__name__)

MARKER = '.moved_from_old_install.json'

# Program files of the old install; the new installer provides its own.
_CODE_NAMES = {'playdate.exe', 'zest.exe', '_internal', '.rollback', 'playdate-rollback.exe', 'zest-rollback.exe'}


def _is_code(name):
    low = name.lower()
    return low in _CODE_NAMES or low.startswith('unins') or low == MARKER.lower()


def _data_entries(root):
    return [n for n in sorted(os.listdir(root)) if not _is_code(n) and not n.lower().endswith(('.db-wal', '.db-shm', '.tmp'))]


def _has_user_data(root):
    if not os.path.isdir(root):
        return False
    names = os.listdir(root)
    return 'config.json' in names or any(n.startswith('games') and n.endswith('.db') for n in names)


def _copy_db(src, dst):
    """A consistent snapshot of a live SQLite file, write-ahead log included."""
    s = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    d = sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()


def _copy_tree(src, dst, created):
    os.makedirs(dst, exist_ok=True)
    for entry in os.scandir(src):
        if entry.name.lower().endswith(('.db-wal', '.db-shm')):
            continue
        target = os.path.join(dst, entry.name)
        if entry.is_dir(follow_symlinks=False):
            if not os.path.exists(target):
                created.append(target)
            _copy_tree(entry.path, target, created)
        else:
            created.append(target)
            if entry.name.lower().endswith('.db'):
                _copy_db(entry.path, target)
            else:
                shutil.copy2(entry.path, target)


def _verify(src, dst):
    """Raise unless dst holds a faithful copy of src (a file, a database or a whole folder)."""
    if os.path.isdir(src):
        for entry in os.scandir(src):
            if not entry.name.lower().endswith(('.db-wal', '.db-shm')):
                _verify(entry.path, os.path.join(dst, entry.name))
        return
    name = os.path.basename(src)
    if name.lower().endswith('.db'):
        con = sqlite3.connect(dst)
        try:
            if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError(f'{name}: copy failed its integrity check')
        finally:
            con.close()
        return
    if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
        raise RuntimeError(f'{name}: copy does not match the original')
    if name.lower().endswith('.json'):
        with open(dst, 'rb') as f:
            json.loads(f.read().decode('utf-8'))


def _undo(created):
    for path in reversed(created):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.lexists(path):
                os.remove(path)
        except OSError:
            pass


def move_install_data(old_dir, new_dir):
    """Copy the user data from old_dir into new_dir. Returns 'none' (nothing to do), 'done', or
    'failed: <why>' (new_dir put back as it was, old_dir untouched)."""
    old_dir, new_dir = os.path.abspath(old_dir), os.path.abspath(new_dir)
    if old_dir == new_dir or not _has_user_data(old_dir):
        return 'none'
    if os.path.exists(os.path.join(new_dir, MARKER)) or _has_user_data(new_dir):
        return 'none'   # moved already, or the new install has its own data: never mix the two

    created = []
    try:
        os.makedirs(new_dir, exist_ok=True)
        for name in _data_entries(old_dir):
            src, dst = os.path.join(old_dir, name), os.path.join(new_dir, name)
            if os.path.isdir(src) and not os.path.islink(src):
                if not os.path.exists(dst):
                    created.append(dst)
                _copy_tree(src, dst, created)
            else:
                created.append(dst)
                if name.lower().endswith('.db'):
                    _copy_db(src, dst)
                else:
                    shutil.copy2(src, dst)
        for name in _data_entries(old_dir):
            _verify(os.path.join(old_dir, name), os.path.join(new_dir, name))
        variants = datadirs._spellings(old_dir)
        for name in _data_entries(new_dir):
            path = os.path.join(new_dir, name)
            if name.lower().endswith('.db') and os.path.isfile(path):
                datadirs._rewrite_db(path, variants, new_dir)
        cfg = os.path.join(new_dir, 'config.json')
        if os.path.isfile(cfg):
            with open(cfg, 'rb') as f:
                data = json.loads(f.read().decode('utf-8'))
            new_data = datadirs._rewrite_strings(data, variants, new_dir)
            if new_data != data:
                with open(cfg, 'w') as f:
                    json.dump(new_data, f, indent=4)
        marker = os.path.join(new_dir, MARKER)
        created.append(marker)
        with open(marker, 'w') as f:
            json.dump({'from': old_dir}, f)
    except Exception as e:
        log.error(f'Moving user data from {old_dir} failed, undoing the copy: {e}', exc_info=True)
        _undo(created)
        return f'failed: {e}'
    log.info(f'User data copied from {old_dir} to {new_dir}')
    return 'done'


def remove_old_data(old_dir):
    """After a successful move and a healthy start: delete the old copies. A file that can't be removed
    (Windows holds it open) is only left behind. Returns the names that are still there."""
    left = []
    if not os.path.isdir(old_dir):
        return left
    for name in _data_entries(old_dir):
        path = os.path.join(old_dir, name)
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError:
            left.append(name)
    for extra in os.listdir(old_dir):
        if extra.lower().endswith(('.db-wal', '.db-shm', '.tmp')):
            try:
                os.remove(os.path.join(old_dir, extra))
            except OSError:
                pass
    try:
        os.rmdir(old_dir)
    except OSError:
        pass   # program files or leftovers remain
    return left


def old_install_dir(exe_dir):
    """The PlayDate folder next to a Zest install folder, if there is one (Windows installer layout)."""
    if os.path.basename(os.path.abspath(exe_dir)).lower() != 'zest':
        return None
    old = os.path.join(os.path.dirname(os.path.abspath(exe_dir)), 'PlayDate')
    return old if os.path.isdir(old) else None


def moved_from(base):
    """The old install folder this install's data was copied from, per the marker, or None."""
    try:
        with open(os.path.join(base, MARKER), encoding='utf-8') as f:
            return json.load(f).get('from')
    except (OSError, ValueError):
        return None


def ask_retry(detail):
    """Windows: tell the user their data could not be moved and ask whether to try again.
    True = retry, False = quit. Anywhere else (or if the box can't be shown) it quits."""
    try:
        import ctypes
        MB_RETRYCANCEL, MB_ICONERROR, IDRETRY = 0x5, 0x10, 4
        text = ('Zest could not move your library from the old PlayDate folder.\n\n'
                'Your data is safe and untouched in the old folder.\n\n' + detail + '\n\nTry again?')
        return ctypes.windll.user32.MessageBoxW(0, text, 'Zest', MB_RETRYCANCEL | MB_ICONERROR) == IDRETRY
    except Exception:
        return False


def finish_move(base):
    """After the first healthy start on the new install: clear the old install's pending-update marker,
    then delete the old data copies. Safe to call on every start; does nothing once everything is gone."""
    old = moved_from(base)
    if not old or not os.path.isdir(old):
        return []
    try:
        import rollback
        rollback.mark_healthy(old)
    except Exception as e:
        log.warning(f'Could not clear the old install\'s update marker: {e}')
    left = remove_old_data(old)
    if left:
        log.info(f'Old install folder still holds: {left}')
    return left
