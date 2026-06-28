# Design Decisions

A running log of significant design decisions for the AlterEgo scoring pipeline,
with the alternatives considered and their tradeoffs. Newest first.

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
