// Mouse actions on game cards, driven by the user's rules (window._CARD_RULES, from
// state.json's card_click_rules): [{button, click, action}] where button is
// left/middle/right/back/forward, click is single/double and action is one of ACTIONS.
// One set of document-level listeners serves the Library (grid + list), Home and Pick 6, so
// cards no longer carry their own onclick/ondblclick attributes.
(function () {
    const BTN = { 0: 'left', 1: 'middle', 2: 'right', 3: 'back', 4: 'forward' };
    // Two presses of one button within this window on the same card make a double click.
    // Counted here rather than from the browser's dblclick so every button works alike.
    const DBL_MS = 300;
    // Where a card reacts to the mouse (not its whole box, which also holds controls).
    const AREA = '.capsule-container, .shelf-capsule-wrap, .result-art, .list-row';
    const CARD = '.game-card[data-appid], .list-row[data-appid], .shelf-capsule-wrap[data-appid], .result-card[data-appid]';
    const SKIP = 'button, a, input, select, textarea, label, .card-edit-overlay';

    const openUrl = url => window.pdCtx && window.pdCtx.openUrl(url);
    const toast = msg => { if (typeof showLaunchToast === 'function') showLaunchToast(msg); };
    const rules = () => window._CARD_RULES || [];
    const hasTipRule = () => rules().some(r => r.action === 'tooltip');

    function areaOf(e) {
        const t = e.target;
        if (!(t instanceof Element) || t.closest(SKIP)) return null;
        const area = t.closest(AREA);
        const card = area && area.closest(CARD);
        if (!area || !card) return null;
        const appid = parseInt(card.dataset.appid, 10);
        return isNaN(appid) ? null : { area, appid };
    }

    // The action for a button + click type, or null when none is set. In list mode a single
    // left click always selects the row (it opens the detail pane), and a double left click
    // still launches when no rule says otherwise, as it did before the rules existed.
    function actionFor(button, click, area) {
        const isRow = area.classList.contains('list-row');
        if (isRow && button === 'left' && click === 'single') return null;
        const r = rules().find(r => r.button === button && r.click === click);
        if (r) return r.action;
        return isRow && button === 'left' && click === 'double' ? 'launch' : null;
    }

    const last = {};   // button -> { appid, t, timer } of the previous press

    function onPress(button, e, hit) {
        const snap = { target: e.target, clientX: e.clientX, clientY: e.clientY, preventDefault() {} };
        const dbl = actionFor(button, 'double', hit.area);
        const sgl = actionFor(button, 'single', hit.area);
        const prev = last[button];
        if (dbl !== null && prev && prev.appid === hit.appid && Date.now() - prev.t < DBL_MS) {
            clearTimeout(prev.timer);
            last[button] = null;
            run(dbl, hit, snap);
            return;
        }
        if (dbl === null) { if (sgl !== null) run(sgl, hit, snap); return; }
        // A double click exists for this button: hold the single click back until it's clear
        // no second press is coming. An earlier card's pending single still fires on its own timer.
        const rec = { appid: hit.appid, t: Date.now(), timer: null };
        if (sgl !== null) {
            rec.timer = setTimeout(() => {
                if (last[button] === rec) last[button] = null;
                run(sgl, hit, snap);
            }, DBL_MS);
        }
        last[button] = rec;
    }

    async function fetchGame(appid) {
        try {
            const d = await (await fetch(`/api/game/${appid}`)).json();
            return d.status === 'success' ? d.game : null;
        } catch (_) { return null; }
    }

    async function run(action, hit, snap) {
        const { appid, area } = hit;
        // Select mode and shelf edit mode own the card clicks; only the menu still opens.
        const busy = (typeof _selectMode !== 'undefined' && _selectMode) || document.body.classList.contains('edit-mode');
        if (action === 'none' || (busy && action !== 'context_menu')) return;
        switch (action) {
            case 'launch': launchGame(appid); return;
            case 'edit': openGameEditor(appid); return;
            case 'context_menu':
                // After the click that triggered this has finished, so the menu's own
                // click-away handler doesn't close it again straight away.
                if (window.pdCtx) setTimeout(() => window.pdCtx.open(snap), 0);
                return;
            case 'tooltip':
                if (!(window.pdCardTip && window.pdCardTip.show(area, appid))) toast('No tooltip is available for this card');
                return;
        }
        const nonSteam = appid < 0;
        if (action === 'open_folder') {
            try {
                const r = await fetch(`/api/open-install-dir/${appid}`, { method: 'POST' });
                const d = await r.json().catch(() => ({}));
                if (d.status !== 'success') toast('Install folder not found (is the game installed?)');
            } catch (_) { toast('Could not open the install folder'); }
            return;
        }
        if (action === 'store') {
            const game = await fetchGame(appid);
            if (!game) { toast('Could not load this game'); return; }
            const api = window._PLUGIN_API && window._PLUGIN_API[game.platform];
            const url = nonSteam
                ? (api && api.store_url && game.platform_slug ? api.store_url.replace('{slug}', game.platform_slug) : null)
                : `https://store.steampowered.com/app/${appid}`;
            if (url) openUrl(url); else toast('This game has no store page');
            return;
        }
        if (action === 'achievements') {
            const id = window.pdCtx && window.pdCtx.steamId;
            if (nonSteam) { toast('Achievements are only linked for Steam games'); return; }
            if (!id) { toast('No Steam account is set up'); return; }
            openUrl(`https://steamcommunity.com/${/^\d+$/.test(id) ? 'profiles' : 'id'}/${id}/stats/${appid}/achievements/`);
            return;
        }
        if (action === 'community_hub') {
            if (nonSteam) { toast('The Community Hub is only available for Steam games'); return; }
            openUrl(`https://steamcommunity.com/app/${appid}`);
        }
    }

    // For the gamepad shortcuts (input.js): run an action on the focused card's element.
    window.pdRunCardAction = (action, appid, el) => {
        const r = el.getBoundingClientRect();
        run(action, { appid, area: el }, { target: el, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, preventDefault() {} });
    };

    // left: click. middle/back/forward: auxclick. right: contextmenu.
    document.addEventListener('click', e => {
        if (e.button !== 0) return;
        const hit = areaOf(e);
        if (hit) onPress('left', e, hit);
    });
    document.addEventListener('auxclick', e => {
        const name = BTN[e.button];
        if (!name || name === 'right') return;
        const hit = areaOf(e);
        if (!hit) return;
        e.preventDefault();
        onPress(name, e, hit);
    });
    // Capture phase: take the event before the generic context menu sees it, so a card's
    // right click does exactly what the rules say (including nothing).
    document.addEventListener('contextmenu', e => {
        const hit = areaOf(e);
        if (!hit) return;
        e.preventDefault();
        e.stopPropagation();
        onPress('right', e, hit);
    }, true);
    // Middle press would start autoscroll, back/forward would navigate the window.
    for (const type of ['mousedown', 'mouseup']) {
        document.addEventListener(type, e => {
            if ((e.button === 1 || e.button === 3 || e.button === 4) && areaOf(e)) e.preventDefault();
        }, true);
    }

    // A tooltip shown by a rule stays until the next press anywhere (or Escape).
    document.addEventListener('mousedown', () => {
        if (hasTipRule() && window.pdCardTip) window.pdCardTip.hide();
    }, true);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && hasTipRule() && window.pdCardTip) window.pdCardTip.hide();
    });
})();
