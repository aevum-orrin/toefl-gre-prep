export const meta = {
  name: 'pos-expand',
  description: 'Opus pass: add missing common parts of speech + fill example-less POS senses',
  phases: [{ title: 'Expand', detail: 'one subagent per 200-word batch' }],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const deck = A.deck, inDir = A.inDir, outDir = A.outDir
function pad(n) { return String(n).padStart(3, '0') }

let idxs = []
if (Array.isArray(A.only) && A.only.length) idxs = A.only.slice()
else for (let i = A.start; i < A.end; i++) idxs.push(i)

const results = await parallel(idxs.map(i => () => {
  const inPath = `${inDir}/batch_${pad(i)}.json`
  const outPath = `${outDir}/batch_${pad(i)}.json`
  const prompt =
`You are an expert lexicographer auditing a TOEFL/GRE study deck for MISSING PARTS OF SPEECH.
Read the JSON file at:
${inPath}
Each row: {term, have: [{pos, en, zh}] (the senses the deck already has), fill: [pos, …] (optional — POS blocks that exist but still have NO example sentence; "?" means the deck could not determine that sense's part of speech)}.

For EACH word do two things:

1. ADD — decide whether a MAJOR learner's dictionary (Oxford / Longman / Merriam-Webster Learner's) lists a COMMON part of speech for this word that is missing from "have". Classic case: "elite" is in the deck only as a noun, but "elite athletes / an elite university" is a common adjective use, so the adjective must be added. Only add a POS that a learner really meets in academic English or campus speech — skip archaic, dialectal, technical-jargon-only, or vanishingly rare uses. Most words need NOTHING added; that is expected and correct.

2. FILL — for every pos listed in "fill", write the missing content for that existing sense. If the pos is "?" the deck failed to tag it: determine the correct part of speech from the meaning and return it under the proper name.

Part-of-speech names must be exactly one of: noun, verb, adjective, adverb, preposition, conjunction, pronoun, determiner, numeral, interjection, abbreviation, phrase.

Output a JSON array containing ONLY the words you have something to say about (skip a word entirely if it needs no ADD and has no FILL):
[
  {"term": "elite",
   "add": [{"pos": "adjective",
            "def_en": "<learner's-dictionary definition of THAT part of speech>",
            "def_zh": "<concise Chinese gloss>",
            "example": "<one natural CEFR B2-C1 sentence that unambiguously shows that POS>",
            "collocations": ["<2-3 common collocations>"]}],
   "fill": [{"pos": "verb", "was": "<the pos string as it appeared in fill, e.g. \\"?\\" or \\"verb\\">",
             "def_zh": "<Chinese gloss if the deck's sense had none, else \\"\\">",
             "example": "<one natural example sentence for that sense>",
             "collocations": ["<2-3 collocations>"]}]}
]
Omit "add" or "fill" when empty. Never invent a meaning the word does not have; ground every definition in the given en/zh.

Write ONLY that JSON array (valid UTF-8, no markdown fences) with the Write tool to EXACTLY:
${outPath}
Then reply with ONLY two integers separated by a slash: <words with an ADD> / <words with a FILL>. Do NOT paste the JSON.`
  return agent(prompt, { label: `pos ${deck} b${pad(i)}`, phase: 'Expand', agentType: 'general-purpose' })
    .then(r => ({ i, r }))
    .catch(() => ({ i, r: null }))
}))

const ok = results.filter(x => x && x.r != null)
log(`pos expand: ${ok.length}/${idxs.length} batches done`)
return { deck, ok: ok.length, total: idxs.length, fails: results.filter(x => x.r == null).map(x => x.i) }
