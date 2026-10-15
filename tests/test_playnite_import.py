"""Playnite import across library plugins: the LiteDB v4 reader (imports._litedb4_documents,
parse_playnite_games) and the matcher that resolves Playnite games to PlayDate rows
(match_playnite_games). The file builder mirrors the layout in LiteDB 4.1.4's source and
a real backup: 4096-byte pages, 25-byte page header, data blocks of
[index u16, extendPageId u32, size u16, bytes], extend pages chained by nextPageId.
The plugin ids below are the real ones seen in public Playnite libraries."""
import sqlite3
import struct
import uuid
import zipfile
from datetime import datetime, timezone

import imports

PAGE = 4096
GOG = 'aebe8b7c-6dc3-4a66-af31-e7375c6b5e9e'
AMAZON = '402674cd-4af6-4886-b6ec-0e695bfa0688'
XBOX = '7e4fbb5e-2ae3-48d4-8ba0-6b30e7a4e287'
EPIC = '00000002-dbd1-46c6-b5d0-b1ba559d10e4'


def _ms(date):
    return int(datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)


def _el(t, key, payload):
    return bytes([t]) + key.encode() + b'\x00' + payload


def _bson(game_id, plugin, name=None, added=None, last=None, playtime=None, pad=0):
    body = b''
    body += _el(0x02, 'Description', struct.pack('<i', pad + 1) + b'x' * pad + b'\x00')
    if name is not None:
        b = name.encode() + b'\x00'
        body += _el(0x02, 'Name', struct.pack('<i', len(b)) + b)
    body += _el(0x03, 'CompletionStatus', struct.pack('<i', 5) + b'\x00')   # embedded doc
    b = game_id.encode() + b'\x00'
    body += _el(0x02, 'GameId', struct.pack('<i', len(b)) + b)
    body += _el(0x05, 'PluginId', struct.pack('<i', 16) + b'\x04' + uuid.UUID(plugin).bytes_le)
    if added:
        body += _el(0x09, 'Added', struct.pack('<q', _ms(added)))
    if last:
        body += _el(0x09, 'LastActivity', struct.pack('<q', _ms(last)))
    if playtime is not None:
        body += _el(0x12, 'Playtime', struct.pack('<q', playtime))
    return struct.pack('<i', len(body) + 5) + body + b'\x00'


def _page(pid, ptype, nxt=0xFFFFFFFF, count=0, content=b''):
    h = struct.pack('<IBIIHH', pid, ptype, 0xFFFFFFFF, nxt, count, 0) + b'\x00' * 8
    return (h + content).ljust(PAGE, b'\x00')


def _litedb(docs):
    """Header page, then one data page per document; a document over 3 KB goes to extend pages."""
    head = bytearray(PAGE)
    head[25:52] = b'** This is a LiteDB file **'
    head[52] = 7
    pages = [bytes(head)]
    for i, d in enumerate(docs):
        pid = len(pages)
        if len(d) <= 3000:
            block = struct.pack('<HIH', 0, 0xFFFFFFFF, len(d)) + d
            pages.append(_page(pid, 4, count=1, content=block))
        else:
            chunks = [d[j:j + 3000] for j in range(0, len(d), 3000)]
            ext_ids = [pid + 1 + k for k in range(len(chunks))]
            block = struct.pack('<HIH', 0, ext_ids[0], 0)
            pages.append(_page(pid, 4, count=1, content=block))
            for k, c in enumerate(chunks):
                nxt = ext_ids[k + 1] if k + 1 < len(chunks) else 0xFFFFFFFF
                pages.append(_page(ext_ids[k], 5, nxt=nxt, count=len(c), content=c))
    return b''.join(pages)


def _zip(tmp_path, blob):
    p = tmp_path / 'backup.zip'
    with zipfile.ZipFile(p, 'w') as zf:
        zf.writestr('library/games.db', blob)
    return str(p)


def _library(rows):
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE games(appid INT, platform TEXT, platform_id TEXT, platform_appname TEXT, name TEXT)")
    db.executemany("INSERT INTO games VALUES (?,?,?,?,?)", rows)
    return db


def test_reads_documents_including_ones_in_extend_pages(tmp_path):
    big = _bson('730', imports.STEAM_PLUGIN_ID, 'Counter-Strike 2', added='2020-01-02', pad=9000)
    small = _bson('1207666073', GOG, 'Witcher', added='2021-03-04', last='2022-05-06', playtime=7200)
    games = imports.parse_playnite_games(_zip(tmp_path, _litedb([big, small])))
    assert games == [
        {'plugin': imports.STEAM_PLUGIN_ID, 'game_id': '730', 'name': 'Counter-Strike 2', 'date_added': '2020-01-02'},
        {'plugin': GOG, 'game_id': '1207666073', 'name': 'Witcher', 'date_added': '2021-03-04',
         'last_played': _ms('2022-05-06') // 1000, 'playtime': 120},
    ]


def test_game_without_a_field_does_not_take_its_neighbours(tmp_path):
    a = _bson('1', imports.STEAM_PLUGIN_ID, 'A', added='2020-01-01', last='2021-01-01', playtime=600)
    b = _bson('2', imports.STEAM_PLUGIN_ID, 'B')
    g = imports.parse_playnite_games(_zip(tmp_path, _litedb([a, b])))
    assert g[1] == {'plugin': imports.STEAM_PLUGIN_ID, 'game_id': '2', 'name': 'B'}


def test_other_file_formats_fall_back_to_the_byte_scan(tmp_path):
    # Not a LiteDB v4 file: a bare GameId + Added, as the older synthetic tests build them.
    gid = b'\x02GameId\x00' + struct.pack('<i', 4) + b'440\x00'
    added = b'\x09Added\x00' + struct.pack('<q', _ms('2020-09-13'))
    g = imports.parse_playnite_games(_zip(tmp_path, b'\x00' * 40 + gid + b'\x00' * 20 + added))
    assert g == [{'plugin': None, 'game_id': '440', 'date_added': '2020-09-13'}]


def _pn(plugin, game_id, name, **vals):
    return {'plugin': plugin, 'game_id': game_id, 'name': name, **vals}


def test_matches_each_plugin_by_its_own_id():
    db = _library([
        (440, 'steam', None, None, 'Team Fortress 2'),
        (-1207666073, 'gog', '1207666073', None, 'Witcher'),
        (-5, 'amazon_games', 'amzn1.adg.product.AAA', None, 'Amazon Game'),
        (-6, 'xbox', None, 'Microsoft.Chelan_8wekyb3d8bbwe', 'Halo'),
    ])
    games = [
        _pn(imports.STEAM_PLUGIN_ID, '440', 'x', date_added='2020-01-01'),
        _pn(GOG, '1207666073', 'x', date_added='2021-01-01'),
        _pn(AMAZON, 'AMZN1.adg.product.aaa', 'x', date_added='2022-01-01'),
        _pn(XBOX, 'Microsoft.Chelan_8wekyb3d8bbwe', 'x', date_added='2023-01-01'),
        _pn(GOG, '999', 'Not Owned', date_added='2024-01-01'),
    ]
    out, per, missing = imports.match_playnite_games(games, db)
    assert {a: v['date_added'] for a, v in out.items()} == {
        440: '2020-01-01', -1207666073: '2021-01-01', -5: '2022-01-01', -6: '2023-01-01'}
    assert per == {'steam': 1, 'gog': 1, 'amazon_games': 1, 'xbox': 1}
    assert missing == 1


def test_a_gog_id_is_never_taken_for_a_steam_appid():
    db = _library([(1207666073, 'steam', None, None, 'Some Steam Game')])
    out, _per, missing = imports.match_playnite_games(
        [_pn(GOG, '1207666073', 'Witcher', date_added='2021-01-01')], db)
    assert out == {} and missing == 1


def test_name_fallback_stays_within_the_plugins_platform():
    # Two GOG games match by id (so Playnite's GOG plugin is known to be PlayDate's 'gog');
    # a third has no id match but the same name as a GOG row, and the same name exists on Epic.
    db = _library([
        (-1, 'gog', '1', None, 'One'), (-2, 'gog', '2', None, 'Two'),
        (-3, 'gog', 'other-id', None, 'Hades: Edition'), (-4, 'epic_games', 'x', None, 'Hades Edition'),
    ])
    games = [_pn(GOG, '1', 'One', playtime=5), _pn(GOG, '2', 'Two', playtime=5),
             _pn(GOG, '77', 'Hades Edition', playtime=9)]
    out, per, _ = imports.match_playnite_games(games, db)
    assert out[-3] == {'playtime': 9} and -4 not in out
    assert per['gog'] == 3


def test_ambiguous_name_is_skipped_not_guessed():
    db = _library([(-1, 'gog', 'a', None, 'Twin'), (-2, 'gog', 'b', None, 'Twin'), (-3, 'gog', '1', None, 'One')])
    games = [_pn(GOG, '1', 'One', playtime=1), _pn(GOG, '9', 'Twin', playtime=2)]
    out, _per, missing = imports.match_playnite_games(games, db)
    assert list(out) == [-3] and missing == 1


def test_hand_added_games_match_custom_games_by_name():
    db = _library([(-9, 'custom', None, None, 'My Game'), (-8, 'gog', None, None, 'My Game')])
    out, per, _ = imports.match_playnite_games(
        [_pn('00000000-0000-0000-0000-000000000000', 'abc', 'My Game', playtime=3)], db)
    assert out == {-9: {'playtime': 3}} and per == {'custom': 1}


def test_a_game_in_playnite_twice_keeps_the_earliest_added_date():
    db = _library([(-1, 'gog', '1', None, 'One')])
    out, _per, _ = imports.match_playnite_games(
        [_pn(GOG, '1', 'One', date_added='2022-02-02'), _pn(GOG, '1', 'One', date_added='2020-02-02')], db)
    assert out[-1]['date_added'] == '2020-02-02'


def test_known_plugin_id_only_matches_its_own_platform():
    # An itch.io game id that happens to equal a GOG product id must not hit the GOG row.
    db = _library([(-1, 'gog', '1035957', None, 'Some GOG Game'), (-2, 'itch_io', '1035957', None, 'Helltaker')])
    out, per, _ = imports.match_playnite_games(
        [_pn('00000001-ebb2-4eec-abcb-7c89937a42bb', '1035957', 'Helltaker', playtime=4)], db)
    assert out == {-2: {'playtime': 4}} and per == {'itch_io': 1}


def test_epic_matches_by_app_name_and_ubisoft_space_id_falls_back_to_title():
    db = _library([
        (-1, 'epic_games', 'catalogitemid', 'Speedwell', 'Metro: Last Light Redux'),
        (-2, 'ubisoft', 'c2294cd6-bd01-4f19-81e9-4e5d32cb763a', None, 'For Honor'),
    ])
    out, per, _ = imports.match_playnite_games([
        _pn(EPIC, 'Speedwell', 'ignored name', playtime=1),
        _pn('c2f038e5-8b92-4877-91f1-da9094155fc5', '569', 'For Honor', playtime=2),
    ], db)
    assert out == {-1: {'playtime': 1}, -2: {'playtime': 2}}
    assert per == {'epic_games': 1, 'ubisoft': 1}
