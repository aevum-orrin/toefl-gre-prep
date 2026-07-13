/* End-to-end test of the vocab-srs frontend: runs the REAL inline script from index.html
   in a stub DOM (node vm) against a REAL backend, and drives the global lookup — search
   from an unrevealed front card, chained jumps, one-step-per-press back.

   The stub honours DOCUMENT ORDER: while the script is executing, elements declared AFTER
   it in index.html do not exist yet (querySelector -> null), exactly as in a browser. That
   is what catches "wired up a node that isn't parsed yet", which silently kills boot() and
   leaves the page stuck on the "…" placeholder.

   Usage:  PREP_DATA_DIR=$(mktemp -d) uvicorn app:app --port 8097 &
           node test_lookup.mjs static/index.html
*/
import fs from 'fs';
import vm from 'vm';

const BASE = process.env.VOCAB_URL || 'http://127.0.0.1:8097';
const HTML = fs.readFileSync(process.argv[2] || new URL('./static/index.html', import.meta.url), 'utf8');

// the app's own script = the first inline <script> (the vendor ones carry src=)
const m = /<script>([\s\S]*?)<\/script>/.exec(HTML);
const SRC = m[1];
const idsIn = s => new Set([...s.matchAll(/id="([\w-]+)"/g)].map(x => x[1]));
const BEFORE = idsIn(HTML.slice(0, m.index));        // in the DOM when the script runs
const AFTER = idsIn(HTML.slice(m.index + m[0].length));
let parsing = true;                                  // true while the script's top level runs

const store = new Map();
const mkEl = () => {
  const cls = new Set();
  const el = {
    value: '', checked: true, textContent: '', innerHTML: '', disabled: false,
    style: {}, dataset: {}, offsetParent: null, handlers: {},
    classList: {
      add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c),
      toggle: (c, on) => { const v = on === undefined ? !cls.has(c) : !!on; v ? cls.add(c) : cls.delete(c); return v; },
    },
    addEventListener: (t, fn) => (el.handlers[t] = fn),
    focus() {}, select() {}, scrollIntoView() {}, closest: () => null, appendChild() {},
  };
  return el;
};
const $ = sel => {
  const id = sel.startsWith('#') ? sel.slice(1) : null;
  if (parsing && id && AFTER.has(id) && !BEFORE.has(id)) return null;   // not parsed yet!
  if (!store.has(sel)) store.set(sel, mkEl());
  return store.get(sel);
};
const hidden = sel => $(sel).classList.contains('hidden');

const document = {
  querySelector: $,
  querySelectorAll: sel =>
    sel.includes('[data-slot]') || sel === '.ttspanel select'
      ? ['usM', 'usF', 'ukM', 'ukF'].map(s => { const e = mkEl(); e.dataset.slot = s; return e; })
      : [],
  addEventListener() {}, createElement: () => mkEl(), body: { appendChild() {} },
};
const speechSynthesis = { getVoices: () => [], addEventListener() {}, cancel() {}, speak() {}, paused: false };
const ctx = vm.createContext({
  document, window: { speechSynthesis, addEventListener() {} }, speechSynthesis,
  localStorage: { getItem: () => null, setItem() {} },
  marked: { parse: s => s }, DOMPurify: { sanitize: s => s },
  Audio: function () { return { play: async () => {}, pause() {} }; },
  URL: { createObjectURL: () => 'blob:x' }, Map, Set, Math, JSON, console,
  SpeechSynthesisUtterance: function () {}, setTimeout, clearTimeout, encodeURIComponent,
  fetch: (u, o) => fetch(u.startsWith('http') ? u : BASE + u, o),
});

vm.runInContext(SRC, ctx);      // throws if the script wires up a not-yet-parsed node
parsing = false;                // the rest of the document is in the DOM now
for (const id of ['lkPanel', 'lkBack', 'back', 'redo']) $('#' + id).classList.add('hidden');  // markup's initial state

const run = code => vm.runInContext(code, ctx);
const wait = ms => new Promise(r => setTimeout(r, ms));
const ok = (c, msg) => { if (!c) { console.error('FAIL: ' + msg); process.exit(1); } console.log('  ✓ ' + msg); };

await wait(800);                                    // boot(): /api/decks + /api/next

console.log('\n0. the script survived parse-time wiring');
ok(run('typeof boot') === 'function' && run('cur') != null,
   'boot() ran and loaded a card (a top-level throw would leave cur = null)');

console.log('\n1. lookup is usable on an UNREVEALED front card');
const w0 = run('cur.term');
ok(run('revealed') === false, `card "${w0}" is on its front (Space not pressed)`);
ok(hidden('#lkPanel') && !hidden('#lkFab'), 'floating 🔎 button present, panel closed');
run('lkOpen(true)');
ok(!hidden('#lkPanel') && hidden('#lkFab'), 'opening the panel needs no Space');

console.log('\n2. substring search over the current deck');
$('#lkInput').value = 'sub';
await run('lookup("sub")');
const hits = run('lkHits.map(h => h.term)');
ok(hits.length > 5 && hits.every(t => t.toLowerCase().includes('sub')),
   `"sub" → ${hits.length} hits: ${hits.slice(0, 4).join(', ')}…`);
ok(run('lkSel') === 0, 'first hit pre-selected (Enter opens it)');

console.log('\n3. chained jumps deepen the back stack');
await run(`jumpTo("${hits[0]}")`);
ok(run('cur.term') === hits[0] && run('revealed') === true, `jumped to "${hits[0]}" as a full study page`);
ok(hidden('#lkPanel'), 'panel auto-closes after a jump');
ok(!hidden('#back') && !hidden('#lkBack'), 'both back buttons appeared');
await run(`jumpTo("${hits[1]}")`);
await run(`jumpTo("${hits[2]}")`);
ok(run('BACK.length') === 3, `3 chained jumps → depth 3 (now on "${run('cur.term')}")`);
ok($('#lkBack').textContent.includes('(3)'), `back button shows depth: "${$('#lkBack').textContent}"`);

console.log('\n4. back = ONE step per press, all the way home');
run('goBack()'); ok(run('cur.term') === hits[1] && run('BACK.length') === 2, `1st back → "${hits[1]}"`);
run('goBack()'); ok(run('cur.term') === hits[0] && run('BACK.length') === 1, `2nd back → "${hits[0]}"`);
run('goBack()'); ok(run('cur.term') === w0 && run('BACK.length') === 0, `3rd back → the original word "${w0}"`);
ok(run('revealed') === false, 'restored UNREVEALED, exactly as it was left');
ok(hidden('#back') && hidden('#lkBack'), 'back buttons hide again at depth 0');
ok(String($('#card').innerHTML).includes('class="front"'), 'its front card was re-rendered');

console.log('\n5. looking up the word already revealed on screen is a no-op');
await run(`jumpTo("${w0}")`);
ok(run('BACK.length') === 1 && run('revealed') === true, 'looking up the current unrevealed word opens its study page');
await run(`jumpTo("${w0}")`);
ok(run('BACK.length') === 1, 'self-lookup pushed no redundant back entry');
run('goBack()');
ok(run('BACK.length') === 0 && run('revealed') === false, 'back returns to its front, stack empty');

console.log('\nALL LOOKUP TESTS PASSED');
