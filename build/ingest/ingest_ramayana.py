"""
ingest_ramayana.py — Ramayana ingest adapter

Turns Griffith's English-verse translation of Valmiki's Ramayana (Project Gutenberg
eBook #24869, a single ~2.4 MB file) into evenly sized segment files under
  <franchise_dir>/state/segments/  as  seg{nnnn}.txt

Why segment on cantos (not fixed blind chunks)?
The universal scorer (core/score_segments.py) treats one .txt file as one segment and rates the
cast *relative to one another within that segment*. The ideal unit is a scene/chapter-sized slice.
Unlike the Harry Potter blob, this source has clean structure: the body is divided into ~493
cantos, each a self-contained episode marked by a column-0 heading ("Canto I. Nárad."). Cantos
average a few KB, so we split on canto headings and then *pack* consecutive cantos up to a target
size — natural narrative boundaries, uniform segment sizes, only a handful of characters per call.

What gets stripped:
  - The Project Gutenberg header/footer (everything outside the START/END markers).
  - The title page + table-of-contents front matter (everything before the first body canto).
  - Inline footnote reference markers like "(7)" / "(26)" that Griffith scatters through the verse.

The text is verse (one short line per physical line); we flow the lines of each canto back into
continuous prose before packing. Casing is intact, so character-name detection still works well.

Stdlib only. Idempotent: if segments already exist in segments/, the run is skipped.

Place the downloaded text in build/franchises/ramayana/books/ (gitignored) first, then:
    python ingest_ramayana.py <franchise_dir>
"""

import re
import sys
from pathlib import Path

# --- tuning constants --------------------------------------------------------- #
# ~2.3 MB of body / CHUNK_TARGET ≈ segment count. 12000 → ~190 segments (≈ chapter-sized
# slices of a few thousand tokens each) — comfortably under the context window and cheap to score.
CHUNK_TARGET = 12000  # target chars per segment
MIN_CHARS = 3000      # merge anything smaller into the previous segment
MAX_CHARS = 20000     # hard cap; split anything larger at a sentence boundary

# Project Gutenberg content markers (everything outside is boilerplate).
_PG_START = re.compile(r"\*\*\*\s*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)
_PG_END = re.compile(r"\*\*\*\s*END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)

# A column-0 canto/book heading begins each body unit (contents entries are indented, so the
# leading-anchor excludes them). Used to cut the body into cantos.
_HEADING = re.compile(r"^(?:Canto |BOOK )", re.MULTILINE)

# The narrative proper begins at the first column-0 "Canto " line. Everything before it (title page
# and the global table of contents — which includes its own column-0 "BOOK II." style headings) is
# front matter to drop.
_BODY_START = re.compile(r"^Canto ", re.MULTILINE)

# Inline footnote references such as "(7)" — drop them; they are not part of the narrative.
_FOOTNOTE_REF = re.compile(r"\(\d+\)")

# Sentence boundary, for splitting any single oversized canto: end punctuation then a capital.
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s*(?=["\']?[A-Z])')


def _strip_boilerplate(raw: str) -> str:
    """Return only the text between the Gutenberg START and END markers."""
    start = _PG_START.search(raw)
    if start:
        raw = raw[start.end():]
    end = _PG_END.search(raw)
    if end:
        raw = raw[:end.start()]
    return raw


def _split_cantos(body: str) -> list[str]:
    """Split the body into per-canto blocks on column-0 'Canto '/'BOOK ' headings.

    Drops everything before the first body 'Canto ' heading (the title page + table of contents,
    whose own column-0 'BOOK' headings would otherwise leak in as junk segments).
    """
    body_start = _BODY_START.search(body)
    if body_start:
        body = body[body_start.start():]
    matches = list(_HEADING.finditer(body))
    if not matches:
        return [body]  # no headings found — treat the whole body as one block (size guardrails apply)
    cantos = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        cantos.append(body[m.start():end])
    return cantos


def _normalize(block: str) -> str:
    """Flow a canto's verse lines into continuous prose and strip footnote refs."""
    block = _FOOTNOTE_REF.sub("", block)
    return " ".join(block.split())  # collapse all whitespace/newlines into single spaces


def _pack(cantos: list[str], target: int) -> list[str]:
    """Pack consecutive cantos into segments of roughly `target` chars (break only between cantos)."""
    segments, cur, size = [], [], 0
    for c in cantos:
        cur.append(c)
        size += len(c) + 1
        if size >= target:
            segments.append(" ".join(cur))
            cur, size = [], 0
    if cur:
        segments.append(" ".join(cur))
    return segments


def _split_oversized(text: str, target: int) -> list[str]:
    """Split a too-large segment into ~target-char pieces at sentence boundaries."""
    sentences = [s for s in (p.strip() for p in _SENTENCE_SPLIT.split(text)) if s]
    pieces, cur, size = [], [], 0
    for s in sentences:
        cur.append(s)
        size += len(s) + 1
        if size >= target:
            pieces.append(" ".join(cur))
            cur, size = [], 0
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def _apply_guardrails(segments: list[str]) -> list[str]:
    """Split oversized segments, then merge tiny ones into the previous segment.

    Splitting runs first so that a small tail piece left over from a split is folded back by the
    subsequent merge pass (rather than surviving as a stray 100-char segment).
    """
    split: list[str] = []
    for seg in segments:
        if len(seg) <= MAX_CHARS:
            split.append(seg)
        else:
            split.extend(_split_oversized(seg, CHUNK_TARGET))
    merged: list[str] = []
    for seg in split:
        if merged and len(seg) < MIN_CHARS:
            merged[-1] = merged[-1] + " " + seg
        else:
            merged.append(seg)
    return merged


def run(franchise_dir: Path) -> None:
    books_dir = franchise_dir / "books"
    segments_dir = franchise_dir / "state" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    if not books_dir.exists():
        print(f"ERROR: {books_dir} not found. Download Gutenberg eBook #24869 "
              f"(The Rámáyan of Válmíki) and place the .txt there.")
        sys.exit(1)

    if list(segments_dir.glob("*.txt")):
        print(f"  SKIP — segments already present in {segments_dir} (delete to re-ingest).")
        return

    book_files = sorted(books_dir.glob("*.txt"))
    if not book_files:
        print(f"ERROR: no .txt files in {books_dir}.")
        sys.exit(1)

    raw = "\n".join(bf.read_text(encoding="utf-8", errors="replace") for bf in book_files)
    body = _strip_boilerplate(raw)

    cantos = [_normalize(c) for c in _split_cantos(body)]
    cantos = [c for c in cantos if c]
    print(f"  Parsed {len(cantos)} cantos from {len(book_files)} file(s).")

    segments = _apply_guardrails(_pack(cantos, CHUNK_TARGET))

    for idx, seg in enumerate(segments, start=1):
        (segments_dir / f"seg{idx:04d}.txt").write_text(seg, encoding="utf-8")

    sizes = [len(s) for s in segments]
    print(f"\nIngest complete: {len(segments)} segments written to {segments_dir}")
    print(f"  segment size chars — min {min(sizes)}, max {max(sizes)}, "
          f"avg {sum(sizes) // len(sizes)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_ramayana.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
