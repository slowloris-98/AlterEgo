"""
build_profiles.py — Raw OCEAN scores → z-vectors → out/characters.json

Usage:
    python build_profiles.py <franchise_dir>

Reads state/raw_scores.json, computes per-trait cast mean and std,
stores each character's z-vector and the cast statistics, writes out/characters.json.
Also asks Claude for a one-line blurb per character based on their score profile.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
BLURB_MODEL = os.getenv("BLURB_MODEL", "claude-haiku-4-5-20251001")


def get_blurb(client: anthropic.Anthropic, name: str, raw: dict[str, float]) -> str:
    """Ask Claude for a one-line personality blurb based on the character's OCEAN scores."""
    score_lines = "\n".join(
        f"  {trait.capitalize()}: {raw[trait]:.0f}/100"
        for trait in TRAITS
    )
    prompt = f"""Given these Big Five personality scores for {name} (from A Song of Ice and Fire),
write a single punchy sentence (max 15 words) describing their personality in plain English.
Do not mention the scores or trait names — just describe the person.

Scores:
{score_lines}

Respond with the sentence only."""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=BLURB_MODEL,
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip().strip('"')
        except anthropic.RateLimitError:
            if attempt < 2:
                time.sleep(10)
            else:
                raise
    return ""


def run(franchise_dir: Path) -> None:
    config = json.loads((franchise_dir / "config.json").read_text())

    raw_path = franchise_dir / "state" / "raw_scores.json"
    if not raw_path.exists():
        print("ERROR: raw_scores.json not found. Run fit_scores.py first.")
        sys.exit(1)

    raw_data = json.loads(raw_path.read_text())
    characters_raw = raw_data["characters"]

    # Compute per-trait cast mean and std
    stats: dict[str, dict] = {}
    for trait in TRAITS:
        values = np.array([c["raw"][trait] for c in characters_raw])
        mean = float(values.mean())
        std  = float(values.std(ddof=1)) if len(values) > 1 else 1.0
        if std < 1e-9:
            std = 1.0  # prevent division by zero if all scores identical
        stats[trait] = {"mean": round(mean, 2), "std": round(std, 2)}

    print("Cast statistics:")
    for trait, s in stats.items():
        print(f"  {trait}: mean={s['mean']}, std={s['std']}")

    # Generate blurbs
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    out_characters = []
    for c in characters_raw:
        z = {
            trait: round((c["raw"][trait] - stats[trait]["mean"]) / stats[trait]["std"], 4)
            for trait in TRAITS
        }
        print(f"  Blurb: {c['name']}...")
        blurb = get_blurb(client, c["name"], c["raw"])

        out_characters.append({
            "name":  c["name"],
            "raw":   {t: round(c["raw"][t], 1) for t in TRAITS},
            "z":     z,
            "blurb": blurb,
        })

    output = {
        "franchise": config["id"],
        "stats":     stats,
        "characters": out_characters,
    }

    out_dir = franchise_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "characters.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\ncharacters.json written to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_profiles.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
