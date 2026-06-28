"""
aggregate_scores.py — per-segment OCEAN ratings → raw OCEAN scores 0-100

Usage:
    python aggregate_scores.py <franchise_dir>

Reads state/segment_scores.jsonl (written by score_segments.py: one row per segment,
each row mapping present character → {trait: 1-10}). For each segment and trait it
**z-scores the present characters against one another** (within-segment normalisation),
then pools each character's normalised values across all segments. The pooled means are
rescaled to [0, 100] per trait and written to state/raw_scores.json — the same schema
fit_scores.py produced, so build_profiles.py is unchanged.

Why within-segment z-scoring: absolute 1-10 ratings drift between calls ("7" in one
episode ≠ "7" in another), so pooling raw scores would be miscalibrated. Z-scoring within
each segment turns the ratings into scale-invariant *relative positions* among the
characters who actually shared that context — recovering most of what pairwise comparison
gave us, without any pairwise API calls. See design_decisions.md.

This replaces the pairwise + Bradley-Terry stage (fit_scores.py), which remains in the
repo as a fallback.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import jsonlines

TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
MIN_SEGMENTS = 5   # flag a character as low-confidence for a trait below this many segments


def run(franchise_dir: Path) -> None:
    config = json.loads((franchise_dir / "config.json").read_text())
    characters = config["characters"]
    names = [c["name"] for c in characters]

    scores_path = franchise_dir / "state" / "segment_scores.jsonl"
    if not scores_path.exists():
        print("ERROR: segment_scores.jsonl not found. Run score_segments.py first.")
        sys.exit(1)

    # Dedupe by segment name (last row wins) — guards against a duplicate row if a
    # run was interrupted between writing the row and updating progress.json.
    rows_by_segment: dict[str, dict] = {}
    for row in jsonlines.open(scores_path):
        rows_by_segment[row["segment"]] = row.get("scores", {})
    print(f"Loaded ratings for {len(rows_by_segment)} segment(s).")

    # Accumulate within-segment z-scores per character per trait.
    z_sums: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(TRAITS))
    z_counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(TRAITS))

    for scores in rows_by_segment.values():
        for ti, trait in enumerate(TRAITS):
            present = [(name, entry[trait]) for name, entry in scores.items()
                       if name in names and trait in entry]
            if len(present) < 2:
                continue  # relative position is undefined with fewer than 2 characters
            vals = np.array([v for _, v in present], dtype=float)
            mean = vals.mean()
            std = vals.std()  # population std across the present cast
            for (name, v) in present:
                z = 0.0 if std < 1e-9 else (v - mean) / std
                z_sums[name][ti] += z
                z_counts[name][ti] += 1

    # Pool to a mean z per character/trait, then rescale the cast to [0, 100] per trait.
    mean_z = np.zeros((len(names), len(TRAITS)))
    counts = np.zeros((len(names), len(TRAITS)), dtype=int)
    for i, name in enumerate(names):
        for ti in range(len(TRAITS)):
            c = z_counts[name][ti]
            counts[i, ti] = c
            mean_z[i, ti] = (z_sums[name][ti] / c) if c else 0.0  # 0 = cast-neutral if unseen

    raw_scores = np.zeros_like(mean_z)
    for ti, trait in enumerate(TRAITS):
        col = mean_z[:, ti]
        lo, hi = col.min(), col.max()
        if hi - lo < 1e-9:
            raw_scores[:, ti] = 50.0
        else:
            raw_scores[:, ti] = (col - lo) / (hi - lo) * 100.0
        seen = int((counts[:, ti] > 0).sum())
        print(f"  [{trait}] {seen}/{len(names)} characters rated; "
              f"z range {lo:.2f} -> {hi:.2f}")

    # Low-confidence: characters rated in fewer than MIN_SEGMENTS segments for a trait.
    low_confidence: dict[str, list[str]] = {}
    for ti, trait in enumerate(TRAITS):
        low = [names[i] for i in range(len(names)) if counts[i, ti] < MIN_SEGMENTS]
        low_confidence[trait] = low
        if low:
            print(f"  Low confidence [{trait}]: {low}")

    output = {
        "franchise": config["id"],
        "characters": [
            {
                "name": c["name"],
                "index": c["index"],
                "raw": {trait: round(float(raw_scores[i, ti]), 2)
                        for ti, trait in enumerate(TRAITS)},
            }
            for i, c in enumerate(characters)
        ],
        "low_confidence": low_confidence,
    }

    out_path = franchise_dir / "state" / "raw_scores.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nraw_scores.json written to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python aggregate_scores.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
