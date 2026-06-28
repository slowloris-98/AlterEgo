"""
score_segments.py — Segment text → per-character OCEAN ratings (universal engine)

Usage:
    python score_segments.py <franchise_dir>

Reads every .txt file in state/segments/ (one segment = one episode/scene/chapter).
For each segment:
  Call A: ask the model which characters from config.json are meaningfully present.
  Call B: ask the model to rate every present character on all five OCEAN traits
          (1-10) in a SINGLE call, judging them relative to one another in the same
          context.
Appends one row per segment to state/segment_scores.jsonl.
Tracks progress in state/progress.json — safe to re-run after interruption (a segment
is now a single atomic call, so the resume unit is the segment).

The per-segment ratings are turned into per-character scores downstream by
aggregate_scores.py (within-segment normalisation → raw_scores.json). There is no
pairwise comparison and no Bradley-Terry step; see design_decisions.md for the
rationale and tradeoffs.

Franchise-agnostic: it knows nothing about books, chapters, or episodes — just a folder
of text files. Segmentation is the ingest adapter's job (build/ingest/ingest_<id>.py).

Models / provider:
  SCORER_PROVIDER — "anthropic" (default) | "openai" | "ollama"
  IDENTIFY_MODEL  — fast/cheap model for Call A (character identification)
  SCORE_MODEL     — model for Call B (per-character ratings)
Set via env vars (build/.env) or edit the constants below.
"""

import json
import os
import sys
import time
from pathlib import Path

import anthropic
import jsonlines
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROVIDER       = os.getenv("SCORER_PROVIDER", "anthropic").lower()
IDENTIFY_MODEL = os.getenv("IDENTIFY_MODEL", "claude-haiku-4-5-20251001")
SCORE_MODEL    = os.getenv("SCORE_MODEL", os.getenv("COMPARE_MODEL", "claude-haiku-4-5-20251001"))
TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]

SCORE_MIN = 1
SCORE_MAX = 10

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds


def load_rubric() -> str:
    return (Path(__file__).parent / "rubric.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Provider abstraction
#
# Only the Anthropic path is implemented today. OpenAI and Ollama are stubbed
# behind the same `generate()` signature so the pipeline can switch providers via
# SCORER_PROVIDER without any changes to the scoring logic — fill them in when
# needed. The scoring task is plain structured JSON, so a cheap cloud model
# (gpt-4.1-mini / gpt-4o-mini) or a local model (qwen2.5 / llama3.1 via Ollama)
# is sufficient.
# --------------------------------------------------------------------------- #

def make_client():
    """Create the provider client. Reused for every call in a run."""
    if PROVIDER == "anthropic":
        return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    if PROVIDER == "openai":
        raise NotImplementedError(
            "SCORER_PROVIDER=openai is not implemented yet. Add an OpenAI client here "
            "(openai.OpenAI()) and handle it in generate()."
        )
    if PROVIDER == "ollama":
        raise NotImplementedError(
            "SCORER_PROVIDER=ollama is not implemented yet. Point generate() at your "
            "local Ollama endpoint (http://localhost:11434)."
        )
    raise ValueError(f"Unknown SCORER_PROVIDER: {PROVIDER!r} (expected anthropic|openai|ollama)")


def call_claude(client, model: str, prompt: str, max_tokens: int, system):
    """Anthropic Messages API with retry/backoff on rate limits.

    `system` may be a list of text blocks (with optional cache_control) to place a
    cacheable prefix ahead of the user prompt, or None.
    """
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        kwargs["system"] = system

    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt < MAX_RETRIES - 1:
                print(f"    Rate limited — waiting {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                raise


def generate(client, model: str, prompt: str, max_tokens: int = 4096, system=None):
    """Provider-agnostic text generation. Returns (text, usage).

    `usage` is the provider's usage object (or None) — used only for logging.
    """
    if PROVIDER == "anthropic":
        resp = call_claude(client, model, prompt, max_tokens, system)
        return resp.content[0].text, resp.usage
    # openai / ollama route through make_client()'s NotImplementedError before
    # reaching here; this guards against a provider added without a generate() arm.
    raise NotImplementedError(f"generate() not implemented for provider {PROVIDER!r}")


def _strip_fences(raw: str) -> str:
    return raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


# --------------------------------------------------------------------------- #
# Call A — character presence
# --------------------------------------------------------------------------- #

def identify_characters(client, segment_text: str, character_names: list[str]) -> list[str]:
    """Call A: return subset of character_names meaningfully present in this segment."""
    names_list = "\n".join(f"- {n}" for n in character_names)
    prompt = f"""You are analysing a segment of a TV/film script (or book) for character presence.

Which of the following characters are meaningfully present in this segment?
"Meaningfully present" means they speak, act, make a decision, or are significantly
described — not merely mentioned in passing by another character.

Character list:
{names_list}

Segment text:
{segment_text}

Respond with a JSON array of names exactly as listed above. Example:
["Jon Snow", "Tyrion Lannister"]
If no characters from the list are meaningfully present, respond with [].
Output only the JSON array, nothing else."""

    raw, _ = generate(client, IDENTIFY_MODEL, prompt, max_tokens=1024)
    try:
        found = json.loads(_strip_fences(raw))
        return [n for n in found if n in character_names]
    except (json.JSONDecodeError, TypeError):
        print(f"    WARNING: could not parse character list response: {raw[:200]}")
        return []


# --------------------------------------------------------------------------- #
# Call B — per-character OCEAN ratings (single call per segment)
# --------------------------------------------------------------------------- #

def _build_score_system(rubric: str, segment_text: str) -> list[dict]:
    """Stable, cacheable prefix for Call B.

    The rubric (constant across all segments) and the segment text go here; the
    cache_control on the segment block caches rubric + segment together so a
    re-run of the same segment is cheap. (Anthropic-specific; other providers
    receive this as a plain system string once they are implemented.)
    """
    return [
        {"type": "text", "text": f"OCEAN TRAIT DEFINITIONS:\n{rubric}"},
        {
            "type": "text",
            "text": f"SEGMENT TEXT:\n{segment_text}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def score_present_characters(client, segment_text: str, present: list[str], rubric: str):
    """Call B: rate each present character on all five traits (1-10) in one call.

    Returns (scores, usage) where scores maps name -> {trait: int in [1, 10]}.
    Characters whose ratings are missing or malformed are dropped.
    """
    system = _build_score_system(rubric, segment_text)
    names_list = "\n".join(f"- {n}" for n in present)
    traits_str = ", ".join(TRAITS)
    example = '{"' + present[0] + '": {' + ", ".join(f'"{t}": 6' for t in TRAITS) + '}, ...}'

    prompt = f"""You are a literary analyst rating fictional characters on the Big Five (OCEAN) personality traits.
Use the OCEAN TRAIT DEFINITIONS and SEGMENT TEXT provided in the system prompt.

TASK:
Rate EACH character below on ALL five traits ({traits_str}) on an integer scale from
{SCORE_MIN} to {SCORE_MAX}, based ONLY on what they say, do, and decide in this segment.

Scale: {SCORE_MIN} = clearly very low on the trait, {SCORE_MAX} = clearly very high.
- Use the FULL range. Do NOT cluster everyone near the middle.
- Differentiate the characters from one another — the ratings are most useful as a
  relative ordering within this segment.
- Judge behaviour shown in THIS segment, not the character's wider reputation.

Characters:
{names_list}

Respond as a JSON object mapping each character name (exactly as listed) to an object
of integer trait scores. Example:
{example}

Output only the JSON object, nothing else."""

    raw, usage = generate(client, SCORE_MODEL, prompt, max_tokens=4096, system=system)
    try:
        data = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        print(f"    WARNING: could not parse rating response: {raw[:200]}")
        return {}, usage

    if not isinstance(data, dict):
        print(f"    WARNING: expected JSON object, got {type(data).__name__}")
        return {}, usage

    scores: dict[str, dict[str, int]] = {}
    for name in present:
        entry = data.get(name)
        if not isinstance(entry, dict):
            continue
        traits: dict[str, int] = {}
        for t in TRAITS:
            v = entry.get(t)
            if isinstance(v, (int, float)) and SCORE_MIN <= v <= SCORE_MAX:
                traits[t] = int(round(v))
        if len(traits) == len(TRAITS):
            scores[name] = traits
    return scores, usage


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def run(franchise_dir: Path) -> None:
    config = json.loads((franchise_dir / "config.json").read_text())
    character_names = [c["name"] for c in config["characters"]]

    segments_dir = franchise_dir / "state" / "segments"
    if not segments_dir.exists():
        print(f"ERROR: {segments_dir} not found. Run the ingest adapter first.")
        sys.exit(1)

    segment_files = sorted(segments_dir.glob("*.txt"))
    if not segment_files:
        print(f"ERROR: no .txt segments in {segments_dir}.")
        sys.exit(1)

    state_dir = franchise_dir / "state"
    scores_path = state_dir / "segment_scores.jsonl"
    progress_path = state_dir / "progress.json"

    done = set(json.loads(progress_path.read_text())) if progress_path.exists() else set()

    rubric = load_rubric()
    client = make_client()

    pending = [f for f in segment_files if f.name not in done]
    print(f"Provider={PROVIDER}, score model={SCORE_MODEL}")
    print(f"{len(done)} segments done, {len(pending)} remaining (of {len(segment_files)} total).")

    for seg_file in pending:
        segment_text = seg_file.read_text(encoding="utf-8")
        print(f"  [{seg_file.name}] ({len(segment_text)} chars)")

        # Call A — identify present characters
        present = identify_characters(client, segment_text, character_names)
        print(f"    Present: {present or '(none)'}")

        scores = {}
        if len(present) >= 2:
            # Call B — one rating call for all present characters
            scores, usage = score_present_characters(client, segment_text, present, rubric)
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            out_tokens = getattr(usage, "output_tokens", 0) or 0
            print(f"    Rated {len(scores)} character(s); output={out_tokens}, cache_read={cache_read} tokens")

            with jsonlines.open(scores_path, mode="a") as writer:
                writer.write({"segment": seg_file.name, "scores": scores})
        else:
            print("    Skipped scoring (need >= 2 present characters to rank).")

        done.add(seg_file.name)
        progress_path.write_text(json.dumps(sorted(done)))

    total = sum(1 for _ in jsonlines.open(scores_path)) if scores_path.exists() else 0
    print(f"\nDone. segment_scores.jsonl has {total} segment rows.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python score_segments.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
