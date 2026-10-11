"""POST /api/artwork/reveal and the file manager call behind it."""
import images


def _client(monkeypatch, tmp_path):
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(images.images_bp)
    monkeypatch.setattr(images, 'VERTICAL_DIR', str(tmp_path))
    return app.test_client()


def test_reveal_existing_file(monkeypatch, tmp_path):
    (tmp_path / '-5.jpg').write_bytes(b'x')
    seen = []
    monkeypatch.setattr(images, 'reveal_in_file_manager', seen.append)
    r = _client(monkeypatch, tmp_path).post('/api/artwork/reveal', json={'appid': -5, 'orientation': 'vertical'})
    assert r.status_code == 200 and seen == [str(tmp_path / '-5.jpg')]


def test_reveal_missing_file_and_bad_input(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    assert c.post('/api/artwork/reveal', json={'appid': 9, 'orientation': 'vertical'}).status_code == 404
    assert c.post('/api/artwork/reveal', json={'appid': 'x', 'orientation': 'vertical'}).status_code == 400
    assert c.post('/api/artwork/reveal', json={'appid': 9, 'orientation': '../x'}).status_code == 400


def test_linux_selects_file_then_falls_back_to_folder(monkeypatch):
    import platform, subprocess
    import runners.sandbox as sb
    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    calls = []
    monkeypatch.setattr(sb, 'host_run', lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 1))
    monkeypatch.setattr(sb, 'host_popen', lambda cmd, **k: calls.append(cmd))
    images.reveal_in_file_manager('/tmp/a b/-5.jpg')
    assert 'array:string:file:///tmp/a%20b/-5.jpg' in calls[0]
    assert calls[1] == ['xdg-open', '/tmp/a b']
