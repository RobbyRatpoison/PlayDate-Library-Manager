"""The update check asks UPDATE_REPOS in order and the first 200 wins."""
import updater


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def _patch(monkeypatch, answers):
    asked = []

    def fake_get(url, **kw):
        asked.append(url)
        for repo, resp in answers.items():
            if f'/repos/{repo}/' in url:
                return resp
        raise AssertionError(url)

    import requests
    monkeypatch.setattr(requests, 'get', fake_get)
    return asked


def test_first_repo_that_answers_wins(monkeypatch):
    monkeypatch.setattr(updater, 'UPDATE_REPOS', ['o/zest', 'o/playdate'])
    asked = _patch(monkeypatch, {'o/zest': _Resp(200, {'tag_name': 'v2.0.0'}),
                                 'o/playdate': _Resp(200, {'tag_name': 'v1.0.0'})})
    assert updater._github_api('releases/latest') == {'tag_name': 'v2.0.0'}
    assert len(asked) == 1


def test_falls_back_to_the_next_repo_on_a_non_200(monkeypatch):
    monkeypatch.setattr(updater, 'UPDATE_REPOS', ['o/zest', 'o/playdate'])
    _patch(monkeypatch, {'o/zest': _Resp(404, {'message': 'Not Found'}),
                         'o/playdate': _Resp(200, {'tag_name': 'v1.0.0'})})
    assert updater._github_api('releases/latest') == {'tag_name': 'v1.0.0'}


def test_returns_the_last_error_body_when_nothing_answers(monkeypatch):
    monkeypatch.setattr(updater, 'UPDATE_REPOS', ['o/zest', 'o/playdate'])
    _patch(monkeypatch, {'o/zest': _Resp(404, {'message': 'a'}),
                         'o/playdate': _Resp(403, {'message': 'rate limit'})})
    assert updater._github_api('releases/latest') == {'message': 'rate limit'}


def test_default_repo_is_unchanged():
    assert updater.UPDATE_REPOS == ['RobbyRatpoison/PlayDate-Library-Manager']
