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

function readingPrompt(tpo) {
  return `You are parsing a REAL retired TOEFL test (TPO) into structured JSON. Read these two files:
${txtDir}/${tpo}/reading_q.txt   (3 reading passages, each followed by numbered questions with A/B/C/D options)
${txtDir}/${tpo}/reading_a.txt   (answer keys, one line per passage like "第一篇：DCBCA BDBB(BCD)" — the letters are the correct options in order; a trailing "(XYZ)" is a multi-select summary question)

Produce a JSON array with ONE object per reading passage (usually 3), keys EXACTLY:
- "id": "${tpo.toLowerCase()}_r_1" / "_r_2" / "_r_3"
- "kind": "academic_passage"
- "title": the passage title (verbatim)
- "passage": the full passage text, VERBATIM English (strip any Chinese watermark lines like 微信号/公众号)
- "questions": for each numbered single-answer question, {"q": question text, "options": [the 4 option strings A,B,C,D in order], "answer": 0-based index from the answer key letter (第一篇 = passage 1's key, 第二篇 = passage 2, 第三篇 = passage 3; A→0 B→1 C→2 D→3), "explanation": ""}. SKIP the final multi-select summary question (the "(XYZ)" one) — do not include it.
- "source": "real"

Only include questions whose answer letter you can read from the key. Keep passage/question/option text verbatim. Write ONLY the JSON array (valid UTF-8, no fences) to:
${outDir}/tpo_${tpo}.json
Then reply with ONLY the integer count of passages written. Do not paste the JSON.`
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

const results = await parallel(tpos.map(tpo => () => {
  const prompt = section === 'reading' ? readingPrompt(tpo) : listeningPrompt(tpo)
  return agent(prompt, { label: `${section} ${tpo}`, phase: 'Parse', agentType: 'general-purpose' })
    .then(r => ({ tpo, r })).catch(() => ({ tpo, r: null }))
}))

const ok = results.filter(x => x && x.r != null).length
log(`TPO ${section} parse: ${ok}/${tpos.length} done`)
return { section, ok, total: tpos.length }
