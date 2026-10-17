#!/usr/bin/env python3
"""Apply manually reviewed number TN to the Minnan hard test set."""

import argparse
import json
import re
from pathlib import Path


REPLACEMENTS = {
    "hard_text_054": {
        "10.5.2": "十点五点二",
        "2TB": "两TB",
        "1.8": "一点八",
        "39900": "三万九千九百",
        "85折": "八五折",
        "45度C": "四十五度C",
    },
    "hard_text_056": {"台北101": "台北一零一", "A13": "A十三"},
    "hard_text_060": {"iPhone 15 Pro Max": "iPhone十五Pro Max"},
    "hard_text_061": {"RTX 4090": "RTX四零九零"},
    "hard_text_062": {"台北101": "台北一零一", "7-11": "Seven Eleven"},
    "hard_text_064": {"Ryzen 9": "Ryzen九", "4K": "四K", "i9": "i九"},
    "hard_text_065": {"台北101": "台北一零一"},
    "hard_text_066": {"5GHz": "五GHz"},
    "hard_text_070": {"iPhone 15 Pro Max": "iPhone十五Pro Max"},
    "hard_text_074": {
        "iPhone 15 Pro Max": "iPhone十五Pro Max",
        "256GB": "二百五十六GB",
    },
    "hard_text_097": {"B2": "B二"},
    "hard_text_098": {"A01": "A零一", "A05": "A零五"},
    "hard_text_099": {"B201": "B二零一"},
    "hard_text_100": {"0800-092-111": "零八零零零九二一一一"},
    "hard_text_101": {"205路": "二零五路"},
    "hard_text_104": {
        "203": "二零三",
        "A-12": "A十二",
        "0418": "零四一八",
    },
    "hard_text_105": {"0912-345-678": "零九一二三四五六七八"},
    "hard_text_106": {"A801": "A八零一"},
    "hard_text_107": {"B2": "B二", "C502": "C五零二"},
    "hard_text_108": {"A11": "A十一", "305": "三零五"},
    "hard_text_111": {"B201": "B二零一"},
    "hard_text_114": {"B2": "B二", "102号": "一零二号"},
    "hard_text_115": {"0912345678": "零九一二三四五六七八"},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    changed = []
    with args.input.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as output:
        for line_no, line in enumerate(source, 1):
            row = json.loads(line)
            original = row["text"]
            for old, new in REPLACEMENTS.get(row["utt"], {}).items():
                if old not in row["text"]:
                    raise ValueError(
                        f"expected text {old!r} missing from {row['utt']} at line {line_no}"
                    )
                row["text"] = row["text"].replace(old, new)
            if row["text"] != original:
                changed.append(row["utt"])
            output.write(json.dumps(row, ensure_ascii=False) + "\n")

    expected = set(REPLACEMENTS)
    if set(changed) != expected:
        raise ValueError(f"changed utt mismatch: {expected - set(changed)}")

    remaining = []
    with args.output.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if re.search(r"[0-9]", row["text"]):
                remaining.append(row["utt"])
    if remaining:
        raise ValueError(f"digits remain in text: {remaining}")
    print(f"Wrote {args.output}: {len(changed)} rows normalized")


if __name__ == "__main__":
    main()
