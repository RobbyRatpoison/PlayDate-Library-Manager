"""
rollback.py -- update safety net.

Before an update replaces the running version, perform_update() snapshots what
it is about to overwrite plus the small user-data files a new version could
migrate (databases, config.json, state.json, theme.json), and writes
`.rollback/pending.json`. A detached watchdog (started by the OLD version, so a
broken new version can't take it down) then supervises the new version's first
start. The new version deletes pending.json once it has actually served a page
to the window (`mark_healthy`). If the new version exits with an error before
that, twice in a row, the watchdog restores the snapshot, records the failed
version so the updater stops offering it, and starts the old version again.

Stdlib only and no imports from the rest of the app: the Windows watchdog is a
copy of the old exe running with `--pd-watchdog`, the source one is this file
run by the old interpreter.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

DIR_NAME = '.rollback'
ATTEMPTS = 2           # starts of the new version before giving up on it
HANG_LIMIT = 180       # seconds still alive but never healthy: leave it alone
PENDING_MAX_AGE = 24 * 3600
USER_JSON = ('config.json', 'state.json', 'theme.json')
FROZEN_PARTS = ('PlayDate.exe', '_internal')
WATCHDOG_EXE = 'PlayDate-Rollback.exe'


def rb_dir(base):
    return os.path.join(base, DIR_NAME)


def _p(base, *parts):
    return os.path.join(rb_dir(base), *parts)


def _read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _log(base, msg):
    try:
        os.makedirs(rb_dir(base), exist_ok=True)
        with open(_p(base, 'watchdog.log'), 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except Exception:
        pass


def _rm(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.lexists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# ── Pending marker ────────────────────────────────────────────────────────────

def read_pending(base):
    return _read_json(_p(base, 'pending.json'))


def begin(base, kind, old_version, new_version):
    """Mark an update as in flight. Call last, once the snapshot is complete."""
    _write_json(_p(base, 'pending.json'), {
        'kind': kind, 'old_version': old_version, 'new_version': new_version,
        'old_pid': os.getpid(), 'started': time.time(),
    })


def abort(base):
    """The update never got as far as replacing anything: drop the snapshot."""
    _rm(_p(base, 'pending.json'))
    discard_snapshot(base)


def discard_snapshot(base):
    for name in ('code', 'data', 'old.flatpak'):
        _rm(_p(base, name))


def mark_healthy(base):
    """Called by the app once it has rendered a page. The one that wrote the
    pending marker (the old process, still alive for a moment) doesn't count."""
    pend = read_pending(base)
    if not pend or pend.get('old_pid') == os.getpid():
        return False
    _rm(_p(base, 'pending.json'))
    discard_snapshot(base)
    return True


def housekeeping(base):
    """Startup: drop a pending marker nothing resolved (installer cancelled,
    watchdog killed), and fold a finished rollback into the failed-versions
    list so the updater stops re-offering the version that failed."""
    pend = read_pending(base)
    if pend and time.time() - float(pend.get('started') or 0) > PENDING_MAX_AGE:
        _rm(_p(base, 'pending.json'))
        discard_snapshot(base)
    rolled = _read_json(_p(base, 'rolled_back.json'))
    if rolled and rolled.get('from_version') and not rolled.get('recorded'):
        failed = failed_versions(base)
        if rolled['from_version'] not in failed:
            failed.append(rolled['from_version'])
            _write_json(_p(base, 'failed.json'), failed)
        rolled['recorded'] = True
        _write_json(_p(base, 'rolled_back.json'), rolled)


def failed_versions(base):
    v = _read_json(_p(base, 'failed.json'), [])
    return v if isinstance(v, list) else []


def read_notice(base):
    return _read_json(_p(base, 'rolled_back.json'))


def clear_notice(base):
    _rm(_p(base, 'rolled_back.json'))


# ── User-data snapshot ────────────────────────────────────────────────────────

def _db_files(base):
    try:
        return [n for n in os.listdir(base) if n.startswith('games') and n.endswith('.db')]
    except OSError:
        return []


def backup_data(base):
    """Copy databases and settings into .rollback/data. Databases go through
    sqlite's backup API: the app is running, so a plain copy could miss WAL."""
    dest = _p(base, 'data')
    _rm(dest)
    os.makedirs(dest, exist_ok=True)
    for name in USER_JSON:
        src = os.path.join(base, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, name))
    for name in _db_files(base):
        src = sqlite3.connect(os.path.join(base, name))
        try:
            out = sqlite3.connect(os.path.join(dest, name))
            try:
                src.backup(out)
            finally:
                out.close()
        finally:
            src.close()


def restore_data(base):
    src_dir = _p(base, 'data')
    if not os.path.isdir(src_dir):
        return
    for name in os.listdir(src_dir):
        if name.endswith('.db'):
            # A -wal/-shm left by the failed version would be replayed onto
            # the restored database.
            _rm(os.path.join(base, name + '-wal'))
            _rm(os.path.join(base, name + '-shm'))
        shutil.copy2(os.path.join(src_dir, name), os.path.join(base, name))


# ── Code snapshot: source installs ────────────────────────────────────────────

def snapshot_source(base, rel_paths):
    """Save every file the update zip is about to overwrite; remember the ones
    it will create so a rollback can delete them."""
    root = _p(base, 'code')
    _rm(root)
    os.makedirs(root, exist_ok=True)
    created = []
    for rel in rel_paths:
        src = os.path.join(base, rel)
        if os.path.isfile(src):
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        else:
            created.append(rel)
    _write_json(_p(base, 'code', '.created.json'), created)


def restore_source(base):
    root = _p(base, 'code')
    if not os.path.isdir(root):
        return
    for rel in _read_json(os.path.join(root, '.created.json'), []):
        _rm(os.path.join(base, rel))
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn == '.created.json' and dirpath == root:
                continue
            src = os.path.join(dirpath, fn)
            dst = os.path.join(base, os.path.relpath(src, root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)


# ── Code snapshot: frozen Windows build ───────────────────────────────────────

def _tree_size(path):
    total = 0
    for dirpath, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def snapshot_frozen(base):
    """Copy PlayDate.exe and _internal. Returns False (and leaves nothing
    behind) if the layout is unexpected or the disk is too full."""
    exe = os.path.join(base, 'PlayDate.exe')
    internal = os.path.join(base, '_internal')
    if not (os.path.isfile(exe) and os.path.isdir(internal)):
        return False
    need = _tree_size(internal) + os.path.getsize(exe) * 2
    if shutil.disk_usage(base).free < need * 1.2:
        return False
    root = _p(base, 'code')
    _rm(root)
    os.makedirs(root, exist_ok=True)
    shutil.copytree(internal, os.path.join(root, '_internal'))
    shutil.copy2(exe, os.path.join(root, 'PlayDate.exe'))
    # The watchdog runs from here under another name: the installer replaces
    # base\PlayDate.exe and the watchdog must not share its image name with the
    # app it is waiting for.
    shutil.copy2(exe, os.path.join(root, WATCHDOG_EXE))
    return True


def restore_frozen(base):
    root = _p(base, 'code')
    if not os.path.isdir(os.path.join(root, '_internal')):
        return False
    live, staged, failed = (os.path.join(base, n) for n in ('_internal', '_internal.restoring', '_internal.failed'))
    exe, exe_new = os.path.join(base, 'PlayDate.exe'), os.path.join(base, 'PlayDate.exe.restoring')
    # Stage the old files beside the live ones, then swap by rename: a rename
    # that fails (a crashed process still holding a lock) leaves the tree as it
    # was, where deleting _internal first could leave it half gone.
    _rm(staged)
    _rm(failed)
    shutil.copytree(os.path.join(root, '_internal'), staged)
    shutil.copy2(os.path.join(root, 'PlayDate.exe'), exe_new)
    for attempt in range(10):
        try:
            os.rename(live, failed)
        except FileNotFoundError:
            pass
        except OSError:
            time.sleep(1.5)
            continue
        try:
            os.rename(staged, live)
            os.replace(exe_new, exe)
        except OSError:
            if not os.path.exists(live) and os.path.exists(failed):
                os.rename(failed, live)   # put back what was there
            time.sleep(1.5)
            continue
        _rm(failed)
        return True
    _rm(staged)
    _rm(exe_new)
    return False


# ── Watchdog ──────────────────────────────────────────────────────────────────

def _spawn(cmd, cwd):
    kw = {'cwd': cwd, 'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
          'stderr': subprocess.DEVNULL}
    if os.name == 'nt':
        kw['creationflags'] = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                               | getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        kw['start_new_session'] = True
    return subprocess.Popen(cmd, **kw)


def _supervise(base, child):
    """'healthy' | 'clean' | 'failed' | 'hung' for one start of the new version."""
    t0 = time.time()
    while True:
        if not read_pending(base):
            return 'healthy'
        rc = child.poll()
        if rc is not None:
            if not read_pending(base):
                return 'healthy'
            return 'clean' if rc == 0 else 'failed'
        if time.time() - t0 > HANG_LIMIT:
            return 'hung'
        time.sleep(0.5)


def _image_running(name):
    try:
        out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {name}', '/NH'],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        return name.lower() in out.lower()
    except Exception:
        return False


def _wait_installer_launch(base, exe_name, give_up=900):
    """Windows: the installer, not us, starts the new exe. Wait for it to show
    up, then for it to either go healthy or vanish. 'failed' only if it vanished."""
    time.sleep(6)   # the old process is exiting; don't mistake it for the new one
    t0 = time.time()
    while not _image_running(exe_name):
        if not read_pending(base):
            return 'healthy'
        if time.time() - t0 > give_up:
            return 'gave_up'   # installer cancelled or never finished
        time.sleep(2)
    t1 = time.time()
    while _image_running(exe_name):
        if not read_pending(base):
            return 'healthy'
        if time.time() - t1 > HANG_LIMIT:
            return 'hung'
        time.sleep(1)
    return 'healthy' if not read_pending(base) else 'failed'


def _do_rollback(base, kind, reason):
    pend = read_pending(base) or {}
    _log(base, f'rolling back ({kind}): {reason}')
    ok = True
    if kind == 'frozen':
        ok = restore_frozen(base)
    else:
        restore_source(base)
    if not ok:
        _log(base, 'could not restore program files; leaving them as they are')
        _rm(_p(base, 'pending.json'))
        return False
    restore_data(base)
    _write_json(_p(base, 'rolled_back.json'), {
        'from_version': pend.get('new_version'), 'to_version': pend.get('old_version'),
        'reason': reason, 'time': time.time()})
    _rm(_p(base, 'pending.json'))
    discard_snapshot(base)
    return True


def watchdog_main(argv):
    """`--base-dir B --kind source|frozen --launch <json argv> [--exe-name N]`"""
    args = {}
    it = iter(argv)
    for a in it:
        if a.startswith('--'):
            args[a[2:]] = next(it, '')
    base, kind = args['base-dir'], args['kind']
    launch = json.loads(args['launch'])
    cwd = base
    _log(base, f'watchdog start kind={kind}')

    attempts = ATTEMPTS
    if kind == 'frozen':
        state = _wait_installer_launch(base, args.get('exe-name', 'PlayDate.exe'))
        if state in ('healthy', 'gave_up', 'hung'):
            _log(base, f'first start: {state}; done')
            return
        attempts -= 1   # the installer's launch was attempt one
    else:
        time.sleep(2)   # let the old process release the port

    while attempts > 0:
        child = _spawn(launch, cwd)
        state = _supervise(base, child)
        _log(base, f'start result: {state}')
        if state != 'failed':
            return
        attempts -= 1
        time.sleep(2)

    if _do_rollback(base, kind, 'the new version failed to start twice'):
        _spawn(launch, cwd)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'watch':
        watchdog_main(sys.argv[2:])


# ── Flatpak watchdog ──────────────────────────────────────────────────────────
# Runs on the host (flatpak-spawn --host), written out by the old version.
# POSIX sh because a host is not guaranteed a python3 on PATH.
# Args: BASE APP_ID MODE LAUNCH NEW_VER OLD_VER
#   MODE child    -- LAUNCH is run as our child, so its exit code is known
#   MODE observe  -- LAUNCH hands off to something else (Steam Game Mode's
#                    rungameid), so we only watch whether the app is running
FLATPAK_WATCHDOG_SH = r'''#!/bin/sh
BASE="$1"; APP="$2"; MODE="$3"; LAUNCH="$4"; NEW="$5"; OLD="$6"
RB="$BASE/.rollback"
LOG="$RB/watchdog.log"
say() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
pending() { [ -f "$RB/pending.json" ]; }
instances() { flatpak ps --columns=instance,application 2>/dev/null | awk -v a="$APP" '$2 == a { print $1 }'; }
new_instance() {
    for i in $(instances); do
        case "$OLD_INST" in *" $i "*) ;; *) echo "$i"; return 0 ;; esac
    done
    return 1
}

# One start of the new version. 0 = fine (healthy, quit cleanly, or still
# starting after HANG_LIMIT), 1 = failed.
start_once() {
    if [ "$MODE" = child ]; then
        sh -c "$LAUNCH" >/dev/null 2>&1 &
        pid=$!
        waited=0
        while kill -0 "$pid" 2>/dev/null; do
            pending || return 0
            sleep 1; waited=$((waited + 1))
            [ "$waited" -ge 180 ] && return 0
        done
        wait "$pid"; rc=$?
        pending || return 0
        [ "$rc" -eq 0 ] && return 0
        return 1
    fi
    # Judge only the instance this launch creates: the old version's sandbox
    # can still be listed for a while after it exits, and treating "any
    # instance of the app" as the new version made a crash look like a start
    # (or a start look like a crash once the old one finally went away).
    sh -c "$LAUNCH" >/dev/null 2>&1 &
    waited=0
    inst=""
    while [ -z "$inst" ]; do
        pending || return 0
        inst=$(new_instance)
        [ -n "$inst" ] && break
        sleep 1; waited=$((waited + 1))
        [ "$waited" -ge 90 ] && return 0
    done
    waited=0
    while instances | grep -qx "$inst"; do
        pending || return 0
        sleep 1; waited=$((waited + 1))
        [ "$waited" -ge 180 ] && return 0
    done
    pending || return 0
    return 1
}

say "watchdog start mode=$MODE"
sleep 2
OLD_INST=" $(instances | tr '\n' ' ') "
attempt=1
while [ "$attempt" -le 2 ]; do
    start_once && { say "start ok"; exit 0; }
    say "start $attempt failed"
    attempt=$((attempt + 1))
    sleep 2
done

say "rolling back to $OLD"
if ! flatpak install --user -y --reinstall "$RB/old.flatpak" >> "$LOG" 2>&1; then
    say "reinstall of the old bundle failed; leaving things as they are"
    rm -f "$RB/pending.json"
    exit 1
fi
if [ -d "$RB/data" ]; then
    for f in "$RB"/data/*.db; do
        [ -e "$f" ] || continue
        rm -f "$BASE/$(basename "$f")-wal" "$BASE/$(basename "$f")-shm"
    done
    cp -a "$RB"/data/. "$BASE"/
fi
printf '{"from_version": "%s", "to_version": "%s", "reason": "the new version failed to start twice", "time": %s}\n' \
    "$NEW" "$OLD" "$(date +%s)" > "$RB/rolled_back.json"
rm -f "$RB/pending.json"
rm -rf "$RB/code" "$RB/data" "$RB/old.flatpak"
sh -c "$LAUNCH" >/dev/null 2>&1 &
exit 0
'''
