"""
ingest_friends.py — Friends ingest adapter

Downloads the full Friends episode transcripts from the public GitHub repo
  fangj/friends  (https://fangj.github.io/friends/  ·  season/SSEE.html)
and writes one segment file per episode into
  <franchise_dir>/state/segments/  as  s{season}e{episode:02d}.txt

These fan transcripts include the *scene directions and action descriptions* (e.g.
"[Scene: Central Perk, everyone is there.]" and "(Phoebe enters and sits down)"), not just
spoken dialogue. That non-spoken behaviour is essential signal for OCEAN scoring — who does what,
how they react — so this source is used in preference to dialogue-only corpora (e.g. ConvoKit).
Each transcript page is HTML; we strip the tags to plain text, one paragraph (line of dialogue or
stage direction) per line, matching the shape of the GoT TV-script segments.

The universal scorer (core/score_segments.py) then reads that segments/ folder. Stdlib only
(html.parser, re) plus requests.

Usage:
    python ingest_friends.py <franchise_dir>

Idempotent: episodes already present in segments/ are skipped.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests

RAW_BASE = "https://raw.githubusercontent.com/fangj/friends/master"
INDEX_URL = f"{RAW_BASE}/index.html"

# Episode transcript filenames: "0101" or two-parters like "0212-0213"; we key the segment off the
# first SSEE. Non-numeric pages (e.g. "07outtakes.html") are skipped.
STEM_RE = re.compile(r"^(\d{2})(\d{2})(?:-\d{4})?$")

# Skip transcript boilerplate lines (nav/credits) that aren't dialogue or scene directions.
SKIP_LINE_RE = re.compile(
    r"^(written by|teleplay by|story by|transcribed by|transcript by|"
    r"with help from|minor improvements|additions by|commercial break|end)\b",
    re.IGNORECASE,
)


class TranscriptParser(HTMLParser):
    """Flatten the transcript HTML to one text line per <p> (dialogue or stage direction)."""

    _BREAK_TAGS = {"p", "br", "tr", "div", "li"}
    _SKIP_CONTENT = {"head", "title", "script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._cur: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP_CONTENT:
            self._skip_depth += 1
        elif tag in self._BREAK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_CONTENT and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BREAK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._cur.append(data)

    def _flush(self) -> None:
        text = " ".join("".join(self._cur).split())
        if text:
            self.lines.append(text)
        self._cur = []

    def get_lines(self) -> list[str]:
        self._flush()
        return self.lines


def _html_to_text(html: str) -> str:
    parser = TranscriptParser()
    parser.feed(html)
    lines = [ln for ln in parser.get_lines() if not SKIP_LINE_RE.match(ln)]
    return "\n".join(lines)


def run(franchise_dir: Path) -> None:
    segments_dir = franchise_dir / "state" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    print("  Fetching transcript index...")
    index = session.get(INDEX_URL, timeout=60)
    index.raise_for_status()
    hrefs = sorted(set(re.findall(r'href="(season/[^"]+\.html)"', index.text)))
    print(f"  {len(hrefs)} transcript links found.")

    downloaded = skipped = miss = nonepisode = 0
    for href in hrefs:
        stem = href.split("/")[-1][: -len(".html")]
        m = STEM_RE.match(stem)
        if not m:
            nonepisode += 1
            continue
        season, episode = int(m.group(1)), int(m.group(2))
        out_file = segments_dir / f"s{season}e{episode:02d}.txt"
        if out_file.exists():
            skipped += 1
            continue

        try:
            resp = session.get(f"{RAW_BASE}/{href}", timeout=60)
        except requests.RequestException as e:
            print(f"  ERROR {stem}: {e}")
            continue
        if resp.status_code != 200:
            print(f"  MISS  {stem}: HTTP {resp.status_code}")
            miss += 1
            continue

        text = _html_to_text(resp.text)
        out_file.write_text(text, encoding="utf-8")
        print(f"  OK    s{season}e{episode:02d}  ({len(text)} chars)")
        downloaded += 1

    total = len(list(segments_dir.glob("*.txt")))
    print(f"\nIngest complete: {downloaded} downloaded, {skipped} already present, "
          f"{miss} missing, {nonepisode} non-episode pages skipped. "
          f"{total} segments total in {segments_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_friends.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
