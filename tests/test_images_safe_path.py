import ntpath
import os

import pytest
import werkzeug.security as sec

import images


@pytest.fixture
def windows_safe_join(monkeypatch):
    # What werkzeug computes at import time on Windows: a backslash in a part is an escape attempt
    monkeypatch.setattr(sec, '_os_alt_seps', ['\\'])


def test_a_nested_windows_relative_path_is_accepted(windows_safe_join):
    root = 'C:\\Users\\Q\\PlayDate\\static\\img'
    rel = ntpath.relpath(root + '\\library\\vertical\\123.jpg', root)
    assert rel == 'library\\vertical\\123.jpg'
    got = images._join_under_root(root, rel, sep='\\')
    assert got is not None and got.endswith('123.jpg') and 'library' in got


def test_the_old_call_refused_it(windows_safe_join):
    # Documents the bug: safe_join straight on the Windows relative path
    assert sec.safe_join('C:\\x\\img', 'library\\vertical\\1.jpg') is None


def test_traversal_is_still_refused(windows_safe_join):
    assert images._join_under_root('C:\\x\\img', '..\\..\\evil.jpg', sep='\\') is None
    assert images._join_under_root('C:\\x\\img', '..\\evil.jpg', sep='\\') is None


def test_posix_paths_still_work_and_escapes_are_refused(tmp_path, monkeypatch):
    root = tmp_path / 'static' / 'img'
    (root / 'library' / 'vertical').mkdir(parents=True)
    monkeypatch.setattr(images, '_IMG_ROOT', os.path.realpath(root))
    ok = images._safe_img_path(str(root / 'library' / 'vertical' / '5.jpg'))
    assert ok == os.path.realpath(root / 'library' / 'vertical' / '5.jpg')
    assert images._safe_img_path(str(tmp_path / 'elsewhere.jpg')) is None
