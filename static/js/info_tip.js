// Game info panel for the optional card hover tooltip. Shared by the Library
// page (library.js, which adds the PAGYWOSG quals on top) and the Home page.
// cfg = window.HOVER_TIP; opts = { orientation(), imgVersion(appid), getGame(appid) }.
window.PDInfoTip = {
    make(cfg, opts) {
        const fields = new Set(cfg ? cfg.fields : []);

        // Dates arrive as 'YYYY-MM-DD' strings (ts_to_date), not timestamps.
        function tipDate(s) {
            if (!s) return null;
            const d = new Date(s);
            return isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
        }

        const descCache = new Map(); // appid -> plain-text description or null

        // Fetches the store blurb after the tooltip has stayed put briefly, so
        // sweeping the mouse across the grid doesn't fire a request per card.
        function hydrateDesc(el, appid, reposition) {
            const slot = el.querySelector('.ht-desc');
            if (!slot) return;
            const apply = text => {
                if (!slot.isConnected) return;
                if (text) { slot.textContent = text; slot.style.display = 'block'; }
                else slot.remove();
                reposition();
            };
            // Steam blurbs top out near 300 chars; the cap only trims long plugin descriptions.
            const clip = t => {
                if (!t || t.length <= 400) return t;
                const cut = t.slice(0, 397);
                return cut.slice(0, cut.lastIndexOf(' ') > 300 ? cut.lastIndexOf(' ') : 397).trimEnd() + '...';
            };
            // Stored server-side (short_description): show it with no request.
            const stored = opts.getGame(appid)?.short_description;
            if (stored) { apply(clip(stored)); return; }
            if (descCache.has(appid)) { apply(descCache.get(appid)); return; }
            setTimeout(() => {
                if (!slot.isConnected) return;
                // Not stored yet: the endpoint fetches it once and saves it for next time.
                fetch(`/api/game-description/${appid}`).then(r => r.json()).then(d => {
                    const t = d.status === 'success' && d.description ? clip(d.description) : null;
                    const g = opts.getGame(appid);
                    if (t && g) g.short_description = d.description;
                    descCache.set(appid, t || null);
                    apply(t);
                }).catch(() => {});
            }, 300);
        }

        // Cover beside the text (horizontal library) needs a wider tooltip than the stacked one.
        function wide() { return !!cfg && fields.has('cover_alt') && opts.orientation() === 'horizontal'; }

        function buildInfo(game) {
            if (!cfg) return null;
            const dim = 'color:var(--text-secondary);';
            const rows = [];
            const row = (label, value) => { if (value) rows.push(`<div><span style="${dim}">${label}:</span> ${escHtml(String(value))}</div>`); };
            let cover = '';
            if (fields.has('cover_alt')) {
                const horiz = opts.orientation() === 'horizontal';
                const kind = horiz ? 'vertical' : 'horizontal';
                // Horizontal library: the tall cover sits beside the text instead of above it.
                // Horizontal art uses the same 616:353 frame as the library's own horizontal cards
                // (a 460:215 frame cropped it). The tall cover stretches to the text's height,
                // its width following from the 2:3 ratio. Height is capped at 300px (the 200px max
                // width at 2:3), so a tall tooltip leaves the cover uncropped instead of trimming its sides.
                const size = horiz ? 'align-self:stretch;height:auto;min-height:210px;max-height:300px;width:auto;max-width:200px;aspect-ratio:2/3;flex:none;'
                                   : 'width:290px;aspect-ratio:616/353;margin-bottom:6px;';
                cover = `<img src="/static/img/library/${kind}/${game.appid}.jpg?v=${opts.imgVersion(game.appid)}" alt="" style="display:block;${size}object-fit:cover;border-radius:4px;" onerror="this.remove()">`;
            }
            let html = '';
            if (fields.has('description')) html += '<div class="ht-desc" style="display:none;margin-bottom:6px;"></div>';
            if (fields.has('playtime')) row('Time played', game.playtime_forever > 0 ? fmtHours(game.playtime_forever) : 'Never played');
            if (fields.has('last_played')) row('Last played', tipDate(game.last_played) || 'Never');
            if (fields.has('date_added')) row('Date added', tipDate(game.date_added));
            if (fields.has('release_date')) row('Released', tipDate(game.release_date));
            if (fields.has('platform')) row('Library', (window._PLAT_LABELS || {})[game.platform || 'steam'] || game.platform || 'steam');
            if (fields.has('community_score') && game.review_percentage != null && game.review_percentage !== '') {
                row('Steam community', `${game.review_score ? game.review_score + ' ' : ''}(${game.review_percentage}%)`);
            }
            if (fields.has('metacritic') && game.metacritic_score != null) row('Metacritic', game.metacritic_score);
            if (fields.has('developers') && game.developers) row('Developer', game.developers.split(',').join(', '));
            if (fields.has('publishers') && game.publishers) row('Publisher', game.publishers.split(',').join(', '));
            html += rows.join('');
            if (!html) return cover || null;
            if (wide()) return `<div style="display:flex;gap:10px;align-items:flex-start;">${cover}<div style="min-width:0;flex:1;">${html}</div></div>`;
            return cover + html;
        }

        // Wrapper caps the content width (the tooltip boxes themselves allow 560px).
        function wrap(body) { return `<div style="max-width:${wide() ? 510 : 330}px;">${body}</div>`; }

        return { wide, buildInfo, hydrateDesc, wrap };
    },

    // Where a fixed tooltip goes relative to a card, as left/top values in the
    // tooltip's own (zoomed) CSS px. Card rects and the viewport are in screen
    // px, but the tooltip lives inside html{zoom} so its offsetWidth and its
    // left/top are scaled by the UI scale; mixing the two pushed it off-screen.
    place(el, card) {
        const z = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
        const rect = card.getBoundingClientRect(), pad = 8;
        const tw = el.offsetWidth * z, th = el.offsetHeight * z;
        let x = rect.left + (rect.width - tw) / 2;
        // Above vs below by card position, not tooltip size, so a whole row flips together.
        let y = rect.top > window.innerHeight / 2 ? rect.top - th - pad : rect.bottom + pad;
        x = Math.max(pad, Math.min(x, window.innerWidth - tw - pad));
        y = Math.max(pad, Math.min(y, window.innerHeight - th - pad));
        return { x: Math.round(x / z), y: Math.round(y / z) };
    },
};
