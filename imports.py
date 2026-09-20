import bisect
import logging
import os
import re
import struct
import sqlite3
import tempfile
import threading
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
    data = _read_playnite_games_db(zip_path)
    if not data:
        return {}
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
            parsed = parse_playnite_fields(zip_path)
            log.info(f"Playnite import: parsed {len(parsed)} Steam games")
        except Exception:
            log.exception("Playnite import: parse failed")
            _playnite_import_state.update({'status': 'error', 'error': 'Failed to parse that backup. Check playdate.log for details.'})
            return
        if not parsed:
            log.warning("Playnite import: no Steam games found")
            _playnite_import_state.update({'status': 'error', 'error': 'No Steam games found in the backup.'})
            return
        # Only count games already in the library: that's all an import can touch.
        db = get_db()
        try:
            owned = {r['appid'] for r in db.execute("SELECT appid FROM games").fetchall()}
        finally:
            db.close()
        matched = {a: v for a, v in parsed.items() if a in owned}
        found = {f: sum(1 for v in matched.values() if f in v) for f in _PLAYNITE_FIELDS}
        _playnite_parsed.clear()
        _playnite_parsed.update(matched)
        _playnite_import_state.update({'status': 'ready', 'error': None, 'found': found})

    with _playnite_import_lock:
        if _playnite_import_state['status'] == 'running':
            return jsonify({"status": "error", "message": "An import is already in progress."}), 409
        _playnite_import_state.update({'status': 'running', 'error': None, 'found': None})
        threading.Thread(target=_run_playnite_scan, daemon=True).start()
    return jsonify({"status": "started"})


_PLAYNITE_FIELDS = ('date_added', 'last_played', 'playtime')
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
