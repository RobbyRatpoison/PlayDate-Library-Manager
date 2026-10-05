// Gamepad layout wizard (Gamepad Diagnostics > Controller layout > Set up custom layout).
//
// Walks through the controls of a pad one at a time, shown by highlighting them on a pad
// drawing (Xbox-style or PlayStation-style shape) instead of by letter, since A, cross and B
// are all the bottom button. Each step waits for the user to press or move that control on the
// real pad and records which raw button, axis or hat it was; the result is saved per controller
// as an SDL mapping string (see gamepad_layout.js). Every step can be skipped, and it starts from
// the layout currently in use so only what is wrong has to be redone.
(function () {
    const SVG_NS = 'http://www.w3.org/2000/svg';

    // ── Steps ─────────────────────────────────────────────────────────────────
    // id = the SDL field it records; hl = the controls highlighted on the drawing.
    const FACE = (id, hl, text, hint) => ({ id, kind: 'button', hl: [hl], text, hint });
    const ALL_STEPS = [
        FACE('a', 'a', 'Press the bottom face button', 'A on Xbox, ✕ on PlayStation, B on Nintendo'),
        FACE('b', 'b', 'Press the right face button', 'B on Xbox, ○ on PlayStation, A on Nintendo'),
        FACE('x', 'x', 'Press the left face button', 'X on Xbox, □ on PlayStation, Y on Nintendo'),
        FACE('y', 'y', 'Press the top face button', 'Y on Xbox, △ on PlayStation, X on Nintendo'),
        { id: 'leftshoulder', kind: 'button', hl: ['lb'], text: 'Press the left bumper (the shoulder button)', hint: 'LB, L1 or L' },
        { id: 'rightshoulder', kind: 'button', hl: ['rb'], text: 'Press the right bumper (the shoulder button)', hint: 'RB, R1 or R' },
        { id: 'lefttrigger', kind: 'trigger', hl: ['lt'], text: 'Pull the left trigger all the way', hint: 'LT, L2 or ZL' },
        { id: 'righttrigger', kind: 'trigger', hl: ['rt'], text: 'Pull the right trigger all the way', hint: 'RT, R2 or ZR' },
        { id: 'dpup', kind: 'dpad', dir: 'up', hl: ['dpup'], text: 'Press up on the d-pad' },
        { id: 'dpdown', kind: 'dpad', dir: 'down', hl: ['dpdown'], text: 'Press down on the d-pad' },
        { id: 'dpleft', kind: 'dpad', dir: 'left', hl: ['dpleft'], text: 'Press left on the d-pad' },
        { id: 'dpright', kind: 'dpad', dir: 'right', hl: ['dpright'], text: 'Press right on the d-pad' },
        { id: 'leftx', kind: 'stick', hl: ['ls'], text: 'Push the left stick all the way right' },
        { id: 'lefty', kind: 'stick', hl: ['ls'], text: 'Push the left stick all the way down' },
        { id: 'rightx', kind: 'stick', hl: ['rs'], text: 'Push the right stick all the way right' },
        { id: 'righty', kind: 'stick', hl: ['rs'], text: 'Push the right stick all the way down' },
        { id: 'leftstick', kind: 'button', hl: ['ls'], text: 'Click the left stick in', hint: 'L3' },
        { id: 'rightstick', kind: 'button', hl: ['rs'], text: 'Click the right stick in', hint: 'R3' },
        { id: 'back', kind: 'button', hl: ['back'], text: 'Press the small button left of center', hint: 'Back, Share or Minus' },
        { id: 'start', kind: 'button', hl: ['start'], text: 'Press the small button right of center', hint: 'Start, Options or Plus' },
        { id: 'guide', kind: 'button', hl: ['guide'], text: 'Press the center logo button, or skip if there is none', hint: 'Guide, PS or Home' },
    ];
    // A retro pad (NES, SNES, Genesis, Saturn...) has no sticks, analog triggers or stick clicks, and with up to six
    // face buttons a position doesn't say which one should confirm: it asks for what each should do instead.
    const RETRO_FACE_TEXT = {
        a: 'Press the button you want to use to confirm', b: 'Press the button you want to use to go back or cancel',
        x: 'Press the button you want to use to open a game\'s menu', y: 'Press the button you want to use to edit a game',
    };
    function stepsFor(shape) {
        if (shape !== 'retro') return ALL_STEPS;
        return ALL_STEPS.filter(st => !['trigger', 'stick'].includes(st.kind) && !['leftstick', 'rightstick', 'guide'].includes(st.id))
            .map(st => RETRO_FACE_TEXT[st.id] ? { ...st, text: RETRO_FACE_TEXT[st.id], hint: 'Any of the face buttons', hl: ['f1', 'f2', 'f3', 'f4', 'f5', 'f6'] } : st);
    }
    const FIELD_LABEL = { a: 'the bottom face button', b: 'the right face button', x: 'the left face button', y: 'the top face button',
        leftshoulder: 'the left bumper', rightshoulder: 'the right bumper', leftstick: 'the left stick click', rightstick: 'the right stick click',
        back: 'the left center button', start: 'the right center button', guide: 'the center button',
        lefttrigger: 'the left trigger', righttrigger: 'the right trigger',
        dpup: 'd-pad up', dpdown: 'd-pad down', dpleft: 'd-pad left', dpright: 'd-pad right' };

    // ── Drawing ───────────────────────────────────────────────────────────────
    // Both shapes share the body; they differ in where the sticks and d-pad sit.
    const BODY = 'M60,70 Q60,40 100,40 L300,40 Q340,40 340,70 L362,188 Q366,232 330,232 Q300,232 285,198 L262,172 L138,172 L115,198 Q100,232 70,232 Q34,232 38,188 Z';
    const SHAPES = {
        xbox: { ls: [112, 96], dpad: [148, 152], rs: [252, 152], guide: [200, 74, 9], back: [172, 100], start: [228, 100] },
        ps:   { ls: [152, 158], dpad: [112, 100], rs: [248, 158], guide: [200, 176, 8], back: [168, 92], start: [232, 92] },
    };
    const FACE_CENTER = [288, 98];
    const FACE_LABELS = {
        xbox: { a: 'A', b: 'B', x: 'X', y: 'Y' }, ps: { a: '✕', b: '○', x: '□', y: '△' },
        nintendo: { a: 'B', b: 'A', x: 'Y', y: 'X' }, other: {},
    };
    const FACE_COLORS = {
        xbox: { a: '#3bb143', b: '#e0393e', x: '#3a7bd5', y: '#f4c20d' },
        ps: { a: '#3a7bd5', b: '#e0393e', x: '#e05fa0', y: '#3bb143' },
    };

    // Retro pad: d-pad on the left, two rows of three face buttons, two shoulder buttons.
    function retroDiagram(hl) {
        const g = (key, inner) => `<g class="gpw-ctl${hl.has(key) ? ' gpw-hl' : ''}">${inner}</g>`;
        const circle = (cx, cy, r) => `<circle cx="${cx}" cy="${cy}" r="${r}"/>`;
        const rect = (x, y, w, h, r = 4) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"/>`;
        const faces = [[236, 100], [276, 100], [316, 100], [236, 140], [276, 140], [316, 140]]
            .map(([x, y], i) => g('f' + (i + 1), circle(x, y, 12))).join('');
        return `<svg class="gpw-svg" viewBox="0 0 400 244" xmlns="${SVG_NS}" role="img" aria-label="Retro controller drawing">` +
            `<path class="gpw-body" d="M44,70 Q44,44 76,44 L324,44 Q356,44 356,70 L356,170 Q356,212 316,212 L84,212 Q44,212 44,170 Z"/>` +
            g('lb', rect(60, 24, 80, 14)) + g('rb', rect(260, 24, 80, 14)) +
            g('dpup', rect(96, 76, 14, 18, 3)) + g('dpdown', rect(96, 120, 14, 18, 3)) +
            g('dpleft', rect(74, 98, 18, 14, 3)) + g('dpright', rect(114, 98, 18, 14, 3)) +
            faces + g('back', circle(172, 176, 7)) + g('start', circle(228, 176, 7)) +
            `</svg>`;
    }

    function diagram(shape, style, highlight) {
        if (shape === 'retro') return retroDiagram(new Set(highlight || []));
        const s = SHAPES[shape] || SHAPES.xbox, hl = new Set(highlight || []);
        const g = (key, inner) => `<g class="gpw-ctl${hl.has(key) ? ' gpw-hl' : ''}">${inner}</g>`;
        const circle = (cx, cy, r) => `<circle cx="${cx}" cy="${cy}" r="${r}"/>`;
        const rect = (x, y, w, h, r = 4) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"/>`;
        const [fx, fy] = FACE_CENTER, [dx, dy] = s.dpad;
        const face = (key, ox, oy) => {
            const label = (FACE_LABELS[style] || {})[key] || '';
            const color = (FACE_COLORS[style] || {})[key];
            return g(key, circle(fx + ox, fy + oy, 10) +
                (label ? `<text class="gpw-lbl" x="${fx + ox}" y="${fy + oy + 4}" text-anchor="middle"${color ? ` style="fill:${color}"` : ''}>${label}</text>` : ''));
        };
        return `<svg class="gpw-svg" viewBox="0 0 400 244" xmlns="${SVG_NS}" role="img" aria-label="Controller drawing">` +
            `<path class="gpw-body" d="${BODY}"/>` +
            g('lt', rect(78, 4, 54, 14, 6)) + g('rt', rect(268, 4, 54, 14, 6)) +
            g('lb', rect(66, 22, 78, 13)) + g('rb', rect(256, 22, 78, 13)) +
            g('ls', circle(s.ls[0], s.ls[1], 22) + circle(s.ls[0], s.ls[1], 11)) +
            g('rs', circle(s.rs[0], s.rs[1], 22) + circle(s.rs[0], s.rs[1], 11)) +
            g('dpup', rect(dx - 6, dy - 22, 12, 16, 3)) + g('dpdown', rect(dx - 6, dy + 6, 12, 16, 3)) +
            g('dpleft', rect(dx - 22, dy - 6, 16, 12, 3)) + g('dpright', rect(dx + 6, dy - 6, 16, 12, 3)) +
            face('a', 0, 20) + face('b', 20, 0) + face('x', -20, 0) + face('y', 0, -20) +
            g('back', circle(s.back[0], s.back[1], 6)) + g('start', circle(s.start[0], s.start[1], 6)) +
            g('guide', circle(s.guide[0], s.guide[1], s.guide[2])) +
            `</svg>`;
    }

    // ── State ─────────────────────────────────────────────────────────────────
    const W = { open: false, padId: null, shape: 'xbox', style: 'xbox', steps: ALL_STEPS, i: -1, rec: {}, base: [], prev: new Set(),
                phase: 'listen', after: 'advance', det: null, calmSince: 0, releaseSince: 0, sig: '', lastChange: 0, raf: null, notice: '' };
    const $ = id => document.getElementById(id);
    const rawPad = () => (typeof _firstGamepad === 'function' ? _firstGamepad(true) : null);
    const stepNow = () => W.steps[W.i];

    function styleFor(id) {
        const saved = (window._GAMEPAD_LAYOUTS || {})[id];
        if (saved && saved.style) return saved.style;
        return typeof _labelStyleFor === 'function' ? _labelStyleFor(id) : 'xbox';
    }

    // The sources a layout already has, keyed by SDL field name.
    function recFromMap(map) {
        const rec = {};
        for (const field of String(map || '').split(',')) {
            const [k, v] = field.split(':');
            const src = PDLayout.parseSource(v);
            if (src && (k in PDLayout.STD_BUTTONS || k in PDLayout.STD_AXES)) rec[k] = src;
        }
        return rec;
    }

    function mapFromRec(rec) {
        const order = [...Object.keys(PDLayout.STD_BUTTONS), ...Object.keys(PDLayout.STD_AXES)];
        return order.filter(k => rec[k]).map(k => `${k}:${PDLayout.sourceToString(rec[k])}`).join(',');
    }

    // Raw buttons and axes already given to another control.
    function usedBy(exceptId) {
        const buttons = new Map(), axes = new Map();
        for (const [k, s] of Object.entries(W.rec)) {
            if (k === exceptId) continue;
            if (s.t === 'b') buttons.set(s.i, k); else if (s.t === 'a') axes.set(s.i, k);
        }
        return { buttons, axes };
    }

    // ── Rendering ─────────────────────────────────────────────────────────────
    function showView(name) {
        for (const v of ['setup', 'steps']) $('gpw-' + v).style.display = v === name ? '' : 'none';
    }

    function render() {
        const stepsView = W.i >= 0;
        showView(stepsView ? 'steps' : 'setup');
        const done = W.i >= W.steps.length;
        $('gpw-back').style.display = stepsView && W.i > 0 ? '' : 'none';
        $('gpw-skip').style.display = stepsView && !done ? '' : 'none';
        $('gpw-save').style.display = stepsView ? '' : 'none';
        $('gpw-start').style.display = stepsView ? 'none' : '';
        if (!stepsView) {
            $('gpw-setup-diagram').innerHTML = diagram(W.shape, W.style, []);
            for (const key of ['xbox', 'ps', 'retro']) $('gpw-shape-' + key).classList.toggle('gpw-on', W.shape === key);
            for (const key of ['xbox', 'ps', 'nintendo', 'other']) $('gpw-style-' + key).classList.toggle('gpw-on', W.style === key);
            return;
        }
        const step = done ? null : stepNow();
        $('gpw-diagram').innerHTML = diagram(W.shape, W.style, step ? step.hl : []);
        $('gpw-progress').textContent = done ? 'All steps done' : `Step ${W.i + 1} of ${W.steps.length}`;
        $('gpw-caption').textContent = done ? 'That is every control. Save to use this layout.' : step.text;
        $('gpw-hint').textContent = done ? '' : (step.hint || '');
        const have = step && W.rec[step.id];
        $('gpw-current').textContent = have ? `Currently set. Skip keeps it.` : '';
        $('gpw-notice').textContent = W.notice;
    }

    function notice(msg) { W.notice = msg; const el = $('gpw-notice'); if (el) el.textContent = msg; }

    // ── Detection ─────────────────────────────────────────────────────────────
    function pressedSet(pad) {
        const s = new Set();
        pad.buttons.forEach((b, i) => { if (b.pressed || b.value > 0.5) s.add(i); });
        return s;
    }

    function beginStep(pad) {
        W.base = Array.from(pad.axes);
        W.prev = pressedSet(pad);
        W.phase = W.prev.size ? 'release' : 'listen';   // a button still held from before must be let go first
        W.after = 'listen';
        W.releaseSince = 0;
        W.det = null;
        W.calmSince = 0;
        notice('');
        render();
    }

    // A control back near where it started: a stick centred, a trigger at rest, or unchanged.
    // -1 counts as rest only for a trigger (loose, used while telling what a moved axis is).
    const settled = (v, base) => Math.abs(v - base) < 0.3 || v < -0.9 || Math.abs(v) < 0.3;

    function commit(src) {
        W.rec[stepNow().id] = src;
        W.phase = 'release';
        W.after = 'advance';
        W.calmSince = 0;
        W.releaseSince = 0;
        notice('Got it. Let go.');
    }

    function advance(pad) { W.i++; if (W.i >= W.steps.length) { W.phase = 'done'; render(); } else beginStep(pad); }

    // The axis that moved furthest from where it started, not already used by another control.
    // restReports: an axis that has never moved reads 0, and when it first reports it often jumps
    // straight to -1 (a trigger telling us where it rests). That is not a pull, so it only updates
    // the baseline. Pulling a trigger the user is asked about goes towards +1, so nothing is lost.
    function movedAxis(pad, threshold, skip, restReports) {
        let best = null;
        pad.axes.forEach((v, i) => {
            if (skip.has(i)) return;
            if (restReports && (W.base[i] || 0) === 0 && v <= -0.99) { W.base[i] = v; return; }
            const d = v - (W.base[i] || 0);
            if (Math.abs(d) > threshold && (!best || Math.abs(d) > Math.abs(best.d))) best = { i, d, v };
        });
        return best;
    }

    function hatHasBeenSet() { return Object.values(W.rec).some(s => s.t === 'h'); }

    function listen(pad) {
        const step = stepNow(), used = usedBy(step.id), now = pressedSet(pad);
        // A button pressed since the last frame (used by buttons, triggers and d-pads).
        const fresh = [...now].filter(i => !W.prev.has(i));
        W.prev = now;
        if (fresh.length && step.kind !== 'stick') {
            const idx = fresh[0];
            if (used.buttons.has(idx)) { notice(`That button is already set as ${FIELD_LABEL[used.buttons.get(idx)] || 'another control'}. Press a different one, or skip.`); return; }
            commit({ t: 'b', i: idx, half: 0, inv: false, mask: 0 });
            return;
        }
        const skipAxes = new Set(used.axes.keys());
        // Once the d-pad is a hat, its two axes are not a stick or trigger (but the d-pad steps still read them).
        if (step.kind !== 'dpad' && hatHasBeenSet()) { skipAxes.add(pad.axes.length - 2); skipAxes.add(pad.axes.length - 1); }

        if (step.kind === 'stick') {
            const m = movedAxis(pad, 0.6, skipAxes);
            if (m) commit({ t: 'a', i: m.i, half: 0, inv: m.d < 0, mask: 0 });   // right and down read positive on a normal axis
        } else if (step.kind === 'trigger') {
            const m = movedAxis(pad, 0.5, skipAxes, true);
            if (m) { W.det = { axis: m.i, sign: m.d > 0 ? 1 : -1, peak: m.v }; W.phase = 'trigger'; notice('Now let go.'); }
        } else if (step.kind === 'dpad') {
            const m = movedAxis(pad, 0.5, skipAxes);
            if (!m) return;
            const n = pad.axes.length, isX = m.i === n - 2, isY = m.i === n - 1;
            if (isX || isY) {   // a hat: the last two axes
                const dir = isX ? (m.d > 0 ? 'right' : 'left') : (m.d > 0 ? 'down' : 'up');
                if (dir !== step.dir) { notice(`That was ${dir}. Press ${step.dir} on the d-pad.`); W.phase = 'release'; W.after = 'listen'; W.releaseSince = 0; return; }
                commit({ t: 'h', i: 0, half: 0, inv: false, mask: { up: 1, right: 2, down: 4, left: 8 }[dir] });
            } else {
                commit({ t: 'a', i: m.i, half: m.d > 0 ? 1 : -1, inv: false, mask: 0 });
            }
        }
    }

    // A trigger on an axis: once let go, an axis back at -1 is a full-range trigger, one back at 0 is a half axis.
    // Let go is "back at a rest value we recognise", or, for a pad that rests somewhere else,
    // "has stopped changing and is clearly away from where it peaked".
    function finishTrigger(pad, quiet) {
        const { axis, sign } = W.det, v = pad.axes[axis], base = W.base[axis] || 0;
        if (Math.abs(v - base) > Math.abs(W.det.peak - base)) W.det.peak = v;
        if (!settled(v, base) && !(quiet && Math.abs(v - W.det.peak) > 0.3)) return false;
        commit(v < -0.9 ? { t: 'a', i: axis, half: 0, inv: false, mask: 0 } : { t: 'a', i: axis, half: sign, inv: false, mask: 0 });
        return true;
    }

    // What is keeping the pad from counting as let go, for the on-screen hint.
    function blocker(pad) {
        const held = [...pressedSet(pad)];
        if (held.length) return `button ${held[0]} still reads as held`;
        const i = pad.axes.findIndex((v, k) => Math.abs(v - (W.base[k] || 0)) >= 0.3 && Math.abs(v) >= 0.3);
        return i >= 0 ? `axis ${i} reads ${pad.axes[i].toFixed(2)}` : 'the controller has not settled';
    }

    // Everything let go. An axis at -1 is at rest only if it is a trigger already recorded as a
    // full-range axis; for anything else (a d-pad held up) -1 is a held direction.
    function released(pad) {
        if (pressedSet(pad).size) return false;
        const triggers = new Set(['lefttrigger', 'righttrigger'].map(k => W.rec[k]).filter(s => s && s.t === 'a' && s.half === 0).map(s => s.i));
        return pad.axes.every((v, i) => Math.abs(v - (W.base[i] || 0)) < 0.3 || Math.abs(v) < 0.3 || (v < -0.9 && triggers.has(i)));
    }

    function tick() {
        W.raf = requestAnimationFrame(tick);
        if (!W.open || W.i < 0 || W.i >= W.steps.length) return;
        const pad = rawPad();
        if (!pad || pad.id !== W.padId) { notice('Controller not detected. Press a button on it.'); return; }
        const t = performance.now();
        // Has anything on the pad changed lately? A pad that rests at an unexpected value still goes quiet.
        const sig = pad.axes.map(v => Math.round(v * 10)).join(',') + '|' + [...pressedSet(pad)].join(',');
        if (sig !== W.sig) { W.sig = sig; W.lastChange = t; }
        const quiet = t - W.lastChange > 600;

        if (W.phase === 'listen') listen(pad);
        else if (W.phase === 'trigger') { if (finishTrigger(pad, quiet)) { W.prev = pressedSet(pad); } }
        else if (W.phase === 'release') {
            if (released(pad) || (quiet && !pressedSet(pad).size)) {
                if (!W.calmSince) W.calmSince = t;
                if (t - W.calmSince > 180) {
                    if (W.after === 'advance') advance(pad);
                    else { W.base = Array.from(pad.axes); W.prev = pressedSet(pad); W.phase = 'listen'; }
                }
            } else {
                W.calmSince = 0;
                if (!W.releaseSince) W.releaseSince = t;
                if (t - W.releaseSince > 1500) notice(`Waiting for the controller to settle (${blocker(pad)}). Use Skip if it won't.`);
            }
        }
    }

    // ── Public actions ────────────────────────────────────────────────────────
    window.gpwOpen = function () {
        const pad = rawPad();
        if (!pad) { alert('No controller detected. Press a button on it with Gamepad Diagnostics open, then try again.'); return; }
        const info = PDLayout.info(pad);
        W.padId = pad.id;
        W.rec = recFromMap(info.map || '');
        W.style = styleFor(pad.id);
        W.shape = W.style === 'ps' ? 'ps' : 'xbox';
        W.i = -1; W.phase = 'listen'; W.notice = '';
        W.open = true;
        $('gamepad-wizard-modal').style.display = 'flex';
        render();
        if (!W.raf) W.raf = requestAnimationFrame(tick);
    };

    window.closeGamepadWizard = function () {
        W.open = false;
        $('gamepad-wizard-modal').style.display = 'none';
        if (W.raf) { cancelAnimationFrame(W.raf); W.raf = null; }
    };

    window.gpwSetShape = function (shape) { W.shape = shape; render(); };
    window.gpwSetStyle = function (style) { W.style = style; render(); };

    window.gpwStart = function () {
        const pad = rawPad();
        if (!pad) return;
        W.steps = stepsFor(W.shape);
        W.i = 0;
        beginStep(pad);
    };

    window.gpwSkip = function () { const pad = rawPad(); if (pad && W.i < W.steps.length) advance(pad); };
    window.gpwBack = function () { const pad = rawPad(); if (pad && W.i > 0) { W.i = Math.min(W.i, W.steps.length) - 1; beginStep(pad); } };

    window.gpwSave = function () {
        const pad = rawPad();
        const need = ['a', 'b'].filter(k => !W.rec[k]);
        const hasMove = ['dpup', 'dpdown', 'dpleft', 'dpright'].every(k => W.rec[k]) || (W.rec.leftx && W.rec.lefty);
        if (need.length || !hasMove) {
            notice('Set at least the bottom and right face buttons, and either the d-pad or the left stick, so the app can be navigated.');
            return;
        }
        const map = mapFromRec(W.rec), layout = PDLayout.parse(map);
        if (!layout || (pad && !PDLayout.fits(layout, pad))) { notice("That layout doesn't match this controller. Try again."); return; }
        PDLayout.save(W.padId, { kind: 'map', map, style: W.style });
        window.closeGamepadWizard();
        if (typeof _gpdLayoutSig !== 'undefined') _gpdLayoutSig = '';   // redraw the chooser
    };

    document.addEventListener('keydown', e => { if (e.key === 'Escape' && W.open) { e.stopPropagation(); window.closeGamepadWizard(); } }, true);

    // Exposed for tests.
    window.PDWizard = { stepsFor, diagram, recFromMap, mapFromRec, state: W };
})();
