"""The once-a-day update check must not trust a result saved before a rollback."""
import time

import config
import updater


def _run(monkeypatch, checked_ago, rolled_back_ago):
    """Run _maybe_update_check with a saved check made `checked_ago` seconds ago and a
    rollback `rolled_back_ago` seconds ago (None = no rollback); True if it went to GitHub."""
    now = time.time()
    saved = {'latest_version': '2026.10.5', 'available': True, 'checked_at': now - checked_ago}
    monkeypatch.setattr(config, 'load_state', lambda: {'check_for_updates': True, 'update_check_cache': saved})
    monkeypatch.setattr(updater.rollback, 'read_notice',
                        lambda base: {'time': now - rolled_back_ago} if rolled_back_ago is not None else None)
    monkeypatch.setattr(updater, '_update_cache', {})
    calls = []
    monkeypatch.setattr(updater, '_do_update_check', lambda: calls.append(1))
    updater._maybe_update_check()
    return bool(calls)


def test_fresh_check_is_trusted_when_nothing_was_rolled_back(monkeypatch):
    assert _run(monkeypatch, checked_ago=3600, rolled_back_ago=None) is False


def test_check_older_than_a_day_always_refreshes(monkeypatch):
    assert _run(monkeypatch, checked_ago=25 * 3600, rolled_back_ago=None) is True


def test_check_made_before_the_rollback_is_refreshed(monkeypatch):
    # checked an hour before the update, rolled back ten minutes ago
    assert _run(monkeypatch, checked_ago=4200, rolled_back_ago=600) is True


def test_check_made_after_the_rollback_is_trusted_again(monkeypatch):
    # rolled back an hour ago, checked five minutes ago (the refresh already happened)
    assert _run(monkeypatch, checked_ago=300, rolled_back_ago=3600) is False
