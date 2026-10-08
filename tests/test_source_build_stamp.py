"""The source-install __build__ stamp written after extracting an update."""
import updater


def _config(tmp_path, build_line='__build__ = __version__'):
    p = tmp_path / 'config.py'
    p.write_text(f'__version__ = "1.12.0"\n# comment\n{build_line}\nOTHER = 1\n', encoding='utf-8')
    return p


def test_stamp_source_build_rewrites_the_build_line(tmp_path):
    p = _config(tmp_path)
    assert updater._stamp_source_build(str(tmp_path), 'v1.12.1-beta.2')
    text = p.read_text(encoding='utf-8')
    assert '__build__ = "1.12.1-beta.2"' in text
    assert '__version__ = "1.12.0"' in text and 'OTHER = 1' in text
    ns = {}
    exec(text, ns)
    assert ns['__build__'] == '1.12.1-beta.2'


def test_stamp_source_build_accepts_a_calendar_version(tmp_path):
    p = _config(tmp_path)
    assert updater._stamp_source_build(str(tmp_path), '2026.11.1')
    assert '__build__ = "2026.11.1"' in p.read_text(encoding='utf-8')


def test_stamp_source_build_leaves_an_already_stamped_file_alone(tmp_path):
    p = _config(tmp_path, '__build__ = "1.12.0-beta.1"')
    before = p.read_text(encoding='utf-8')
    assert not updater._stamp_source_build(str(tmp_path), '1.12.1')
    assert p.read_text(encoding='utf-8') == before


def test_stamp_source_build_refuses_anything_that_is_not_a_version(tmp_path):
    p = _config(tmp_path)
    before = p.read_text(encoding='utf-8')
    for bad in ('', None, '1.0"\nimport os', '1.0; os.system("x")', 'latest', '../../x', '1..2'):
        assert not updater._stamp_source_build(str(tmp_path), bad)
    assert p.read_text(encoding='utf-8') == before
