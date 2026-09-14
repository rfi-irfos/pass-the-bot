from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

Category = Literal[
    "languages", "frameworks", "tools", "certifications",
    "job_titles", "hard_skills", "soft_skills",
]
Status = Literal["curated", "ai-suggested-pending", "ai-suggested-approved"]

DISCRETE_CATEGORIES: set[str] = {
    "languages", "frameworks", "tools", "certifications", "job_titles", "hard_skills",
}
ACTIVE_STATUSES: set[str] = {"curated", "ai-suggested-approved"}


@dataclass
class SkillEntry:
    id: str
    category: Category
    display: dict[str, str]
    status: Status
    added: str
    aliases: list[str] = field(default_factory=list)
    anchor_phrases: list[str] = field(default_factory=list)
    embedding_threshold: float | None = None


def load_skill_graph(data_dir: Path) -> list[SkillEntry]:
    """Load every *.yaml file directly under data_dir into a flat list of SkillEntry."""
    entries: list[SkillEntry] = []
    for yaml_file in sorted(data_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or []
        for entry_idx, item in enumerate(raw):
            try:
                entries.append(
                    SkillEntry(
                        id=item["id"],
                        category=item["category"],
                        display=item["display"],
                        status=item["status"],
                        added=item["added"],
                        aliases=item.get("aliases", []),
                        anchor_phrases=item.get("anchor_phrases", []),
                        embedding_threshold=item.get("embedding_threshold"),
                    )
                )
            except KeyError as e:
                entry_id = item.get("id", f"entry at index {entry_idx}")
                raise ValueError(
                    f"Missing required field {e} in {yaml_file.name} for {entry_id}"
                ) from e
    return entries


def active_entries(entries: list[SkillEntry]) -> list[SkillEntry]:
    """Filter to entries eligible for matching (curated or ai-suggested-approved)."""
    return [e for e in entries if e.status in ACTIVE_STATUSES]
