import logging
import math
import re
import sqlite3
from datetime import datetime, timezone


log = logging.getLogger(__name__)


def date_to_ts(date_str):
    """'YYYY-MM-DD' string → Unix timestamp int, or None."""
    if not date_str:
        return None
    try:
        return int(datetime.strptime(str(date_str)[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
    except (ValueError, TypeError):
        return None


def ts_to_date(ts):
    """Unix timestamp int → 'YYYY-MM-DD' string, or None.
    If already a 'YYYY-MM-DD' string, returns it as-is (handles GOG date strings)."""
    if not ts:
        return None
    if isinstance(ts, str) and len(ts) >= 10 and ts[4:5] == '-':
        return ts[:10]
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime('%Y-%m-%d')
    except (ValueError, OSError, TypeError):
        return None


def _db():
    """Returns the active account's database file path."""
    from config import get_active_db_path
    return get_active_db_path()


def _open_conn(db_file, timeout=30):
    conn = sqlite3.connect(db_file, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_db():
    db_file = _db()
    conn = _open_conn(db_file)
    # Auto-init if the games table is missing (e.g. DB was deleted while running)
    try:
        conn.execute("SELECT 1 FROM games LIMIT 1")
    except sqlite3.OperationalError:
        conn.close()
        init_db()
        conn = _open_conn(db_file)
    return conn


# Cache of appid (int) -> duplicate_of appid string, used to redirect art requests
# for a duplicate game to its canonical version's cached image. Avoids a DB
# round-trip on every image request for games without local art files.
_dup_cache: dict = {}
_dup_cache_loaded = False


def get_dup_cache():
    global _dup_cache_loaded
    if not _dup_cache_loaded:
        try:
            db = get_db()
            rows = db.execute("SELECT appid, duplicate_of FROM games WHERE duplicate_of IS NOT NULL AND duplicate_of != ''").fetchall()
            db.close()
            _dup_cache.update({row['appid']: row['duplicate_of'] for row in rows})
        except Exception:
            pass
        _dup_cache_loaded = True
    return _dup_cache


def invalidate_dup_cache():
    global _dup_cache_loaded
    _dup_cache.clear()
    _dup_cache_loaded = False

def init_db():
    """Initializes the database and ensures all columns exist."""
    db_file = _db()
    conn = sqlite3.connect(db_file, timeout=10)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            appid INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(games)")
    columns = [column[1] for column in cursor.fetchall()]

    required_columns = {
        'playtime_forever': 'INT',       # Total playtime in minutes
        'installed': 'INT',              # 1 for yes, 0 for no
        'last_played': 'INTEGER',        # Last played — Unix timestamp
        'date_added': 'INTEGER',         # Date added — Unix timestamp
        'developers': 'TEXT',            # Developer metadata
        'publishers': 'TEXT',            # Publisher metadata
        'completion_status': 'TEXT',     # e.g., "Not Played", "Completed"
        'tags': 'TEXT',                  # Genres/Tags
        'release_date': 'INTEGER',       # Game release date — Unix timestamp
        'unlocked_achievements': 'INT',  # Achievements earned
        'total_achievements': 'INT',     # Total achievements available
        'review_score': 'TEXT',          # e.g., 'Very Positive'
        'review_percentage': 'INT',      # 0-100 score
        'metacritic_score': 'INT',       # Metacritic score from the Steam store page (NULL = none)
        'short_description': 'TEXT',     # Plain-text store blurb (Steam or plugin); NULL = not fetched yet
        'vertical_art_source': 'TEXT',   # Source of vertical capsule art
        'horizontal_art_source': 'TEXT', # Source of horizontal header art
        'icon_source': 'TEXT',           # Source of game icon
        'icon_hash': 'TEXT',             # Steam icon hash for re-downloading
        'weighted_percentage': 'INT',    # Scaling penalties for total_reviews under 100
        'total_reviews': 'INT',
        'positive_reviews': 'INT',
        'groups': 'TEXT',
        'genres': 'TEXT',                # Comma-separated Steam genres (e.g. Action,RPG)
        'categories': 'TEXT',            # Comma-separated Steam categories (e.g. Single-player,Co-op)
        'is_free': 'INT',                # 1 if free to play, 0 otherwise
        'art_fetched': 'TEXT',           # '0' = never fetched, YYYY-MM-DD = date last fetched
        'meta_fetched': 'TEXT',          # '0' = never fetched, YYYY-MM-DD = date last fetched
        'cheevos_fetched': 'TEXT',       # '0' = never fetched, YYYY-MM-DD = date last fetched
        'protondb_tier': 'TEXT',         # platinum/gold/silver/bronze/borked or NULL
        'protondb_confidence': 'TEXT',   # strong/good/weak or NULL
        'protondb_fetched': 'TEXT',      # '0' = never fetched, YYYY-MM-DD = date last fetched
        'hltb_main': 'INT',              # Main story time in minutes
        'hltb_extras': 'INT',            # Main + extras time in minutes
        'hltb_completionist': 'INT',     # Completionist time in minutes
        'hltb_id': 'INT',               # HLTB game ID (for direct URL)
        'hltb_matched_name': 'TEXT',     # HLTB game name as returned by search
        'hltb_match_score': 'INT',       # 0-100 name similarity score
        'hltb_fetched': 'TEXT',          # '0' = pending, YYYY-MM-DD = confirmed, 'unconfirmed' = below threshold
        'platform': 'TEXT',              # 'steam' (default), 'gog', 'egs', 'ea_app', 'ubisoft'
        'platform_id': 'TEXT',           # Service-native ID used for launching (GOG ID, EGS appName, etc.)
        'platform_slug': 'TEXT',         # Platform store slug for building store URLs (e.g. GOG slug 'the_witcher_3_wild_hunt')
        'platform_ns': 'TEXT',           # Platform-specific namespace (e.g. Epic catalog namespace)
        'platform_appname': 'TEXT',      # Platform-internal app/launch name distinct from store slug (e.g. Epic appName)
        'steam_appid': 'INTEGER',        # Steam AppID resolved via PCGW/Steam-search for non-Steam games (NULL = not yet looked up); see metadata.py
        'meta_backfill_fetched': 'TEXT', # metadata backfill outcome (any platform): '0'/NULL = never, YYYY-MM-DD = done, 'no_match', 'unconfirmed'. Gates only the auto startup sweep; explicit backfills re-attempt on missing fields alone. Renaming a game resets this to '0'.
        'install_path': 'TEXT',          # Local install directory (non-Steam games)
        'wine_prefix': 'TEXT',           # Path to Wine/Proton prefix (Windows games)
        'runner_path': 'TEXT',           # Path to Proton binary used for this game
        'platform_executable': 'TEXT',   # Relative path to main exe within install_path
        'duplicate_of': 'TEXT',          # appid of preferred version of this game (e.g. Steam appid for a GOG duplicate); NULL = canonical
        'duplicate_auto': 'INT',         # 1 = set by auto-detection; 0/NULL = manually set
        'name_from_store': 'INT',        # 1 = name confirmed from Steam store API; 0/NULL = from GetOwnedGames or local files
        'tag_similarity': 'REAL',        # Cosine similarity to the Beaten/Completed taste profile; see recalculate_tag_similarity()
        'sg_dlc_win': 'INT',             # 1 = this game's "Won on SteamGifts" membership traces only to an adopted DLC win, no direct win of the base game itself; see steamgifts.py's apply_wins()/sg_adopt_dlc_base(). Surfaces a "mention the DLC" note in the PAGYWOSG quals tooltip/panel -- PAGYWOSG (its own independent site/community, not a SteamGifts-official feature) requires disclosing this when submitting the game there.
    }

    for column_name, column_type in required_columns.items():
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE games ADD COLUMN {column_name} {column_type}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_installed         ON games(installed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_completion_status ON games(completion_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_last_played       ON games(last_played)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_playtime_forever  ON games(playtime_forever)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_platform          ON games(platform)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_name              ON games(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_duplicate_of      ON games(duplicate_of)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_release_date      ON games(release_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_hltb_fetched      ON games(hltb_fetched)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_meta_fetched      ON games(meta_fetched)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_art_fetched       ON games(art_fetched)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_cheevos_fetched   ON games(cheevos_fetched)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            date_blacklisted TEXT,
            platform_id TEXT,
            platform TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE blacklist ADD COLUMN platform_id TEXT")
    except Exception:
        pass  # column already exists

    try:
        cursor.execute("ALTER TABLE blacklist ADD COLUMN platform TEXT")
    except Exception:
        pass  # column already exists

    conn.commit()
    conn.close()

def add_new_game(appid, name):
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO games (appid, name) VALUES (?, ?)", (int(appid), name))
        conn.commit()
    finally:
        conn.close()

def batch_insert_placeholder_games(games, today):
    """
    Batch-inserts placeholder rows for a list of new games in a single transaction.
    Each game dict must have: appid, name, playtime_forever, last_played, completion_status,
    installed, icon_hash. Phase columns are initialised to '0'.
    Games already in the DB are skipped (INSERT OR IGNORE).
    """
    if not games:
        return
    cols = [
        'appid', 'name', 'playtime_forever', 'last_played', 'date_added',
        'completion_status', 'installed', 'icon_hash', 'platform',
        'art_fetched', 'meta_fetched', 'cheevos_fetched', 'protondb_fetched', 'hltb_fetched',
    ]
    placeholders = ', '.join('?' * len(cols))
    col_str = ', '.join(cols)
    rows = [
        (
            str(g['appid']), g['name'], g['playtime_forever'], g['last_played'],
            today, g['completion_status'], g['installed'], g.get('icon_hash', ''),
            'steam', '0', '0', '0', '0', '0',
        )
        for g in games
    ]
    conn = get_db()
    try:
        conn.executemany(f"INSERT OR IGNORE INTO games ({col_str}) VALUES ({placeholders})", rows)
        conn.commit()
    finally:
        conn.close()

def update_game_data(appid, **kwargs):
    """
    Updates specific columns for a game in the database.
    Example: update_game_data('123', completion_status='played', rating=5)
    """
    if not kwargs:
        return

    conn = sqlite3.connect(_db(), timeout=10)
    cursor = conn.cursor()

    columns = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values())
    values.append(appid)

    query = f"UPDATE games SET {columns} WHERE appid = ?"

    try:
        cursor.execute(query, values)
        conn.commit()
    except sqlite3.Error as e:
        log.error(f"Database update failed: {e}")
    finally:
        conn.close()

def bulk_update_column(appids, column, value):
    """
    Updates a single column to a specific value for a list of appids.
    Example: bulk_update_column([10, 20, 30], 'installed', 1)
    """
    if not appids:
        return

    conn = sqlite3.connect(_db(), timeout=10)
    cursor = conn.cursor()

    placeholders = ", ".join(["?"] * len(appids))
    query = f"UPDATE games SET {column} = ? WHERE appid IN ({placeholders})"
    params = [value] + list(appids)

    try:
        cursor.execute(query, params)
        conn.commit()
    except sqlite3.Error as e:
        log.error(f"Bulk update failed: {e}")
    finally:
        conn.close()

# ── Blacklist helpers ──────────────────────────────────────────────────────────

def get_blacklist():
    """Return all blacklisted entries sorted by date_blacklisted DESC.
    `platform` is NULL for entries blacklisted before that column existed;
    callers group those under a fallback bucket (steam if platform_id is
    NULL, since only non-Steam blacklisting ever set platform_id -- else
    unknown)."""
    conn = sqlite3.connect(_db(), timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT appid, name, date_blacklisted, platform_id, platform FROM blacklist ORDER BY date_blacklisted DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_to_blacklist(appid, name, platform_id=None, platform=None):
    """Add an appid to the blacklist. Safe to call if already present.
    Pass platform_id for non-Steam games so re-sync skips them, and platform
    so the Blacklist Manager can group entries by platform."""
    conn = sqlite3.connect(_db(), timeout=10)
    conn.execute(
        "INSERT OR REPLACE INTO blacklist (appid, name, date_blacklisted, platform_id, platform) VALUES (?, ?, ?, ?, ?)",
        (int(appid), name, datetime.now().strftime('%Y-%m-%d'), platform_id, platform)
    )
    conn.commit()
    conn.close()

def remove_from_blacklist(appid):
    """Remove an appid from the blacklist."""
    conn = sqlite3.connect(_db(), timeout=10)
    conn.execute("DELETE FROM blacklist WHERE appid = ?", (int(appid),))
    conn.commit()
    conn.close()

def get_blacklisted_appids():
    """Return a set of blacklisted appids for fast membership testing."""
    conn = sqlite3.connect(_db(), timeout=10)
    rows = conn.execute("SELECT appid FROM blacklist").fetchall()
    conn.close()
    return {row[0] for row in rows}


import logging as _logging
_log = _logging.getLogger(__name__)

PLATFORM_PRIORITY_DEFAULT = ['steam', 'gog', 'epic_games', 'ea_app', 'ubisoft', 'itch_io']


def next_negative_appid(db):
    """Return the next available negative appid for a non-Steam game."""
    row = db.execute('SELECT MIN(appid) FROM games WHERE appid < 0').fetchone()
    return (row[0] - 1) if (row[0] is not None) else -1


def _normalize_name_for_dup(name):
    name = name.lower()
    name = re.sub(
        r'\s*[-–:]\s*(goty|game of the year|complete edition|deluxe edition|gold edition|'
        r'definitive edition|remastered|remaster|enhanced edition|anniversary edition|'
        r'director\'?s cut|ultimate edition|premium edition)\s*$',
        '', name, flags=re.IGNORECASE
    )
    name = re.sub(r"[^\w\s']", ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def auto_detect_duplicates(platform_priority=None):
    """Match games across platforms by normalized name and set duplicate_of.
    Lower-priority platform versions are marked as duplicates of higher-priority ones.
    Clears previously auto-detected duplicates before re-running.
    Returns count of newly marked duplicates.
    """
    if platform_priority is None:
        platform_priority = PLATFORM_PRIORITY_DEFAULT

    conn = get_db()
    try:
        conn.execute("UPDATE games SET duplicate_of = NULL, duplicate_auto = 0 WHERE duplicate_auto = 1")

        games_by_platform = {}
        for row in conn.execute(
            "SELECT appid, name, platform FROM games WHERE name IS NOT NULL"
        ).fetchall():
            plat = row['platform']
            if plat not in games_by_platform:
                games_by_platform[plat] = {}
            norm = _normalize_name_for_dup(row['name'])
            games_by_platform[plat][norm] = str(row['appid'])

        updated = 0
        for i, high_plat in enumerate(platform_priority):
            if high_plat not in games_by_platform:
                continue
            high_games = games_by_platform[high_plat]
            for low_plat in platform_priority[i + 1:]:
                if low_plat not in games_by_platform:
                    continue
                for norm, low_appid in games_by_platform[low_plat].items():
                    if norm in high_games:
                        conn.execute(
                            "UPDATE games SET duplicate_of = ?, duplicate_auto = 1 WHERE appid = ?",
                            (high_games[norm], low_appid)
                        )
                        _log.info(f'Auto-duplicate ({low_plat}→{high_plat}): appid {low_appid} → {high_games[norm]}')
                        updated += 1

        if updated:
            conn.commit()
        return updated
    finally:
        conn.close()


def refresh_duplicate_detection():
    """Re-run cross-platform duplicate auto-detection with the user's saved
    platform priority (plus any newly registered plugin platforms), refresh the
    art-redirect cache, and return the new total number of auto-detected
    duplicates. Safe to call repeatedly -- auto_detect_duplicates() clears its
    own prior results first. Called after a Steam populate / bulk rescrape and
    once at startup so a plugin library sync done in a previous session gets
    picked up without the user having to click "Detect Duplicates".
    """
    try:
        from config import load_state
        from plugins import get_platform_priority
        saved   = load_state().get('platform_priority') or []
        dynamic = get_platform_priority()
        priority = saved + [p for p in dynamic if p not in saved]
    except Exception:
        priority = None
    # auto_detect_duplicates() clears its prior auto-marks first, so its return
    # value is the full current auto-detected total, not just newly-added ones.
    count = auto_detect_duplicates(platform_priority=priority)
    invalidate_dup_cache()
    return count


def recalculate_tag_similarity():
    """Recompute the tag_similarity column for every game against a
    liked-vs-library tag affinity profile, same formula as pick.py's own
    tag_similarity() (duplicated rather than shared -- that one is a request-
    scoped closure over an already-filtered candidate pool with no DB writes,
    this one is a whole-library recompute-and-persist pass, so sharing would
    mean threading a cache-vs-live-request distinction through both call
    sites). For each tag, `affinity = liked_rate - library_rate` (fraction of
    the Beaten/Completed pool carrying it, minus fraction of the whole Steam
    library carrying it) -- a tag you finish proportionally *more* than it
    shows up in your library at all is a real preference; one you finish
    proportionally *less* than its library presence is a real avoidance,
    whether that's active dislike or just a genre that never rises out of the
    backlog. A tag common to both pools cancels toward neutral on its own, no
    separate IDF/rarity correction needed -- unlike the old playtime-weighted-
    sum approach this replaced, where ubiquitous tags like "Action" or
    "Singleplayer" dominated every score regardless of whether they said
    anything distinctive about taste (confirmed live against a real 548-game
    profile: those two tags alone carried 35-40% of the old profile vector's
    total magnitude).

    An earlier version of this formula used "Won't Play" (this project's
    explicit terrible/broken marker) as the negative pool instead of the whole
    library. Replaced after live comparison: both independently surfaced the
    same core pattern (confirming it's real signal, not an artifact of
    either method), but the library-wide version was judged to track actual
    avoided tags more strongly, and doesn't depend on there being enough
    "Won't Play" games to form a pool at all.

    Unlike pick.py's version, this one keeps the raw signed score rather than
    rescaling to [0,1] -- there's no downstream `1.0 - s` direction-flip
    assumption here, just a sort column, so the scale doesn't matter.

    Cheap enough (~130ms even at 30,000 games, measured) to just run inline
    on every call -- no daemon-thread/cancellation machinery needed the way
    bulk_rescrape_games() needs it. Returns the number of games scored.

    The liked pool is playtime-weighted (added v1.10.8, same formula
    duplicated in pick.py's tag_similarity() closure): a game barely
    touched before being marked Beaten/Completed shouldn't define "what
    tags this person likes" as strongly as one that was actually played for
    a long time. `_playtime_weight()` is a log curve that saturates at
    `_PLAYTIME_WEIGHT_CAP_HOURS` -- heavily-diminishing returns rather than
    a hard cutoff, so a 100hr and a 1000hr game land close together near the
    cap (both near-fully weighted) while a 1hr game counts for much less and
    a 5-minute one barely registers at all. The library-wide baseline pool
    stays uniformly weighted -- it represents genre *presence* in the
    library, not how much any of it was played.
    """
    from config import load_state
    _tuning = load_state()
    conn = get_db()
    try:
        # Tunable via Settings -> Tuning; see config.DEFAULT_STATE
        # for the shipped defaults these fall back to.
        _PLAYTIME_WEIGHT_CAP_HOURS = _tuning.get('tag_similarity_playtime_cap_hours', 60)

        def _playtime_weight(playtime_minutes):
            hours = (playtime_minutes or 0) / 60.0
            if hours <= 0:
                return 0.0
            return min(1.0, math.log1p(hours) / math.log1p(_PLAYTIME_WEIGHT_CAP_HOURS))

        def _tag_pool_rate(rows, weights=None):
            n = len(rows) if weights is None else sum(weights)
            if not n:
                return {}
            counts: dict[str, float] = {}
            for i, row in enumerate(rows):
                w = 1.0 if weights is None else weights[i]
                if w <= 0:
                    continue
                for tag in [t.strip() for t in (row['tags'] or '').split(',') if t.strip()]:
                    counts[tag] = counts.get(tag, 0) + w
            return {t: c / n for t, c in counts.items()}

        # Steam only -- other platforms' plugins don't all populate `tags` with
        # a real community-tag vocabulary. Confirmed live: PlayDate's Epic
        # Games plugin stores Epic's own review-attribute checkboxes ("Windows",
        # "Recommend this Game", "Extremely Fun", "Amazing Storytelling") in
        # this same column, which isn't genre/style data at all and would
        # otherwise poison both pools with noise unrelated to actual taste.
        liked_rows = conn.execute(
            "SELECT tags, playtime_forever FROM games "
            "WHERE completion_status IN ('Beaten', 'Completed') "
            "AND platform = 'steam' AND tags IS NOT NULL AND tags != ''"
        ).fetchall()
        if not liked_rows:
            liked_rows = conn.execute(
                "SELECT tags, playtime_forever FROM games "
                "WHERE platform = 'steam' AND tags IS NOT NULL AND tags != '' "
                "ORDER BY playtime_forever DESC LIMIT 50"
            ).fetchall()
        library_rows = conn.execute(
            "SELECT tags FROM games WHERE platform = 'steam' AND tags IS NOT NULL AND tags != ''"
        ).fetchall()

        liked_weights = [_playtime_weight(r['playtime_forever']) for r in liked_rows]
        if not any(w > 0 for w in liked_weights):
            # No playtime data on any liked game at all (e.g. an imported
            # library with untracked playtime) -- fall back to a flat count
            # rather than losing the whole signal to an all-zero weighting.
            liked_weights = None
        liked_rate = _tag_pool_rate(liked_rows, liked_weights)
        library_rate = _tag_pool_rate(library_rows)
        # A tag in only a handful of library games can swing wildly on one or
        # two data points -- not enough sample to trust either direction, so
        # it's excluded rather than treated as a real signal (falls back to
        # 0.0/neutral wherever it's looked up, same as an unknown tag).
        MIN_LIBRARY_RATE = _tuning.get('tag_similarity_min_library_rate', 2.0) / 100.0
        library_rate = {t: r for t, r in library_rate.items() if r >= MIN_LIBRARY_RATE}
        # Iterate library_rate's (already-filtered) keys only, not the union
        # with liked_rate -- a tag the floor above excluded must default to a
        # clean 0.0/neutral affinity, not fall through to whatever its
        # unfiltered liked_rate alone happens to be.
        tag_affinity = {t: liked_rate.get(t, 0.0) - library_rate[t] for t in library_rate}

        # Smoothing pseudo-count: without it, a game with one strongly-liked
        # tag and nothing else beats one with several matching tags, purely
        # for having nothing to dilute its lone lucky tag. Empirically tuned
        # against a real library, not a principled constant.
        SMOOTHING_K = _tuning.get('tag_similarity_smoothing_k', 4)

        rows = conn.execute("SELECT appid, tags FROM games").fetchall()
        updates = []
        for row in rows:
            candidate_tags = [t.strip() for t in (row['tags'] or '').split(',') if t.strip()]
            if not candidate_tags:
                # NULL, not 0.0 -- a game with no tags at all has no signal to
                # compare, which is different from a tagged game that happens
                # to net zero against the affinity profile (a real, known 0.0).
                # NULL sorts last regardless of direction (see VIRTUAL_SORT_COLS
                # in library.py); a real 0.0 would sort in the middle in either
                # direction, which would be wrong for a game we simply know
                # nothing about.
                sim = None
            else:
                total = sum(tag_affinity.get(t, 0.0) for t in candidate_tags)
                sim = total / (len(candidate_tags) + SMOOTHING_K)
            updates.append((sim, row['appid']))

        conn.executemany("UPDATE games SET tag_similarity = ? WHERE appid = ?", updates)
        conn.commit()
        return len(updates)
    finally:
        conn.close()


def recalculate_weighted_scores():
    """Recompute games.weighted_percentage from the stored raw review counts
    using the current confidence curve (Settings -> Tuning -> Review Scores).

    Same trigger-point pattern as recalculate_tag_similarity(): the weighted
    score is a cached derived value, so changing the curve has to rewrite it.
    Uses review_percentage/total_reviews exactly as scrapers.fetch_review_data
    stored them, so a recompute at unchanged settings is a no-op. Games with no
    review count are left untouched. Steam only: plugins that report reviews
    (Epic Games, ...) compute weighted_percentage with their own formula, which
    this must not overwrite. Returns the number of rows rescored."""
    from config import load_state
    from utils import weighted_review_score
    half_trust = load_state().get('review_half_trust_count', 10)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT appid, review_percentage, total_reviews FROM games "
            "WHERE platform = 'steam' "
            "AND typeof(total_reviews) IN ('integer', 'real') AND total_reviews > 0 "
            "AND typeof(review_percentage) IN ('integer', 'real')"
        ).fetchall()
        updates = [(weighted_review_score(r['review_percentage'], r['total_reviews'], half_trust), r['appid'])
                   for r in rows]
        conn.executemany("UPDATE games SET weighted_percentage = ? WHERE appid = ?", updates)
        conn.commit()
        return len(updates)
    finally:
        conn.close()
