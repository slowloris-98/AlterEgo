# Design Decisions

A running log of significant design decisions for the AlterEgo scoring pipeline,
with the alternatives considered and their tradeoffs. Newest first.

---

## 2026-06-29 — Cosine similarity for character matching (fix centroid magnet)

### Problem

The match step found the **Euclidean-nearest** character to the user's OCEAN z-vector
([scoring.ts](app/lib/scoring.ts), mirrored in [validate.py](build/core/validate.py)). Expanding
the squared distance, `dist² = ‖user‖² − 2·(user·char) + ‖char‖²`, the `‖char‖²` term **penalizes
every extreme character**. The characters whose z-vector sits closest to the cast centroid therefore
win for any respondent who answers near the middle — which Likert averaging + reverse-coding makes
the common case.

This is the matching-side twin of the 2026-06-27 "everyone matches Daenerys" failure, and it was
**systemic across all franchises**. A 20,000 uniform-random-respondent simulation through the real
pipeline funnelled the bulk of users into the one or two lowest-z-magnitude characters:

| Franchise | Top-2 share | Reachable (≥1%) | Magnet(s) |
|-----------|-------------|-----------------|-----------|
| ramayana  | **71%** | 10/14 | Sugriva, Angad |
| hp        | **66%** | 8/15  | Ginny, Harry |
| friends   | **60%** | 6/11  | Chandler, Rachel |
| breakingbad | **57%** | 7/9 | Hank, Skyler |
| got       | **41%** | 14/25 | Robb/Arya/Daenerys; Joffrey **never** matched |

The existing [validate.py](build/core/validate.py) confusion-matrix check did **not** catch this: it
only feeds *in-character* answer keys (extreme answers that land near their own character), so it
measures the diagonal, never what a moderate real user gets.

---

### Option A (considered, NOT chosen) — unit-normalize z-vectors, keep Euclidean

Normalize each character's z-vector (and the user's) to unit length, then keep Euclidean distance.

**Pros**
- Removes the `‖char‖²` magnitude penalty; mathematically near-identical to cosine.
- Leaves room to later blend a mild *intensity* term back in (distance on the unit sphere + a
  magnitude factor).

**Cons**
- More machinery than needed for a result that is, in practice, the same as cosine.
- Two-step (normalize then distance) is less direct to read and to keep in sync across the TS and
  Python implementations.

---

### Option B (CHOSEN) — cosine similarity

Rank characters by **cosine similarity** of the user's z-vector to each character's z-vector — i.e.
match on the *pattern/direction* of the traits, not their intensity. This drops the `‖char‖²` penalty
entirely.

**Pros**
- Simplest, standard "which character are you most like" fix; one helper in each of
  [scoring.ts](app/lib/scoring.ts) and [validate.py](build/core/validate.py).
- **Preserves every answer-key diagonal** — all 74 keys across the 5 franchises still self-match, so
  no character regressed.
- Top-2 shares drop to **23–45%** and nearly every character becomes reachable (e.g. ramayana
  14/14, got 21/25, Joffrey reachable again).

**Cons / accepted tradeoffs**
1. **Slightly higher extreme-character share** under uniform-random answering (e.g. villains), because
   random answering is itself unrealistic; real users cluster less extremely. Accepted — far better
   than the centroid magnet.
2. **Thinner winning margins** on tightly-packed casts (got/ramayana smallest cosine margin ~0.02 vs
   comfortable Euclidean gaps). Still correct, but the diagonal is less padded if a character's OCEAN
   profile is later tweaked.
3. Cosine ranges `[-1, 1]`; the displayed match percentage maps it to `(cos + 1) / 2 ∈ [0, 1]` so the
   UI stays monotonic and never shows a negative percentage. Sort order is unaffected.

### Decision

Adopt **cosine similarity**, mirrored in [scoring.ts](app/lib/scoring.ts) and
[build/core/validate.py](build/core/validate.py) (the two implementations must stay in sync). Guard
against regression with the per-franchise **no-magnet** check (no character >40% of random
respondents) plus answer-key parity in [scoring.test.ts](app/lib/scoring.test.ts), and add a
`validate.py --simulate [N]` mode that prints the random-respondent distribution so the bias can be
re-measured for any new franchise without an API key.

---

## 2026-06-27 — Replace pairwise OCEAN comparison with per-segment single-shot rating

### Problem

The original Call B in [build/core/score_segments.py](build/core/score_segments.py) did an
O(present²) pairwise comparison for every segment, ran *both* orderings of each pair, and
wrote a free-text `reason` for every judgement.

Measured cost:
- One episode (s1e01, 15 characters present) → **1,303 comparison records**, ~27 Call B batches.
- All 73 GOT episodes extrapolate to **~95,000 records and ~2,000+ Call B API requests**, with
  output tokens (the per-record `reason`) dominating the bill. Unaffordable even on Haiku.

Two findings that make a cheaper design safe:
1. **Downstream ignores segments.** [fit_scores.py:46](build/core/fit_scores.py#L46) pools *all*
   records and never uses the `segment` field (it's only for checkpointing). Per-episode
   granularity adds no modeling value, and whole-character profiles are all the app needs.
2. **`build_profiles.py` only needs a per-character raw OCEAN vector** (`raw_scores.json`). Anything
   that produces a valid `raw_scores.json` leaves it unchanged.

The new shape, common to both options below: keep **Call A** (presence gate); replace **Call B**
with **one rating call per segment** that scores every present character on all five traits at
once (1–10 scale, no per-judgement `reason`) → ~73 API calls for the whole series instead of
~2,000. The two options differ only in how those per-segment ratings become a per-character score.

---

### Option A (considered, NOT chosen) — derive pairwise locally, keep Bradley-Terry

From each segment's rating table, generate pairwise win/loss records **locally** (no API): for each
trait, every pair of present characters with different scores → one record in the existing
`comparisons.jsonl` schema; equal scores → tie (skipped). Feed the unchanged Bradley-Terry fit in
[fit_scores.py](build/core/fit_scores.py).

**Pros**
- Reuses the *validated* ranking method; downstream (`fit_scores.py`, `build_profiles.py`) untouched.
- Bradley-Terry is a regularized maximum-likelihood fit — robust to sparse characters and uneven
  comparison counts; naturally discriminating.
- Fully reversible; same API cost (~73 calls — the pairwise derivation is free/local).

**Cons**
- Keeps the `choix` dependency and the `comparisons.jsonl` record explosion (~95k rows) — disk and
  conceptual overhead for data that is now derived, not measured.
- More moving parts than the project needs given whole-character profiles are sufficient.

---

### Option B (CHOSEN) — no pairwise, aggregate ratings directly

Skip pairwise comparison and Bradley-Terry entirely. Aggregate the per-segment ratings directly
into `raw_scores.json`, then run `build_profiles.py` as-is.

**Pros**
- Simpler pipeline: drop the `choix` dependency and remove `fit_scores.py` from the default path.
- No ~95k-row `comparisons.jsonl`; store ~73 × 15 × 5 small numbers instead.
- More interpretable — a character's trait score is derived directly from their episode ratings.
- Reversible: the same Call B output can still derive pairwise later, so we are not locked in.
- API cost is the same ~73 calls as Option A.

**Cons / accepted tradeoffs**
1. **Calibration / scale drift (the big one).** Absolute ratings drift between calls; "7/10
   openness" in ep 3 ≠ ep 40. This is *exactly* why the original spec chose pairwise.
   **Mandatory mitigation:** normalize *within each segment* (z-score / rank the present characters
   per trait) before pooling. That converts absolute scores into scale-invariant relative positions,
   recovering most of pairwise's benefit. Pooling across many episodes then cancels noise. **Never
   pool raw absolute scores across calls** — that re-introduces the original "everyone matches
   Daenerys" failure.
2. **Less principled aggregation.** A plain mean is more sensitive to outlier episodes and present-set
   composition than Bradley-Terry's regularized MLE. Mitigation: appearance weighting + a
   low-confidence flag for characters seen in few segments (port `MIN_COMPARISONS`).
3. **Central-tendency compression.** LLMs cluster absolute ratings near the middle; after the
   cross-cast z-scoring in `build_profiles`, compressed scores amplify noise. Mitigation: 1–10 scale,
   a prompt demanding full-range use, and a spread check during verification.

### Decision

Go with **Option B (no pairwise)**, with **within-segment normalization as a mandatory step** (not
raw averaging). It is close to Option A's quality for a 25-character cast seen across dozens of
episodes, and is markedly simpler. `fit_scores.py` and the pairwise approach are retained in the
repo as a documented fallback should sparse-data robustness ever prove insufficient.

The rejected sub-option — dropping pairwise *and* averaging raw absolutes with no normalization — is
explicitly avoided, as it reinstates the scale-drift failure the rebuild was meant to fix.
