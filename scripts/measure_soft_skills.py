"""Soft-skill precision/recall on the labelled postings for one embedding
model, across a range of thresholds (gold key: soft_expected).

Usage:
  python scripts/measure_soft_skills.py [MODEL_NAME]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import yaml

from passthebot.embeddings import Embedder
from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.normalizer import detect_language, extract_soft_skills

POSTINGS_DIR = Path(__file__).resolve().parent.parent / "tests" / "data" / "postings"
THRESHOLDS = [0.40, 0.45, 0.48, 0.50, 0.55, 0.60, 0.65, 0.70]


def main(model_name: str) -> None:
    embedder = Embedder(model_name)
    soft = [
        replace(e, embedding_threshold=0.0)
        for e in active_entries(load_skill_graph(DEFAULT_DATA_DIR))
        if e.category == "soft_skills"
    ]
    scored = []
    for posting in sorted(POSTINGS_DIR.glob("*.txt")):
        gold = yaml.safe_load(posting.with_suffix(".expected.yaml").read_text())
        scores = {k.id: k.confidence for k in extract_soft_skills(posting.read_text(), soft, embedder)}
        lang = detect_language(posting.read_text())
        scored.append((posting.stem, set(gold.get("soft_expected") or []), scores, lang))

    print(f"model {model_name}")
    for lang in sorted({row[3] for row in scored}):
        for t in THRESHOLDS:
            tp = fp = fn = 0
            for _, expected, scores, row_lang in scored:
                if row_lang != lang:
                    continue
                found = {i for i, s in scores.items() if s >= t}
                tp += len(found & expected)
                fp += len(found - expected)
                fn += len(expected - found)
            print(f"  {lang} threshold {t:.2f}: hits {tp} · false {fp} · missed {fn}")
    for name, expected, scores, _ in scored:
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
        print(f"  {name}: expected {sorted(expected)}")
        print("      " + ", ".join(f"{i} {s:.2f}{'*' if i in expected else ''}" for i, s in top))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all-MiniLM-L6-v2")
