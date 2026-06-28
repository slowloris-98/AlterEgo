"""
ingest_hp.py — Harry Potter ingest adapter

Turns the raw Harry Potter book text (Kaggle dataset moxxis/harry-potter-lstm —
"Harry Potter all books (preprocessed)") into evenly sized segment files under
  <franchise_dir>/state/segments/  as  seg{nnnn}.txt

Why fixed-size chunks (not chapters)?
The universal scorer (core/score_segments.py) treats one .txt file as one segment and rates the
cast *relative to one another within that segment*. The ideal unit is a scene/chapter-sized slice:
small enough to never strain the context window, plentiful enough to give the within-segment
z-scoring real signal, with only a handful of characters present per call.

This particular dataset, however, is a single ~6 MB blob: NO chapter markers ("CHAPTER N" is
absent), NO usable book separators (the 7 books are concatenated), and NO line/sentence delimiters
(the advertised '|' is not actually present). Chapter titles survive only as ALL-CAPS fragments that
are indistinguishable from shouted dialogue and signage, so they can't be used to cut reliably.
Casing IS intact, so character-name presence detection still works well.

Given that, we reconstruct sentences from the glued text and pack them into uniform ~chapter-sized
chunks. This is the pipeline's native "segment = scene-sized unit" model; the scorer is agnostic to
how the cut was made. If a future source has real chapter markers, segment on those instead.

Stdlib only. Idempotent: if segments already exist in segments/, the run is skipped.

Place the downloaded text in build/franchises/hp/books/ (gitignored) first, then:
    python ingest_hp.py <franchise_dir>
"""

import re
import sys
from pathlib import Path

# --- tuning constants --------------------------------------------------------- #
# ~6 MB / CHUNK_TARGET ≈ segment count. 12000 → ~500 segments (≈ chapter-sized slices),
# each a few thousand tokens — comfortably under the context window and cheap to score.
CHUNK_TARGET = 12000  # target chars per segment
MIN_CHARS = 3000      # merge anything smaller into the previous segment
MAX_CHARS = 20000     # hard cap; split anything larger at a sentence boundary

# Sentence boundary in the glued text: end punctuation (optionally preceded by a stray space, as the
# preprocessing leaves " .Word"), then optional spaces, then an opening quote or capital letter.
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s*(?=["\']?[A-Z])')


def _reconstruct_sentences(raw: str) -> list[str]:
    """Turn the source into a list of sentences, whatever delimiter style it uses.

    Handles three shapes: '|'-delimited, newline-delimited, or one glued blob (this dataset).
    """
    if "|" in raw:
        pieces = raw.split("|")
    elif raw.count("\n") > 50:
        pieces = raw.splitlines()
    else:
        pieces = _SENTENCE_SPLIT.split(raw)
    out = []
    for p in pieces:
        s = " ".join(p.split())  # collapse whitespace, drop stray newlines/tabs
        if s:
            out.append(s)
    return out


def _chunk_by_size(sentences: list[str], target: int) -> list[list[str]]:
    """Pack sentences into chunks of roughly `target` chars, breaking only between sentences."""
    chunks, cur, size = [], [], 0
    for s in sentences:
        cur.append(s)
        size += len(s) + 1
        if size >= target:
            chunks.append(cur)
            cur, size = [], 0
    if cur:
        chunks.append(cur)
    return chunks


def _apply_guardrails(segments: list[list[str]]) -> list[list[str]]:
    """Merge tiny segments into the previous one; split oversized ones at sentence boundaries."""
    merged: list[list[str]] = []
    for seg in segments:
        if merged and sum(len(x) + 1 for x in seg) < MIN_CHARS:
            merged[-1].extend(seg)
        else:
            merged.append(list(seg))
    out: list[list[str]] = []
    for seg in merged:
        if sum(len(x) + 1 for x in seg) <= MAX_CHARS:
            out.append(seg)
        else:
            out.extend(_chunk_by_size(seg, MAX_CHARS))
    return out


def run(franchise_dir: Path) -> None:
    books_dir = franchise_dir / "books"
    segments_dir = franchise_dir / "state" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    if not books_dir.exists():
        print(f"ERROR: {books_dir} not found. Download the Kaggle dataset "
              f"(moxxis/harry-potter-lstm) and place the readable .txt there.")
        sys.exit(1)

    if list(segments_dir.glob("*.txt")):
        print(f"  SKIP — segments already present in {segments_dir} (delete to re-ingest).")
        return

    # Prefer the readable preprocessed text; never ingest the char-separated LSTM file.
    book_files = sorted(
        f for f in books_dir.glob("*.txt") if "char_separated" not in f.name.lower()
    )
    if not book_files:
        print(f"ERROR: no readable .txt files in {books_dir}.")
        sys.exit(1)

    sentences: list[str] = []
    for bf in book_files:
        sentences.extend(_reconstruct_sentences(bf.read_text(encoding="utf-8", errors="replace")))
    print(f"  Reconstructed {len(sentences)} sentences from {len(book_files)} file(s).")

    segments = _apply_guardrails(_chunk_by_size(sentences, CHUNK_TARGET))

    for idx, seg in enumerate(segments, start=1):
        (segments_dir / f"seg{idx:04d}.txt").write_text("\n".join(seg), encoding="utf-8")

    sizes = [sum(len(x) + 1 for x in s) for s in segments]
    print(f"\nIngest complete: {len(segments)} segments written to {segments_dir}")
    print(f"  segment size chars — min {min(sizes)}, max {max(sizes)}, "
          f"avg {sum(sizes) // len(sizes)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_hp.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
