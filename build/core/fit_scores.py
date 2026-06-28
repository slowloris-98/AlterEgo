"""
fit_scores.py — Bradley-Terry fitting via choix → raw OCEAN scores 0-100

Usage:
    python fit_scores.py <franchise_dir>

Reads state/comparisons.jsonl, fits a Bradley-Terry model per trait using
choix.ilsr_pairwise, normalises parameters to [0, 100], and writes
state/raw_scores.json.

Also flags characters with fewer than MIN_COMPARISONS records for a trait
as low-confidence in the output.
"""

import json
import sys
from pathlib import Path

import numpy as np
import choix
import jsonlines

TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
MIN_COMPARISONS = 10   # warn if a character has fewer records than this for any trait
ALPHA = 0.1            # regularisation — prevents divergence for sparse characters


def run(franchise_dir: Path) -> None:
    config = json.loads((franchise_dir / "config.json").read_text())
    characters = config["characters"]
    n = len(characters)
    name_by_index = {c["index"]: c["name"] for c in characters}

    comparisons_path = franchise_dir / "state" / "comparisons.jsonl"
    if not comparisons_path.exists():
        print("ERROR: comparisons.jsonl not found. Run pairwise_rank.py first.")
        sys.exit(1)

    all_records = list(jsonlines.open(comparisons_path))
    print(f"Loaded {len(all_records)} comparison records.")

    raw_scores: dict[str, list[float]] = {}
    confidence: dict[str, list[str]] = {}  # trait -> list of low-confidence character names

    for trait in TRAITS:
        records = [(r["winner_idx"], r["loser_idx"])
                   for r in all_records if r["trait"] == trait]

        if len(records) < n:
            print(f"  WARNING [{trait}]: only {len(records)} records — may be insufficient.")

        # Count comparisons per character
        counts = [0] * n
        for w, l in records:
            counts[w] += 1
            counts[l] += 1

        low_conf = [name_by_index[i] for i, c in enumerate(counts) if c < MIN_COMPARISONS]
        if low_conf:
            print(f"  Low confidence [{trait}]: {low_conf}")
        confidence[trait] = low_conf

        try:
            params = choix.ilsr_pairwise(n, records, alpha=ALPHA)
        except Exception as e:
            print(f"  ERROR fitting {trait}: {e}")
            # Fall back to uniform scores
            params = np.zeros(n)

        lo, hi = params.min(), params.max()
        if hi - lo < 1e-9:
            # All identical — assign 50 across the board
            normalised = [50.0] * n
        else:
            normalised = ((params - lo) / (hi - lo) * 100).tolist()

        raw_scores[trait] = normalised
        print(f"  [{trait}] fitted. Range: {lo:.3f} → {hi:.3f}")

    # Build output keyed by character name
    output = {
        "franchise": config["id"],
        "characters": [],
        "low_confidence": confidence,
    }

    for c in characters:
        idx = c["index"]
        output["characters"].append({
            "name": c["name"],
            "index": idx,
            "raw": {trait: round(raw_scores[trait][idx], 2) for trait in TRAITS},
        })

    out_path = franchise_dir / "state" / "raw_scores.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nraw_scores.json written to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fit_scores.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
