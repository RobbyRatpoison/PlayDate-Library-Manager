"""Plugin min_core_version comparison."""


def test_semver_ignores_a_prerelease_suffix():
    from plugins import _semver
    assert _semver('1.12.0-beta.8') == (1, 12, 0)
    assert _semver('v1.12.0-rc.1') == (1, 12, 0)
    assert _semver('1.9.4') == (1, 9, 4)
    assert _semver('1.9.4') < _semver('1.12.0-beta.8')   # the comparison that used to fail
    assert _semver('garbage') == (0, 0, 0)


def test_calendar_plugin_versions_outrank_the_old_scheme():
    from plugins import _semver
    assert _semver('2026.10.1') == (2026, 10, 1)
    assert _semver('1.3.1') < _semver('2026.10.1') < _semver('2026.10.2') < _semver('2026.11.1')
    assert _semver('2026.9.12') < _semver('2026.10.1')   # numeric, not string, comparison
