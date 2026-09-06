"""Lets a user send playdate.log (plus a version/OS/diagnostics summary) to a
Cloudflare Worker relay (tools/log-relay/), which forwards it to Discord for
support triage, without needing a GitHub account. config.json is never sent
-- that's the only file holding API keys/account tokens. state.json has no
credentials in it (those live solely in config.json), so its settings are
included in the diagnostics summary to help reproduce filter/platform-visibility
bugs like an empty library page."""
import json
import logging
import os
import platform
import sys
import threading
import time

import requests
from flask import Blueprint, jsonify, request

from config import (BASE_DIR, IN_FLATPAK, IS_PORTABLE, __version__, load_state,
                     save_state, api_error, _current_renderer_display, qt_renderer_relevant)

log = logging.getLogger(__name__)

diagnostics_bp = Blueprint('diagnostics', __name__)

# Fill this in with the deployed log-relay Worker's URL to enable in-app log
# submission (see tools/log-relay/README.md). Left blank, /api/submit-log
# just reports itself unavailable.
#
# NOTE: this ships inside the built app and public source, so it is
# discoverable and postable-to by anyone, not just PlayDate's UI -- same as
# any URL baked into a public binary. Unlike the raw Discord webhook this
# used to hold directly, the relay never lets a direct caller inject raw
# content/mentions/embeds; it only ever forwards a fixed message template
# (see tools/log-relay/src/worker.js), so finding this URL doesn't hand out
# a "post anything to our Discord" credential. The real Discord webhook now
# lives only as a secret on the relay, never in source.
RELAY_URL = 'https://playdate-log-relay.robbyratpoison.workers.dev'

MAX_LOG_BYTES        = 1024 * 1024  # matches the RotatingFileHandler cap (app.py)
MAX_DIAG_BYTES       = 256 * 1024   # generous cap for state.json + counts; guards against a huge saved_filters dict
SUBMIT_COOLDOWN_SECONDS = 5 * 60
MAX_MESSAGE_CHARS    = 1000

_submit_lock = threading.Lock()


def _install_channel():
    if IN_FLATPAK:
        return 'flatpak'
    if IS_PORTABLE:
        return 'portable'
    if getattr(sys, 'frozen', False):
        return 'installer'
    return 'source'


def _diagnostics_snapshot(state):
    """Everything besides the log itself that's useful for reproducing a bug --
    library/platform counts, installed plugins, renderer, and the full contents
    of state.json (filters, hidden platforms, shelf layout, etc). No secrets
    live in state.json, so nothing here is redacted."""
    from database import get_db
    from plugins import loaded as _plugins_loaded, plugin_manifest as _plugin_manifest

    snapshot = {'state': state}

    try:
        db = get_db()
        total_games = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        hidden_dupes = db.execute(
            "SELECT COUNT(*) FROM games WHERE duplicate_of IS NOT NULL AND duplicate_of != ''"
        ).fetchone()[0]
        platform_counts = {
            row['platform']: row['n']
            for row in db.execute("SELECT platform, COUNT(*) as n FROM games GROUP BY platform").fetchall()
        }
        db.close()
        snapshot['library'] = {
            'total_games': total_games,
            'hidden_dupes': hidden_dupes,
            'platform_counts': platform_counts,
        }
    except Exception as e:
        snapshot['library'] = {'error': str(e)}

    try:
        snapshot['plugins'] = {
            pid: _plugin_manifest(pid).get('version', '?')
            for pid in _plugins_loaded()
        }
    except Exception as e:
        snapshot['plugins'] = {'error': str(e)}

    try:
        snapshot['renderer'] = {
            'active': _current_renderer_display(state),
            'qt_relevant': qt_renderer_relevant(),
        }
    except Exception as e:
        snapshot['renderer'] = {'error': str(e)}

    return snapshot


@diagnostics_bp.route('/api/submit-log', methods=['POST'])
def submit_log():
    if not RELAY_URL:
        return jsonify({"status": "error", "message": "Log submission isn't configured for this build."}), 501

    if not _submit_lock.acquire(blocking=False):
        return jsonify({"status": "error", "message": "A submission is already in progress."}), 409
    try:
        state = load_state()
        last  = state.get('last_log_submit_at')
        if last and time.time() - last < SUBMIT_COOLDOWN_SECONDS:
            wait = int(SUBMIT_COOLDOWN_SECONDS - (time.time() - last))
            return jsonify({"status": "error", "message": f"Please wait {wait}s before submitting again."}), 429

        message = ((request.json or {}).get('message') or '').strip()[:MAX_MESSAGE_CHARS]

        log_path = os.path.join(BASE_DIR, 'playdate.log')
        try:
            with open(log_path, 'rb') as f:
                log_bytes = f.read()
        except OSError as e:
            return api_error('Could not read log file. Check playdate.log for details.', 500, exc=e)
        if len(log_bytes) > MAX_LOG_BYTES:
            log_bytes = log_bytes[-MAX_LOG_BYTES:]

        meta = {
            'message': message,
            'version': __version__,
            'install_channel': _install_channel(),
            'os': f"{platform.system()} {platform.release()}",
        }

        try:
            diag_bytes = json.dumps(_diagnostics_snapshot(state), indent=2, default=str).encode('utf-8')
        except Exception as e:
            diag_bytes = json.dumps({'error': str(e)}).encode('utf-8')
        if len(diag_bytes) > MAX_DIAG_BYTES:
            diag_bytes = json.dumps({'error': 'diagnostics snapshot too large, omitted'}).encode('utf-8')

        try:
            resp = requests.post(
                RELAY_URL,
                data={'meta': json.dumps(meta)},
                files={
                    'file': ('playdate.log', log_bytes, 'text/plain'),
                    'diagnostics': ('diagnostics.json', diag_bytes, 'application/json'),
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"Log submission failed: {e}")
            return jsonify({"status": "error", "message": "Could not reach the report server. Try again later."}), 502

        save_state({'last_log_submit_at': time.time()})
        return jsonify({"status": "success"})
    finally:
        _submit_lock.release()
