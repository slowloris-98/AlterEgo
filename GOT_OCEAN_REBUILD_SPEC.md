# Game of Thrones Personality Test — Rebuild Spec (OCEAN, book-grounded, free-tier)

> **How to use this document:** This is a self-contained build specification. Drop it into an
> empty repo and hand it to a fresh agent/developer session. It contains the full context,
> architecture, verified resources, file-by-file plan, and verification steps needed to build the
> project from scratch. No prior conversation is required.

---

## 1. What we're building & why

A web quiz that matches a user to a **Game of Thrones character** based on personality. The user
answers ~25 GoT-themed questions; the app scores them on the **Big Five (OCEAN)** traits and returns
the closest-matching character with a similarity score and a radar chart.

**This is a ground-up rebuild of an earlier version** that had two flaws we are explicitly fixing:

1. **"Everyone gets Daenerys."** The old app used **cosine similarity**, which ignores magnitude —
   a "moderate on everything" character became an attractor almost every user matched. **Fix:**
   z-score the traits and use **Euclidean distance**.
2. **Unreliable character scoring.** The old app used a zero-shot BART pipeline that sliced
   `result["scores"][0:5]` assuming label order, but HuggingFace zero-shot returns scores **sorted
   by confidence**, scrambling trait attribution. **Fix:** score characters with **Claude pairwise
   comparison + Bradley-Terry ranking**, grounded in book evidence.

**Design decisions already made (do not re-litigate):**

| Decision | Choice |
|---|---|
| Trait framework | Big Five / OCEAN (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism) |
| Character grounding | **The books (A Song of Ice and Fire)** — only source rich in actions/scenes/inner thoughts (see §3) |
| Scoring method | **Claude pairwise comparison → Bradley-Terry** (NO fine-tuning — see §6 rationale) |
| Processing | **Book-by-book / incremental** — comparisons accumulate across the 5 books; per-book snapshots retained for character arcs |
| Matching | **z-score + Euclidean distance** (replaces cosine) |
| Quiz | GoT-themed re-skins of public-domain **IPIP-50** items, with a hidden trait mapping |
| Runtime stack | **Next.js + TypeScript** on **Vercel** (free) |
| Database | **Supabase Postgres** (free) — logs every quiz for later analysis |
| Theming | Product stays **show-themed** (recognizable names/images) even though scoring is book-grounded |

---

## 2. Verified resource availability (checked June 2026)

| Resource | Status | Notes / link |
|---|---|---|
| **IPIP-50 Big Five items + scoring key** | ✅ Public domain, free | Canonical source: https://ipip.ori.org — 5 × 10-item scales, 1–5 Likert, +/- keyed items |
| **`choix` (Bradley-Terry in Python)** | ✅ On PyPI, maintained | https://pypi.org/project/choix/ · https://github.com/lucasmaystre/choix |
| **Anthropic Python SDK** | ✅ `pip install anthropic` | Used offline only for character scoring |
| **Supabase free tier** | ✅ 500 MB DB, 2 projects, unlimited API requests | ⚠️ Free projects **pause after ~1 week inactivity**; no auto-backups |
| **Vercel Hobby (free)** | ✅ Serverless functions, free TLS, GitHub deploy | Next.js first-class |
| **Recharts (radar chart)** | ✅ React `<RadarChart>` | Replaces old Plotly chart |
| **ASoIaF book full text** | ⚠️ **Copyrighted; no legitimate dataset** | Unofficial `.txt` copies exist on Kaggle/GitHub (e.g. `khulasasndh/game-of-thrones-books`, `kingabzpro/gameofthronesbooks`). Legality is gray. See §3 for posture + fallback. |
| **An API of Ice and Fire** | ✅ Free structured metadata | https://anapioficeandfire.com — character names/aliases/houses (useful for `aliases.json`) |
| **GoT show dialogue (Kaggle)** | ✅ Available (fallback) | `albenft/game-of-thrones-script-all-seasons` — dialogue-only, no scene descriptions |

**Sources:** [IPIP](https://ipip.ori.org), [choix PyPI](https://pypi.org/project/choix/),
[Supabase free tier 2026](https://uibakery.io/blog/supabase-pricing),
[An API of Ice and Fire](https://anapioficeandfire.com),
[ASoIaF book dataset (Kaggle)](https://www.kaggle.com/datasets/khulasasndh/game-of-thrones-books).

---

## 3. The book-text question (important — read before building)

The book-grounded approach depends on having the 5 books as plaintext. **The books are copyrighted.**
Unofficial `.txt` copies circulate, but there is no clean, legitimate "dataset" of the full text.

**Posture this spec assumes:** book text is used **locally only**, for **private analysis**, to
derive **numeric trait scores + short paraphrased justifications**. The raw text is **git-ignored and
never committed or redistributed**. Only derived JSON (`characters.json`) ships. This is a defensible
personal/educational-use posture, but the builder should make their own call on sourcing the text.

**Fallback if you don't want to use book text:** ground scoring on **show dialogue** (Kaggle,
available) plus Claude's own knowledge of the characters. Lower signal (no actions/inner thoughts),
but fully clean. The pipeline below is unchanged except `index_corpus.py` reads dialogue CSV rows
per character instead of book passages, and there is no "book-by-book" loop (one pass).

---

## 4. Architecture (two phases)

```
PHASE 1 — OFFLINE BUILD (Python, run once on your machine)
  books (local) ──► retrieve per character per book ──► running briefs ──► pairwise compares
                                                                              │
                                                                  Bradley-Terry (choix)
                                                                              │
                                                                     characters.json  (committed)
  IPIP-50 ──► hand-author GoT-themed quiz ─────────────────────────────► quiz.json     (committed)

PHASE 2 — RUNTIME (Next.js on Vercel, free)
  browser quiz ──► POST /api/match ──► z-score + Euclidean over characters.json
                                   └─► log row to Supabase ──► return {match, scores, chart}
```

The only LLM/Python work is **offline**. The runtime does trivial math, so there is **no Python
server** and no cold-start problem. `ANTHROPIC_API_KEY` is needed **only locally for the build**,
never in production.

---

## 5. Repository structure

```
got-personality-test/
├── build/                       # Python, offline, run locally
│   ├── books/                   # ASoIaF plaintext book1..book5  (LOCAL ONLY — git-ignored)
│   ├── aliases.json             # character -> [name aliases]  (seed from An API of Ice and Fire)
│   ├── rubric.md                # OCEAN trait definitions + anchor characters for comparisons
│   ├── index_corpus.py          # ONE book -> per-character passages (POV chapters + alias windows)
│   ├── build_briefs.py          # merge a book's evidence into each character's running brief
│   ├── pairwise_rank.py         # per-book pairwise compares -> append comparison records
│   ├── fit_scores.py            # choix Bradley-Terry over accumulated records -> raw OCEAN 0-100
│   ├── run_books.py             # driver: loop books 1..5 (index->brief->compare), checkpoint
│   ├── build_profiles.py        # raw OCEAN -> cast mean/std + z-vectors -> out/characters.json
│   ├── validate.py              # "answer-in-character" harness -> confusion matrix
│   ├── requirements.txt         # anthropic, choix, pandas, numpy, python-dotenv
│   ├── state/                   # checkpoints: briefs/<char>.md, comparisons.jsonl, per-book snapshots
│   └── out/{characters.json, quiz.json}
├── app/                         # Next.js (TypeScript, App Router)
│   ├── data/{characters.json, quiz.json}   # copied from build/out (server-side only)
│   ├── app/page.tsx             # quiz UI
│   ├── app/result/page.tsx      # result view (or render inline)
│   ├── app/api/match/route.ts   # compute match + log to Supabase
│   ├── lib/scoring.ts           # answers -> OCEAN -> z-score -> Euclidean match
│   ├── lib/db.ts                # Supabase client (service-role key, server-only)
│   ├── components/{Quiz,ResultCard,RadarChart}.tsx
│   └── package.json
├── supabase/schema.sql          # quiz_logs table
├── .gitignore                   # build/books/, .env*, build/state/
└── README.md
```

---

## 6. Offline build pipeline (the core)

**Why not fine-tuning** (in case it comes up): there is no labeled OCEAN ground truth to train on;
fine-tuning teaches output format/style, not reasoning; and it's overkill for scoring ~26 characters
once. In-context reasoning (retrieval + pairwise prompting) is strictly better here.

**Why pairwise, not absolute 0–100 scores:** LLMs are far more reliable at *relative* judgments
("who is more ambitious, A or B?") than absolute numbers. Pairwise + Bradley-Terry also naturally
**spreads characters apart**, directly countering the old "everyone clusters" problem.

**Key trick: decouple retrieval (per character, once per book) from comparison (reuses briefs).**
You never do retrieval at comparison time.

`run_books.py` loops books 1→5; for each book `b`:

1. **`index_corpus.py` — retrieve within book `b`.** Split book `b` into paragraphs. Detect each
   chapter's POV character (ASoIaF chapters are titled by POV). For each of ~26 characters collect:
   (their POV chapters in `b`) + (paragraphs in `b` matching their name/aliases, with a ±1-paragraph
   window for action context). Pronoun-only passages are intentionally skipped (no coreference); the
   volume of named mentions compensates.
2. **`build_briefs.py` — update running brief.** Claude merges book `b`'s passages into each
   character's cumulative **evidence brief** (~1–1.5k tokens), noting what's **new/changed this
   book** (this captures arcs). Map-reduce if a book's per-character passages exceed context.
   Checkpoint to `state/briefs/<char>.md`.
3. **`pairwise_rank.py` — per-book comparisons.** For each trait, for each character pair with
   sufficient evidence in book `b`, prompt Claude with the two briefs: *"Who shows more {trait}?
   Answer A or B + one-line reason."* Run **both directions** (A-vs-B and B-vs-A) to cancel position
   bias. **Append** each result to `state/comparisons.jsonl` (fields: `book, trait, winner, loser`).
   Snapshot the count state per book for arc analysis.

After book 5:

4. **`fit_scores.py` — Bradley-Terry via `choix`.** For each trait, feed all accumulated comparison
   records into `choix` (e.g. `choix.ilsr_pairwise`) to get per-character strength parameters →
   normalize to **raw OCEAN 0–100**. (Per-book snapshots = fit on records up to book `b`, optional
   for arcs.) Flag characters with too few comparisons as low-confidence.
5. **`build_profiles.py` — bake the matching scale.** Compute cast per-trait mean `μ_t` and std
   `σ_t`. Store each character's **z-vector** `char_z[t] = (raw_t − μ_t) / σ_t`, plus the `{μ_t,
   σ_t}` stats and a short justification (from the brief), into `out/characters.json`.

**Default weighting:** equal across all 5 books (whole-saga personality). Per-book snapshots are
retained so you can switch to recency-weighting ("who they became") or expose arcs without re-running.

**Model choice:** use Claude via the Anthropic API. Bulk pairwise (hundreds of cheap calls) →
`claude-sonnet-4-6` (or `claude-haiku-4-5` for lowest cost); brief synthesis → `claude-opus-4-8` or
`claude-sonnet-4-6`. All offline, run once.

### `characters.json` shape

```jsonc
{
  "stats": { "openness": {"mean": 52.1, "std": 18.3}, "conscientiousness": { ... }, ... },
  "characters": [
    { "name": "Tyrion Lannister",
      "raw":   { "openness": 78, "conscientiousness": 61, "extraversion": 70, "agreeableness": 55, "neuroticism": 48 },
      "z":     { "openness": 1.41, "conscientiousness": 0.33, ... },
      "blurb": "Sharp, curious, pragmatic; loyal to few, cynical about power." }
  ]
}
```

---

## 7. Quiz design (themed but principled)

- **25 questions, 5 per OCEAN trait**, authored as GoT-themed re-skins of **IPIP-50** items. Keep
  the validated trait + keying of each source item; only the *wording* becomes Westeros-flavored.
- **5-point Likert** (1–5). Include some **reverse-keyed** items per trait (mirror IPIP's keying).
- `quiz.json` carries the **hidden mapping** (the contract between build and runtime):

```jsonc
{ "questions": [
  { "id": "q1",
    "text": "Before the army reaches your gates, you've already...",
    "trait": "conscientiousness",
    "reverse": false,
    "options": [
      {"label": "Drilled every plan twice", "value": 5},
      {"label": "Made a rough plan", "value": 4},
      {"label": "Figured we'd improvise", "value": 2},
      {"label": "Not thought about it", "value": 1}
    ] }
] }
```

> **Authoring guardrail:** a themed rewrite must still measure its assigned trait/direction. E.g.
> "Would you stand and fight?" *reads* like courage but psychometrically loads on low Neuroticism /
> high Extraversion — keep the IPIP trait tag, don't trust the surface theme.

---

## 8. Runtime: matching math & scoring

`lib/scoring.ts`:

1. **Raw OCEAN from answers:** for each trait, flip reverse-keyed items (`6 − value`), average the
   trait's item values, scale to **0–100** → `user_raw[trait]`.
2. **Project onto the cast scale:** `user_z[trait] = (user_raw[trait] − μ_t) / σ_t` using the
   `stats` block in `characters.json`.
3. **Match:** `distance(user, char) = sqrt( Σ_t (user_z[t] − char_z[t])² )`; pick the minimum.
   Friendly similarity = `1 / (1 + distance)` (or rank-percentile).

Euclidean in z-space (not cosine) makes magnitude and per-trait spread matter, so extreme characters
stop being drowned out. The match runs **server-side** in `/api/match` (enables logging + keeps
`characters.json` off the client bundle).

---

## 9. Database (Supabase `quiz_logs`)

No PII. One row per submission, for "is the match distribution healthy?" analysis.

```sql
create table quiz_logs (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),
  answers       jsonb not null,        -- { "q1": 5, "q2": 2, ... }
  trait_scores  jsonb not null,        -- computed OCEAN 0-100
  match         text  not null,
  distance      double precision,
  session_id    text,                  -- anonymous client id (dedupe), optional
  referrer      text                   -- optional, no PII
);
```

Inserts happen **server-side** in `app/api/match/route.ts` via the Supabase **service-role** key
(never exposed to the client). Client POSTs answers → route computes match → logs → returns result.

---

## 10. Implementation phases (suggested order for a fresh session)

1. **Scaffold runtime.** `npx create-next-app@latest app --typescript --app`; add `recharts` and
   `@supabase/supabase-js`. Create `supabase/schema.sql`; run it in the Supabase SQL editor.
2. **Stub data.** Hand-write a tiny placeholder `characters.json` (3–4 characters) and a 5-question
   `quiz.json` so the runtime can be built/tested before the real build pipeline exists.
3. **Runtime core.** `lib/scoring.ts` (answers→OCEAN→z→Euclidean), `lib/db.ts`,
   `app/api/match/route.ts` (compute + log + return). Unit-test scoring with the stub data.
4. **Frontend.** `Quiz.tsx` (renders `quiz.json`, Likert inputs), `ResultCard.tsx` (match +
   similarity + trait bars + blurb), `RadarChart.tsx` (user vs match, OCEAN axes).
5. **Quiz authoring.** Map IPIP-50 items → 25 themed questions in `quiz.json` with trait/keying.
6. **Offline build (Python).** Seed `aliases.json` (from An API of Ice and Fire) + `rubric.md`;
   implement `index_corpus.py`, `build_briefs.py`, `pairwise_rank.py`, `fit_scores.py`,
   `build_profiles.py`, driven by `run_books.py`. Generate the real `characters.json`.
7. **Validate.** `validate.py`: have Claude answer the quiz *in character* for each character, run
   through the same scoring, produce a confusion matrix. **Pass = strong diagonal AND no single
   character dominating** (explicit "Daenerys magnet" regression check).
8. **Deploy.** Push to GitHub → import to Vercel → set env vars (below). Smoke-test live.

---

## 11. Environment / secrets

| Var | Where | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | **local build only** (`build/.env`) | Character scoring. **Never** in production. |
| `SUPABASE_URL` | Vercel + local | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Vercel (server-only) | Server-side log inserts. Never exposed client-side. |

`.gitignore` must include: `build/books/`, `build/state/`, `**/.env*`.

---

## 12. Verification (end-to-end)

- **Build sanity:** inspect `characters.json` — extreme characters (e.g. Ramsay, Eddard,
  Littlefinger) sit far apart in z-space, not bunched.
- **Validation harness:** `python build/validate.py` → confusion matrix; strong diagonal, no magnet.
- **Local app:** `npm run dev`; take the quiz; confirm match, similarity, trait bars, and radar
  render; confirm a row appears in Supabase `quiz_logs`.
- **Deployed smoke test:** submit on the Vercel URL; verify the log row; confirm `ANTHROPIC_API_KEY`
  is absent from the production runtime.
- **Distribution analysis (the real payoff of logging):**
  `select match, count(*) from quiz_logs group by match order by 2 desc;` — confirm matches are
  spread across characters, not collapsed onto one.

---

## 13. Open defaults (safe to change)

- DB = Supabase (Neon is an equivalent free Postgres alternative).
- Character set = ~26 most prominent; can trim to a top-15 list.
- Pairwise = round-robin both directions per book, skipping evidence-poor pairs; down-sample if cost
  matters.
- Book weighting = equal across books; snapshots retained for recency-weighting / arc features.
- If book text is not used, switch to the show-dialogue grounding fallback in §3 (single pass, no
  book loop).

---

## 14. Future franchises (planned, NOT yet built)

The Phase 1 build was implemented with an **adapter architecture**: a universal scorer engine
reads a flat folder of `.txt` segment files (`state/segments/`) and a small per-franchise
**ingest adapter** (`build/ingest/ingest_<id>.py`) is the only piece that knows how to turn a
given franchise's raw source into those segments. Adding a franchise = one adapter + a character
list in `config.json`. No engine, scoring, or fitting changes.

Current scope is **Game of Thrones only** (TV show scripts from the
`shekharkoirala/Game_of_Thrones` repo, one segment per episode). The two franchises below have
**verified-available data** and slot into the same pipeline when we choose to build them.

| Franchise | Verified data source | Adapter approach (`ingest_<id>.py`) |
|---|---|---|
| **Friends** | [EmilHvitfeldt/friends](https://github.com/EmilHvitfeldt/friends) — entire transcript in tidy format, ~67,373 utterances tagged by season / episode / scene / speaker. Also on [Kaggle](https://www.kaggle.com/datasets/divyansh22/friends-tv-show-script). | Read the tidy transcript, group rows by episode, render each as `SPEAKER: text` lines → write one `.txt` per episode into `state/segments/`. ~228 episodes. |
| **Harry Potter** | [Kornflex28/hp-dataset](https://github.com/Kornflex28/hp-dataset) — script/dialogue for all 8 films (also on [Kaggle](https://www.kaggle.com/datasets/kornflex/harry-potter-movies-dataset)). | Read each film's script → write one `.txt` per film (or per scene if finer granularity is wanted) into `state/segments/`. 8 films. |

**Notes / caveats for when these are built:**
- Each needs its own `build/franchises/<id>/config.json` with a **locked character list** (fixed
  integer indices — never reorder mid-run).
- Each needs its own themed `out/quiz.json` (25 IPIP-50-based items, mind the Emotional Stability
  → Neuroticism inversion).
- The GoT repo's `scrapper.py` (Genius.com album scraper) is **not** a general solution — it is
  hardcoded to GoT's Genius album layout. Friends and HP use their own structured datasets above,
  so each gets a purpose-built adapter rather than a shared scraper.
- Grounding is on **show/film canon**, which can diverge from the books — acceptable since the
  product is screen-themed and users recognize screen portrayals.
