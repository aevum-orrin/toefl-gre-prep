# TOEFL iBT 2026 — Verified Official Format & Scoring

> Reform **effective 2026-01-21**. This file is the single source of truth the apps/rubrics
> encode. Everything here is anchored to official ETS sources; third-party details are flagged.
> Compiled 2026-07-09 from deep web research against ETS pages + the official rubric PDFs.

## Structure (official ETS content pages)

| Order | Section | ~Time | Items | Adaptive |
|-------|---------|-------|-------|----------|
| 1 | Reading | 30 min | 50 | Yes (multistage) |
| 2 | Listening | 29 min | 47 | Yes (multistage) |
| 3 | Writing | 23 min | 12 | No |
| 4 | Speaking | 8 min | 11 | No |

Active testing ≈ **90 min**; ETS quotes "~2 hours" for the whole appointment. Item counts include
many auto-scored micro-items (each blank / sentence-build counts), so they overstate the number of
"real" comprehension questions.

**Changed vs. the 2023-07 format:** R & L became adaptive; Speaking fully rebuilt (old 4 tasks →
Listen-and-Repeat + Take-an-Interview); **Integrated Writing removed** (Writing = Build-a-Sentence +
Write-an-Email + Write-for-an-Academic-Discussion); scale moved to 1.0–6.0 (CEFR).

## Scoring scale

- **1.0–6.0, 0.5 increments**, per section AND overall. Overall = mean of 4 section bands, rounded
  to nearest 0.5.
- CEFR: 6.0→C2 · 5.0–5.5→C1 · 4.0–4.5→B2 · 3.0–3.5→B1 · 2.0–2.5→A2 · 1.0–1.5→A1.
- **Task-level rubrics are 0–5** (Speaking & Writing); these feed the 1–6 section band. ETS does NOT
  publish the raw-to-band conversion.
- Transition window **2026-01-21 → 2028-01-21**: reports also show a comparable 0–120. Rough
  equivalents: 100≈5.0, 90≈4.5, 80≈4.0.

## Speaking (2 tasks, 11 items, ~8 min, NO prep time)

**A. Listen and Repeat** — hear 7 short sentences (campus/community, often w/ a visual), each played
once, repeat exactly after a beep. Response windows ~8–12 s (third-party). Scored 0–5 per item.
Official rubric facets: repetition exactness, intelligibility, meaning preservation.

**B. Take an Interview** — a simulated interview: 4 spoken questions on ONE topic (academic/campus,
experiences & opinions), spontaneous, ~45 s each, no prep. Scored 0–5 per item.
Official rubric facets: topic relevance & elaboration, fluency & pace, intelligibility/pronunciation,
language use (grammar+vocab range/accuracy).

Official rubric PDF: https://www.ets.org/pdfs/toefl/speaking-rubrics.pdf (© 2025 ETS).

## Writing (3 tasks, 12 items, ~23 min)

**1. Build a Sentence** — arrange words/phrases into a grammatical sentence. Auto-scored, right/wrong,
no essay rubric (accounts for most of the 12 items).

**2. Write an Email** — write an email in an academic/social situation (request, give info, propose a
solution). ~80–120 words, ~7 min (third-party). Scored 0–5.
Official facets: elaboration & purpose · syntax & vocabulary · **social conventions** (politeness,
register, appropriate request/refusal/criticism, organization — email-specific) · language accuracy.

**3. Write for an Academic Discussion** — a professor posts a question, two classmates reply, you add
your post stating & supporting an opinion. ~100–130 words, ~10 min (third-party). Scored 0–5.
Official facets: relevance & elaboration · syntax & vocabulary · **discourse engagement** (functions as
a genuine contribution to the discussion) · language accuracy.

Official rubric PDF: https://www.ets.org/pdfs/toefl/writing-rubrics.pdf (© 2025 ETS).

> ETS rubrics are **holistic** (each 0–5 level is one bundled descriptor). The facets above are the
> named sub-constructs *inside* each level — used to drive AI feedback, but ETS does not report
> per-facet sub-scores.

## Reading (up to ~50 items, ~28–30 min, multistage adaptive)
Delivered in **two modules**: module 1 is the same for everyone; based on that performance module 2
is **easy** (daily-life-heavy) or **hard** (academic-heavy). Task types:
- **Read an Academic Text** — a ~200-word academic passage + ~5 MC questions (main idea, detail,
  inference, vocabulary-in-context, purpose). Note: much shorter than the pre-2026 ~700-word passages.
- **Read in Daily Life** — a 15–150-word practical text (email, text-message chain, memo, poster,
  menu, invoice, schedule…) + a couple of MC questions.
- **Complete the Words** — vocabulary-in-context cloze: an academic paragraph with target words
  blanked; supply/choose the word. We model each blank as a 4-option MC so it auto-scores.

All auto-scored → 1–6 band.

## Listening (up to ~47 items, ~29 min, multistage adaptive)
Also **two modules** (module 2 easy/hard by performance). Multiple native accents. Task types:
- **Listen and Choose a Response** — hear one short statement/question, pick the most natural spoken
  reply (1 MC).
- **Listen to a Conversation** — a 2-speaker campus conversation + ~4 MC.
- **Listen to an Announcement** — a campus/classroom announcement + ~3 MC.
- **Listen to an Academic Talk** — a single-speaker mini-lecture + ~5 MC.

All auto-scored → 1–6 band. Transcripts are played (TTS in our tool) and never shown.

> Per-module item counts and the exact task mix are **not published by ETS** (the format is adaptive).
> Our `mock-test` tool assembles a fixed, full-length approximation at "standard" difficulty and says
> so — it does not fake the adaptive routing. Sources (fetched 2026-07-10): ETS content page +
> BestMyTest / TOEFL Resources / Magoosh 2026-format write-ups.

## Official practice resources
- **TOEFL Go! app** (free, AI scoring w/ the real rubrics): https://toeflgo.ets.org
- **Free full-length sample test (Jan 2026)**: https://www.ets.org/toefl/test-takers/ibt/prepare/sample-test-jan-2026-1.html
- Prep hub: https://www.ets.org/toefl/test-takers/ibt/prepare.html
- Scoring guides: writing-rubrics.pdf · speaking-rubrics.pdf (linked above)

## Known gaps / caveats (be honest in the app)
- Per-task second/word counts are third-party, not ETS-published.
- Adaptive routing rules & score caps are third-party.
- Raw-to-band conversion tables are NOT published by ETS.
- MyBest/superscore status on the 1–6 scale is unconfirmed.

## Sources (most load-bearing)
ETS transformation announcement · ETS content pages (reading/listening/speaking/writing) ·
ETS China score-scale-update page · the two ETS rubric PDFs. All fetched 2026-07-09.
