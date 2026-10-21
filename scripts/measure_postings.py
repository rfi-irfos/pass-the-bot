"""Measure keyword recall and false positives on labelled job postings.

Each posting `<name>.txt` has a gold file `<name>.expected.yaml` with:
  expected:       skill ids the posting really asks for
  forbidden:      skill ids that must not be found (false-positive traps)
  open_expected:  substrings that must appear in some open requirement
  open_forbidden: substrings that must not appear in any open requirement
                  (benefits read as requirements)

Usage:
  python scripts/measure_postings.py [DIR ...]   # default: tests/data/postings
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.normalizer import extract_discrete_keywords, extract_open_requirements

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "tests" / "data" / "postings"


def measure_posting(text: str, gold: dict, entries) -> dict:
    found = {k.id for k in extract_discrete_keywords(text, entries)}
    phrases = [r.phrase.lower() for r in extract_open_requirements(text)]
    expected = set(gold.get("expected", []))
    forbidden = set(gold.get("forbidden", []))
    open_expected = [s.lower() for s in gold.get("open_expected", [])]
    open_forbidden = [s.lower() for s in gold.get("open_forbidden", [])]
    return {
        "found": found,
        "hits": expected & found,
        "missed": expected - found,
        "forbidden_hits": forbidden & found,
        "open_missed": [s for s in open_expected if not any(s in p for p in phrases)],
        "open_forbidden_hits": [s for s in open_forbidden if any(s in p for p in phrases)],
        "expected_total": len(expected),
    }


def main(dirs: list[Path]) -> None:
    entries = active_entries(load_skill_graph(DEFAULT_DATA_DIR))
    total_expected = total_hits = total_false = total_open_bad = 0
    for directory in dirs:
        for posting in sorted(directory.glob("*.txt")):
            gold_file = posting.with_suffix(".expected.yaml")
            gold = yaml.safe_load(gold_file.read_text()) if gold_file.exists() else {}
            m = measure_posting(posting.read_text(), gold, entries)
            total_expected += m["expected_total"]
            total_hits += len(m["hits"])
            total_false += len(m["forbidden_hits"])
            total_open_bad += len(m["open_missed"]) + len(m["open_forbidden_hits"])
            print(f"{posting.stem}: {len(m['hits'])}/{m['expected_total']} skills")
            if m["missed"]:
                print(f"    missed: {sorted(m['missed'])}")
            if m["forbidden_hits"]:
                print(f"    FALSE: {sorted(m['forbidden_hits'])}")
            extra = m["found"] - set(gold.get("expected", []))
            if extra:
                print(f"    other found: {sorted(extra)}")
            if m["open_missed"]:
                print(f"    open missed: {m['open_missed']}")
            if m["open_forbidden_hits"]:
                print(f"    open BENEFIT: {m['open_forbidden_hits']}")
    recall = 100 * total_hits / total_expected if total_expected else 0.0
    print(
        f"\nrecall {total_hits}/{total_expected} ({recall:.0f}%) · "
        f"false positives {total_false} · open-requirement errors {total_open_bad}"
    )


if __name__ == "__main__":
    main([Path(d) for d in sys.argv[1:]] or [DEFAULT_DIR])
