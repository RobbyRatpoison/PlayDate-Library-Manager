// Gamepad layout wizard (Gamepad Setup > Controller layout > Set up custom layout).
//
// A controller is drawn as a body outline with controls placed on it (d-pad, sticks, face buttons,
// bumpers, triggers, center buttons, other buttons). The user picks a body and arranges the parts by
// dragging them, so any pad can be represented (NES, Genesis, N64, GameCube, fight pads...). The
// wizard then walks the placed parts one at a time, highlighting each on the drawing and waiting for
// it on the real pad; the result is saved per controller as an SDL mapping string (see
// gamepad_layout.js) plus the drawing itself (`shape` and `parts` in state.json's gamepad_layouts).
// Every step can be skipped, and it starts from the layout currently in use.
//
// What a part is recorded as depends on its type and position (derive()): the first bumper on each
// side is the standard left/right shoulder, the sticks are left then right by position, the center
// buttons are Back / Guide / Start by position, a face button is whichever of Confirm / Back / Menu /
// Edit (SDL a, b, x, y) the user marks it as, and anything else is an extra raw button.
(function () {
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const VB_W = 400, VB_H = 244;

    // ── Bodies ────────────────────────────────────────────────────────────────
    // path = the outline; starter() = the parts a fresh drawing of that body starts with (all editable).
    const part = (type, x, y, extra) => Object.assign({ type, x, y }, extra || {});
    const faceDiamond = (cx, cy, d, roles) => [
        part('face', cx, cy + d, roles ? { role: 'a' } : {}), part('face', cx + d, cy, roles ? { role: 'b' } : {}),
        part('face', cx - d, cy, roles ? { role: 'x' } : {}), part('face', cx, cy - d, roles ? { role: 'y' } : {}),
    ];
    const GAMEPAD_BODY = 'M60,70 Q60,40 100,40 L300,40 Q340,40 340,70 L362,188 Q366,232 330,232 Q300,232 285,198 L262,172 L138,172 L115,198 Q100,232 70,232 Q34,232 38,188 Z';
    const BODIES = {
        xbox: {
            label: 'Gamepad (Xbox-style)', path: GAMEPAD_BODY,
            starter: () => [...faceDiamond(288, 98, 20, true),
                part('shoulder', 105, 28), part('shoulder', 295, 28), part('trigger', 105, 11), part('trigger', 295, 11),
                part('stick', 112, 96), part('dpad', 148, 152), part('stick', 252, 152),
                part('center', 172, 100), part('center', 200, 74), part('center', 228, 100)],
        },
        ps: {
            label: 'Gamepad (PlayStation-style)', path: GAMEPAD_BODY,
            starter: () => [...faceDiamond(288, 98, 20, true),
                part('shoulder', 105, 28), part('shoulder', 295, 28), part('trigger', 105, 11), part('trigger', 295, 11),
                part('dpad', 112, 100), part('stick', 152, 158), part('stick', 248, 158),
                part('center', 168, 92), part('center', 200, 176), part('center', 232, 92)],
        },
        retro: {
            label: 'Rounded retro pad (SNES, Genesis, Saturn)',
            path: 'M44,70 Q44,44 76,44 L324,44 Q356,44 356,70 L356,170 Q356,212 316,212 L84,212 Q44,212 44,170 Z',
            starter: () => [part('dpad', 103, 110), ...faceDiamond(296, 112, 22, true),
                part('shoulder', 100, 28), part('shoulder', 300, 28), part('center', 172, 176), part('center', 228, 176)],
        },
        wide: {
            label: 'Wide pad (6 buttons, arcade)',
            path: 'M30,60 Q30,44 46,44 L354,44 Q370,44 370,60 L370,200 Q370,216 354,216 L46,216 Q30,216 30,200 Z',
            starter: () => [part('dpad', 90, 122), part('face', 230, 100), part('face', 270, 100), part('face', 310, 100),
                part('face', 230, 142), part('face', 270, 142), part('face', 310, 142), part('center', 170, 190), part('center', 230, 190)],
        },
        box: {
            label: 'Square box (old joystick)',
            path: 'M80,50 Q80,40 90,40 L310,40 Q320,40 320,50 L320,200 Q320,210 310,210 L90,210 Q80,210 80,200 Z',
            starter: () => [part('stick', 150, 130), part('face', 250, 150), part('face', 290, 110)],
        },
        n64: {
            label: 'Three-prong (N64)',
            path: 'M30,70 Q30,40 70,40 L330,40 Q370,40 370,70 L370,190 Q370,228 340,228 Q312,228 308,196 L300,150 L260,150 L250,224 Q248,232 240,232 L160,232 Q152,232 150,224 L140,150 L100,150 L92,196 Q88,228 60,228 Q30,228 30,190 Z',
            starter: () => [part('dpad', 78, 100), part('stick', 200, 112), part('center', 200, 64),
                part('face', 322, 150), part('face', 296, 128),
                part('other', 340, 66, { label: 'C↑' }), part('other', 340, 114, { label: 'C↓' }),
                part('other', 316, 90, { label: 'C←' }), part('other', 364, 90, { label: 'C→' }),
                part('shoulder', 80, 28), part('shoulder', 320, 28), part('trigger', 200, 200)],
        },
        blank: {
            label: 'Blank', path: 'M50,60 Q50,44 66,44 L334,44 Q350,44 350,60 L350,196 Q350,212 334,212 L66,212 Q50,212 50,196 Z',
            starter: () => [],
        },
    };
    const BODY_ORDER = ['xbox', 'ps', 'retro', 'wide', 'box', 'n64', 'blank'];
    const PART_NAMES = { dpad: 'D-pad', stick: 'Stick', face: 'Face button', shoulder: 'Bumper', trigger: 'Trigger', center: 'Center button', other: 'Other button' };
    const PART_LIMIT = { dpad: 1, stick: 2 };
    const ROLES = { a: 'Confirm', b: 'Back', x: 'Menu', y: 'Edit' };

    const clone = parts => parts.map(p => Object.assign({}, p));

    // ── What each placed part records ─────────────────────────────────────────
    // Returns one entry per part: { kind: 'btn'|'extra'|'trig'|'dpad'|'stick', field?, fields? }.
    // A part with an explicit `field` (drawings built in memory from a layout) keeps it.
    function derive(parts) {
        const info = parts.map(() => ({ kind: 'extra' }));
        const sortedIdx = type => parts.map((p, i) => i).filter(i => parts[i].type === type).sort((a, b) => parts[a].x - parts[b].x);
        const sideOf = (i, count) => (count === 1 && parts[i].type === 'stick') || parts[i].x < VB_W / 2 ? 'left' : 'right';

        for (const type of ['shoulder', 'trigger']) {
            const taken = new Set();
            for (const i of sortedIdx(type)) {
                const side = sideOf(i, 2);
                if (taken.has(side)) continue;
                taken.add(side);
                info[i] = type === 'shoulder' ? { kind: 'btn', field: side + 'shoulder' } : { kind: 'trig', field: side + 'trigger' };
            }
        }
        sortedIdx('stick').slice(0, 2).forEach((i, n, all) => {
            const side = all.length === 1 ? 'left' : (n === 0 ? 'left' : 'right');
            info[i] = { kind: 'stick', fields: { x: side + 'x', y: side + 'y', click: side + 'stick' } };
        });
        sortedIdx('dpad').slice(0, 1).forEach(i => { info[i] = { kind: 'dpad', fields: { up: 'dpup', down: 'dpdown', left: 'dpleft', right: 'dpright' } }; });
        const centers = sortedIdx('center'), n = centers.length;
        centers.forEach((i, k) => {
            const field = n === 1 ? 'start' : k === 0 ? 'back' : k === n - 1 ? 'start' : k === 1 ? 'guide' : null;
            if (field) info[i] = { kind: 'btn', field };
        });
        const roleUsed = new Set();
        parts.forEach((p, i) => {
            if (p.type === 'face' && p.role && !roleUsed.has(p.role)) { roleUsed.add(p.role); info[i] = { kind: 'btn', field: p.role }; }
        });
        // An explicit field wins (a drawing built from a layout).
        parts.forEach((p, i) => {
            if (!p.field) return;
            info[i] = p.fields ? { kind: p.type === 'dpad' ? 'dpad' : 'stick', fields: p.fields }
                : { kind: /trigger$/.test(p.field) ? 'trig' : 'btn', field: p.field };
        });
        return info;
    }

    // Every recordable slot of the drawing: { key: 'p3.up', i: part index, sub, field|null }.
    function slotsOf(parts) {
        const info = derive(parts), out = [];
        parts.forEach((p, i) => {
            const d = info[i];
            if (d.kind === 'dpad') for (const sub of ['up', 'down', 'left', 'right']) out.push({ key: `p${i}.${sub}`, i, sub, field: d.fields[sub] });
            else if (d.kind === 'stick') for (const sub of ['x', 'y', 'click']) out.push({ key: `p${i}.${sub}`, i, sub, field: d.fields[sub] });
            else out.push({ key: `p${i}`, i, sub: '', field: d.field || null });
        });
        return out;
    }

    // ── Drawing ───────────────────────────────────────────────────────────────
    const FACE_LABELS = {
        xbox: { a: 'A', b: 'B', x: 'X', y: 'Y' }, ps: { a: '✕', b: '○', x: '□', y: '△' },
        nintendo: { a: 'B', b: 'A', x: 'Y', y: 'X' }, other: {},
    };
    const FACE_COLORS = {
        xbox: { a: '#3bb143', b: '#e0393e', x: '#3a7bd5', y: '#f4c20d' },
        ps: { a: '#3a7bd5', b: '#e0393e', x: '#e05fa0', y: '#3bb143' },
    };
    const PS_SYMBOLS = {
        a: (x, y) => `M${x - 4},${y - 4}L${x + 4},${y + 4}M${x + 4},${y - 4}L${x - 4},${y + 4}`,            // cross
        b: (x, y) => `M${x - 5},${y}a5,5 0 1,0 10,0a5,5 0 1,0 -10,0`,                                    // circle
        x: (x, y) => `M${x - 4},${y - 4}h8v8h-8Z`,                                                        // square
        y: (x, y) => `M${x},${y - 5}L${x + 5},${y + 3.5}L${x - 5},${y + 3.5}Z`,                          // triangle
    };
    const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // drawing = { shape, parts }; highlight = keys ('p3', 'p3.up') to pulse; opts.selected = part index.
    function diagram(drawing, style, highlight, opts) {
        opts = opts || {};
        const shape = BODIES[drawing.shape] ? drawing.shape : 'xbox', parts = drawing.parts || [];
        const hl = new Set(highlight || []), info = derive(parts), STD = (window.PDLayout && PDLayout.STD_BUTTONS) || {};
        const g = (key, inner, attrs) => `<g data-ctl="${key}" class="gpw-ctl${hl.has(key) ? ' gpw-hl' : ''}"${attrs || ''}>${inner}</g>`;
        const circle = (cx, cy, r) => `<circle cx="${cx}" cy="${cy}" r="${r}"/>`;
        const rect = (x, y, w, h, r = 4) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"/>`;
        // What a live frame reads for a button-like control: a standard button number, or a raw one for an extra.
        const btnAttr = (d, p) => {
            if (d.field && d.field in STD) return ` data-btn="${STD[d.field]}"${d.kind === 'trig' ? ' data-trig="1"' : ''}`;
            return p.raw != null ? ` data-raw="${p.raw}"` : '';
        };
        const body = parts.map((p, i) => {
            const d = info[i], k = 'p' + i, x = p.x, y = p.y;
            let inner;
            if (p.type === 'dpad') {
                const at = sub => d.fields ? ` data-btn="${STD[d.fields[sub]]}"` : '';
                inner = g(`${k}.up`, rect(x - 6, y - 22, 12, 16, 3), at('up')) + g(`${k}.down`, rect(x - 6, y + 6, 12, 16, 3), at('down')) +
                        g(`${k}.left`, rect(x - 22, y - 6, 16, 12, 3), at('left')) + g(`${k}.right`, rect(x + 6, y - 6, 16, 12, 3), at('right'));
            } else if (p.type === 'stick') {
                const ax = d.fields && d.fields.x === 'rightx' ? '2,3' : '0,1';
                const click = d.fields ? ` data-btn="${STD[d.fields.click]}"` : '';
                inner = g(`${k}.x`, circle(x, y, 22) + `<circle data-stick="${ax}" cx="${x}" cy="${y}" r="11"/>`, click);
            } else if (p.type === 'shoulder') {
                inner = g(k, rect(x - 39, y - 6, 78, 13), btnAttr(d, p));
            } else if (p.type === 'trigger') {
                inner = g(k, rect(x - 27, y - 7, 54, 14, 6), btnAttr(d, p));
            } else if (p.type === 'center') {
                inner = g(k, circle(x, y, 6), btnAttr(d, p));
            } else {   // face, other
                const role = p.type === 'face' && !p.label ? p.role : null;
                const label = p.label || (role ? (FACE_LABELS[style] || {})[role] || '' : '');
                const color = role ? (FACE_COLORS[style] || {})[role] : null;
                // PlayStation symbols are drawn as shapes: font glyphs of them differ in size and baseline and look small and off-centre.
                const symbol = style === 'ps' && role ? PS_SYMBOLS[role](x, y) : null;
                inner = g(k, circle(x, y, 10) + (symbol ? `<path class="gpw-sym" d="${symbol}" style="stroke:${color}"/>` :
                    label ? `<text class="gpw-lbl" x="${x}" y="${y + 4}" text-anchor="middle"${color ? ` style="fill:${color}"` : ''}>${esc(label)}</text>` : ''), btnAttr(d, p));
            }
            return `<g class="gpw-part${opts.selected === i ? ' gpw-sel' : ''}" data-part="${i}">${inner}</g>`;
        }).join('');
        return `<svg class="gpw-svg" viewBox="0 0 ${VB_W} ${VB_H}" xmlns="${SVG_NS}" role="img" aria-label="Controller drawing">` +
            `<path class="gpw-body" d="${BODIES[shape].path}"/>${body}</svg>`;
    }

    // ── The drawing a pad has ─────────────────────────────────────────────────
    // The saved one, else the starter for a shape picked by rule (PlayStation pad -> PlayStation gamepad,
    // layout without a left stick -> rounded retro, else Xbox-style) with the controls the layout in use
    // doesn't have left out. `map` is the SDL string of the layout in use.
    function drawingFor(padId, style, map) {
        const saved = (window._GAMEPAD_LAYOUTS || {})[padId] || {};
        if (saved.parts && saved.parts.length) return { shape: saved.shape || 'xbox', parts: clone(saved.parts) };
        const shape = saved.shape || (style === 'ps' ? 'ps' : (map && !/(^|,)leftx:/.test(map) ? 'retro' : 'xbox'));
        const parts = BODIES[shape].starter();
        if (!map) return { shape, parts };
        const have = new Set(String(map).split(',').map(f => f.split(':')[0]));
        const info = derive(parts), kept = [];
        parts.forEach((p, i) => {
            const d = info[i];
            if (d.kind === 'dpad') { if (have.has('dpup')) kept.push(Object.assign({}, p, { field: 'dpup', fields: d.fields })); }
            else if (d.kind === 'stick') { if (have.has(d.fields.x)) kept.push(Object.assign({}, p, { field: d.fields.x, fields: d.fields })); }
            else if (d.field) { if (have.has(d.field)) kept.push(Object.assign({}, p, { field: d.field })); }
            else kept.push(p);
        });
        return { shape, parts: kept };
    }

    // ── State ─────────────────────────────────────────────────────────────────
    const W = { open: false, padId: null, map: '', fresh: new Set(), shape: 'xbox', style: 'xbox', parts: [], dirty: false, sel: null, steps: [], i: -1, rec: {}, base: [],
                prev: new Set(), phase: 'listen', after: 'advance', det: null, calmSince: 0, releaseSince: 0, sig: '', lastChange: 0, raf: null, notice: '' };
    const $ = id => document.getElementById(id);
    const rawPad = () => (typeof _firstGamepad === 'function' ? _firstGamepad(true) : null);
    const stepNow = () => W.steps[W.i];
    const toast = msg => { if (typeof showLaunchToast === 'function') showLaunchToast(msg); };

    function styleFor(id) {
        const saved = (window._GAMEPAD_LAYOUTS || {})[id];
        if (saved && saved.style) return saved.style;
        return typeof _labelStyleFor === 'function' ? _labelStyleFor(id) : 'xbox';
    }

    // The sources a layout already has, keyed by slot, plus each extra part's saved raw button.
    function recFromLayout(map) {
        const bySdl = {};
        for (const field of String(map || '').split(',')) {
            const [k, v] = field.split(':');
            const src = PDLayout.parseSource(v);
            if (src && (k in PDLayout.STD_BUTTONS || k in PDLayout.STD_AXES)) bySdl[k] = src;
        }
        const rec = {};
        for (const s of slotsOf(W.parts)) {
            if (s.field) { if (bySdl[s.field]) rec[s.key] = bySdl[s.field]; }
            else if (W.parts[s.i].raw != null) rec[s.key] = { t: 'b', i: W.parts[s.i].raw, half: 0, inv: false, mask: 0 };
        }
        return rec;
    }

    // Raw buttons and axes already given to another slot *in this run*. What the layout in use had for
    // controls not visited yet does not count: on a pad whose triggers share an axis with a stick, the
    // control being asked about would otherwise be ignored and the step could never finish.
    function usedBy(exceptKey) {
        const buttons = new Map(), axes = new Map();
        for (const [k, s] of Object.entries(W.rec)) {
            if (k === exceptKey || !W.fresh.has(k)) continue;
            if (s.t === 'b') buttons.set(s.i, k); else if (s.t === 'a') axes.set(s.i, k);
        }
        return { buttons, axes };
    }

    // ── Steps ─────────────────────────────────────────────────────────────────
    function stepsFor(parts) {
        const info = derive(parts), steps = [];
        parts.forEach((p, i) => {
            const k = 'p' + i, d = info[i], what = p.label ? `the ${p.label} button` : null;
            if (p.type === 'dpad' && d.kind === 'dpad') {
                for (const dir of ['up', 'down', 'left', 'right']) steps.push({ key: `${k}.${dir}`, kind: 'dpad', dir, hl: [`${k}.${dir}`], text: `Press ${dir} on the d-pad` });
            } else if (p.type === 'stick' && d.kind === 'stick') {
                steps.push({ key: `${k}.x`, kind: 'stick', hl: [`${k}.x`], text: 'Push the highlighted stick all the way right' });
                steps.push({ key: `${k}.y`, kind: 'stick', hl: [`${k}.x`], text: 'Push the highlighted stick all the way down' });
                steps.push({ key: `${k}.click`, kind: 'button', hl: [`${k}.x`], text: 'Click the highlighted stick in', hint: 'L3 / R3. Skip if it has no click' });
            } else if (p.type === 'trigger') {
                steps.push({ key: k, kind: d.kind === 'trig' ? 'trigger' : 'button', hl: [k], text: 'Pull the highlighted trigger all the way', hint: 'A trigger that is really a button is fine too' });
            } else {
                const role = p.type === 'face' && p.role ? ROLES[p.role] : null;
                const text = p.type === 'shoulder' ? 'Press the highlighted bumper' : p.type === 'center' ? 'Press the highlighted center button' : `Press ${what || 'the highlighted button'}`;
                steps.push({ key: k, kind: 'button', hl: [k], text, hint: role ? `This one will be ${role}` : (p.type === 'face' ? 'Choose its job after the steps' : '') });
            }
        });
        return steps;
    }

    // ── Rendering ─────────────────────────────────────────────────────────────
    function showView(name) {
        for (const v of ['setup', 'steps']) $('gpw-' + v).style.display = v === name ? '' : 'none';
    }

    const drawing = () => ({ shape: W.shape, parts: W.parts });
    const isDone = () => W.i >= W.steps.length && W.i >= 0;

    function render() {
        const stepsView = W.i >= 0;
        showView(stepsView ? 'steps' : 'setup');
        const done = isDone();
        $('gpw-back').style.display = stepsView && W.i > 0 ? '' : 'none';
        $('gpw-skip').style.display = stepsView && !done ? '' : 'none';
        $('gpw-save').style.display = stepsView ? '' : 'none';
        $('gpw-start').style.display = stepsView ? 'none' : '';
        $('gpw-edit-again').style.display = done ? '' : 'none';
        if (!stepsView) {
            $('gpw-setup-diagram').innerHTML = diagram(drawing(), W.style, [], { selected: W.sel });
            for (const key of BODY_ORDER) $('gpw-shape-' + key).classList.toggle('gpw-on', W.shape === key);
            for (const key of ['xbox', 'ps', 'nintendo', 'other']) $('gpw-style-' + key).classList.toggle('gpw-on', W.style === key);
            renderInspector('gpw-inspector');
            return;
        }
        const step = done ? null : stepNow();
        $('gpw-diagram').innerHTML = diagram(drawing(), W.style, step ? step.hl : [], { selected: done ? W.sel : null });
        $('gpw-progress').textContent = done ? 'All steps done' : `Step ${W.i + 1} of ${W.steps.length}`;
        $('gpw-caption').textContent = done ? 'That is every control.' : step.text;
        $('gpw-hint').textContent = done ? '' : (step.hint || '');
        const have = step && W.rec[step.key];
        $('gpw-current').textContent = have ? `Currently set. Skip keeps it.` : '';
        $('gpw-notice').textContent = W.notice;
        renderInspector('gpw-inspector-done');
    }

    function notice(msg) { W.notice = msg; const el = $('gpw-notice'); if (el) el.textContent = msg; }

    // The controls for the selected part (setup, and the finished screen for face-button jobs).
    function renderInspector(hostId) {
        const host = $(hostId);
        if (!host) return;
        const editing = hostId === 'gpw-inspector';
        if (!editing && !isDone()) { host.innerHTML = ''; return; }
        const p = W.sel != null ? W.parts[W.sel] : null;
        const btn = (label, call, on) => `<button class="nav-btn${on ? ' gpw-on' : ''}" data-modal-row="0" onclick="${call}" style="font-size:0.78rem; padding:3px 10px;">${label}</button>`;
        let html = '';
        if (!editing) {
            const faces = W.parts.filter(q => q.type === 'face').length;
            const hasConfirm = W.parts.some(q => q.type === 'face' && q.role === 'a');
            html += `<div style="font-size:0.8rem; color:var(--text-secondary); text-align:center; margin-bottom:6px;">` +
                (faces ? (hasConfirm ? 'Click a face button to change its job.' : 'Click a face button and choose which one confirms. Confirm is required.') : 'No face buttons were placed, so nothing can confirm. Use Edit drawing to add one.') + `</div>`;
        }
        if (p && (editing || p.type === 'face')) {
            html += `<div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:center;">` +
                `<span style="font-size:0.8rem; color:var(--text-primary);">${PART_NAMES[p.type]}</span>`;
            if (p.type === 'face') html += ['a', 'b', 'x', 'y'].map(r => btn(ROLES[r], `gpwSetRole('${r}')`, p.role === r)).join('') + btn('Extra', `gpwSetRole('')`, !p.role);
            if (p.type === 'other' && editing) html += `<input type="text" id="gpw-label" maxlength="12" data-modal-row="60" value="${esc(p.label || '')}" placeholder="Name (C, Z...)" oninput="gpwSetLabel(this.value)" style="width:120px; margin:0; font-size:0.85rem;">`;
            if (editing) html += btn('Remove', 'gpwRemove()');
            html += `</div>`;
        } else if (editing) {
            html += `<div style="font-size:0.8rem; color:var(--text-secondary); text-align:center;">Click a control to select it, drag it to move it. Add more with the buttons above.</div>`;
        }
        host.innerHTML = html;
    }

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
        const key = stepNow().key;
        // A recording wins over what the old layout had on the same button or axis for another control.
        for (const [k, o] of Object.entries(W.rec)) if (k !== key && !W.fresh.has(k) && o.t === src.t && o.i === src.i && src.t !== 'h') delete W.rec[k];
        W.rec[key] = src;
        W.fresh.add(key);
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
        const step = stepNow(), used = usedBy(step.key), now = pressedSet(pad);
        // A button pressed since the last frame (used by buttons, triggers and d-pads).
        const fresh = [...now].filter(i => !W.prev.has(i));
        W.prev = now;
        if (fresh.length && step.kind !== 'stick') {
            const idx = fresh[0];
            if (used.buttons.has(idx)) { notice('That button is already set for another control. Press a different one, or skip.'); return; }
            commit({ t: 'b', i: idx, half: 0, inv: false, mask: 0 });
            return;
        }
        const skipAxes = new Set(used.axes.keys());
        // Once the d-pad is a hat, its two axes are not a stick or trigger (but the d-pad steps still read them).
        if (step.kind !== 'dpad' && hatHasBeenSet()) { skipAxes.add(pad.axes.length - 2); skipAxes.add(pad.axes.length - 1); }

        // Some pads move the same axis for two controls (a trigger that also moves a stick axis). When nothing
        // free moves, an axis another control already took is accepted rather than leaving the step stuck.
        const reuse = new Set();   // axes to ignore in that second pass: the free ones (already tried) and a hat
        for (let i = 0; i < pad.axes.length; i++) if (!used.axes.has(i)) reuse.add(i);
        if (step.kind !== 'dpad' && hatHasBeenSet()) { reuse.add(pad.axes.length - 2); reuse.add(pad.axes.length - 1); }
        const moved = (thr, rest) => movedAxis(pad, thr, skipAxes, rest) || (used.axes.size ? movedAxis(pad, thr, reuse, rest) : null);

        if (step.kind === 'stick') {
            const m = moved(0.6);
            if (m) commit({ t: 'a', i: m.i, half: 0, inv: m.d < 0, mask: 0 });   // right and down read positive on a normal axis
        } else if (step.kind === 'trigger') {
            const m = moved(0.5, true);
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
        const triggers = new Set(Object.values(W.rec).filter(s => s.t === 'a' && s.half === 0).map(s => s.i));
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

    // ── Editing the drawing (mouse or touch) ──────────────────────────────────
    function toSvg(svg, ev) {
        const pt = svg.createSVGPoint();
        pt.x = ev.clientX; pt.y = ev.clientY;
        const m = svg.getScreenCTM();
        return m ? pt.matrixTransform(m.inverse()) : { x: 0, y: 0 };
    }

    function select(i) {
        W.sel = i;
        for (const host of ['gpw-setup-diagram', 'gpw-diagram']) {
            const el = $(host);
            if (el) el.querySelectorAll('.gpw-part').forEach(n => n.classList.toggle('gpw-sel', +n.dataset.part === i));
        }
        renderInspector(W.i >= 0 ? 'gpw-inspector-done' : 'gpw-inspector');
    }

    let drag = null;
    function onPointerDown(ev) {
        const host = W.open && ev.target.closest && ev.target.closest('#gpw-setup-diagram, #gpw-diagram');
        if (!host) return;
        const g = ev.target.closest('.gpw-part'), svg = host.querySelector('svg');
        if (!g || !svg) { if (W.sel != null) select(null); return; }
        const i = +g.dataset.part, p = W.parts[i];
        if (W.i >= 0 && !(isDone() && p.type === 'face')) return;   // while recording, only face buttons can be picked, once the steps are done
        select(i);
        if (W.i >= 0) return;
        const at = toSvg(svg, ev);
        drag = { i, g, svg, dx: p.x - at.x, dy: p.y - at.y, ox: p.x, oy: p.y, moved: false };
        if (svg.setPointerCapture) svg.setPointerCapture(ev.pointerId);
        ev.preventDefault();
    }
    function onPointerMove(ev) {
        if (!drag) return;
        const at = toSvg(drag.svg, ev), p = W.parts[drag.i];
        p.x = Math.max(0, Math.min(VB_W, Math.round(at.x + drag.dx)));
        p.y = Math.max(0, Math.min(VB_H, Math.round(at.y + drag.dy)));
        drag.moved = true;
        drag.g.setAttribute('transform', `translate(${p.x - drag.ox} ${p.y - drag.oy})`);
    }
    function onPointerUp() {
        if (!drag) return;
        const moved = drag.moved;
        drag = null;
        if (moved) { W.dirty = true; const keep = W.sel; render(); select(keep); }   // roles and sides depend on position
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', onPointerUp);
    document.addEventListener('pointercancel', onPointerUp);

    // ── Public actions ────────────────────────────────────────────────────────
    window.gpwOpen = function () {
        const pad = rawPad();
        if (!pad) { toast('No controller detected. Press a button on the controller, then try again.'); return; }
        const savedLayout = (window._GAMEPAD_LAYOUTS || {})[pad.id] || {};
        // A browser-mapped pad starts from the identity layout, not a database guess made for raw order.
        const info = pad.mapping === 'standard' && savedLayout.kind !== 'map' ? { map: PDLayout.STANDARD_MAP } : PDLayout.info(pad);
        W.padId = pad.id;
        W.style = styleFor(pad.id);
        const saved = (window._GAMEPAD_LAYOUTS || {})[pad.id] || {};
        const d = saved.parts && saved.parts.length ? drawingFor(pad.id, W.style, null) : { shape: saved.shape || (W.style === 'ps' ? 'ps' : 'xbox'), parts: null };
        W.shape = d.shape;
        W.parts = d.parts || BODIES[W.shape].starter();
        W.dirty = !!(saved.parts && saved.parts.length);
        W.sel = null;
        W.map = info.map || '';
        W.rec = recFromLayout(W.map);
        W.steps = []; W.i = -1; W.phase = 'listen'; W.notice = '';
        W.open = true;
        $('gamepad-wizard-modal').style.display = 'flex';
        render();
        if (!W.raf) W.raf = requestAnimationFrame(tick);
    };

    window.closeGamepadWizard = function () {
        W.open = false;
        drag = null;
        $('gamepad-wizard-modal').style.display = 'none';
        if (W.raf) { cancelAnimationFrame(W.raf); W.raf = null; }
    };

    window.gpwSetShape = function (shape) {
        if (!BODIES[shape] || shape === W.shape) return;
        const apply = () => { W.shape = shape; W.parts = BODIES[shape].starter(); W.dirty = false; W.sel = null; W.rec = recFromLayout(W.map); render(); };
        if (W.dirty && typeof confirmCustom === 'function') confirmCustom('Changing the shape replaces the controls you placed with that shape\'s starting arrangement.', 'Replace', 'Cancel').then(ok => { if (ok) apply(); });
        else apply();
    };
    window.gpwSetStyle = function (style) { W.style = style; render(); };

    window.gpwAdd = function (type) {
        if (PART_LIMIT[type] && W.parts.filter(p => p.type === type).length >= PART_LIMIT[type]) { toast(`A controller drawing has at most ${PART_LIMIT[type]} ${PART_NAMES[type].toLowerCase()}${PART_LIMIT[type] > 1 ? 's' : ''}.`); return; }
        if (W.parts.length >= 40) { toast('That is the most controls a drawing can hold.'); return; }
        const n = W.parts.length;
        W.parts.push({ type, x: 200 + (n % 5) * 16 - 32, y: 122 + (n % 4) * 14 - 20 });
        W.dirty = true;
        W.rec = remapRec(W.rec);
        W.sel = W.parts.length - 1;
        render();
    };

    // Recorded sources are keyed by part index, so they must follow the parts when one is removed.
    let rekeyMap = null;
    function remapRec(rec) {
        if (!rekeyMap) return rec;
        const out = {};
        for (const [k, v] of Object.entries(rec)) {
            const m = /^p(\d+)(.*)$/.exec(k), to = m ? rekeyMap.get(+m[1]) : null;
            if (to != null) out[`p${to}${m[2]}`] = v;
        }
        rekeyMap = null;
        return out;
    }

    window.gpwRemove = function () {
        if (W.sel == null) return;
        rekeyMap = new Map();
        W.parts.forEach((p, i) => { if (i < W.sel) rekeyMap.set(i, i); else if (i > W.sel) rekeyMap.set(i, i - 1); });
        W.parts.splice(W.sel, 1);
        W.rec = remapRec(W.rec);
        W.sel = null;
        W.dirty = true;
        render();
    };

    window.gpwSetRole = function (role) {
        const p = W.parts[W.sel];
        if (!p || p.type !== 'face') return;
        if (role) W.parts.forEach(q => { if (q !== p && q.role === role) delete q.role; });
        if (role) p.role = role; else delete p.role;
        W.dirty = true;
        W.notice = '';
        const keep = W.sel;
        render();
        select(keep);
    };

    window.gpwSetLabel = function (value) {
        const p = W.parts[W.sel];
        if (!p) return;
        const v = String(value).trim().slice(0, 12);
        if (v) p.label = v; else delete p.label;
        W.dirty = true;
        const host = $('gpw-setup-diagram');
        if (host) host.innerHTML = diagram(drawing(), W.style, [], { selected: W.sel });
    };

    window.gpwStart = function () {
        const pad = rawPad();
        if (!pad) return;
        W.steps = stepsFor(W.parts);
        if (!W.steps.length) { toast('Add at least one control to the drawing first.'); return; }
        W.sel = null;
        W.fresh = new Set();
        W.i = 0;
        beginStep(pad);
    };

    window.gpwEditAgain = function () { W.i = -1; W.sel = null; W.phase = 'listen'; notice(''); render(); };
    window.gpwSkip = function () { const pad = rawPad(); if (pad && W.i < W.steps.length) advance(pad); };
    window.gpwBack = function () { const pad = rawPad(); if (pad && W.i > 0) { W.i = Math.min(W.i, W.steps.length) - 1; beginStep(pad); } };

    window.gpwSave = function () {
        const pad = rawPad();
        const slots = slotsOf(W.parts), rec = {}, extras = [];
        const sdl = {};
        for (const s of slots) {
            const src = W.rec[s.key];
            if (!src) continue;
            if (s.field) sdl[s.field] = src; else if (src.t === 'b') extras.push([s.i, src.i]);
        }
        const hasMove = ['dpup', 'dpdown', 'dpleft', 'dpright'].every(k => sdl[k]) || (sdl.leftx && sdl.lefty);
        if (!sdl.a || !hasMove) {
            notice(!sdl.a ? 'Set a face button as Confirm (click it on the drawing), and record it, so the app can be navigated.'
                          : 'Record either the d-pad or the left stick, so the app can be navigated.');
            return;
        }
        const order = [...Object.keys(PDLayout.STD_BUTTONS), ...Object.keys(PDLayout.STD_AXES)];
        const map = order.filter(k => sdl[k]).map(k => `${k}:${PDLayout.sourceToString(sdl[k])}`).join(','), layout = PDLayout.parse(map);
        if (!layout || (pad && !PDLayout.fits(layout, pad))) { notice("That layout doesn't match this controller. Try again."); return; }
        // The drawing keeps each extra's raw button, so the live view lights it and a typed name can be saved against it.
        const parts = clone(W.parts).map(p => { delete p.raw; return p; });
        for (const [i, raw] of extras) parts[i].raw = raw;
        PDLayout.save(W.padId, { kind: 'map', map, style: W.style, shape: W.shape, parts });
        const names = Object.assign({}, ((window._GAMEPAD_LAYOUTS || {})[W.padId] || {}).names || {});
        for (const [i, raw] of extras) if (parts[i].label) names[String(raw)] = parts[i].label;
        PDLayout.setNames(W.padId, names);
        window.closeGamepadWizard();
        if (typeof _gpdLayoutSig !== 'undefined') _gpdLayoutSig = '';   // redraw the chooser
    };

    document.addEventListener('keydown', e => { if (e.key === 'Escape' && W.open) { e.stopPropagation(); window.closeGamepadWizard(); } }, true);

    // ── Live view (Gamepad Setup) ─────────────────────────────────────────────
    // Lights the controls that are pressed on a drawing made by diagram(), and moves the stick
    // thumbs. `pad` is the converted (standard-shaped) pad; an extra button is found through its raw
    // number (pad._pdRaw maps converted index -> raw).
    function liveUpdate(svg, pad) {
        if (!svg || !pad) return;
        const value = i => { const b = i >= 0 ? pad.buttons[i] : null; return b ? (typeof b.value === 'number' ? b.value : (b.pressed ? 1 : 0)) : 0; };
        svg.querySelectorAll('[data-btn],[data-raw]').forEach(el => {
            const i = el.dataset.btn !== undefined ? +el.dataset.btn : (pad._pdRaw ? pad._pdRaw.indexOf(+el.dataset.raw) : +el.dataset.raw);
            el.classList.toggle('gpw-live', value(i) > (el.dataset.trig ? 0.15 : 0.5));
        });
        svg.querySelectorAll('[data-stick]').forEach(c => {
            const [ax, ay] = c.dataset.stick.split(',').map(Number);
            c.setAttribute('transform', `translate(${(pad.axes[ax] || 0) * 9} ${(pad.axes[ay] || 0) * 9})`);
        });
    }

    // True while a step is waiting for a button or axis (input.js then stops the pad from navigating).
    window._gpwRecording = () => W.open && W.i >= 0 && W.i < W.steps.length;

    window.PDWizard = { BODIES, derive, slotsOf, stepsFor, diagram, drawingFor, liveUpdate, state: W };
})();
