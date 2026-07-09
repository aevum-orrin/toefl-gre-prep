# vocab-srs — spaced-repetition vocabulary trainer

A shared TOEFL/GRE flashcard web page driven by `prep_core.SRS` (the SM-2 algorithm, the same family
Anki started with). Scheduling only — no network, no cost.

```bash
source ../../env.sh
uvicorn app:app --reload --port 8003   # http://localhost:8003
```

## How to use
- Switch **TOEFL / GRE** decks at the top (wordlists come from `toefl/vocab/` and `gre/vocab/`).
- See the word → press **Space** to reveal the definition/example → grade yourself with the
  Anki-style buttons:
  - **Again (1)** didn't recall → repeat tomorrow
  - **Hard (2)** / **Good (3)** / **Easy (4)** → recalled; the interval grows per SM-2
- Keyboard: `Space` reveals, `1/2/3/4` grade.

## Data
- Wordlist (content): JSON of `{term, definition, example, pos}` under each exam's `vocab/` folder;
  extend freely.
- Review state (scheduling): `data/srs/<deck>.json` (gitignored), saved automatically on each grade.
- Adding words: append to the wordlist JSON; new terms are merged in on startup and existing review
  progress is untouched.

> SM-2 is plenty for a personal sprint. To minimize review load later you can swap the scheduler for
> FSRS (Anki's current default) without changing the rest of the app — see the research notes under
> `docs/`.
