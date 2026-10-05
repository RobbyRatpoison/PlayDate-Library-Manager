// Gamepad layouts: turn a pad the browser has no "standard" mapping for into a standard-shaped
// one, so input.js and the Gamepad screens only ever deal with the W3C button/axis numbers.
//
// A layout is an SDL mapping string ("a:b0,leftx:a0,lefttrigger:a2,dpup:h0.1,..."): which raw
// button, axis or hat feeds each standard control. The same format covers the bundled
// SDL_GameControllerDB entries (static/data/gamepad_layouts.json, built by
// tools/build_gamepad_db.py), the built-in fallback below, and a user's saved or custom choice
// (state.json's gamepad_layouts, window._GAMEPAD_LAYOUTS).
//
// Which layout a pad gets, first match wins:
//   1. the user's saved choice for that controller ("standard" leaves it alone)
//   2. the bundled database entry for its USB vendor/product id that fits the pad
//   3. the Xbox-style raw order, recognised by both trigger axes resting at -1
//   4. none: the pad is used as the browser reports it
(function () {
    // Standard button index for each SDL field (W3C Standard Gamepad order).
    const STD_BUTTONS = { a: 0, b: 1, x: 2, y: 3, leftshoulder: 4, rightshoulder: 5, lefttrigger: 6, righttrigger: 7,
                          back: 8, start: 9, leftstick: 10, rightstick: 11, dpup: 12, dpdown: 13, dpleft: 14, dpright: 15, guide: 16 };
    const STD_AXES = { leftx: 0, lefty: 1, rightx: 2, righty: 3 };
    const STD_BUTTON_COUNT = 17;

    // Raw Linux order of an Xbox-style pad with no standard mapping (Chromium's
    // MapperXInputStyleGamepad and SDL's Xbox entries agree on it).
    const XBOX_RAW = 'a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,rightshoulder:b5,back:b6,start:b7,guide:b8,leftstick:b9,rightstick:b10,' +
                     'leftx:a0,lefty:a1,rightx:a3,righty:a4,lefttrigger:a2,righttrigger:a5,dpup:h0.1,dpright:h0.2,dpdown:h0.4,dpleft:h0.8';

    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const DEAD = Object.freeze({ pressed: false, touched: false, value: 0 });

    // ── Parsing ───────────────────────────────────────────────────────────────
    // b4 = button 4, a2 = axis 2, +a2 / -a2 = one direction of an axis, a2~ = inverted,
    // h0.4 = hat 0, bit 4 (1 up, 2 right, 4 down, 8 left).
    function parseSource(v) {
        const m = /^([+-]?)([abh])(\d+)(?:\.(\d+))?(~?)$/.exec(v || '');
        if (!m) return null;
        return { t: m[2], i: +m[3], half: m[1] === '+' ? 1 : m[1] === '-' ? -1 : 0, inv: m[5] === '~', mask: m[4] ? +m[4] : 0 };
    }

    const parsed = new Map();   // mapping string -> layout (or null)
    function parse(str) {
        if (parsed.has(str)) return parsed.get(str);
        const layout = { str, btn: {}, ax: {}, usedButtons: new Set() };
        for (const field of String(str).split(',')) {
            const [k, v] = field.split(':');
            const src = parseSource(v);
            if (!src) continue;
            if (k in STD_BUTTONS) {
                layout.btn[STD_BUTTONS[k]] = src;
                if (src.t === 'b') layout.usedButtons.add(src.i);
            } else if (k in STD_AXES) layout.ax[STD_AXES[k]] = src;
        }
        const result = Object.keys(layout.btn).length ? layout : null;
        parsed.set(str, result);
        return result;
    }

    // Every index the layout reads exists on this pad, and a hat does not overlap a stick axis
    // (the hat is the pad's last two axes).
    function fits(layout, gp) {
        const sources = [...Object.values(layout.btn), ...Object.values(layout.ax)];
        let maxAxis = -1, hat = false;
        for (const s of sources) {
            if (s.t === 'b' && s.i >= gp.buttons.length) return false;
            if (s.t === 'a') { if (s.i >= gp.axes.length) return false; maxAxis = Math.max(maxAxis, s.i); }
            if (s.t === 'h') hat = true;
        }
        return !hat || (gp.axes.length >= 2 && maxAxis < gp.axes.length - 2);
    }

    // ── Reading a source ──────────────────────────────────────────────────────
    function axisValue(src, gp) {
        const v = gp.axes[src.i] || 0;
        return src.inv ? -v : v;
    }

    // Axes that have reported a non-zero value on the pad being read. A browser may report 0 for
    // an axis that has not moved yet, which a trigger resting at -1 would turn into half pulled.
    let axesSeen = new Set();

    // 0..1 for a button-like control (a full axis is a trigger resting at -1).
    function analog(src, gp) {
        if (src.t === 'b') {
            const b = gp.buttons[src.i];
            return b ? (typeof b.value === 'number' ? b.value : (b.pressed ? 1 : 0)) : 0;
        }
        if (src.t === 'a') {
            const v = axisValue(src, gp);
            if (src.half === 0 && !axesSeen.has(src.i)) return 0;
            return clamp(src.half > 0 ? v : src.half < 0 ? -v : (v + 1) / 2, 0, 1);
        }
        // hat 0 is the pad's last two axes
        const n = gp.axes.length, x = gp.axes[n - 2] || 0, y = gp.axes[n - 1] || 0;
        const bits = (y < -0.5 ? 1 : 0) | (x > 0.5 ? 2 : 0) | (y > 0.5 ? 4 : 0) | (x < -0.5 ? 8 : 0);
        return src.i === 0 && (bits & src.mask) ? 1 : 0;
    }

    function button(src, gp) {
        if (!src) return DEAD;
        if (src.t === 'b' && gp.buttons[src.i]) return gp.buttons[src.i];
        const n = analog(src, gp);
        return { pressed: n > 0.5, touched: n > 0.05, value: n };
    }

    // A standard-shaped copy of the pad. Raw buttons the layout doesn't use (paddles, extras)
    // follow the standard 17 in the pad's own order, so they stay reachable for the remap screen.
    const seenByPad = new Map();   // pad key -> axes that have reported a non-zero value
    function apply(gp, layout, info) {
        const key = gp.id + '#' + gp.index;
        axesSeen = seenByPad.get(key) || seenByPad.set(key, new Set()).get(key);
        gp.axes.forEach((v, i) => { if (v !== 0) axesSeen.add(i); });
        const buttons = [], rawOf = [];   // rawOf[i]: the raw button behind converted button i (null for an axis or hat)
        for (let i = 0; i < STD_BUTTON_COUNT; i++) {
            buttons.push(button(layout.btn[i], gp));
            rawOf.push(layout.btn[i] && layout.btn[i].t === 'b' ? layout.btn[i].i : null);
        }
        for (let i = 0; i < gp.buttons.length; i++) if (!layout.usedButtons.has(i)) { buttons.push(gp.buttons[i]); rawOf.push(i); }
        const axes = [0, 1, 2, 3].map(i => {
            const s = layout.ax[i];
            return s && s.t === 'a' ? clamp(axisValue(s, gp), -1, 1) : 0;
        });
        return { id: gp.id, index: gp.index, connected: gp.connected, timestamp: gp.timestamp,
                 mapping: 'standard', _pdNormalized: true, _pdLayout: info, _pdRaw: rawOf, axes, buttons };
    }

    // ── Finding the layout ────────────────────────────────────────────────────
    // "Vendor: 2dc8 Product: 310b" (Chromium and Qt), or "2dc8-310b-Name" (Firefox).
    function vendorProduct(id) {
        const m = /Vendor:\s*([0-9a-f]{4})\s+Product:\s*([0-9a-f]{4})/i.exec(id || '') || /^([0-9a-f]{4})-([0-9a-f]{4})-/i.exec(id || '');
        return m ? `${m[1].toLowerCase()}:${m[2].toLowerCase()}` : null;
    }

    let db = null, dbRequested = false;
    const cache = new Map();   // pad key -> resolved choice
    function invalidate() { cache.clear(); }

    function loadDb() {
        if (dbRequested) return;
        dbRequested = true;
        fetch('/static/data/gamepad_layouts.json').then(r => r.json()).then(d => {
            db = (d && d.layouts) || {};
            invalidate();
        }).catch(() => { dbRequested = false; db = db || {}; });
    }

    // Database entries for this pad that fit it: [{name, map, layout}]
    function candidates(gp) {
        const key = vendorProduct(gp.id);
        const entry = key && db && db[key];
        if (!entry) return [];
        return entry.maps.map(map => ({ name: entry.name, map, layout: parse(map) })).filter(c => c.layout && fits(c.layout, gp));
    }

    // Both trigger axes resting at -1 is how an Xbox-style raw pad shows itself. Browsers can
    // report 0 for an axis that has not moved yet, so this may only succeed after a trigger
    // press; the saved choice and the database lookup don't depend on it.
    function looksXboxRaw(gp) {
        return gp.axes.length >= 8 && gp.buttons.length >= 11 && gp.axes[2] < -0.99 && gp.axes[5] < -0.99;
    }

    // How well the pad's current axes agree with a layout: a trigger axis rests at -1 (+1 each),
    // a stick axis cannot (-1 each).
    function restScore(layout, gp) {
        let score = 0;
        for (const i of [6, 7]) {
            const s = layout.btn[i];
            if (s && s.t === 'a' && s.half === 0 && (gp.axes[s.i] || 0) < -0.99) score++;
        }
        for (const s of Object.values(layout.ax)) if (s.t === 'a' && (gp.axes[s.i] || 0) < -0.99) score--;
        return score;
    }

    function resolve(gp) {
        const key = gp.id + '#' + gp.index;
        const hit = cache.get(key);
        if (hit) return hit;
        const done = r => { cache.set(key, r); return r; };

        const saved = (window._GAMEPAD_LAYOUTS || {})[gp.id];
        if (saved && saved.kind === 'standard') return done({ layout: null, source: 'standard' });
        if (saved && saved.kind === 'map') {
            const layout = parse(saved.map);
            return done(layout && fits(layout, gp) ? { layout, source: 'saved', map: saved.map } : { layout: null, source: 'mismatch' });
        }

        if (vendorProduct(gp.id)) {
            if (!db) { loadDb(); }
            else {
                const cands = candidates(gp);
                if (cands.length === 1) return done({ layout: cands[0].layout, source: 'database', map: cands[0].map, name: cands[0].name });
                if (cands.length > 1) {
                    // One product can have several layouts (the kernel driver changed them over time).
                    // The resting readings tell them apart; until they do, use the first without settling.
                    const scored = cands.map(c => ({ c, s: restScore(c.layout, gp) })).sort((a, b) => b.s - a.s);
                    const r = { layout: scored[0].c.layout, source: 'database', map: scored[0].c.map, name: scored[0].c.name };
                    return scored[0].s > scored[1].s ? done(r) : r;
                }
            }
        }
        if (looksXboxRaw(gp)) return done({ layout: parse(XBOX_RAW), source: 'detected', map: XBOX_RAW });
        return { layout: null, source: 'none' };   // not cached: detection may still succeed
    }

    // Entry point: the pad as the app should read it (the pad itself when no layout applies).
    window.pdStandardizeGamepad = function (gp) {
        if (!gp || gp.mapping === 'standard' || gp === window._pdPad) return gp;
        const r = resolve(gp);
        return r.layout ? apply(gp, r.layout, { source: r.source, map: r.map, name: r.name }) : gp;
    };

    // ── Bindings on extra buttons survive a layout change ─────────────────────
    // Gamepad Controls stores a binding under the converted button number, and extras are numbered
    // after the standard 17 in raw order, so a different layout moves them. When a layout is saved,
    // move each binding on an extra to the same physical button.
    function connectedPad(id) {
        const list = navigator.getGamepads ? navigator.getGamepads() : [];
        for (const g of list) if (g && g.id === id) return g;
        return null;
    }
    const rawNumbers = pad => window.pdStandardizeGamepad(pad)._pdRaw || null;   // null: used as reported, raw = converted

    function keepExtraBindings(before, after) {
        const out = {};
        let changed = false;
        for (const [k, action] of Object.entries(window._BUTTON_REMAPS || {})) {
            const idx = +k;
            if (idx < STD_BUTTON_COUNT) { out[k] = action; continue; }
            const raw = before ? before[idx] : idx;                       // the physical button it was on
            const now = raw == null ? -1 : (after ? after.indexOf(raw) : raw);
            if (now >= STD_BUTTON_COUNT) { out[String(now)] = action; if (now !== idx) changed = true; }
            else changed = true;   // that button is now a standard control; leaving the binding would hijack it
        }
        if (!changed) return;
        window._BUTTON_REMAPS = out;
        if (window._inputMgr && window._inputMgr.setButtonRemaps) window._inputMgr.setButtonRemaps(out);
        if (typeof savePreference === 'function') savePreference({ button_remaps: out });
    }

    // For the Diagnostics screen: what is in use and what could be chosen instead.
    window.PDLayout = {
        XBOX_RAW, parse, fits, apply, vendorProduct, invalidate, loadDb,
        info(gp) {
            if (vendorProduct(gp.id)) loadDb();   // the choices come from the database even when a saved one is in use
            const r = resolve(gp);
            return { source: r.source, map: r.map || null, name: r.name || null,
                     candidates: candidates(gp).map(c => ({ name: c.name, map: c.map })),
                     xboxFits: !!fits(parse(XBOX_RAW), gp) };
        },
        // Standard control names (SDL fields) for the wizard, and the source <-> string forms.
        STD_BUTTONS, STD_AXES, parseSource,
        sourceToString(s) {
            if (s.t === 'b') return 'b' + s.i;
            if (s.t === 'h') return `h${s.i}.${s.mask}`;
            return (s.half > 0 ? '+' : s.half < 0 ? '-' : '') + 'a' + s.i + (s.inv ? '~' : '');
        },
        // Names the user gave buttons, keyed by the pad's raw button number (a physical button's
        // number never changes, whichever layout is in use): { '17': 'Z' }. Blank names are dropped.
        setNames(id, names) {
            const all = Object.assign({}, window._GAMEPAD_LAYOUTS || {});
            const rec = Object.assign({}, all[id] || {});
            const clean = {};
            for (const [k, v] of Object.entries(names || {})) if (String(v).trim()) clean[k] = String(v).trim().slice(0, 12);
            if (Object.keys(clean).length) rec.names = clean; else delete rec.names;
            if (rec.kind || rec.style || rec.names || rec.shape) all[id] = rec; else delete all[id];
            window._GAMEPAD_LAYOUTS = all;
            invalidate();
            if (typeof savePreference === 'function') savePreference({ gamepad_layouts: all });
        },
        // Button-label style only ('xbox' | 'ps' | 'nintendo' | 'other', or 'auto' to go back to
        // guessing from the vendor); the saved layout is left as it is.
        setStyle(id, style) {
            const all = Object.assign({}, window._GAMEPAD_LAYOUTS || {});
            const rec = Object.assign({}, all[id] || {});
            if (style && style !== 'auto') rec.style = style; else delete rec.style;
            if (rec.kind || rec.style || rec.names || rec.shape) all[id] = rec; else delete all[id];
            window._GAMEPAD_LAYOUTS = all;
            invalidate();
            if (typeof savePreference === 'function') savePreference({ gamepad_layouts: all });
        },
        // Remember a choice for this controller: { kind: 'auto' | 'standard' | 'map', map?, style? }.
        // The button-label style is kept when a later choice doesn't name one.
        save(id, choice) {
            const pad = connectedPad(id);
            const before = pad ? rawNumbers(pad) : null;
            const all = Object.assign({}, window._GAMEPAD_LAYOUTS || {});
            const rec = Object.assign({}, choice || {});
            if (!rec.kind || rec.kind === 'auto') delete rec.kind;
            const prev = all[id] || {};
            if (rec.style === undefined && prev.style) rec.style = prev.style;
            if (rec.names === undefined && prev.names) rec.names = prev.names;
            if (rec.shape === undefined && prev.shape) rec.shape = prev.shape;
            if (!rec.kind && !rec.style && !rec.names && !rec.shape) delete all[id]; else all[id] = rec;
            window._GAMEPAD_LAYOUTS = all;
            invalidate();
            if (pad) keepExtraBindings(before, rawNumbers(pad));
            if (typeof savePreference === 'function') savePreference({ gamepad_layouts: all });
        },
    };
})();
