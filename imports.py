import bisect
import logging
import os
import re
import struct
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from database import get_db, date_to_ts
from config import BASE_DIR
from utils import validate_user_path

log = logging.getLogger(__name__)

imports_bp = Blueprint('imports', __name__)

TEMP_DB_PATH = os.path.join(BASE_DIR, "temp_import.db")

# ── Playnite date import ──────────────────────────────────────────────────────
_playnite_import_lock  = threading.Lock()
# idle|running|ready|error. 'ready' = backup scanned, `found` holds per-field counts and
# `_playnite_parsed` the data, waiting for /api/import/playnite-apply to write the
# fields the user picks (so a multi-GB backup is only parsed once).
_playnite_import_state = {'status': 'idle', 'error': None, 'found': None}
_playnite_parsed = {}

# ── Step 1: Upload DB and return its tables + columns ──
def _inspect_temp_db():
    """Inspect TEMP_DB_PATH (already written) and return a Flask JSON response."""
    try:
        ext_conn = sqlite3.connect(TEMP_DB_PATH)
        ext_cur = ext_conn.cursor()

        tables = [row[0] for row in ext_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]

        if not tables:
            ext_conn.close()
            os.remove(TEMP_DB_PATH)
            return jsonify({"status": "error", "message": "No tables found in this database."})

        table_columns = {}
        table_column_types = {}
        for table in tables:
            pragma = ext_cur.execute(f"PRAGMA table_info({table})").fetchall()
            table_columns[table] = [row[1] for row in pragma]
            table_column_types[table] = {row[1]: row[2].upper() for row in pragma}

        ext_conn.close()

        local_db = get_db()
        local_pragma = local_db.execute("PRAGMA table_info(games)").fetchall()
        local_cols = [row[1] for row in local_pragma]
        local_col_types = {row[1]: row[2].upper() for row in local_pragma}
        local_db.close()

        return jsonify({
            "status": "success",
            "tables": tables,
            "table_columns": table_columns,
            "table_column_types": table_column_types,
            "local_columns": local_cols,
            "local_column_types": local_col_types
        })

    except Exception as e:
        if os.path.exists(TEMP_DB_PATH):
            os.remove(TEMP_DB_PATH)
        log.error("inspect DB failed: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": "Could not read that database. Check playdate.log for details."})


def inspect_database(request_files):
    if 'external_db' not in request_files:
        return jsonify({"status": "error", "message": "No file uploaded"})

    file = request_files['external_db']
    if os.path.exists(TEMP_DB_PATH):
        os.remove(TEMP_DB_PATH)
    file.save(TEMP_DB_PATH)
    return _inspect_temp_db()


def inspect_database_from_path(path):
    import shutil
    if not os.path.isfile(path):
        return jsonify({"status": "error", "message": "File not found."})
    if os.path.exists(TEMP_DB_PATH):
        os.remove(TEMP_DB_PATH)
    shutil.copy2(path, TEMP_DB_PATH)
    return _inspect_temp_db()


def _types_compatible(src_type, tgt_type):
    """
    Returns (compatible: bool, warning: str|None).
    SQLite is loosely typed, so we only warn on INT<->TEXT mismatches
    where data loss is likely, not block the import entirely.
    """
    # Normalize — SQLite types can be things like "INTEGER", "INT", "TEXT", "REAL"
    def bucket(t):
        t = t.upper()
        if any(x in t for x in ('INT', 'NUM', 'REAL', 'FLOAT')):
            return 'numeric'
        return 'text'

    sb, tb = bucket(src_type), bucket(tgt_type)
    if sb != tb:
        return False, f"Type mismatch: source is {src_type}, target is {tgt_type}. Values will be imported as-is — numeric columns may receive text data."
    return True, None


# ── Step 2: Execute the import with user-specified column mappings ──
def normalize_date(value):
    """Try to parse a date value into YYYY-MM-DD. Returns original if unparseable."""
    if not value:
        return value
    value = str(value).strip()

    # Already correct format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        return value

    # Unix timestamp (integer seconds)
    if re.match(r'^\d{9,11}$', value):
        try:
            return datetime.utcfromtimestamp(int(value)).strftime('%Y-%m-%d')
        except Exception:
            pass

    formats = [
        '%d %b %Y',     # 15 Jan 2020
        '%b %d, %Y',    # Jan 15, 2020
        '%B %d, %Y',    # January 15, 2020
        '%d/%m/%Y',     # 15/01/2020
        '%m/%d/%Y',     # 01/15/2020
        '%d-%m-%Y',     # 15-01-2020
        '%Y/%m/%d',     # 2020/01/15
        '%d.%m.%Y',     # 15.01.2020
        '%Y%m%d',       # 20200115
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return value  # return as-is if nothing matched


def execute_import(data):
    """
    data = {
        "table": "games",                          # source table name
        "appid_column": "appid",                   # source column to match on appid
        "mappings": [                              # list of {source, target} column pairs
            {"source": "date_added", "target": "date_added"},
            {"source": "status",     "target": "completion_status"}
        ],
        "normalize_dates": true                    # whether to try date normalization
    }
    """
    if not os.path.exists(TEMP_DB_PATH):
        return jsonify({"status": "error", "message": "No uploaded database found. Please upload again."})

    table = data.get("table")
    appid_col = data.get("appid_column", "appid")
    mappings = data.get("mappings", [])
    normalize_dates = data.get("normalize_dates", False)

    if not table or not mappings:
        return jsonify({"status": "error", "message": "Table and at least one column mapping are required."})

    try:
        ext_conn = sqlite3.connect(TEMP_DB_PATH)
        ext_conn.row_factory = sqlite3.Row
        ext_cur = ext_conn.cursor()

        # Validate table against actual tables in the uploaded DB; re-bind from
        # the validated set so static analysis sees a controlled value downstream.
        valid_tables = {row[0] for row in ext_cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        table = next((t for t in valid_tables if t == table), None)
        if not table:
            ext_conn.close()
            return jsonify({"status": "error", "message": "Table not found in uploaded database."}), 400

        # Build type maps for warning generation
        src_pragma = {row[1]: row[2].upper() for row in ext_cur.execute(f'PRAGMA table_info("{table}")').fetchall()}

        local_db_check = get_db()
        tgt_pragma = {row[1]: row[2].upper() for row in local_db_check.execute("PRAGMA table_info(games)").fetchall()}
        local_db_check.close()

        # Check type compatibility for all mappings and collect warnings
        type_warnings = []
        for mapping in mappings:
            src_col = mapping["source"]
            tgt_col = mapping["target"]
            src_type = src_pragma.get(src_col, 'TEXT')
            tgt_type = tgt_pragma.get(tgt_col, 'TEXT')
            compatible, warning = _types_compatible(src_type, tgt_type)
            if warning:
                type_warnings.append(f"{src_col} → {tgt_col}: {warning}")

        # Re-bind each column from the validated set so static analysis sees
        # controlled values downstream.
        valid_cols = {c: c for c in src_pragma.keys()}
        source_cols = [appid_col] + [m["source"] for m in mappings if m["source"] != appid_col]
        safe_cols = [valid_cols.get(c) for c in source_cols]
        if any(c is None for c in safe_cols):
            missing = [source_cols[i] for i, c in enumerate(safe_cols) if c is None]
            ext_conn.close()
            return jsonify({"status": "error", "message": f"Column(s) not found in table: {', '.join(missing)}"}), 400
        col_list = ", ".join(f'"{c}"' for c in safe_cols)
        rows = ext_cur.execute(f'SELECT {col_list} FROM "{table}"').fetchall()
        ext_conn.close()

        local_db = get_db()
        updated_count = 0
        skipped_count = 0

        for row in rows:
            row = dict(row)
            appid = row.get(appid_col)
            if not appid:
                skipped_count += 1
                continue

            update_kwargs = {}
            for mapping in mappings:
                src = mapping["source"]
                tgt = mapping["target"]
                val = row.get(src)
                if val is None or str(val).strip() == '':
                    continue
                if normalize_dates:
                    val = normalize_date(val)
                    # normalize_date() always returns a 'YYYY-MM-DD' string,
                    # which is right for TEXT-ish target columns (meta_fetched
                    # etc.) but silently corrupts an INTEGER-affinity one
                    # (date_added/last_played/release_date all store Unix
                    # timestamps) -- a column with a mix of INTEGER and TEXT
                    # values sorts by storage class first, not by real date.
                    # Same bug class as the GOG plugin's release_date fix.
                    if 'INT' in tgt_pragma.get(tgt, '').upper():
                        val = date_to_ts(val)
                        if val is None:
                            continue
                update_kwargs[tgt] = val

            if not update_kwargs:
                skipped_count += 1
                continue

            set_clause = ", ".join(f"{k} = ?" for k in update_kwargs)
            values = list(update_kwargs.values()) + [appid]
            cursor = local_db.execute(
                f"UPDATE games SET {set_clause} WHERE appid = ?", values
            )
            if cursor.rowcount > 0:
                updated_count += 1
            else:
                skipped_count += 1

        local_db.commit()
        local_db.close()

        # Clean up temp file
        os.remove(TEMP_DB_PATH)

        return jsonify({
            "status": "success",
            "updated": updated_count,
            "skipped": skipped_count,
            "type_warnings": type_warnings
        })

    except Exception as e:
        if os.path.exists(TEMP_DB_PATH):
            os.remove(TEMP_DB_PATH)
        log.error("generic DB import failed: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": "Import failed. Check playdate.log for details."})


_PLAYNITE_WINDOW = 8192
_PLAYNITE_FIELDS = ('date_added', 'last_played', 'playtime')


def _read_playnite_games_db(zip_path):
    """Bytes of library/games.db (Playnite's LiteDB file) from a backup ZIP, or None."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        games_db_entry = next(
            (n for n in names if n.replace('\\', '/').lower().endswith('library/games.db')),
            None
        )
        if not games_db_entry:
            return None
        with tempfile.NamedTemporaryFile(delete=False, suffix='.litedb') as tmp:
            tmp_path = tmp.name
            tmp.write(zf.read(games_db_entry))

    try:
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


def _playnite_gameids(data):
    """[(byte_position, steam_appid_int)] for every numeric GameId field.
    BSON string: type=0x02, key="GameId\\x00", then int32 length + bytes + null."""
    gameids = []
    for m in re.finditer(b'\x02GameId\x00', data):
        pos = m.end()
        if pos + 4 > len(data):
            continue
        slen = struct.unpack_from('<i', data, pos)[0]
        if slen < 1 or slen > 20:
            continue
        val = data[pos + 4:pos + 4 + slen - 1].decode('utf-8', errors='replace')
        if val.isdigit():
            gameids.append((m.start(), int(val)))
    return gameids


def parse_playnite_fields(zip_path):
    data = _read_playnite_games_db(zip_path)
    return _parse_playnite_fields_scan(data) if data else {}


def _parse_playnite_fields_scan(data):
    """
    Extracts Last Played and Time Played (plus Date Added) for Steam games from a
    Playnite backup ZIP. Returns
    {appid: {'date_added': 'YYYY-MM-DD', 'last_played': unix_seconds, 'playtime': minutes}}
    with only the keys a game actually has.

    Unlike Added (present on every game), LastActivity/Playtime can be absent from
    a document, so pairing each GameId to its nearest field could hand a game its
    neighbour's value. Fields are therefore paired the other way round: each field
    occurrence goes to its *nearest GameId* (within the window), and a game keeps
    the closest occurrence assigned to it -- a game without the field gets nothing.

    NOTE: LastActivity (datetime, 0x09) and Playtime (int64 seconds, 0x12, int32
    0x10 also accepted) are inferred from Playnite's data model, not yet checked
    against a real backup (see tests/test_parse_playnite_dates.py).
    """
    gameids = _playnite_gameids(data)
    if not gameids:
        return {}
    gameids.sort()
    gpositions = [g[0] for g in gameids]

    def _collect(pattern, fmt, size, convert):
        out = {}   # appid -> (distance, value)
        for m in re.finditer(pattern, data):
            pos = m.end()
            if pos + size > len(data):
                continue
            value = convert(struct.unpack_from(fmt, data, pos)[0])
            if value is None:
                continue
            idx = bisect.bisect_left(gpositions, m.start())
            best = None
            for i in (idx - 1, idx):
                if 0 <= i < len(gpositions):
                    dist = abs(gpositions[i] - m.start())
                    if dist <= _PLAYNITE_WINDOW and (best is None or dist < best[0]):
                        best = (dist, gameids[i][1])
            if best and (best[1] not in out or best[0] < out[best[1]][0]):
                out[best[1]] = (best[0], value)
        return {appid: v for appid, (_d, v) in out.items()}

    def _ms_to_seconds(ms):
        return ms // 1000 if 0 < ms < 4102444800000 else None

    def _seconds_to_minutes(sec):
        return sec // 60 if sec > 0 else None

    results = {}
    for field, pattern, fmt, size, convert in (
        ('date_added',  b'\x09Added\x00',        '<q', 8, _ms_to_seconds),
        ('last_played', b'\x09LastActivity\x00', '<q', 8, _ms_to_seconds),
        ('playtime',    b'\x12Playtime\x00',     '<q', 8, _seconds_to_minutes),
        ('playtime',    b'\x10Playtime\x00',     '<i', 4, _seconds_to_minutes),
    ):
        for appid, value in _collect(pattern, fmt, size, convert).items():
            if field == 'date_added':
                value = datetime.fromtimestamp(value, tz=timezone.utc).strftime('%Y-%m-%d')
            results.setdefault(appid, {}).setdefault(field, value)
    return results


STEAM_PLUGIN_ID = 'cb91dfc9-b977-43bf-8e70-55f46e410fab'
_NO_PLUGIN = '00000000-0000-0000-0000-000000000000'
# Playnite's own library plugins (ids from their source, Guid.Parse in each *Library.cs) ->
# PlayDate platform. What each stores as GameId, checked against public libraries or the
# plugin source: Steam appid; GOG product id (= platform_id); Epic appName (= platform_appname);
# Amazon product id; Xbox package family name (= platform_appname); itch.io game id;
# Humble machine name; Battle.net product code; Rockstar titleId; Ubisoft uplay id (the
# numeric launch id; PlayDate keeps the spaceId GUID when there is one, so those games fall
# to the title match); EA offerId (Origin.OFR.50.xxxx, equal to PlayDate's platform_id only
# when both sides saw the same offer).
KNOWN_PLAYNITE_PLUGINS = {
    STEAM_PLUGIN_ID: 'steam',
    'aebe8b7c-6dc3-4a66-af31-e7375c6b5e9e': 'gog',
    '00000002-dbd1-46c6-b5d0-b1ba559d10e4': 'epic_games',
    '402674cd-4af6-4886-b6ec-0e695bfa0688': 'amazon_games',
    '7e4fbb5e-2ae3-48d4-8ba0-6b30e7a4e287': 'xbox',
    'c2f038e5-8b92-4877-91f1-da9094155fc5': 'ubisoft',
    '85dd7072-2f20-4e76-a007-41035e390724': 'ea_app',
    '00000001-ebb2-4eec-abcb-7c89937a42bb': 'itch_io',
    '96e8c4bc-ec5c-4c8b-87e7-18ee5a690626': 'humble',
    'e3c26a3d-d695-4cb7-a769-5ff7612c7edd': 'battle_net',
    '88409022-088a-4de8-805a-fdbac291f00a': 'rockstar',
}


def _playnite_strings(data, key, max_len=300):
    """[(byte_position, value)] for every BSON string field `key`."""
    out = []
    for m in re.finditer(b'\x02' + re.escape(key) + b'\x00', data):
        pos = m.end()
        if pos + 4 > len(data):
            continue
        slen = struct.unpack_from('<i', data, pos)[0]
        if 1 <= slen <= max_len:
            out.append((m.start(), data[pos + 4:pos + 4 + slen - 1].decode('utf-8', errors='replace')))
    return out


_LITEDB4_PAGE = 4096
_LITEDB4_HEADER = 25
_NO_PAGE = 0xFFFFFFFF


def _litedb4_documents(data):
    """Whole BSON documents of every collection in a LiteDB v4 file (the format Playnite
    writes: file version 7, 4096-byte pages), [] for any other format.

    Page: pageId u32, type u8 (4 = data, 5 = extend), prev u32, next u32, itemCount u16,
    freeBytes u16, 8 reserved = 25 bytes. A data page holds itemCount blocks of
    [index u16, extendPageId u32, size u16, bytes]; a document too big for a page keeps its
    bytes in a chain of extend pages instead (each: itemCount bytes of content, linked by
    nextPageId) and its block's own bytes are empty."""
    if len(data) < _LITEDB4_PAGE * 2 or data[25:52] != b'** This is a LiteDB file **' or data[52] != 7:
        return []
    page, hdr = _LITEDB4_PAGE, _LITEDB4_HEADER
    npages = len(data) // page
    extends = {}
    for pid in range(npages):
        base = pid * page
        if data[base + 4] == 5:
            nxt, count = struct.unpack_from('<IH', data, base + 9)
            if count <= page - hdr:
                extends[pid] = (nxt, data[base + hdr:base + hdr + count])
    docs = []
    for pid in range(npages):
        base = pid * page
        if data[base + 4] != 4:
            continue
        count = struct.unpack_from('<H', data, base + 13)[0]
        off = base + hdr
        for _ in range(count):
            if off + 8 > base + page:
                break
            _idx, ext, size = struct.unpack_from('<HIH', data, off)
            off += 8
            if ext != _NO_PAGE:
                parts, seen = [], set()
                while ext in extends and ext not in seen:
                    seen.add(ext)
                    nxt, chunk = extends[ext]
                    parts.append(chunk)
                    ext = nxt
                docs.append(b''.join(parts))
            else:
                docs.append(data[off:off + size])
            off += size
    return docs


def _bson_fields(doc, want):
    """{key: value} for the top-level fields of one BSON document named in `want`:
    strings, bools, ints, datetimes (ms since epoch), binary (bytes). Other types are
    skipped; a malformed document yields whatever was read before the problem."""
    out = {}
    if len(doc) < 5:
        return out
    end = min(struct.unpack_from('<i', doc, 0)[0], len(doc))
    pos = 4
    sizes = {0x01: 8, 0x07: 12, 0x08: 1, 0x09: 8, 0x0A: 0, 0x10: 4, 0x12: 8, 0x13: 16, 0xFF: 0, 0x7F: 0}
    while pos < end - 1:
        t = doc[pos]
        k_end = doc.find(b'\x00', pos + 1)
        if k_end < 0:
            break
        key = doc[pos + 1:k_end].decode('utf-8', errors='replace')
        pos = k_end + 1
        if t == 0x02:
            n = struct.unpack_from('<i', doc, pos)[0]
            if n < 1 or pos + 4 + n > len(doc):
                break
            if key in want:
                out[key] = doc[pos + 4:pos + 3 + n].decode('utf-8', errors='replace')
            pos += 4 + n
        elif t in (0x03, 0x04):
            n = struct.unpack_from('<i', doc, pos)[0]
            if n < 5:
                break
            pos += n
        elif t == 0x05:
            n = struct.unpack_from('<i', doc, pos)[0]
            if n < 0 or pos + 5 + n > len(doc):
                break
            if key in want:
                out[key] = doc[pos + 5:pos + 5 + n]
            pos += 5 + n
        elif t in sizes:
            if key in want:
                if t == 0x08:
                    out[key] = bool(doc[pos])
                elif t in (0x09, 0x12):
                    out[key] = struct.unpack_from('<q', doc, pos)[0]
                elif t == 0x10:
                    out[key] = struct.unpack_from('<i', doc, pos)[0]
            pos += sizes[t]
        else:
            break
    return out


def _ms_to_seconds(ms):
    return ms // 1000 if isinstance(ms, int) and 0 < ms < 4102444800000 else None


def _playnite_game_from_doc(f):
    game = {'plugin': None, 'game_id': f['GameId'], 'name': f.get('Name')}
    pid = f.get('PluginId')
    if isinstance(pid, bytes) and len(pid) == 16:
        game['plugin'] = str(uuid.UUID(bytes_le=pid))
    added = _ms_to_seconds(f.get('Added'))
    if added:
        game['date_added'] = datetime.fromtimestamp(added, tz=timezone.utc).strftime('%Y-%m-%d')
    last = _ms_to_seconds(f.get('LastActivity'))
    if last:
        game['last_played'] = last
    play = f.get('Playtime')
    if isinstance(play, int) and play >= 60:
        game['playtime'] = play // 60
    return game


def parse_playnite_games(zip_path):
    """
    Every game in a Playnite backup, from any library plugin, as a list of
    {'plugin': 'cb91dfc9-...' | None, 'game_id': str, 'name': str | None,
     'date_added': 'YYYY-MM-DD', 'last_played': unix_seconds, 'playtime': minutes}
    with only the date keys a game actually has.

    `plugin` is the library plugin's PluginId; `game_id` is that plugin's own ID for the
    game (Steam appid, GOG product id, 'amzn1.adg.product...', an Xbox package name...).
    Read from real documents (a LiteDB v4 reader), so one game's fields can't be paired
    with another's. A file in some other format falls back to scanning for byte patterns
    near each GameId: Steam-style GameId plus nearest dates, no names.
    """
    data = _read_playnite_games_db(zip_path)
    if not data:
        return []
    games = []
    for doc in _litedb4_documents(data):
        f = _bson_fields(doc, ('GameId', 'Name', 'PluginId', 'Added', 'LastActivity', 'Playtime'))
        if isinstance(f.get('GameId'), str):
            games.append(_playnite_game_from_doc(f))
    if games:
        return games
    # Fallback: not a v4 file. Only Steam appids can be recognised without a plugin id.
    return [{'plugin': None, 'game_id': str(appid), **vals}
            for appid, vals in _parse_playnite_fields_scan(data).items()]


def match_playnite_games(games, db):
    """
    Resolve parsed Playnite games to PlayDate appids.
    Returns ({appid: {'date_added':..., ...}}, {platform_label: matched_count}, unmatched_count).

    Steam: PluginId is Steam's and GameId is the appid. Every other plugin: GameId is
    compared with the platform_id / platform_appname of non-Steam games (GOG product id,
    Epic appName, Amazon product id, Xbox package name, ...), confined to the plugin's own
    PlayDate platform when it is one of Playnite's built-in libraries
    (KNOWN_PLAYNITE_PLUGINS). A community plugin's platform is learned from its id matches.
    Either way the platform then confines the name fallback (exact normalised name), so a
    same-named game on another store is not touched.
    A name that fits several games in the platform is skipped rather than guessed.
    """
    from database import _normalize_name_for_dup as norm
    rows = db.execute(
        "SELECT appid, platform, platform_id, platform_appname, name FROM games WHERE platform != 'steam'"
    ).fetchall()
    steam_owned = {r['appid'] for r in db.execute("SELECT appid FROM games WHERE platform = 'steam'").fetchall()}
    by_id = {}      # lowercased id -> [(platform, appid)]
    by_name = {}    # (platform, normalised name) -> [appid]
    for r in rows:
        for key in (r['platform_id'], r['platform_appname']):
            if key not in (None, ''):
                by_id.setdefault(str(key).strip().lower(), []).append((r['platform'], r['appid']))
        by_name.setdefault((r['platform'], norm(r['name'] or '')), []).append(r['appid'])

    have_plugins = any(g['plugin'] for g in games)
    resolved = {}   # index -> (platform, appid)
    votes = {}      # plugin not in the table above -> {platform: n}
    for i, g in enumerate(games):
        plugin = g['plugin']
        if plugin == STEAM_PLUGIN_ID or (not have_plugins and g['game_id'].isdigit()):
            if g['game_id'].isdigit() and int(g['game_id']) in steam_owned:
                resolved[i] = ('steam', int(g['game_id']))
            continue
        if plugin in (None, _NO_PLUGIN):
            continue
        hits = by_id.get(g['game_id'].strip().lower(), [])
        if plugin in KNOWN_PLAYNITE_PLUGINS:
            hits = [h for h in hits if h[0] == KNOWN_PLAYNITE_PLUGINS[plugin]]
        if len(hits) == 1:
            resolved[i] = hits[0]
            if plugin not in KNOWN_PLAYNITE_PLUGINS:
                votes.setdefault(plugin, {}).setdefault(hits[0][0], 0)
                votes[plugin][hits[0][0]] += 1
    plugin_platform = dict(KNOWN_PLAYNITE_PLUGINS)
    plugin_platform.update({p: max(v, key=v.get) for p, v in votes.items()})

    for i, g in enumerate(games):
        if i in resolved or g['plugin'] == STEAM_PLUGIN_ID:
            continue
        plugin = g['plugin']
        # A plugin with no ID matches at all is not tied to a platform: names may match
        # any non-Steam platform, but only when exactly one game does.
        platforms = ([plugin_platform[plugin]] if plugin in plugin_platform
                     else [None] if plugin not in (None, _NO_PLUGIN) else ['custom'])
        for name in ([g['name']] if g.get('name') else []):
            n = norm(name)
            if not n:
                continue
            cands = [(plat, a) for (plat, nn), apps in by_name.items() if nn == n
                     for a in apps if platforms == [None] or plat in platforms]
            if len(cands) == 1:
                resolved[i] = cands[0]
                break

    out, per_platform = {}, {}
    for i, (plat, appid) in resolved.items():
        vals = {f: games[i][f] for f in _PLAYNITE_FIELDS if f in games[i]}
        if not vals:
            continue
        cur = out.setdefault(appid, {})
        for f, v in vals.items():
            # A game with copies in Playnite: earliest date added, otherwise first seen wins.
            if f == 'date_added' and f in cur:
                cur[f] = min(cur[f], v)
            else:
                cur.setdefault(f, v)
        per_platform[plat] = per_platform.get(plat, 0) + 1
    return out, per_platform, len(games) - len(resolved)


def parse_playnite_dates(zip_path):
    """
    Extracts 'date added' values for Steam games from a Playnite backup ZIP.
    Playnite stores its library in a LiteDB binary file (library/games.db inside the ZIP).
    Uses proximity matching between GameId and Added BSON fields (±8KB window) to pair them.
    Returns {appid_int: 'YYYY-MM-DD'} dict.
    """
    data = _read_playnite_games_db(zip_path)
    if not data:
        return {}
    gameids = _playnite_gameids(data)

    # Extract all Added datetime field positions and values.
    # BSON datetime: type=0x09, key="Added\x00", then int64 ms since Unix epoch.
    added_map = {}
    for m in re.finditer(b'\x09Added\x00', data):
        pos = m.end()
        if pos + 8 > len(data):
            continue
        ms = struct.unpack_from('<q', data, pos)[0]
        if 0 < ms < 4102444800000:  # sanity: between 1970 and 2100
            dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
            added_map[m.start()] = dt

    added_positions = sorted(added_map.keys())

    # Pair each GameId with its nearest Added field within ±8KB.
    # Documents span LiteDB 8KB pages, so large documents (with long descriptions) have their
    # fields split across non-contiguous file regions. However, GameId and Added are both short
    # metadata fields that typically land in the same page segment, keeping them within 8KB.
    WINDOW = 8192
    results = {}
    for gpos, appid in gameids:
        idx = bisect.bisect_left(added_positions, gpos)
        best_pos = None
        best_dist = WINDOW + 1
        for i in (idx - 1, idx):
            if 0 <= i < len(added_positions):
                apos = added_positions[i]
                dist = abs(apos - gpos)
                if dist < best_dist:
                    best_dist = dist
                    best_pos = apos
        if best_pos is not None:
            results[appid] = added_map[best_pos]

    return results


# ── Routes ───────────────────────────────────────────────────────────────────

@imports_bp.route('/api/import-inspect', methods=['POST'])
def import_inspect():
    return inspect_database(request.files)

@imports_bp.route('/api/import-inspect-path', methods=['POST'])
def import_inspect_path():
    path = validate_user_path((request.json or {}).get('path', '').strip())
    return inspect_database_from_path(path)

@imports_bp.route('/api/import-execute', methods=['POST'])
def import_execute():
    return execute_import(request.json)

@imports_bp.route('/api/import/playnite-dates', methods=['POST'])
def import_playnite_dates():
    # Playnite backups can be several GB (see imports.py) — parsing runs in
    # a background thread and is polled via /api/import/playnite-dates-status
    # rather than blocking the request. Same fix as /api/restore-from-path:
    # a long synchronous request over a Flatpak portal-mounted path can
    # outlast the client's HTTP connection and surface as "Load failed"
    # even though nothing actually errored.
    data = request.json or {}
    zip_path = validate_user_path(data.get('path', '').strip())
    log.info(f"Playnite import: request received, path={zip_path!r}")
    if not zip_path or not os.path.isfile(zip_path):
        log.warning(f"Playnite import: file not found at {zip_path!r}")
        return jsonify({"status": "error", "message": "File not found."}), 400

    def _run_playnite_scan():
        try:
            games = parse_playnite_games(zip_path)
            log.info(f"Playnite import: parsed {len(games)} games")
        except Exception:
            log.exception("Playnite import: parse failed")
            _playnite_import_state.update({'status': 'error', 'error': 'Failed to parse that backup. Check playdate.log for details.'})
            return
        if not games:
            log.warning("Playnite import: no games found")
            _playnite_import_state.update({'status': 'error', 'error': 'No games found in the backup.'})
            return
        # Only games already in the library can be updated.
        db = get_db()
        try:
            matched, per_platform, unmatched = match_playnite_games(games, db)
        finally:
            db.close()
        log.info(f"Playnite import: matched {per_platform}, {unmatched} not in library")
        found = {f: sum(1 for v in matched.values() if f in v) for f in _PLAYNITE_FIELDS}
        _playnite_parsed.clear()
        _playnite_parsed.update(matched)
        _playnite_import_state.update({'status': 'ready', 'error': None, 'found': found,
                                       'platforms': per_platform, 'unmatched': unmatched})

    with _playnite_import_lock:
        if _playnite_import_state['status'] == 'running':
            return jsonify({"status": "error", "message": "An import is already in progress."}), 409
        _playnite_import_state.update({'status': 'running', 'error': None, 'found': None, 'platforms': None, 'unmatched': None})
        threading.Thread(target=_run_playnite_scan, daemon=True).start()
    return jsonify({"status": "started"})


_PLAYNITE_COLUMNS = {'date_added': 'date_added', 'last_played': 'last_played', 'playtime': 'playtime_forever'}


@imports_bp.route('/api/import/playnite-apply', methods=['POST'])
def playnite_apply():
    """Writes the chosen fields from the last scanned backup.
    mode 'fill': only where PlayDate has no value (Date Added: keep the earlier of the two).
    mode 'overwrite': replace PlayDate's value."""
    data = request.json or {}
    fields = [f for f in data.get('fields', []) if f in _PLAYNITE_FIELDS]
    mode = data.get('mode') if data.get('mode') in ('fill', 'overwrite') else 'fill'
    if not fields:
        return jsonify({"status": "error", "message": "Choose at least one field to import."}), 400
    with _playnite_import_lock:
        if _playnite_import_state['status'] != 'ready' or not _playnite_parsed:
            return jsonify({"status": "error", "message": "Scan a Playnite backup first."}), 409
        parsed = dict(_playnite_parsed)

    db = get_db()
    updated = {f: 0 for f in fields}
    try:
        for appid, vals in parsed.items():
            for f in fields:
                if f not in vals:
                    continue
                col = _PLAYNITE_COLUMNS[f]
                new = date_to_ts(vals[f]) if f == 'date_added' else vals[f]
                if new is None:
                    continue
                if mode == 'overwrite':
                    cond, params = "", ()
                elif f == 'date_added':
                    cond, params = " AND (date_added IS NULL OR date_added = 0 OR date_added > ?)", (new,)
                else:
                    cond, params = f" AND ({col} IS NULL OR {col} = 0)", ()
                # col comes from the fixed _PLAYNITE_COLUMNS map, never from the request.
                cur = db.execute(f"UPDATE games SET {col} = ? WHERE appid = ?{cond}", (new, appid) + params)
                updated[f] += cur.rowcount
        db.commit()
    finally:
        db.close()
    log.info(f"Playnite import: applied {fields} (mode={mode}): {updated}")
    return jsonify({"status": "success", "updated": updated})

@imports_bp.route('/api/import/playnite-dates-status')
def playnite_import_status():
    return jsonify(_playnite_import_state)
