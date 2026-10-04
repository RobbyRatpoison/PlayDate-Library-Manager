"""Gamepad layouts: saved choices are validated, and the SDL database build script reads
vendor/product ids and mapping strings correctly."""
import importlib.util
import json
import os

import config

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('build_gamepad_db', os.path.join(HERE, '..', 'tools', 'build_gamepad_db.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

PAD = '8BitDo (Vendor: 2dc8 Product: 310b)'
MAP = 'a:b0,b:b1,leftx:a0,lefty:a1,dpup:h0.1,lefttrigger:+a2,leftshoulder:b4~'


def test_normalize_keeps_valid_entries():
    got = config.normalize_gamepad_layouts({
        PAD: {'kind': 'map', 'map': MAP, 'style': 'xbox'},
        'Other pad': {'kind': 'standard'},
        'Styled only': {'style': 'ps'},
    })
    assert got == {PAD: {'kind': 'map', 'map': MAP, 'style': 'xbox'},
                   'Other pad': {'kind': 'standard'},
                   'Styled only': {'style': 'ps'}}


def test_normalize_drops_bad_entries():
    got = config.normalize_gamepad_layouts({
        'bad kind': {'kind': 'rm -rf'},
        'bad map chars': {'kind': 'map', 'map': 'a:b0; DROP TABLE'},
        'map missing': {'kind': 'map'},
        'too long': {'kind': 'map', 'map': 'a' * 1001},
        'bad style': {'style': 'sega'},
        '': {'kind': 'standard'},
        'x' * 201: {'kind': 'standard'},
        'not a dict': 'standard',
        'auto is never stored': {'kind': 'auto'},
    })
    assert got == {}


def test_normalize_rejects_non_dicts_and_caps_the_count():
    assert config.normalize_gamepad_layouts(None) == {}
    assert config.normalize_gamepad_layouts([PAD]) == {}
    many = {f'pad {i}': {'kind': 'standard'} for i in range(100)}
    assert len(config.normalize_gamepad_layouts(many)) == 64


def test_vid_pid_reads_the_guid():
    assert build.vid_pid('03000000c82d00000b31000014010000') == ('2dc8', '310b')
    assert build.vid_pid('030000004c050000cc09000000810000') == ('054c', '09cc')


def test_vid_pid_skips_name_based_guids():
    assert build.vid_pid('0000000058626f782033363020576900') is None   # "Xbox 360 Wi" name hash
    assert build.vid_pid('not a guid') is None
    assert build.vid_pid('03000000000000000b31000014010000') is None   # no vendor


def test_build_keeps_linux_entries_and_dedupes(tmp_path, monkeypatch):
    src = tmp_path / 'db.txt'
    src.write_text('\n'.join([
        '# comment',
        '03000000c82d00000b31000014010000,8BitDo Ultimate 2,a:b0,b:b1,leftx:a0,platform:Linux,',
        '03000000c82d00000b31000015010000,8BitDo Ultimate 2,a:b0,b:b1,leftx:a0,platform:Linux,',   # same mapping, other version
        '03000000c82d00000b31000016010000,8BitDo Ultimate 2,a:b1,b:b0,leftx:a0,platform:Linux,',   # a different layout
        '03000000c82d00000b31000014010000,8BitDo Ultimate 2,a:b0,platform:Windows,',               # other platform
        '0000000058626f782033363020576900,Xbox 360 Controller,a:b0,platform:Linux,',               # name-based guid
    ]), encoding='utf-8')
    out = tmp_path / 'out.json'
    monkeypatch.setattr(build, 'OUT', str(out))
    build.main(str(src))
    layouts = json.loads(out.read_text())['layouts']
    assert list(layouts) == ['2dc8:310b']
    assert layouts['2dc8:310b']['maps'] == ['a:b0,b:b1,leftx:a0', 'a:b1,b:b0,leftx:a0']


def test_bundled_database_has_the_8bitdo_pad():
    path = os.path.join(HERE, '..', 'static', 'data', 'gamepad_layouts.json')
    layouts = json.load(open(path))['layouts']
    maps = layouts['2dc8:310b']['maps']
    assert any('lefttrigger:a2' in m and 'righttrigger:a5' in m for m in maps)
