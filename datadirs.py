"""Where PlayDate keeps its own per-user folders (Wine prefixes, plugin game installs), and the one-time
move of that folder when the app's folder name changes.

The folder is `<parent>/<DATA_FOLDER_NAME>`: ~/.local/share on Linux, %LOCALAPPDATA% on Windows,
~/Library/Application Support on macOS. DATA_FOLDER_NAME equals LEGACY_FOLDER_NAME until the folder rename
ships, which makes everything here a no-op; flipping it to 'Zest' is the switch.

`migrate()` renames the old folder, leaves a symlink (junction on Windows) at the old name so every
absolute path in the wild keeps working (paths inside Wine prefixes, a plugin that still writes to the
old name), rewrites the paths PlayDate itself stored, and undoes all of it if any step fails."""
import json
import logging
import os
import sys

log = logging.getLogger(__name__)

DATA_FOLDER_NAME = 'PlayDate'
LEGACY_FOLDER_NAME = 'PlayDate'

# games columns that hold absolute paths
_DB_PATH_COLUMNS = ('install_path', 'runner_path')


def _parent_dir():
    if sys.platform == 'win32':
        return os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    if sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support')
    return os.path.expanduser('~/.local/share')


def data_root(parent=None, name=None, legacy=None):
    """The folder to use: the new one if it exists, else the legacy one if that exists (not migrated
    yet, or the migration was skipped), else the new one (a fresh install)."""
    parent = parent or _parent_dir()
    new = os.path.join(parent, name or DATA_FOLDER_NAME)
    old = os.path.join(parent, legacy or LEGACY_FOLDER_NAME)
    if os.path.lexists(new):
        return new
    if os.path.lexists(old):
        return old
    return new


def _under(path, root):
    """path is root itself or inside it (a boundary match, so 'PlayDateX' is not under 'PlayDate')."""
    return path == root or path.startswith(root.rstrip('/\\') + os.sep) or path.startswith(root.rstrip('/\\') + '/')


def _swap_prefix(value, variants, new_root):
    """value with a leading old root (any spelling in `variants`) replaced by new_root, else None."""
    for old in variants:
        if _under(value, old):
            return new_root + value[len(old):]
    return None


def _rewrite_strings(obj, variants, new_root):
    """Deep copy of a JSON value with every string that points into the old folder re-pointed."""
    if isinstance(obj, str):
        swapped = _swap_prefix(obj, variants, new_root)
        return obj if swapped is None else swapped
    if isinstance(obj, list):
        return [_rewrite_strings(x, variants, new_root) for x in obj]
    if isinstance(obj, dict):
        return {k: _rewrite_strings(v, variants, new_root) for k, v in obj.items()}
    return obj


def _spellings(old_root):
    """The old folder as it may be stored: absolute, and with the home directory as '~'."""
    out = [old_root]
    home = os.path.expanduser('~')
    if old_root.startswith(home + os.sep):
        out.append('~' + old_root[len(home):])
    return out


def _link(old_root, new_root):
    if sys.platform == 'win32':
        import _winapi
        _winapi.CreateJunction(new_root, old_root)
    else:
        os.symlink(new_root, old_root, target_is_directory=True)


def _rewrite_db(db_path, variants, new_root):
    """Re-point the path columns of one games database inside a single transaction.
    Returns the (rowid, column, old value) list needed to undo it."""
    import sqlite3
    con = sqlite3.connect(db_path)
    undo = []
    try:
        cols = [c[1] for c in con.execute('PRAGMA table_info(games)').fetchall()]
        use = [c for c in _DB_PATH_COLUMNS if c in cols]
        if not use:
            return undo
        with con:
            for col in use:
                rows = con.execute(f'SELECT rowid, "{col}" FROM games WHERE "{col}" IS NOT NULL AND "{col}" != \'\'').fetchall()
                for rowid, value in rows:
                    if not isinstance(value, str):
                        continue
                    swapped = _swap_prefix(value, variants, new_root)
                    if swapped is not None:
                        con.execute(f'UPDATE games SET "{col}" = ? WHERE rowid = ?', (swapped, rowid))
                        undo.append((rowid, col, value))
    finally:
        con.close()
    return undo


def _undo_db(db_path, undo):
    import sqlite3
    con = sqlite3.connect(db_path)
    try:
        with con:
            for rowid, col, value in undo:
                con.execute(f'UPDATE games SET "{col}" = ? WHERE rowid = ?', (value, rowid))
    finally:
        con.close()


def migrate(db_paths=(), config_path=None, parent=None, name=None, legacy=None, in_use=None):
    """Move <parent>/<legacy> to <parent>/<name>. Returns a short status string:
    'none' (nothing to do), 'done', 'skipped: <why>' (left exactly as it was, tried again next start),
    or 'rolled back: <why>' (a step failed and everything was put back).

    in_use(path) -> bool lets the caller refuse while something (a running Wine prefix) lives there."""
    parent = parent or _parent_dir()
    name = name or DATA_FOLDER_NAME
    legacy = legacy or LEGACY_FOLDER_NAME
    if name == legacy:
        return 'none'
    new_root = os.path.join(parent, name)
    old_root = os.path.join(parent, legacy)
    if not os.path.lexists(old_root) or os.path.islink(old_root):
        return 'none'   # nothing there, or already moved (the old name is the link we left)
    if os.path.lexists(new_root):
        return 'skipped: both folders exist'
    if in_use is not None:
        try:
            if in_use(old_root):
                return 'skipped: in use'
        except Exception as e:
            return f'skipped: could not check whether it is in use ({e})'

    try:
        os.rename(old_root, new_root)
    except OSError as e:
        return f'skipped: could not rename ({e})'

    variants = _spellings(old_root)
    linked = False
    db_undo = {}
    config_backup = None
    try:
        _link(old_root, new_root)
        linked = True
        for db in db_paths:
            if db and os.path.isfile(db):
                db_undo[db] = _rewrite_db(db, variants, new_root)
        if config_path and os.path.isfile(config_path):
            with open(config_path, 'rb') as f:
                config_backup = f.read()
            data = json.loads(config_backup.decode('utf-8'))
            new_data = _rewrite_strings(data, variants, new_root)
            if new_data != data:
                tmp = config_path + '.tmp'
                with open(tmp, 'w') as f:
                    json.dump(new_data, f, indent=4)
                os.replace(tmp, config_path)
        if not os.path.samefile(old_root, new_root):
            raise RuntimeError('the old name does not lead to the new folder')
    except Exception as e:
        log.error(f'Data folder move failed, putting everything back: {e}', exc_info=True)
        try:
            if config_backup is not None:
                with open(config_path, 'wb') as f:
                    f.write(config_backup)
            for db, undo in db_undo.items():
                if undo:
                    _undo_db(db, undo)
            if linked:
                os.rmdir(old_root) if sys.platform == 'win32' else os.unlink(old_root)
            os.rename(new_root, old_root)
        except Exception as e2:
            log.error(f'Could not fully undo the data folder move: {e2}', exc_info=True)
            return f'rolled back: {e} (undo incomplete: {e2})'
        return f'rolled back: {e}'
    log.info(f'Data folder moved: {old_root} -> {new_root}')
    return 'done'


def _prefix_in_use(root):
    """Linux: a Wine/Proton process is running from one of the prefixes under root."""
    if not sys.platform.startswith('linux'):
        return False
    from runners.wine import list_prefix_processes
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if os.path.isdir(path) and list_prefix_processes(path):
            return True
    return False


def migrate_standard():
    """The startup call: migrate with this install's databases and config. Never raises."""
    try:
        import glob
        from config import BASE_DIR, CONFIG_PATH
        status = migrate(sorted(glob.glob(os.path.join(BASE_DIR, 'games*.db'))), CONFIG_PATH, in_use=_prefix_in_use)
        if status != 'none':
            log.info(f'Data folder migration: {status}')
        return status
    except Exception as e:
        log.error(f'Data folder migration failed: {e}', exc_info=True)
        return f'error: {e}'
