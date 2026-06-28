"""
ingest_got.py — Game of Thrones ingest adapter

Downloads the per-episode TV-script .txt files from the public GitHub repo
  shekharkoirala/Game_of_Thrones  (Data/season{S}/e{E}.txt)
and writes them into <franchise_dir>/state/segments/ as one segment file per episode.

The universal scorer (core/score_segments.py) then reads that segments/ folder.
No scraping needed — the files already exist in the repo; we just download them raw.

Usage:
    python ingest_got.py <franchise_dir>

Idempotent: episodes already present in segments/ are skipped.
"""

import sys
from pathlib import Path

import requests

RAW_BASE = "https://raw.githubusercontent.com/shekharkoirala/Game_of_Thrones/master/Data"

# Episode counts per season (S1-6 = 10, S7 = 7, S8 = 6).
SEASON_EPISODES = {1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 7, 8: 6}

MIN_BYTES = 200  # skip placeholder/empty episode files (repo has a couple of stubs)


def run(franchise_dir: Path) -> None:
    segments_dir = franchise_dir / "state" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    downloaded = 0
    skipped = 0
    empty = 0

    for season, n_eps in SEASON_EPISODES.items():
        for ep in range(1, n_eps + 1):
            out_file = segments_dir / f"s{season}e{ep:02d}.txt"
            if out_file.exists():
                skipped += 1
                continue

            url = f"{RAW_BASE}/season{season}/e{ep}.txt"
            try:
                resp = session.get(url, timeout=30)
            except requests.RequestException as e:
                print(f"  ERROR s{season}e{ep:02d}: {e}")
                continue

            if resp.status_code != 200:
                print(f"  MISS  s{season}e{ep:02d}: HTTP {resp.status_code}")
                continue

            text = resp.text
            if len(text.encode("utf-8")) < MIN_BYTES:
                print(f"  EMPTY s{season}e{ep:02d}: {len(text)} chars — skipping")
                empty += 1
                continue

            out_file.write_text(text, encoding="utf-8")
            print(f"  OK    s{season}e{ep:02d}  ({len(text)} chars)")
            downloaded += 1

    total = len(list(segments_dir.glob("*.txt")))
    print(f"\nIngest complete: {downloaded} downloaded, {skipped} already present, "
          f"{empty} empty/skipped. {total} segments total in {segments_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_got.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
