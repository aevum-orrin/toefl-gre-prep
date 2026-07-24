export const meta = {
  name: 'scene-pos-defen',
  description: 'Fill missing pos / def_en on the TOEFL scene-vocab deck (phrase-heavy)',
  phases: [{ title: 'Fill', detail: 'one agent per ~40-sense batch' }],
}

// args = { indices: [int,...], model?: "sonnet" }
const CACHE = '/scratch/nmasoud_owned_root/nmasoud_owned1/ctlang/lang-prep-cache'
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const INDIR = `${CACHE}/enrich_batches/scenes`
const OUTDIR = `${CACHE}/enrich_out/scenes`
const indices = A.indices || []
const MODEL = A.model || undefined
log(`scene pos/def_en: ${indices.length} batches`)

const pad = (i) => String(i).padStart(4, '0')

function prompt(i) {
  const inf = `${INDIR}/batch_${pad(i)}.json`
  const outf = `${OUTDIR}/batch_${pad(i)}.out.json`
  return `You are a lexicographer completing a TOEFL listening "campus scene" vocabulary deck for
Chinese learners. Many entries are MULTI-WORD PHRASES (e.g. "drop out of school", "financial aid") —
this is expected and they must be handled, not skipped.

Read the JSON file: ${inf}
It is an array of items: {term, sense_index, zh (the Chinese gloss — the meaning is ALREADY FIXED),
example (an existing example sentence, may be empty), have_pos, need (which fields are missing)}.

For EACH item produce {term, sense_index, pos, def_en}:
- pos: the part of speech OF THE MEANING GIVEN BY \`zh\`. Use exactly one of:
  noun, verb, adjective, adverb, phrase, preposition, conjunction, pronoun, interjection.
  For multi-word entries choose by the phrase's grammatical function:
    "financial aid" -> noun        (a noun phrase)
    "drop out of school" -> verb   (a verb phrase)
    "below average" -> adjective
  Use "phrase" ONLY when it genuinely fits none of the above (e.g. a fixed sentence-like formula).
  If \`have_pos\` is non-empty, KEEP that value verbatim — do not re-label it.
- def_en: ONE concise learner's-dictionary definition IN ENGLISH of that same meaning
  (Oxford/Merriam-Webster learner style, ~5-20 words). It must match \`zh\`; do NOT define a
  different sense of the word. Ground it in \`zh\` and \`example\`. No trailing period needed.

RULES:
- Return one record per input item, SAME order, keeping \`term\` and \`sense_index\` EXACTLY as given.
- Never invent a meaning that contradicts \`zh\`.
- Plain ASCII quotes only inside strings, and escape any quote you use, so the file stays valid JSON.

Write the result as a JSON array to EXACTLY this path using the Write tool: ${outf}
The content must be valid JSON: [{"term":"...","sense_index":0,"pos":"noun","def_en":"..."}, ...]

Then reply with just: "batch ${pad(i)}: <count> senses".`
}

const results = await parallel(
  indices.map((i) => () => agent(prompt(i), { label: `scene:${pad(i)}`, phase: 'Fill', model: MODEL }))
)
const done = results.filter(Boolean).length
log(`scene fill complete: ${done}/${indices.length} agents returned`)
return { requested: indices.length, returned: done }
