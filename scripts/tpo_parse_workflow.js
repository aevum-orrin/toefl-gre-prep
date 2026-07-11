export const meta = {
  name: 'tpo-parse',
  description: 'Parse real TPO reading/listening text into structured items (source:real)',
  phases: [{ title: 'Parse', detail: 'one subagent per TPO section' }],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const section = A.section          // 'reading' | 'listening'
const tpos = A.tpos                // e.g. ['TPO54','TPO55',...]
const txtDir = A.txtDir            // .../official-real/tpo_txt
const outDir = A.outDir            // .../official-real/<section>

function readingPrompt(tpo, p) {
  const zh = p === 1 ? '第一篇' : p === 2 ? '第二篇' : '第三篇'
  return `You are parsing a REAL retired TOEFL test (TPO) into structured JSON. Read these two files:
${txtDir}/${tpo}/reading_q.txt   (3 reading passages; each has a title, the passage, then numbered questions "1." "2." ... each with options "A." "B." "C." "D.")
${txtDir}/${tpo}/reading_a.txt   (answer keys, one line per passage like "${zh}：DCBCA BDBB(BCD)")

Focus ONLY on reading passage #${p} (the ${p}${p === 1 ? 'st' : p === 2 ? 'nd' : 'rd'} passage in reading_q.txt) and its answer-key line "${zh}：...".

Output a SINGLE JSON object (not an array), keys EXACTLY:
- "id": "${tpo.toLowerCase()}_r_${p}"
- "kind": "academic_passage"
- "title": the passage's title, verbatim
- "passage": the FULL passage text of passage #${p}, VERBATIM English (fix words that got glued together by PDF extraction by re-inserting the obvious spaces; strip Chinese watermark lines like 微信号/公众号)
- "questions": an array — one entry PER numbered question of passage #${p}. Each = {"q": full question text, "options": [the 4 option strings in A,B,C,D order, verbatim], "answer": the 0-based index from the "${zh}" key (its letters map to questions in order: A→0 B→1 C→2 D→3), "explanation": ""}. SKIP the final multi-select summary question (the one whose key is in parentheses like "(BCD)").
- "source": "real"

CRITICAL correctness rule: the correct answers come ONLY from the "${zh}" line in reading_a.txt. If that line is present, extract ~9-10 questions and map each answer from its letters. If reading_a.txt has NO "${zh}" answer-key line (file empty or missing that passage), output "questions": [] and do NOT invent any answers — never guess. A TOEFL passage has ~9-10 questions, not more; if you're producing 12+, you've mis-split the options into questions.

Write ONLY that JSON object (valid UTF-8, no fences) to:
${outDir}/tpo_${tpo}_p${p}.json
Then reply with ONLY the integer number of questions written. Do not paste the JSON.`
}

function listeningPrompt(tpo) {
  return `You are parsing a REAL retired TOEFL test (TPO) listening section into structured JSON. Read:
${txtDir}/${tpo}/listening_transcript.txt   (the spoken transcripts: conversations and lectures, labelled like S1C1, S1L1, S1L2, S2C1, S2L1...)
${txtDir}/${tpo}/listening_q.txt            (the questions with A/B/C/D options for each conversation/lecture)
${txtDir}/${tpo}/listening_a.txt            (answer keys per section/passage)

Produce a JSON array, ONE object per conversation or lecture, keys EXACTLY:
- "id": "${tpo.toLowerCase()}_l_1", "_l_2", ... (in order)
- "kind": "conversation" for the C (conversation) items, "academic_talk" for the L (lecture) items
- "title": a short title from the topic
- "transcript": the full transcript for that item, VERBATIM English (strip Chinese watermark lines)
- "questions": [{"q": question text, "options": [A,B,C,D strings], "answer": 0-based index from the key, "explanation": ""}] — SKIP any question you cannot confidently key or that is multi-select.
- "source": "real"

Match each transcript to its questions and its answer-key entry by the S#C#/S#L# label and order. Keep text verbatim. Write ONLY the JSON array (valid UTF-8, no fences) to:
${outDir}/tpo_${tpo}.json
Then reply with ONLY the integer count of items written. Do not paste the JSON.`
}

let tasks
if (Array.isArray(A.pairs) && A.pairs.length) {
  tasks = A.pairs.map(([tpo, p]) => ({ tpo, p, label: `reading ${tpo} p${p}` }))  // explicit retry list
} else if (section === 'reading') {
  tasks = tpos.flatMap(tpo => [1, 2, 3].map(p => ({ tpo, p, label: `reading ${tpo} p${p}` })))
} else {
  tasks = tpos.map(tpo => ({ tpo, label: `listening ${tpo}` }))
}

const results = await parallel(tasks.map(t => () => {
  const prompt = section === 'reading' ? readingPrompt(t.tpo, t.p) : listeningPrompt(t.tpo)
  return agent(prompt, { label: t.label, phase: 'Parse', agentType: 'general-purpose' })
    .then(r => ({ t, r })).catch(() => ({ t, r: null }))
}))

const ok = results.filter(x => x && x.r != null).length
log(`TPO ${section} parse: ${ok}/${tasks.length} tasks done`)
return { section, ok, total: tasks.length }
