export const meta = {
  name: 'enrich-vocab-opus',
  description: 'Opus-enrich a range of TOEFL/GRE vocab batches (subscription subagents)',
  phases: [{ title: 'Enrich', detail: 'one subagent per 60-word batch' }],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const deck = A.deck
const start = A.start
const end = A.end
const inDir = A.inDir
const outDir = A.outDir

function pad(n) { return String(n).padStart(3, '0') }

let idxs = []
if (Array.isArray(A.only) && A.only.length) {
  idxs = A.only.slice()          // explicit list of batch indices (e.g. resume the missing ones)
} else {
  for (let i = start; i < end; i++) idxs.push(i)
}

const results = await parallel(idxs.map(i => () => {
  const inPath = `${inDir}/batch_${pad(i)}.json`
  const outPath = `${outDir}/batch_${pad(i)}.json`
  const prompt =
`You are an expert lexicographer building a TOEFL/GRE study deck. Read the JSON file at:
${inPath}
It is a list of words, each {term, zh (Chinese gloss), def_en (a rough English gloss, may be empty), pos (list of part-of-speech labels)}.

For EACH word produce an enrichment object:
{
  "term": <same term>,
  "gloss_en": ONE clear learner's-dictionary definition of the word's MOST COMMON meaning, in plain English (Oxford/Merriam-Webster learner style). Ground it in the given zh/def_en — phrase the KNOWN meaning, do not invent a different one.
  "senses": for EACH part of speech in the word's "pos" list, one object {
    "pos": <exact pos label as given>,
    "example": one natural example sentence at CEFR B2-C1 that unambiguously shows THAT part-of-speech meaning; exam-appropriate, self-explanatory,
    "collocations": [2-3 common collocations or fixed phrases for that sense]
  }
}
Use exactly the pos labels provided; do not add parts of speech that weren't requested. Keep sentences natural and accurate.

Write the result as a JSON array (one object per input word, same order) to EXACTLY this path using the Write tool:
${outPath}
Write ONLY valid UTF-8 JSON to that file (no markdown fences). Then reply with ONLY the integer count of words you wrote — do NOT paste the JSON into your reply.`
  return agent(prompt, { label: `enrich ${deck} b${pad(i)}`, phase: 'Enrich', agentType: 'general-purpose' })
    .then(r => ({ i, r }))
    .catch(() => ({ i, r: null }))
}))

const ok = results.filter(x => x && x.r != null).length
log(`enrich wave done: ${ok}/${idxs.length} batches returned`)
return { deck, start, end, ok, total: idxs.length }
