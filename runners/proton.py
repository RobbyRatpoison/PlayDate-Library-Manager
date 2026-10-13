"""
runners/proton.py — Detect and launch Proton for Windows GOG games.
"""

import glob
import logging
import os
import re

from runners.sandbox import host_popen

log = logging.getLogger(__name__)

# Folders that hold community Proton builds (GE-Proton, Proton-CachyOS, Proton-EM, UMU-Proton, ...),
# one directory per build with a `proton` script inside. Steam installed natively, through Flatpak,
# through Snap, or by the distro (CachyOS/Arch ship proton-cachyos under /usr/share/steam).
_COMPAT_TOOL_DIRS = [
    '~/.local/share/Steam/compatibilitytools.d',
    '~/.steam/steam/compatibilitytools.d',
    '~/.steam/root/compatibilitytools.d',
    '~/.var/app/com.valvesoftware.Steam/.local/share/Steam/compatibilitytools.d',
    '~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d',
    '~/snap/steam/common/.local/share/Steam/compatibilitytools.d',
    '/usr/share/steam/compatibilitytools.d',
    '/usr/local/share/steam/compatibilitytools.d',
]

# Steam roots, whose steamapps/common/Proton */ holds the official builds (also in extra libraries).
_STEAM_ROOTS = [
    '~/.local/share/Steam',
    '~/.steam/steam',
    '~/.var/app/com.valvesoftware.Steam/.local/share/Steam',
    '~/.var/app/com.valvesoftware.Steam/data/Steam',
    '~/snap/steam/common/.local/share/Steam',
]


def _host_listing(patterns):
    """Matches for shell glob `patterns` on the host. Under Flatpak the sandbox can't see other apps'
    data (~/.var/app/...) or a distro's /usr, so ask the host."""
    from runners.sandbox import IN_FLATPAK, host_run
    import subprocess
    if not IN_FLATPAK:
        return None
    script = 'for p in "$@"; do for f in $p; do [ -e "$f" ] && echo "$f"; done; done'
    try:
        r = host_run(['sh', '-c', script, 'sh'] + patterns, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, timeout=10)
        return [l for l in r.stdout.decode('utf-8', errors='replace').splitlines() if l.strip()]
    except Exception as e:
        log.info(f'Host Proton search failed: {e}')
        return None


def _steam_library_roots():
    """Every extra Steam library folder named in a libraryfolders.vdf we can read."""
    roots = []
    for root in _STEAM_ROOTS:
        vdf = os.path.join(os.path.expanduser(root), 'config', 'libraryfolders.vdf')
        try:
            with open(vdf, encoding='utf-8', errors='ignore') as f:
                for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                    roots.append(m.group(1).replace('\\\\', '\\'))
        except OSError:
            pass
    return roots


def _candidate_patterns():
    pats = []
    for d in _COMPAT_TOOL_DIRS:
        pats.append(os.path.join(os.path.expanduser(d), '*', 'proton'))
    for root in [os.path.expanduser(r) for r in _STEAM_ROOTS] + _steam_library_roots():
        pats.append(os.path.join(root, 'steamapps', 'common', 'Proton*', 'proton'))
    return pats


def _rank(path):
    """GE-Proton first (broadest compatibility), then other community builds, then official Proton."""
    name = os.path.basename(os.path.dirname(path)).lower()
    if name.startswith('ge-proton'):
        return 0
    if os.sep + 'compatibilitytools.d' + os.sep in path:
        return 1
    return 2


def find_proton_versions():
    """
    Return all installed Proton versions as a list of dicts:
        [{'name': str, 'path': str}]
    GE-Proton first, then other community builds, then official Proton; newest name first within each.
    """
    pats = _candidate_patterns()
    paths = _host_listing(pats)
    if paths is None:
        paths = [p for pat in pats for p in glob.glob(pat)]
    seen  = set()   # resolved real paths to avoid symlink duplicates
    found = []
    for path in sorted(set(paths)):
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        found.append({'name': os.path.basename(os.path.dirname(path)), 'path': path})
    # newest name first inside each rank (names carry the version)
    found.sort(key=lambda v: (_rank(v['path']), [-ord(c) for c in v['name'].lower()]))
    return found


def get_default_proton():
    """
    Return the best available Proton dict, or None if nothing is installed.
    Prefers GE-Proton for broader compatibility.
    """
    versions = find_proton_versions()
    return versions[0] if versions else None


def _find_steam_root(proton_path):
    """Walk up from proton_path until we find a directory that contains 'steamapps'."""
    d = os.path.dirname(os.path.abspath(proton_path))
    while d and d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, 'steamapps')):
            return d
        d = os.path.dirname(d)
    # Hard-coded fallback
    for candidate in ('~/.steam/steam', '~/.local/share/Steam'):
        expanded = os.path.expanduser(candidate)
        if os.path.isdir(expanded):
            return expanded
    return os.path.expanduser('~/.steam/steam')


def launch_game(install_path, executable, wine_prefix, proton_path=None, env_extra=None,
                args=None, cwd=None):
    """
    Launch a Windows game via Proton.

    install_path  : directory where the game is installed
    executable    : relative path to the .exe within install_path
    wine_prefix   : directory for the Wine/Proton prefix (created automatically if absent)
    proton_path   : absolute path to the 'proton' script; auto-detected if None
    env_extra     : dict of extra environment variables to set
    args          : list of extra arguments to pass to the executable
    cwd           : working directory for the process; defaults to install_path

    Returns the Popen object (caller should not wait — game runs in background).
    Raises RuntimeError if no Proton is found.
    """
    if proton_path is None:
        p = get_default_proton()
        if not p:
            raise RuntimeError(
                'No Proton installation found. '
                'Install Proton via Steam (Tools section) or GE-Proton.'
            )
        proton_path = p['path']

    os.makedirs(wine_prefix, exist_ok=True)

    steam_root = _find_steam_root(proton_path)
    env = dict(os.environ)
    env['STEAM_COMPAT_DATA_PATH']           = wine_prefix
    env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
    if env_extra:
        env.update(env_extra)

    exe_abs = os.path.join(install_path, executable)
    cmd     = [proton_path, 'run', exe_abs] + (args or [])
    log.info(f'Proton launch: {cmd[0]} run {executable}  (prefix={wine_prefix})')
    return host_popen(cmd, env=env, cwd=cwd or install_path)
