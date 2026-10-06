"""Plugin min_core_version comparison."""


def test_semver_ignores_a_prerelease_suffix():
    from plugins import _semver
    assert _semver('1.12.0-beta.8') == (1, 12, 0)
    assert _semver('v1.12.0-rc.1') == (1, 12, 0)
    assert _semver('1.9.4') == (1, 9, 4)
    assert _semver('1.9.4') < _semver('1.12.0-beta.8')   # the comparison that used to fail
    assert _semver('garbage') == (0, 0, 0)
