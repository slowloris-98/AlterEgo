---
name: build-franchise
description: Build the complete AlterEgo pipeline for a brand-new series/movie — Phase 1 (find a transcript+scene dataset, segment it, auto-discover the character roster, score OCEAN profiles, author the themed quiz + answer keys) and Phase 2 (wire the franchise into the Next.js web app with its own theme), additively so existing franchises keep working. Use when asked to "add a new series/movie", "build the whole pipeline for <show>", "set up a new franchise", or "do phase 1 and phase 2 for <title>".
---

# build-franchise — add a whole new series to AlterEgo

AlterEgo matches quiz-takers to characters of a franchise on the Big-Five (OCEAN) traits.
This skill takes a series/movie title and produces a live, themed quiz page end-to-end. It
**reuses the existing build pipeline** (`build/`) and the **filesystem-driven** web app
(`app/`); it does not rewrite scoring math or the quiz keying.

## Ground rules

- **Reuse, don't reinvent.** The Python pipeline (`build/run_franchise.py` + `build/core/*`)
  already does ingest → discover → score → aggregate → profiles. Drive it; don't reimplement.
- **Additive only.** Never edit another franchise's data, the shared scoring code, or
  existing `[data-theme]` / `:root` blocks. New work goes in new files; the only edits to
  shared files are *appends* (a new CSS theme block).
- **One human gate:** confirming the dataset (step 2). After that, run end-to-end, stopping
  only on errors.
- **The quiz keying is LOCKED.** Question wording is re-skinned per franchise; the trait and
  `reverse` of each of `q1`–`q25` are fixed (see `build/franchises/hp/quiz_keying.md`).
- **IDs:** `id` is lowercase, short, slug-safe (`The Office` → `office`, `Breaking Bad` →
  `breakingbad`). The same `id` is the franchise dir name, the app data dir name, and the
  CSS theme name.
- **Cost:** scoring calls the Anthropic API (~1–2 calls/segment). Episodic series ≈ 70–250
  calls; a book blob ≈ ~500. Models come from `build/.env` (default Haiku). Mention the rough
  segment count before the scoring run.

## Prerequisites (check first)

- `build/.env` exists with `ANTHROPIC_API_KEY`. If missing, stop and ask the user.
- Python env: use `build/venv` if present (`build/venv/Scripts/python.exe` on Windows),
  else system `python`. Deps are in `build/core/requirements.txt` (anthropic, jsonlines,
  python-dotenv, requests).
- Run pipeline commands from the `build/` directory.

---

# PHASE 1 — data → OCEAN profiles → quiz + answer keys

### Step 1 — Resolve id & guard against clobber
Derive `<id>`, confirm the display name with the user. **Abort** if
`build/franchises/<id>/` or `app/data/<id>/` already exists (don't overwrite a franchise).

### Step 2 — Find the dataset (the one human gate)
The data must have **dialogue + scene/action descriptions** (scene context is what gives the
OCEAN signal). Use WebSearch to find candidates, in this preference order:
- **Per-episode script repos on GitHub** (best — like got's `shekharkoirala/Game_of_Thrones`).
  Downloadable as raw `.txt`, one file per episode = one natural segment.
- **HTML transcript sites/repos** with stage directions (like friends' `fangj/friends`).
- **Kaggle transcript datasets** (may need auth/manual download — like hp).
- Full book/script text (a delimiter-less blob is fine; the hp adapter shows how to chunk it).

Present the best 1–2 candidates with their URL, coverage, and whether scene directions are
present. **Stop and get the user's confirmation** (and any Kaggle/manual download or creds)
before downloading anything.

### Step 3 — Scaffold the franchise
Create `build/franchises/<id>/config.json` with an **empty** roster (discovery fills it):
```json
{
  "id": "<id>",
  "display_name": "<Display Name>",
  "source": { "type": "<github_repo|html_transcripts|kaggle_dataset|...>",
              "description": "<what it is>", "ref": "<repo / dataset / url>" },
  "characters": []
}
```
Copy `build/franchises/hp/quiz_keying.md` to `build/franchises/<id>/quiz_keying.md` and swap
the franchise name in the heading/intro — **leave the locked trait/reverse table verbatim**.

### Step 4 — Write the ingest adapter
Create `build/ingest/ingest_<id>.py` exposing `run(franchise_dir: Path)` that writes
`state/segments/*.txt` (one segment per scene/episode/chapter-sized slice). Model it on the
closest existing adapter — read it first and follow its shape:
- Per-episode GitHub `.txt` → `build/ingest/ingest_got.py` (download raw, idempotent skip).
- HTML transcripts → `build/ingest/ingest_friends.py` (strip HTML, **keep** scene directions).
- One big blob with no chapter markers → `build/ingest/ingest_hp.py` (reconstruct sentences,
  pack to ~12 KB chunks with merge/split guardrails). Place source in
  `build/franchises/<id>/books/` (gitignored) when the source is a manual download.
Keep adapters idempotent (skip if `state/segments/` already populated). Segment size must
stay well under the model context window — match the size targets in the template adapter.

### Step 5 — Run Phase 1 end-to-end
From `build/`: `python run_franchise.py <id>`
Runs **ingest → discover → score → aggregate → profiles**, then copies
`out/{characters,quiz}.json` to `app/data/<id>/`.
- **discover** (`build/core/discover_characters.py`) auto-fills `config.json`'s roster from a
  sample of segments: recurring named characters, aliases merged, ranked by appearances. It
  keeps the core cast and **tops up with side characters until there are at least 7**. Review
  the printed roster; if it's off, edit `config.json`'s `characters` and re-run
  `python run_franchise.py <id> --step discover` (delete the list first to force re-discovery)
  or just hand-edit, then continue with `--step score`.
- Re-running is safe/resumable: scoring tracks `state/progress.json`; discover self-skips once
  a roster exists.
- Note: `out/quiz.json` does not exist yet, so the copy step will SKIP it — that's expected;
  you author it next and re-copy.

### Step 6 — Author the themed quiz
Write `build/franchises/<id>/out/quiz.json`:
```json
{ "franchise": "<id>", "questions": [ { "id": "q1", "text": "...", "trait": "openness",
  "reverse": false, "options": [ {"label": "...", "value": 5}, ... , {"label": "...", "value": 1} ] }, ... ] }
```
Rules (see `build/franchises/<id>/quiz_keying.md` and the hp quiz at `app/data/hp/quiz.json`
for tone):
- Exactly 25 questions `q1`–`q25`; **`trait` and `reverse` copied exactly from the locked
  table** (5 questions per trait; the neuroticism inversion is already encoded as `reverse`).
- Each question: a short series-flavored scenario, then 5 options with `value` 5→1, where
  value 5 = strongest agreement with the source IPIP item's own pole (direction is handled by
  `reverse` at scoring time — do NOT pre-invert the wording).
- Make scenarios distinctly evoke this series; keep options graded and parallel.

### Step 7 — Generate & verify answer keys
From `build/`: `python core/answer_keys.py franchises/<id>`
Writes `out/answer_keys.{json,md}` and **must report `N/N keys verified, 0 failures`** (each
character reproduces itself; no duplicate answer vectors). If it fails, the quiz can't
separate those characters — revisit the quiz wording/spread or the roster, then re-run.
(Optional sanity check: `python core/validate.py franchises/<id>` for an in-character
confusion matrix — this makes API calls.)

---

# PHASE 2 — wire it into the web app (additive only)

The app auto-discovers any `app/data/<id>/` folder containing `meta.json` + `quiz.json` +
`characters.json` (`app/lib/registry.ts`). No code registration needed.

### Step 8 — Place the data files
Ensure `app/data/<id>/characters.json` and `app/data/<id>/quiz.json` exist. `characters.json`
was copied in step 5; copy the freshly-authored quiz:
`cp build/franchises/<id>/out/quiz.json app/data/<id>/quiz.json`
(or re-run `python run_franchise.py <id> --step profiles` which re-copies both — profiles is
cheap, no scoring).

### Step 9 — Write meta.json
`app/data/<id>/meta.json`:
```json
{ "id": "<id>", "display_name": "<Display Name>",
  "tagline": "<short hook question>",
  "description": "Answer 25 questions from <world>. We score you on the Big Five (OCEAN) traits and find the <Display Name> character closest to you.",
  "theme": "<id>", "image": "/art/<id>.jpg" }
```
The `image` path may dangle — art is added manually later.

### Step 10 — Append the theme block
Append a `[data-theme="<id>"]` block to `app/app/globals.css` (just before the `body {` rule),
choosing a palette that evokes the series. Copy the 8 variables + `background-image` pattern
from an existing block (e.g. `[data-theme="hp"]`). **Append only — never touch `:root` or
other franchises' blocks.** Variables: `--bg --surface --border --fg --muted --accent
--accent-ink --danger` (space-separated RGB channels for Tailwind opacity modifiers).

### Step 11 — Images: skip
Don't add character art or card art. `ResultCard.tsx` falls back to themed initials, so a
missing `public/art/...` breaks nothing. (Listed in the repo `todo` for manual follow-up.)

---

# Verification (run before reporting done)

1. `python core/answer_keys.py franchises/<id>` → `N/N keys verified, 0 failures`.
2. `cd app && npm run build` passes (`generateStaticParams` pre-renders `/test/<id>`).
3. `npm run dev`, then:
   - landing page `/` shows the new franchise card (via `listFranchises()`),
   - `/test/<id>` renders with the new theme; submitting returns a match + radar chart from
     `/api/match`,
   - **got / friends / hp still render unchanged** (regression check).
4. Summarize what was created and note the two manual follow-ups: character/card art, and
   committing the new files.

# Files this skill creates/edits

- New code (one-time, already in repo): `build/core/discover_characters.py`, the `discover`
  step in `build/run_franchise.py`.
- Per run — new: `build/franchises/<id>/{config.json,quiz_keying.md}`,
  `build/ingest/ingest_<id>.py`, `build/franchises/<id>/out/*` (generated),
  `app/data/<id>/{meta.json,quiz.json,characters.json}`.
- Per run — appended: `app/app/globals.css` (one `[data-theme="<id>"]` block).
