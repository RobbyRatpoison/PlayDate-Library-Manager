import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, 'playdate.spec')


def _hiddenimports():
    """Run the real spec with PyInstaller's objects stubbed out and return the list it builds."""
    class Stub:
        def __init__(self, *a, **k):
            self.pure = self.zipped_data = self.scripts = self.binaries = self.zipfiles = self.datas = []
        def __getattr__(self, name):
            return []
    ns = {'SPEC': SPEC, 'Analysis': Stub, 'PYZ': Stub, 'EXE': Stub, 'COLLECT': Stub, 'BUNDLE': Stub}
    hooks = types.ModuleType('PyInstaller.utils.hooks')
    hooks.collect_data_files = lambda *a, **k: []
    hooks.collect_submodules = lambda *a, **k: []      # as it behaved in the CI build
    saved = {k: sys.modules.get(k) for k in ('PyInstaller', 'PyInstaller.utils', 'PyInstaller.utils.hooks')}
    sys.modules.update({'PyInstaller': types.ModuleType('PyInstaller'), 'PyInstaller.utils': types.ModuleType('PyInstaller.utils'),
                        'PyInstaller.utils.hooks': hooks})
    try:
        exec(compile(open(SPEC, encoding='utf-8').read(), SPEC, 'exec'), ns)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return set(ns['hiddenimports'])


def test_the_windows_build_bundles_every_runners_module():
    """Plugins import runners.* modules the app itself never does (installdir, diskspace, native_exe,
    windows), so PyInstaller only bundles them if the spec says so; missing ones make plugins fail to
    load on Windows ('No module named runners.installdir'). collect_submodules() is stubbed to return
    nothing, as it did in CI, so this fails if the spec leans on it."""
    on_disk = {'runners.' + f[:-3] for f in os.listdir(os.path.join(ROOT, 'runners'))
               if f.endswith('.py') and f != '__init__.py'}
    missing = on_disk - _hiddenimports()
    assert not missing, f'not bundled: {sorted(missing)}'
    assert 'runners.installdir' in _hiddenimports()


def test_yaml_is_bundled_for_the_ubisoft_plugin():
    assert 'yaml' in _hiddenimports()
