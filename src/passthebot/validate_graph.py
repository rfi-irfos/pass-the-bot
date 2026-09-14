from __future__ import annotations

import re
import sys
from pathlib import Path

from passthebot.graph import DISCRETE_CATEGORIES, SkillEntry, load_skill_graph

VALID_CATEGORIES = DISCRETE_CATEGORIES | {"soft_skills"}
VALID_STATUSES = {"curated", "ai-suggested-pending", "ai-suggested-approved"}


class GraphValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def normalize_string(s: str) -> str:
    """Lowercase and collapse whitespace/punctuation for alias-collision comparison."""
    return re.sub(r"[\s\.\-_]+", " ", s.strip().lower()).strip()


def validate_graph(entries: list[SkillEntry]) -> None:
    errors: list[str] = []

    seen_ids: dict[str, int] = {}
    for e in entries:
        seen_ids[e.id] = seen_ids.get(e.id, 0) + 1
    for id_, count in seen_ids.items():
        if count > 1:
            errors.append(f"duplicate id '{id_}' appears {count} times")

    for e in entries:
        if e.category not in VALID_CATEGORIES:
            errors.append(f"entry '{e.id}' has invalid category '{e.category}'")
        if e.status not in VALID_STATUSES:
            errors.append(f"entry '{e.id}' has invalid status '{e.status}'")

    alias_owner: dict[str, str] = {}
    for e in entries:
        strings = e.aliases if e.category in DISCRETE_CATEGORIES else e.anchor_phrases
        for raw in strings:
            key = normalize_string(raw)
            if key in alias_owner and alias_owner[key] != e.id:
                errors.append(
                    f"alias/phrase '{raw}' (normalized '{key}') claimed by both "
                    f"'{alias_owner[key]}' and '{e.id}'"
                )
            else:
                alias_owner[key] = e.id

    if errors:
        raise GraphValidationError(errors)


def main() -> int:
    data_dir = Path(__file__).parent.parent.parent / "data" / "skills"
    entries = load_skill_graph(data_dir)
    try:
        validate_graph(entries)
    except GraphValidationError as exc:
        print("Skill graph validation FAILED:", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"Skill graph validation passed ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
