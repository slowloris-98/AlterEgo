# AlterEgo

**▶︎ Live app: [alter-ego-smort.vercel.app](https://alter-ego-smort.vercel.app/)**

**Which character are you?** AlterEgo is a personality-quiz web app. You answer a short,
themed quiz; it scores you on the **Big Five (OCEAN)** personality traits and matches you to the
fictional character whose personality is closest to yours — with a similarity score, runner-up
matches, and a radar chart.

It's built to host **many tests** (one per franchise). The first one is **Game of Thrones**; adding
another is a drop-in (see [Adding a new test](#adding-a-new-test)).

---

## How it works

The project has two halves:

### 1. Offline build (`build/`) — Python, run once locally
Turns source material into character personality profiles.

- Reads show scripts (one text segment per episode) for each character.
- Uses Claude to rate every character on the five OCEAN traits, segment by segment.
- Aggregates and standardizes those into a **z-scored profile** per character.
- Outputs `characters.json` (profiles) and a hand-authored, themed `quiz.json`.

The scoring deliberately uses **z-scores + Euclidean distance** (not cosine similarity) so that
distinctive characters stay distinct, instead of everyone collapsing onto one "average" match.

> This half needs an `ANTHROPIC_API_KEY` and is run **only locally**. Its outputs are committed; the
> raw source text and intermediate state are git-ignored.

### 2. Runtime (`app/`) — Next.js, deployed on Vercel
The website users actually visit.

- A **landing page** lists every available test.
- Each test has its own **independent, themed flow** at `/test/<id>`.
- Questions are **reshuffled on every visit** so a repeat visitor doesn't get the same order.
- On submit, the server computes the match (OCEAN scoring all happens server-side) and returns the
  closest character, the top 3 runners-up, and the user's trait percentages.
- Each submission is **logged anonymously** to Supabase (salted IP hash only, no personal data) for
  later analysis. Logging gracefully no-ops if Supabase isn't configured.

All the heavy AI/Python work is offline, so the live app is pure TypeScript math — fast, free to
host, and with no API keys in production.

---

## Repository layout

```
AlterEgo/
├── build/                  # Offline Python pipeline (run locally, once)
│   ├── core/               # scoring, aggregation, profile + quiz validation
│   ├── franchises/<id>/    # per-franchise config, source segments, outputs
│   └── run_franchise.py    # pipeline driver
├── app/                    # Next.js runtime (this is what gets deployed)
│   ├── app/                # routes: landing, /test/[franchise], /api/match
│   ├── components/         # Quiz, ResultCard, RadarChart
│   ├── lib/                # scoring, registry, Supabase logging
│   └── data/<id>/          # characters.json, quiz.json, meta.json per test
├── supabase/schema.sql     # quiz_logs table
└── GOT_OCEAN_REBUILD_SPEC.md  # full design spec
```

---

## Running locally

### The web app
```bash
cd app
npm install
npm run dev          # http://localhost:3000
```
The app runs immediately with the existing Game of Thrones data. Logging stays off until you
configure Supabase (below).

### Logging (optional)
Create `app/.env.local`:
```
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
IP_HASH_SALT=any-long-random-string
```
Then run [`supabase/schema.sql`](supabase/schema.sql) in your Supabase project's SQL editor.

### Rebuilding the data (optional)
```bash
cd build
pip install -r core/requirements.txt
# set ANTHROPIC_API_KEY in build/.env
python run_franchise.py got
```

---

## Adding a new test

1. Run the build pipeline for the new franchise to produce its `characters.json` + `quiz.json`.
2. Drop them, plus a `meta.json`, into `app/data/<id>/`.
3. (Optional) Add a `[data-theme="<id>"]` block in `app/app/globals.css` for its own colour theme.

The landing page auto-discovers the folder and gives the new test its own isolated flow — **no code
changes needed**.

---

## Deployment

Live at **[alter-ego-smort.vercel.app](https://alter-ego-smort.vercel.app/)**, hosted on
**Vercel** (free Hobby tier) with **Root Directory set to `app/`**. Add the three Supabase env vars
in the Vercel project settings. Every push to `main` auto-deploys.

---

## Tech

Next.js · TypeScript · Tailwind CSS · Recharts · Supabase (Postgres) · Python + Anthropic SDK
(offline build).
