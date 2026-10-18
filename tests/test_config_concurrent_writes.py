import json
import threading

import config


def _hammer(tmp_path, monkeypatch, writers=6, rounds=150):
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_PATH', str(path))
    config._save_config_data({'seed': 'x' * 50})
    errors = []
    stop = threading.Event()

    def write(n):
        # Different sizes each round, so an interleaved or unfinished write cannot parse by accident
        for i in range(rounds):
            try:
                config._save_config_data({'writer': n, 'round': i, 'pad': 'p' * ((n * 37 + i * 11) % 400)})
            except Exception as e:
                errors.append(f'write: {e!r}')

    def read():
        while not stop.is_set():
            try:
                json.loads(json.dumps(config.load_config()))
            except Exception as e:
                errors.append(f'read: {e!r}')

    readers = [threading.Thread(target=read) for _ in range(2)]
    pool = [threading.Thread(target=write, args=(n,)) for n in range(writers)]
    for t in readers + pool:
        t.start()
    for t in pool:
        t.join()
    stop.set()
    for t in readers:
        t.join()
    return path, errors


def test_concurrent_saves_never_corrupt_or_tear_the_file(tmp_path, monkeypatch):
    path, errors = _hammer(tmp_path, monkeypatch)
    assert errors == []
    json.loads(path.read_text())           # the file on disk is whole JSON
    assert list(tmp_path.iterdir()) == [path]   # and no temp files were left behind


def test_failed_save_leaves_the_old_file_and_no_temp(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_PATH', str(path))
    config._save_config_data({'a': 1})

    class Unserialisable:
        pass
    try:
        config._save_config_data({'a': Unserialisable()})
    except TypeError:
        pass
    assert json.loads(path.read_text()) == {'a': 1}
    assert list(tmp_path.iterdir()) == [path]
