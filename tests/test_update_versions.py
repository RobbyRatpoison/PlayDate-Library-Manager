"""Calendar versions (YYYY.M.N) flowing through the update machinery, and the
source-install __build__ stamp."""
import updater


def test_calendar_version_is_newer_than_the_old_scheme():
    assert updater._build_is_newer('2026.11.1', '1.12.0')
    assert updater._build_is_newer('v2026.11.1', '1.12.1')
    assert not updater._build_is_newer('1.12.0', '2026.11.1')


def test_calendar_versions_order_numerically():
    assert updater._build_is_newer('2026.11.2', '2026.11.1')
    assert updater._build_is_newer('2026.11.1', '2026.10.9')
    assert updater._build_is_newer('2026.10.1', '2026.9.12')   # not a string comparison
    assert updater._build_is_newer('2027.1.1', '2026.12.7')


def test_calendar_betas_rank_below_their_final():
    assert updater._build_is_newer('2026.11.1', '2026.11.1-beta.3')
    assert not updater._build_is_newer('2026.11.1-beta.3', '2026.11.1')
    assert updater._build_is_newer('2026.11.1-beta.2', '2026.11.1-beta.1')
    assert updater._build_is_newer('2026.11.1-beta.1', '2026.10.4')


def test_other_version_parsers_accept_calendar_versions():
    from config import _parse_version_tuple
    from plugins import _semver
    assert _parse_version_tuple('2026.11.1') == (2026, 11, 1)
    assert _parse_version_tuple('v2026.11.1-beta.2') == (2026, 11, 1)
    assert _semver('2026.11.1') > _semver('1.12.0')
    assert _semver('2026.11.1-beta.2') == (2026, 11, 1)


# ── The update texts' app name (templates/base.html) ─────────────────────────
# The rule lives in the page's JavaScript, so run the real functions in Node.

import json
import os
import shutil
import subprocess

import pytest

_BASE_HTML = os.path.join(os.path.dirname(__file__), '..', 'templates', 'base.html')


def _name_rule(running, offered, rename_from='2026.11.0'):
    src = open(_BASE_HTML, encoding='utf-8').read()
    a = src.index('function _versionAtLeast(')
    b = src.index('function _setUpdateAvailable(')
    script = (
        'const window = {_APP_VERSION: %s, _RENAME_FROM: %s};\n%s\n'
        'console.log(JSON.stringify({name: _updateAppName(%s), rename: _isRenameUpdate(%s)}));'
    ) % (json.dumps(running), json.dumps(rename_from), src[a:b], json.dumps(offered), json.dumps(offered))
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


needs_node = pytest.mark.skipif(shutil.which('node') is None, reason='node not installed')


@needs_node
def test_name_stays_before_the_rename_version():
    assert _name_rule('1.12.0', '2026.10.1') == {'name': 'PlayDate', 'rename': False}
    assert _name_rule('2026.10.1', '2026.10.2') == {'name': 'PlayDate', 'rename': False}
    assert _name_rule('1.12.0', '1.12.1') == {'name': 'PlayDate', 'rename': False}


@needs_node
def test_the_rename_version_is_announced_to_older_installs():
    assert _name_rule('1.12.0', '2026.11.1') == {'name': 'Zest', 'rename': True}
    assert _name_rule('2026.10.1', '2026.11.1') == {'name': 'Zest', 'rename': True}
    assert _name_rule('2026.10.9', '2026.12.1') == {'name': 'Zest', 'rename': True}
    assert _name_rule('2026.10.1', '2026.11.1-beta.2') == {'name': 'Zest', 'rename': True}


@needs_node
def test_after_the_rename_updates_use_the_new_name_without_the_notice():
    assert _name_rule('2026.11.1', '2026.11.2') == {'name': 'Zest', 'rename': False}
    assert _name_rule('2026.11.1', '2027.1.1') == {'name': 'Zest', 'rename': False}


def test_rename_cutoff_is_a_calendar_version_after_the_bridge_release():
    import config
    assert config.RENAME_FROM_VERSION == '2026.11.0'
    assert updater._build_is_newer(config.RENAME_FROM_VERSION, config.__version__)
