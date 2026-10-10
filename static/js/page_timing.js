// TEMPORARY diagnostics: one line per Home page load in playdate.log ("page timing {...}"),
// to find out why covers appear later in some installs than others. Remove once understood.
(function () {
    if (!window.PerformanceObserver || !navigator.sendBeacon) return;
    var long = { n: 0, total: 0, max: 0 }, lcp = 0, firstSrc = 0, firstCover = 0, lastCover = 0, covers = 0, painted = 0;
    var isCover = function (el) { return el && el.tagName === 'IMG' && el.classList.contains('shelf-capsule'); };
    try {
        new PerformanceObserver(function (l) {
            l.getEntries().forEach(function (e) { long.n++; long.total += e.duration; long.max = Math.max(long.max, e.duration); });
        }).observe({ type: 'longtask', buffered: true });
    } catch (e) { /* not supported */ }
    try {
        new PerformanceObserver(function (l) { var es = l.getEntries(); lcp = es[es.length - 1].startTime; })
            .observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) { /* not supported */ }
    new MutationObserver(function (ms) {
        ms.forEach(function (m) { if (!firstSrc && isCover(m.target)) firstSrc = performance.now(); });
    }).observe(document, { subtree: true, attributes: true, attributeFilter: ['src'] });
    document.addEventListener('load', function (e) {
        if (!isCover(e.target)) return;
        var t = performance.now(); covers++; if (!firstCover) firstCover = t; lastCover = t;
        requestAnimationFrame(function () { requestAnimationFrame(function () { painted = performance.now(); }); });
    }, true);

    function gpu() {
        try {
            var gl = document.createElement('canvas').getContext('webgl');
            if (!gl) return 'no-webgl';
            var x = gl.getExtension('WEBGL_debug_renderer_info');
            return x ? String(gl.getParameter(x.UNMASKED_RENDERER_WEBGL)).slice(0, 120) : 'webgl-no-info';
        } catch (e) { return 'error'; }
    }
    var ms = function (n) { return Math.round(n || 0); };
    var med = function (a) { if (!a.length) return 0; a = a.slice().sort(function (x, y) { return x - y; }); return a[Math.floor(a.length / 2)]; };

    function report() {
        var nav = (performance.getEntriesByType('navigation') || [])[0] || {};
        var fp = {};
        (performance.getEntriesByType('paint') || []).forEach(function (p) { fp[p.name] = p.startTime; });
        var rs = performance.getEntriesByType('resource').filter(function (r) { return r.name.indexOf('/static/img/library/vertical/') !== -1; });
        var wait = [], server = [], dl = [], cached = 0, end = 0;
        rs.forEach(function (r) {
            wait.push(r.requestStart - r.startTime); server.push(r.responseStart - r.requestStart); dl.push(r.responseEnd - r.responseStart);
            if (r.transferSize === 0 && r.decodedBodySize > 0) cached++;
            end = Math.max(end, r.responseEnd);
        });
        var body = {
            ttfb: ms(nav.responseStart), interactive: ms(nav.domInteractive), dcl: ms(nav.domContentLoadedEventEnd), load: ms(nav.loadEventEnd),
            fp: ms(fp['first-paint']), fcp: ms(fp['first-contentful-paint']), lcp: ms(lcp),
            srcFirst: ms(firstSrc), coverFirst: ms(firstCover), coverLast: ms(lastCover), coverPainted: ms(painted), covers: covers,
            res: { n: rs.length, cached: cached, waitMed: ms(med(wait)), serverMed: ms(med(server)), dlMed: ms(med(dl)), lastEnd: ms(end) },
            longTasks: { n: long.n, totalMs: ms(long.total), maxMs: ms(long.max) },
            html: nav.encodedBodySize || 0,
            env: { gpu: gpu(), ua: navigator.userAgent.replace(/^Mozilla\/5\.0 /, '').slice(0, 160), dpr: window.devicePixelRatio, w: innerWidth, h: innerHeight, cores: navigator.hardwareConcurrency || 0 }
        };
        navigator.sendBeacon('/api/debug/page-timing', new Blob([JSON.stringify(body)], { type: 'application/json' }));
    }
    // After load, then a few seconds more so late covers (scrolling shelves) are included.
    window.addEventListener('load', function () { setTimeout(report, 3000); });
})();
