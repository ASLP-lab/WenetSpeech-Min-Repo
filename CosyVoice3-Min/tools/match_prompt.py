#!/usr/bin/env python3
"""Randomly match prompt_wav/prompt_text from JSONL A into JSONL B.

Each line in B gets a random valid prompt from A.

Prompts whose audio duration is shorter than min_prompt_duration are skipped.
If A has fewer valid prompts than B, prompts are cycled and re-shuffled each
pass to avoid repeating the same order.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import soundfile as sf


def shuffled_cycle(items, n):
    """Yield n items from items, cycling and re-shuffling each full pass."""
    pool = list(range(len(items)))
    random.shuffle(pool)

    for i in range(n):
        yield items[pool[i % len(pool)]]

        if (i + 1) % len(pool) == 0:
            random.shuffle(pool)


def get_audio_duration(wav_path):
    """Get audio duration in seconds without loading the full waveform."""
    try:
        info = sf.info(wav_path)
        return info.duration
    except Exception as e:
        print(
            f"Warning: failed to read audio: {wav_path}, error: {e}",
            file=sys.stderr
        )
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Randomly match valid prompt fields from A into B"
    )

    parser.add_argument(
        "prompt_jsonl",
        type=Path,
        help="JSONL with wav_path and text_minnan_clean (prompt source)"
    )

    parser.add_argument(
        "target_jsonl",
        type=Path,
        help="JSONL to augment with prompt fields"
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSONL (default: <target>_w_prompt.jsonl)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed"
    )

    parser.add_argument(
        "--min_prompt_duration",
        type=float,
        default=1.0,
        help="Minimum prompt audio duration in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    random.seed(args.seed)

    if args.output is None:
        args.output = args.target_jsonl.with_name(
            f"{args.target_jsonl.stem}_w_prompt.jsonl"
        )

    # ============================================================
    # Load valid prompts from A
    # ============================================================

    prompts = []

    total_prompts = 0
    skipped_short = 0
    skipped_invalid = 0
    skipped_missing = 0

    with open(args.prompt_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            total_prompts += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(
                    f"Warning: invalid JSON: {e}",
                    file=sys.stderr
                )
                skipped_invalid += 1
                continue

            wav_path = obj.get("wav_path")
            prompt_text = obj.get("text_minnan_clean")

            # Check required fields
            if not wav_path or prompt_text is None:
                skipped_invalid += 1
                continue

            # Check file existence
            if not Path(wav_path).exists():
                print(
                    f"Warning: audio not found: {wav_path}",
                    file=sys.stderr
                )
                skipped_missing += 1
                continue

            # Get duration
            duration = get_audio_duration(wav_path)

            if duration is None:
                skipped_invalid += 1
                continue

            # Skip short prompt audio
            if duration < args.min_prompt_duration:
                skipped_short += 1
                continue

            prompts.append({
                "prompt_wav": wav_path,
                "prompt_text": prompt_text,
            })

    # ============================================================
    # Check valid prompts
    # ============================================================

    if not prompts:
        print(
            "Error: no valid prompts after duration filtering",
            file=sys.stderr
        )
        sys.exit(1)

    print()
    print("Prompt statistics:")
    print(f"  Total input prompts : {total_prompts}")
    print(f"  Valid prompts       : {len(prompts)}")
    print(f"  Skipped short       : {skipped_short}")
    print(f"  Skipped missing     : {skipped_missing}")
    print(f"  Skipped invalid     : {skipped_invalid}")
    print(f"  Minimum duration    : {args.min_prompt_duration:.2f}s")
    print()

    # ============================================================
    # Load target lines from B
    # ============================================================

    target_lines = []

    with open(args.target_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                target_lines.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(
                    f"Warning: invalid target JSON: {e}",
                    file=sys.stderr
                )

    # ============================================================
    # Write output
    # ============================================================

    total = 0

    with open(args.output, "w", encoding="utf-8") as fout:
        for prompt, obj in zip(
            shuffled_cycle(prompts, len(target_lines)),
            target_lines
        ):
            obj.update(prompt)

            fout.write(
                json.dumps(obj, ensure_ascii=False) + "\n"
            )

            total += 1

    # ============================================================
    # Statistics
    # ============================================================

    cycles = total // len(prompts)
    rem = total % len(prompts)

    print(f"Matched {len(prompts)} valid prompts -> {total} target lines")

    if cycles > 0:
        print(f"  {cycles} full cycle(s) + {rem} leftover")

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()