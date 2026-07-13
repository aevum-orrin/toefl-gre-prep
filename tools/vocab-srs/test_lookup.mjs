/* Drives the REAL frontend script (stub DOM + real fetch to a live backend) to verify the
   global lookup: search from an unrevealed front, chained jumps, one-step-per-press back. */
import fs from 'fs';
import vm from 'vm';

const BASE = 'http://127.0.0.1:8097';
const SRC = fs.readFileSync(process.argv[2], 'utf8');

const store = new Map();
const mkEl = (sel = '') => {
  const cls = new Set();
  const el = {
    sel, value: '', checked: true, textContent: '', innerHTML: '', disabled: false,
    style: {}, dataset: {}, offsetParent: null, handlers: {},
    classList: {
      add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c),
      toggle: (c, on) => { const v = on === undefined ? !cls.has(c) : !!on; v ? cls.add(c) : cls.delete(c); return v; },
    },
    _cls: cls,
    addEventListener: (t, fn) => (el.handlers[t] = fn),
    focus() {}, select() {}, scrollIntoView() {}, closest: () => null, appendChild() {},
  };
  return el;
};
const $ = sel => { if (!store.has(sel)) store.set(sel, mkEl(sel)); return store.get(sel); };
const hidden = sel => $(sel).classList.contains('hidden');
// mirror the markup's initial state: these carry class="hidden" in index.html
for (const id of ['#lkPanel', '#lkBack', '#back', '#redo']) $(id).classList.add('hidden');

const document = {
  querySelector: $,
  querySelectorAll: sel => {
    if (sel.includes('[data-slot]') || sel === '.ttspanel select')
      return ['usM', 'usF', 'ukM', 'ukF'].map(s => { const e = mkEl(); e.dataset.slot = s; return e; });
    return [];
  },
  addEventListener() {}, createElement: () => mkEl(), body: { appendChild() {} },
};
const speechSynthesis = { getVoices: () => [], addEventListener() {}, cancel() {}, speak() {}, paused: false };
const sandbox = {
  document, window: { speechSynthesis, addEventListener() {} }, speechSynthesis,
  localStorage: { getItem: () => null, setItem() {} },
  marked: { parse: s => s }, DOMPurify: { sanitize: s => s },
  Audio: function () { return { play: async () => {}, pause() {} }; },
  URL: { createObjectURL: () => 'blob:x' }, Map, Set, Math, JSON, console,
  SpeechSynthesisUtterance: function () {},
  setTimeout, clearTimeout, encodeURIComponent,
  fetch: (u, o) => fetch(u.startsWith('http') ? u : BASE + u, o),
};
const ctx = vm.createContext(sandbox);
vm.runInContext(SRC, ctx);

const run = code => vm.runInContext(code, ctx);
const wait = ms => new Promise(r => setTimeout(r, ms));
const ok = (cond, msg) => { if (!cond) { console.error('FAIL: ' + msg); process.exit(1); } console.log('  ✓ ' + msg); };

await wait(600);                                   // boot() → /api/decks + /api/next

console.log('\n1. lookup is usable on an UNREVEALED front card');
const w0 = run('cur.term'), rev0 = run('revealed');
ok(!!w0 && rev0 === false, `card "${w0}" is on its front (not revealed)`);
ok(hidden('#lkPanel') && !hidden('#lkFab'), 'floating 🔎 button is present, panel closed');
run('lkOpen(true)');
ok(!hidden('#lkPanel') && hidden('#lkFab'), 'pressing / (lkOpen) opens the panel — no Space needed');

console.log('\n2. substring search over the current deck');
$('#lkInput').value = 'sub';
await run('lookup("sub")');
const hits = run('lkHits.map(h => h.term)');
ok(hits.length > 5 && hits.every(t => t.toLowerCase().includes('sub')), `"sub" → ${hits.length} hits: ${hits.slice(0, 4).join(', ')}…`);
ok(run('lkSel') === 0, 'first hit pre-selected (Enter opens it)');

console.log('\n3. chained jumps: each push deepens the back stack');
await run(`jumpTo("${hits[0]}")`);
ok(run('cur.term') === hits[0] && run('revealed') === true, `jumped to "${hits[0]}" as a full (revealed) study page`);
ok(hidden('#lkPanel'), 'panel auto-closes after a jump');
ok(run('BACK.length') === 1, 'BACK depth 1');
ok(!hidden('#back') && !hidden('#lkBack'), 'both back buttons appeared');

await run(`jumpTo("${hits[1]}")`);
await run(`jumpTo("${hits[2]}")`);
ok(run('cur.term') === hits[2] && run('BACK.length') === 3, `3 chained jumps → depth 3 (now on "${hits[2]}")`);
ok($('#lkBack').textContent.includes('(3)'), `back button shows the depth: "${$('#lkBack').textContent}"`);

console.log('\n4. back = ONE step per press, all the way home');
run('goBack()');
ok(run('cur.term') === hits[1] && run('BACK.length') === 2, `1st back → "${hits[1]}" (depth 2)`);
run('goBack()');
ok(run('cur.term') === hits[0] && run('BACK.length') === 1, `2nd back → "${hits[0]}" (depth 1)`);
run('goBack()');
ok(run('cur.term') === w0 && run('BACK.length') === 0, `3rd back → the original word "${w0}"`);
ok(run('revealed') === false, 'and it is restored UNREVEALED, exactly as it was left');
ok(hidden('#back') && hidden('#lkBack'), 'back buttons hide again at depth 0');
ok(String($('#card').innerHTML).includes('class="front"'), 'the front card was re-rendered (Space still pending)');

console.log('\n5. looking up the word already revealed on screen is a no-op (no phantom back step)');
await run(`jumpTo("${w0}")`);                       // from its front: legit — jumps to its answer page
ok(run('BACK.length') === 1 && run('revealed') === true, 'looking up the current (unrevealed) word opens its study page, depth 1');
await run(`jumpTo("${w0}")`);                       // same word, already revealed
ok(run('BACK.length') === 1, `self-lookup pushed no redundant entry (depth still ${run('BACK.length')})`);
run('goBack()');
ok(run('BACK.length') === 0 && run('cur.term') === w0 && run('revealed') === false, 'back returns to its front, stack empty');

console.log('\nALL LOOKUP TESTS PASSED');
