"""
run_franchise.py — Pipeline driver for a single franchise

Usage:
    python run_franchise.py <franchise_id> [--step <step>]

    franchise_id: must match a folder in build/franchises/ (e.g. "got")

    --step ingest      run only the ingest adapter (build/ingest/ingest_<id>.py)
    --step discover    run only discover_characters (auto-fill config.json roster)
    --step score       run only score_segments
    --step aggregate   run only aggregate_scores
    --step profiles    run only build_profiles
    (default: run all steps in order)

Pipeline:  ingest -> discover -> score_segments -> aggregate_scores -> build_profiles
After all steps succeed, copies out/characters.json and out/quiz.json to
../app/data/<franchise_id>/.

Examples:
    cd build
    python run_franchise.py got
    python run_franchise.py got --step ingest
    python run_franchise.py got --step score
"""

import importlib.util
import shutil
import sys
from pathlib import Path

CORE_DIR = Path(__file__).parent / "core"
INGEST_DIR = Path(__file__).parent / "ingest"
sys.path.insert(0, str(CORE_DIR))

import score_segments
import aggregate_scores
import build_profiles
import discover_characters


def load_ingest_adapter(franchise_id: str):
    """Dynamically load build/ingest/ingest_<id>.py if it exists; else None."""
    adapter_path = INGEST_DIR / f"ingest_{franchise_id}.py"
    if not adapter_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"ingest_{franchise_id}", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_output(franchise_dir: Path, franchise_id: str) -> None:
    out_dir = franchise_dir / "out"
    app_data_dir = Path(__file__).parent.parent / "app" / "data" / franchise_id
    app_data_dir.mkdir(parents=True, exist_ok=True)

    for fname in ("characters.json", "quiz.json"):
        src = out_dir / fname
        if src.exists():
            shutil.copy2(src, app_data_dir / fname)
            print(f"  Copied {fname} -> app/data/{franchise_id}/")
        else:
            print(f"  SKIP (not found): {fname}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python run_franchise.py <franchise_id> [--step <step>]")
        sys.exit(1)

    franchise_id = args[0]
    franchise_dir = Path(__file__).parent / "franchises" / franchise_id
    if not franchise_dir.exists():
        print(f"ERROR: franchises/{franchise_id}/ not found.")
        sys.exit(1)

    step = None
    if "--step" in args:
        idx = args.index("--step")
        if idx + 1 < len(args):
            step = args[idx + 1]

    valid_steps = {"ingest", "discover", "score", "aggregate", "profiles"}
    if step and step not in valid_steps:
        print(f"ERROR: unknown step '{step}'. Choose from: {', '.join(sorted(valid_steps))}")
        sys.exit(1)

    print(f"=== AlterEgo Build: {franchise_id.upper()} ===\n")

    if step is None or step == "ingest":
        print("--- Step 1: ingest ---")
        adapter = load_ingest_adapter(franchise_id)
        if adapter is None:
            print(f"  No ingest_{franchise_id}.py found — assuming state/segments/ "
                  f"is populated manually.")
        else:
            adapter.run(franchise_dir)
        print()

    if step is None or step == "discover":
        print("--- Step 2: discover_characters ---")
        discover_characters.run(franchise_dir)
        print()

    if step is None or step == "score":
        print("--- Step 3: score_segments ---")
        score_segments.run(franchise_dir)
        print()

    if step is None or step == "aggregate":
        print("--- Step 4: aggregate_scores ---")
        aggregate_scores.run(franchise_dir)
        print()

    if step is None or step == "profiles":
        print("--- Step 5: build_profiles ---")
        build_profiles.run(franchise_dir)
        print()

    if step is None:
        print("--- Copying output to app/data/ ---")
        copy_output(franchise_dir, franchise_id)
        print("\n=== Build complete ===")


if __name__ == "__main__":
    main()
