"""
discover_characters.py — Auto-discover the character roster from the segments

Usage:
    python discover_characters.py <franchise_dir>

A brand-new franchise has no character list, but score_segments.py needs one up front
(config.json -> "characters"). This step fills that gap: it reads a representative sample
of state/segments/*.txt, asks the model which named characters recur, canonicalises name
variants ("Hermione" / "Miss Granger" -> "Hermione Granger"), ranks them by how many
segments they appear in, and writes the roster into config.json.

Selection rule:
  - Keep the core cast (model-classified "main"), capped at CORE_CEILING.
  - If fewer than MIN_ROSTER mains cross the bar, top up with the highest-appearing side
    characters until the roster reaches MIN_ROSTER (the ">=7" requirement).

Idempotent / backward-compatible: if config.json already has a non-empty "characters" list
(every existing franchise does), the run is a no-op — so re-running run_franchise.py on
got/friends/hp never disturbs their hand-curated rosters.

Reuses the provider plumbing from score_segments.py (make_client / generate / .env models),
so it honours SCORER_PROVIDER and the model overrides. Adds one optional override:
  DISCOVER_MODEL — model for discovery (default: IDENTIFY_MODEL, i.e. cheap/fast).
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

# Reuse the exact provider plumbing the scorer uses — no second client to drift.
sys.path.insert(0, str(Path(__file__).parent))
from score_segments import make_client, generate, _strip_fences, IDENTIFY_MODEL

DISCOVER_MODEL = os.getenv("DISCOVER_MODEL", IDENTIFY_MODEL)

MIN_ROSTER = 7        # the ">=7 characters" requirement
CORE_CEILING = 15     # don't let the main cast balloon past this
SAMPLE_SEGMENTS = 40  # how many segments to scan (evenly spaced) to bound cost
SEGMENT_CHAR_CAP = 8000  # truncate each sampled segment to stay well within context


def _sample_segments(segment_files: list[Path], n: int) -> list[Path]:
    """Pick up to n evenly-spaced segments across the whole series (start..end)."""
    if len(segment_files) <= n:
        return segment_files
    step = len(segment_files) / n
    return [segment_files[int(i * step)] for i in range(n)]


def _extract_names(client, segment_text: str) -> list[str]:
    """One call: names of characters meaningfully present in this segment (free-form)."""
    prompt = f"""You are reading one segment of a TV/film script or book.

List the NAMED characters who are meaningfully present here — they speak, act, make a
decision, or are significantly described (not merely mentioned in passing). Use each
character's most complete/canonical name as it appears (e.g. "Hermione Granger", not
"Hermione" or "Miss Granger"). Ignore unnamed roles ("the guard", "a waiter").

Segment text:
{segment_text}

Respond with ONLY a JSON array of name strings, e.g. ["Jon Snow", "Tyrion Lannister"].
If there are no named characters, respond with []."""
    raw, _ = generate(client, DISCOVER_MODEL, prompt, max_tokens=1024)
    try:
        names = json.loads(_strip_fences(raw))
        return [n.strip() for n in names if isinstance(n, str) and n.strip()]
    except (json.JSONDecodeError, TypeError):
        print(f"    WARNING: could not parse name list: {raw[:160]}")
        return []


def _consolidate(client, counts: Counter, display_name: str) -> list[dict]:
    """One call: merge aliases of the same person, sum appearances, tag main vs side.

    Returns a list of {name, appearances, tier} sorted by appearances desc.
    """
    listing = "\n".join(f"- {name}: {count}" for name, count in counts.most_common())
    prompt = f"""These are raw character-name tallies harvested from segments of "{display_name}".
Counts are how many sampled segments each spelling appeared in.

{listing}

Tasks:
1. Merge spellings/aliases that refer to the SAME character into one canonical full name,
   summing their counts (e.g. "Hermione" + "Miss Granger" -> "Hermione Granger").
2. Drop entries that are not actual recurring characters (typos, groups, places).
3. Tag each remaining character as "main" (central recurring cast) or "side"
   (recurring but secondary).

Respond with ONLY a JSON array, sorted by appearances descending, of objects:
[{{"name": "Hermione Granger", "appearances": 31, "tier": "main"}}, ...]"""
    raw, _ = generate(client, DISCOVER_MODEL, prompt, max_tokens=4096)
    try:
        data = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        print(f"    WARNING: could not parse consolidation: {raw[:200]}")
        data = []
    out = []
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and isinstance(d.get("name"), str):
            out.append({
                "name": d["name"].strip(),
                "appearances": int(d.get("appearances", 0) or 0),
                "tier": "main" if d.get("tier") == "main" else "side",
            })
    out.sort(key=lambda d: d["appearances"], reverse=True)
    return out


def _select_roster(ranked: list[dict]) -> list[str]:
    """Core cast (capped), topped up with side characters until >= MIN_ROSTER."""
    mains = [d["name"] for d in ranked if d["tier"] == "main"][:CORE_CEILING]
    roster = list(mains)
    if len(roster) < MIN_ROSTER:
        for d in ranked:
            if d["name"] not in roster:
                roster.append(d["name"])
            if len(roster) >= MIN_ROSTER:
                break
    return roster


def run(franchise_dir: Path) -> None:
    config_path = franchise_dir / "config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Write the config skeleton first.")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("characters"):
        print(f"  SKIP — config.json already has {len(config['characters'])} characters "
              f"(delete the 'characters' list to re-discover).")
        return

    segments_dir = franchise_dir / "state" / "segments"
    segment_files = sorted(segments_dir.glob("*.txt")) if segments_dir.exists() else []
    if not segment_files:
        print(f"ERROR: no .txt segments in {segments_dir}. Run the ingest adapter first.")
        sys.exit(1)

    sample = _sample_segments(segment_files, SAMPLE_SEGMENTS)
    client = make_client()
    display_name = config.get("display_name", franchise_dir.name)
    print(f"  Scanning {len(sample)} of {len(segment_files)} segments (model={DISCOVER_MODEL})...")

    counts: Counter = Counter()
    for seg in sample:
        text = seg.read_text(encoding="utf-8")[:SEGMENT_CHAR_CAP]
        for name in _extract_names(client, text):
            counts[name] += 1

    if not counts:
        print("ERROR: no named characters found in the sample.")
        sys.exit(1)

    ranked = _consolidate(client, counts, display_name)
    if not ranked:
        print("ERROR: consolidation produced no characters.")
        sys.exit(1)

    roster = _select_roster(ranked)
    config["characters"] = [{"index": i, "name": name} for i, name in enumerate(roster)]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    n_main = sum(1 for d in ranked if d["tier"] == "main")
    print(f"  Discovered {len(ranked)} characters ({n_main} main); selected {len(roster)}:")
    for c in config["characters"]:
        print(f"    {c['index']:>2}  {c['name']}")
    print(f"  Wrote roster to {config_path.relative_to(franchise_dir.parent.parent)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python discover_characters.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
