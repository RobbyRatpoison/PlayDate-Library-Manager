import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_windows_build_bundles_every_runners_module():
    """Plugins import runners.* modules the app itself never does (installdir, diskspace, native_exe,
    windows), so PyInstaller only bundles them if the spec says so; missing ones make plugins fail to
    load on Windows ('No module named runners.installdir')."""
    spec = open(os.path.join(ROOT, 'playdate.spec'), encoding='utf-8').read()
    if "collect_submodules('runners')" in spec:
        return
    listed = set(re.findall(r"^\s*'(runners\.[A-Za-z0-9_]+)'\s*,", spec, re.M))
    on_disk = {'runners.' + f[:-3] for f in os.listdir(os.path.join(ROOT, 'runners'))
               if f.endswith('.py') and f != '__init__.py'}
    assert on_disk <= listed, f'not bundled: {sorted(on_disk - listed)}'


def test_yaml_is_bundled_for_the_ubisoft_plugin():
    spec = open(os.path.join(ROOT, 'playdate.spec'), encoding='utf-8').read()
    assert re.search(r"^\s*'yaml'\s*,", spec, re.M)
