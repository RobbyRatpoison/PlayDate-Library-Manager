"""Dev-only: build static/data/gamepad_layouts.json from SDL_GameControllerDB.

    python tools/build_gamepad_db.py path/to/gamecontrollerdb.txt

Keeps the platform:Linux entries whose GUID carries a USB/Bluetooth vendor and product id,
keyed "vvvv:pppp" (lowercase hex). Each value is the controller's name and the distinct
SDL mapping strings (name, GUID, platform and crc dropped). static/js/gamepad_layout.js
reads those strings directly, so an SDL entry is a PlayDate layout. SDL_GameControllerDB
is zlib licensed; static/data/SDL_GameControllerDB_LICENSE.txt ships with the output.
"""
import json
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'data', 'gamepad_layouts.json')


def vid_pid(guid):
    """('2dc8', '310b') for a GUID laid out as bus, crc, vendor, 0, product, 0, version, or None."""
    if len(guid) != 32:
        return None
    try:
        raw = bytes.fromhex(guid)
    except ValueError:
        return None
    if raw[6:8] != b'\0\0' or raw[10:12] != b'\0\0':
        return None  # name-based GUID, no vendor/product inside
    vendor, product = raw[4] | raw[5] << 8, raw[8] | raw[9] << 8
    if not vendor or not product:
        return None
    return f'{vendor:04x}', f'{product:04x}'


def main(src):
    layouts = {}
    for line in open(src, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or 'platform:Linux' not in line:
            continue
        guid, name, *fields = line.rstrip(',').split(',')
        ids = vid_pid(guid)
        if not ids:
            continue
        mapping = ','.join(f for f in fields if f and not f.startswith(('platform:', 'crc:')))
        entry = layouts.setdefault(':'.join(ids), {'name': name, 'maps': []})
        if mapping not in entry['maps']:
            entry['maps'].append(mapping)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'source': 'SDL_GameControllerDB (zlib), Linux entries', 'layouts': layouts}, f, separators=(',', ':'), sort_keys=True)
    print(f'{len(layouts)} controllers, {os.path.getsize(OUT) // 1024} KB -> {os.path.normpath(OUT)}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
