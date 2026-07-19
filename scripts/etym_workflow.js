export const meta = {
  name: 'etym-reformat',
  description: 'Reformat kaikki etymology_text -> Chinese 词根词缀 {breakdown,story,origin} per batch',
  phases: [{ title: 'Reformat', detail: 'one Opus agent per ~30-word batch' }],
}

// args = { deck?: "toefl"|"gre", indices: [int,...], model?: "sonnet" }
const CACHE = '/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache'
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const DECK = A.deck || 'toefl'
const INDIR = `${CACHE}/enrich_batches/etym/${DECK}`
const OUTDIR = `${CACHE}/enrich_out/etym/${DECK}`
const indices = A.indices || []
const MODEL = A.model || undefined  // undefined = inherit session model
log(`etym reformat: deck=${DECK}, ${indices.length} batches`)

const pad = (i) => String(i).padStart(4, '0')

function prompt(i) {
  const inf = `${INDIR}/batch_${pad(i)}.json`
  const outf = `${OUTDIR}/batch_${pad(i)}.out.json`
  return `You are an etymology teacher for Chinese students preparing for TOEFL/GRE, teaching the 词根词缀+词源 method.

Read the JSON file: ${inf}
It is an array of words: {term, etymology_text (authoritative Wiktionary facts), gloss_en, glosses}.

For EACH word, produce a record {term, useful, breakdown, story, origin}:
- Decide if a roots/affixes/origin analysis GENUINELY helps a Chinese learner remember this word
  (classic Latin/Greek roots, transparent prefix/suffix logic, or an interesting loanword story).
  If NOT (opaque native Germanic word with no decomposable learner-useful roots, or etymology_text
  is empty/uninformative), return {term, useful:false} and omit the other fields.
- When useful:true, use the etymology_text as the AUTHORITATIVE source (source language, roots,
  cognates) and REFORMAT it into concise mixed Chinese-English:
  - breakdown: the word split into morphemes, each glossed in Chinese, joined with ' + '.
    Example for "subsequent": "sub-(在下/在后) + sequ(跟随, 同 sequence 序列) + -ent(形容词后缀)"
  - story: ONE short line deriving the meaning from the parts.
    Example: "跟在一个序列后面 → 随后的、后来的"
  - origin: source language + cognates. Example: "来自拉丁语 subsequī; 同根词: sequence, consequence, pursue".
    If it is a loanword (舶来词, e.g. ballet, tsunami), say so: "舶来词: 来自法语 ballet".
RULES:
- Only give CORRECT, standard etymologies grounded in the given etymology_text. NEVER invent roots.
  If etymology_text does not support a clean learner-useful decomposition, prefer useful:false.
- Keep it concise. Chinese glosses for every morpheme.

Write the result as a JSON array (one record per input word, same order) to EXACTLY this path
using the Write tool: ${outf}
The file content must be valid JSON: [{"term":"...","useful":true,"breakdown":"...","story":"...","origin":"..."}, {"term":"...","useful":false}, ...]

Then reply with just: "batch ${pad(i)}: <useful_count> useful / <total> words".`
}

const results = await parallel(
  indices.map((i) => () => agent(prompt(i), { label: `etym:${pad(i)}`, phase: 'Reformat', model: MODEL }))
)
const done = results.filter(Boolean).length
log(`etym reformat complete: ${done}/${indices.length} agents returned`)
return { requested: indices.length, returned: done }
