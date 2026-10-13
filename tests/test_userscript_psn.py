"""The PlayStation mode of steam_date_import.user.js: the pure helpers between the PS-BEGIN / PS-END markers
(building the history URL, picking product purchases out of transactions, paging and de-duplicating, falling
back across rotated hashes and page sizes) are run in node against scripted Sony replies. The DOM and network
parts of the script are not exercised."""
import json
import os
import re
import shutil
import subprocess

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'steam_date_import.user.js')
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')


def _block():
    src = open(SCRIPT, encoding='utf8').read()
    m = re.search(r'// PS-BEGIN.*?\n(.*?)// PS-END', src, re.S)
    assert m, 'PS-BEGIN / PS-END markers missing from the userscript'
    return m.group(1)


def _run(js_body):
    program = ("const h = new Function(%s + '\\nreturn {psnHistoryUrl, psnPurchases, psnAddUnique, psnReadReply, "
               "psnCollect, PSN_HASHES, PSN_ENDPOINT};')();\n%s" % (json.dumps(_block()), js_body))
    out = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _tx(tid, date, *items):
    return {'id': tid, 'date': date, 'purchaseDetails': {'productPurchases': [
        {'productName': n, 'skuId': sku, 'orderItemId': oi} for n, sku, oi in items]}}


def test_the_url_carries_the_operation_variables_and_hash():
    r = _run("""
      const u = new URL(h.psnHistoryUrl(h.PSN_HASHES[0], '2026-10-13T00:00:00.000Z', 50));
      console.log(JSON.stringify({host: u.host, path: u.pathname, op: u.searchParams.get('operationName'),
        vars: JSON.parse(u.searchParams.get('variables')), ext: JSON.parse(u.searchParams.get('extensions'))}));""")
    assert r['host'] == 'web.np.playstation.com' and r['op'] == 'transactionHistoryRetrieve'
    assert r['vars'] == {'startDate': '1994-12-03T00:00:00.000Z', 'endDate': '2026-10-13T00:00:00.000Z', 'limit': 50}
    assert r['ext']['persistedQuery']['sha256Hash'] == '496f6f30273e14e92498da51447f773b1c9e30c3cfefb8739627c31673d08751'


def test_only_product_purchases_with_a_date_and_a_sku_are_kept():
    txs = [_tx('1', '2026-10-13T01:06:35.072Z', ('Blades of Fire Demo', 'UP4040-PPSA30074_00-DEMOBLADESFOFIRE-U001', 'o1')),
           {'id': '2', 'date': '2026-01-01T00:00:00Z', 'purchaseDetails': None},                  # a wallet top-up
           _tx('3', None, ('No Date', 'X-1-Y-U001', 'o3')),                                       # no date
           _tx('4', '2025-05-05T00:00:00Z', ('No Sku', None, 'o4')),                              # no sku
           _tx('5', '2025-06-06T00:00:00Z', ('Delisted', 'EP1-CUSA1_00-DEL-U001', 'o5'), (None, 'EP1-CUSA1_00-DLC-U001', 'o6'))]
    r = _run("console.log(JSON.stringify(h.psnPurchases(%s)));" % json.dumps(txs))
    assert [(p['name'], p['sku']) for p in r] == [
        ('Blades of Fire Demo', 'UP4040-PPSA30074_00-DEMOBLADESFOFIRE-U001'),
        ('Delisted', 'EP1-CUSA1_00-DEL-U001'), ('', 'EP1-CUSA1_00-DLC-U001')]      # a null name does not drop the row
    assert len({p['id'] for p in r}) == 3


def test_a_reply_with_data_and_partial_errors_is_still_usable():
    r = _run("""
      const ok = h.psnReadReply({data: {transactionHistoryRetrieve: {transactions: []}}, errors: [{message: 'name is null'}]});
      const bad = h.psnReadReply({errors: [{message: 'PersistedQueryNotFound'}], data: null});
      const code = h.psnReadReply({errors: [{extensions: {code: 'UNAUTHENTICATED'}}]});
      console.log(JSON.stringify({ok: !!ok.block, bad: bad.error, code: code.error, empty: h.psnReadReply(null).error}));""")
    assert r == {'ok': True, 'bad': 'PersistedQueryNotFound', 'code': 'UNAUTHENTICATED', 'empty': 'unexpected reply'}


def test_pages_are_followed_by_the_cursor_and_repeated_rows_are_dropped():
    pages = [
        {'data': {'transactionHistoryRetrieve': {'hasMore': True, 'nextEndDate': '2026-01-01T00:00:00.000Z', 'transactions': [
            _tx('1', '2026-10-13T01:00:00Z', ('A', 'EP-1-A-U001', 'a')), _tx('2', '2026-05-01T00:00:00Z', ('B', 'EP-1-B-U001', 'b'))]}}},
        {'data': {'transactionHistoryRetrieve': {'hasMore': False, 'nextEndDate': None, 'transactions': [
            _tx('2', '2026-05-01T00:00:00Z', ('B', 'EP-1-B-U001', 'b')),                 # the boundary row comes back
            _tx('3', '2025-02-02T00:00:00Z', ('C', 'EP-1-C-U001', 'c'))]}}},
    ]
    r = _run("""
      const pages = %s, asked = [];
      const getPage = async (hash, end, limit) => { asked.push({hash, end, limit}); return pages[asked.length - 1]; };
      const progress = [];
      h.psnCollect(getPage, '2026-10-14T00:00:00.000Z', (n, p) => progress.push([n, p])).then(res =>
        console.log(JSON.stringify({names: res.rows.map(r => r.name), pages: res.pages, asked, progress})));""" % json.dumps(pages))
    assert r['names'] == ['A', 'B', 'C'] and r['pages'] == 2
    assert r['asked'][0]['end'] == '2026-10-14T00:00:00.000Z' and r['asked'][1]['end'] == '2026-01-01T00:00:00.000Z'
    assert r['asked'][0]['limit'] == 50 and r['progress'] == [[2, 1], [3, 2]]


def test_a_rotated_hash_falls_through_to_the_next_one():
    good = {'data': {'transactionHistoryRetrieve': {'hasMore': False, 'transactions': [_tx('1', '2026-01-01T00:00:00Z', ('A', 'EP-1-A-U001', 'a'))]}}}
    r = _run("""
      const good = %s, asked = [];
      const getPage = async (hash) => { asked.push(hash); return asked.length === 1 ? {errors: [{message: 'PersistedQueryNotFound'}]} : good; };
      h.psnCollect(getPage, 'now').then(res => console.log(JSON.stringify({n: res.rows.length, asked})));""" % json.dumps(good))
    assert r['n'] == 1 and r['asked'][0] != r['asked'][1] and len(r['asked']) == 2


def test_a_smaller_page_is_tried_when_the_first_size_is_refused_and_a_real_failure_is_reported():
    r = _run("""
      const limits = [];
      const getPage = async (hash, end, limit) => { limits.push(limit);
        return limit === 50 ? {errors: [{message: 'limit too large'}]}
             : {data: {transactionHistoryRetrieve: {hasMore: false, transactions: []}}}; };
      h.psnCollect(getPage, 'now').then(res => console.log(JSON.stringify({limits, rows: res.rows.length})));""")
    assert r['limits'] == [50, 15] and r['rows'] == 0
    r = _run("""
      const getPage = async () => ({errors: [{message: 'access token does not contain the required scope(s)'}]});
      h.psnCollect(getPage, 'now').then(() => console.log('{"threw": false}'), e => console.log(JSON.stringify({threw: true, msg: e.message})));""")
    assert r == {'threw': True, 'msg': 'access token does not contain the required scope(s)'}


def test_a_failure_after_some_pages_keeps_what_was_read():
    p1 = {'data': {'transactionHistoryRetrieve': {'hasMore': True, 'nextEndDate': 'x', 'transactions': [_tx('1', '2026-01-01T00:00:00Z', ('A', 'EP-1-A-U001', 'a'))]}}}
    r = _run("""
      let n = 0; const p1 = %s;
      const getPage = async () => (++n === 1 ? p1 : {errors: [{message: 'boom'}]});
      h.psnCollect(getPage, 'now').then(res => console.log(JSON.stringify({rows: res.rows.length, warning: res.warning})));""" % json.dumps(p1))
    assert r == {'rows': 1, 'warning': 'boom'}


def test_the_script_is_armed_only_for_store_pages_and_its_header_advertises_it():
    src = open(SCRIPT, encoding='utf8').read()
    assert '// @match        https://store.playstation.com/*' in src
    assert "pd_psn_import" in src and "hostname === 'store.playstation.com'" in src
    assert re.search(r'// @version\s+3\.3', src)


# -- the WHOLE userscript, run in node against a stubbed page, Sony and PlayDate ----------------------------
# The helper tests above run the PS block on its own, in order. They could not see that the real script returns
# early at its dispatch and reaches `runPlayStation` before the constants it uses are initialised (a `const`
# declared further down the file is still in its temporal dead zone). These run the file top to bottom.

_HARNESS = r'''
const vm = require('node:vm'), fs = require('node:fs');
const scenario = JSON.parse(process.env.SCENARIO);
const src = fs.readFileSync(process.env.SCRIPT, 'utf8');
const fetches = [], posts = [], store = new Map(), els = {};
if (scenario.flag) store.set('pd_psn_import', '1');
const el = (id) => els[id] || (els[id] = { id, textContent: '', style: {}, onclick: null });
const sb = {
  URL, URLSearchParams, setTimeout, clearTimeout, console, Promise, JSON, Date, Math, Set, String, Error,
  crypto: require('node:crypto').webcrypto,
  location: { hostname: scenario.host || 'store.playstation.com', href: scenario.href, search: scenario.search, pathname: '/en-us/pages/latest' },
  sessionStorage: { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) },
  performance: { getEntriesByType: () => scenario.nav ? [{ name: scenario.nav }] : [] },
  document: {
    createElement: () => ({ style: {}, set innerHTML(v) { this._h = v; }, remove() { this.removed = true; } }),
    body: { appendChild() {} }, getElementById: el,
  },
  fetch: async (url, init) => {
    fetches.push({ url, credentials: init && init.credentials, client: init && init.headers && init.headers['apollographql-client-name'] });
    if (url.includes('io.playstation.com')) return { status: 200, json: async () => ({ handle: '"RobbyRatpoison"' }) };
    const reply = scenario.replies[Math.min(fetches.filter(f => f.url.includes('transactionHistory')).length - 1, scenario.replies.length - 1)];
    return { status: 200, json: async () => reply };
  },
  GM_xmlhttpRequest: (o) => setImmediate(() => {
    if (o.url.includes('/api/update-status')) return o.onload({ responseText: '{"current_version":"2026.10.5"}' });
    posts.push({ url: o.url, body: JSON.parse(o.data) });
    if (scenario.pdDown) return o.onerror(new Error('down'));
    o.onload({ responseText: JSON.stringify({ status: 'success', updated: 1, matched: 1 }) });
  }),
};
sb.window = sb;
vm.runInNewContext(src, sb);
const started = Date.now();
(function wait() {
  const done = els['pd-psn-close'] && els['pd-psn-close'].style.display === 'inline-block';
  if (done || Date.now() - started > (scenario.expectNothing ? 400 : 4000)) {
    console.log(JSON.stringify({ fetches, posts, status: (els['pd-psn-status'] || {}).textContent || '', done: !!done, flag: store.get('pd_psn_import') || null }));
  } else setTimeout(wait, 20);
})();
'''

_PAGE = {'data': {'transactionHistoryRetrieve': {'hasMore': False, 'nextEndDate': None, 'transactions': [
    {'id': '1', 'date': '2026-10-13T01:06:35.072Z', 'purchaseDetails': {'productPurchases': [
        {'productName': 'Blades of Fire Demo', 'skuId': 'UP4040-PPSA30074_00-DEMOBLADESFOFIRE-U001', 'orderItemId': 'o1'}]}}]}}}
_URL = 'https://store.playstation.com/en-us/pages/latest?transactAction=viewTransactionHistory&cartAction=view&ref=playdate'


def _smoke(**scenario):
    scenario.setdefault('replies', [_PAGE])
    scenario.setdefault('href', _URL)
    scenario.setdefault('search', '?' + _URL.split('?', 1)[1])
    env = dict(os.environ, SCENARIO=json.dumps(scenario), SCRIPT=SCRIPT)
    out = subprocess.run(['node', '-e', _HARNESS], capture_output=True, text=True, timeout=30, env=env)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_whole_script_imports_when_opened_by_playdate():
    r = _smoke()
    hist = [f for f in r['fetches'] if 'transactionHistoryRetrieve' in f['url']]
    assert hist and hist[0]['credentials'] == 'include' and hist[0]['client'] == '@sie-ppr-web-checkout/app'
    assert '496f6f30273e14e92498da51447f773b1c9e30c3cfefb8739627c31673d08751' in hist[0]['url']
    assert len(r['posts']) == 1 and r['posts'][0]['url'] == 'http://localhost:5000/api/playstation/purchase-dates'
    body = r['posts'][0]['body']
    assert body['online_id'] == 'RobbyRatpoison' and body['purchases'] == [
        {'date': '2026-10-13T01:06:35.072Z', 'name': 'Blades of Fire Demo', 'sku': 'UP4040-PPSA30074_00-DEMOBLADESFOFIRE-U001'}]
    assert r['done'] and r['status'].startswith('Done: 1 date set, 1 of your PlayStation games matched')
    assert r['flag'] is None                                    # the arming flag is cleared when the run ends


def test_it_still_runs_when_the_store_has_stripped_the_query_or_a_sign_in_bounced_the_tab():
    stripped = _smoke(href='https://store.playstation.com/en-us/pages/latest', search='', nav=_URL)    # the first navigation had it
    assert stripped['done'] and len(stripped['posts']) == 1
    bounced = _smoke(href='https://store.playstation.com/en-us/pages/latest', search='', flag=True)    # armed earlier in this tab
    assert bounced['done'] and len(bounced['posts']) == 1


def test_an_ordinary_visit_to_the_store_does_nothing():
    r = _smoke(href='https://store.playstation.com/en-us/pages/latest', search='', expectNothing=True)
    assert not [f for f in r['fetches'] if 'transactionHistory' in f['url']] and r['posts'] == [] and not r['done']


def test_sonys_refusal_and_an_unreachable_playdate_are_reported_not_swallowed():
    r = _smoke(replies=[{'errors': [{'message': 'access token does not contain the required scope(s)'}]}])
    assert r['done'] and r['posts'] == [] and 'required scope' in r['status'] and r['status'].startswith('Could not read')
    r = _smoke(pdDown=True)
    assert r['done'] and r['status'] == 'Could not reach PlayDate. Make sure it is running.'
