"""
validate.py — In-character quiz → confusion matrix

Usage:
    python validate.py <franchise_dir>

For each character in characters.json, asks Claude to answer the quiz as that character,
runs the answers through the same OCEAN scoring and matching math, and prints a confusion
matrix. A good result has a strong diagonal (character matches themselves) and no single
character dominating matches.

This is the regression check for the "Daenerys magnet" problem.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

VALIDATE_MODEL = os.getenv("VALIDATE_MODEL", "claude-sonnet-4-6")
TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]


# ---------------------------------------------------------------------------
# Scoring math (mirrors lib/scoring.ts — must stay in sync)
# ---------------------------------------------------------------------------

def answers_to_raw(answers: dict[str, int], questions: list[dict]) -> dict[str, float]:
    """Convert quiz answers to raw OCEAN scores (0-100)."""
    trait_values: dict[str, list[float]] = {t: [] for t in TRAITS}
    q_map = {q["id"]: q for q in questions}

    for qid, value in answers.items():
        q = q_map.get(qid)
        if not q:
            continue
        v = 6 - value if q.get("reverse") else value
        trait_values[q["trait"]].append(v)

    raw = {}
    for trait in TRAITS:
        vals = trait_values[trait]
        if vals:
            avg = sum(vals) / len(vals)
            raw[trait] = (avg - 1) / 4 * 100  # 1-5 Likert → 0-100
        else:
            raw[trait] = 50.0
    return raw


def raw_to_z(raw: dict[str, float], stats: dict) -> dict[str, float]:
    return {
        trait: (raw[trait] - stats[trait]["mean"]) / stats[trait]["std"]
        for trait in TRAITS
    }


def euclidean(a: dict[str, float], b: dict[str, float]) -> float:
    return math.sqrt(sum((a[t] - b[t]) ** 2 for t in TRAITS))


def find_match(user_z: dict[str, float], characters: list[dict]) -> str:
    best_name = ""
    best_dist = float("inf")
    for c in characters:
        d = euclidean(user_z, c["z"])
        if d < best_dist:
            best_dist = d
            best_name = c["name"]
    return best_name


# ---------------------------------------------------------------------------
# In-character quiz answering
# ---------------------------------------------------------------------------

def answer_quiz_as_character(
    client: anthropic.Anthropic,
    character_name: str,
    questions: list[dict],
    franchise_name: str,
) -> dict[str, int]:
    """Ask Claude to answer the quiz as the given character. Returns {qid: value}."""
    q_lines = "\n".join(
        f'{q["id"]}: "{q["text"]}"  '
        f'[Options: {", ".join(str(o["value"]) + "=" + o["label"] for o in q["options"])}]'
        for q in questions
    )

    prompt = f"""You are answering a personality quiz as {character_name} from {franchise_name}.
Answer each question as {character_name} would, based on their established personality,
values, and behaviours from the source material.

For each question, respond with the numeric value (1-5 or as specified) that best
represents {character_name}'s answer.

Questions:
{q_lines}

Respond as a JSON object mapping question id to numeric value.
Example: {{"q1": 4, "q2": 2, "q3": 5}}
Output only the JSON object, nothing else."""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VALIDATE_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            answers = json.loads(raw)
            return {str(k): int(v) for k, v in answers.items()}
        except (json.JSONDecodeError, anthropic.RateLimitError) as e:
            if isinstance(e, anthropic.RateLimitError) and attempt < 2:
                time.sleep(10)
            else:
                print(f"    WARNING: failed to parse answer for {character_name}: {e}")
                return {}
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(franchise_dir: Path) -> None:
    config = json.loads((franchise_dir / "config.json").read_text())

    characters_path = franchise_dir / "out" / "characters.json"
    quiz_path = franchise_dir / "out" / "quiz.json"

    if not characters_path.exists():
        print("ERROR: out/characters.json not found. Run build_profiles.py first.")
        sys.exit(1)
    if not quiz_path.exists():
        print("ERROR: out/quiz.json not found. Author the quiz first.")
        sys.exit(1)

    char_data  = json.loads(characters_path.read_text())
    quiz_data  = json.loads(quiz_path.read_text())
    characters = char_data["characters"]
    stats      = char_data["stats"]
    questions  = quiz_data["questions"]
    franchise_name = config["display_name"]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # confusion_matrix[true_char][predicted_char] = count
    char_names = [c["name"] for c in characters]
    matrix: dict[str, dict[str, int]] = {n: {m: 0 for m in char_names} for n in char_names}

    for character in characters:
        name = character["name"]
        print(f"  Answering as {name}...")

        answers = answer_quiz_as_character(client, name, questions, franchise_name)
        if not answers:
            print(f"    SKIP: no answers returned.")
            continue

        raw   = answers_to_raw(answers, questions)
        z     = raw_to_z(raw, stats)
        match = find_match(z, characters)

        matrix[name][match] += 1
        status = "✓" if match == name else f"✗ → {match}"
        print(f"    {status}")

    # Print confusion matrix
    print("\n--- Confusion Matrix ---")
    col_w = max(len(n) for n in char_names)
    header = " " * (col_w + 2) + "  ".join(n[:8].ljust(8) for n in char_names)
    print(header)

    correct = 0
    total   = 0
    dominated_by: dict[str, int] = {}

    for true_name in char_names:
        row = matrix[true_name]
        cells = "  ".join(str(row[pred]).ljust(8) for pred in char_names)
        print(f"{true_name.ljust(col_w)}  {cells}")
        for pred, count in row.items():
            total += count
            if true_name == pred:
                correct += count
            dominated_by[pred] = dominated_by.get(pred, 0) + count

    print(f"\nAccuracy: {correct}/{total} = {correct/total*100:.1f}%")

    # Daenerys-magnet check
    most_matched = max(dominated_by, key=dominated_by.get)
    most_count   = dominated_by[most_matched]
    threshold    = len(char_names) * 0.4  # flag if >40% of all matches go to one character
    if most_count > threshold:
        print(f"⚠️  MAGNET WARNING: '{most_matched}' attracts {most_count}/{total} matches.")
    else:
        print(f"✓ No magnet character detected. Most matched: '{most_matched}' ({most_count}/{total})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
