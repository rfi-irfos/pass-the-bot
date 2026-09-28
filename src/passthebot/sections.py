"""Resume section detection for the honest-dashboard metrics.

Detects four standard resume sections by scanning for heading lines (a
line on its own, five words or fewer, that names the section) in German
and English. Known V1 limitation: only catches headings that sit alone
on their own line (e.g. "Skills\\nPython, Docker") -- a single-line
format like "Skills: Python, Docker" is not detected, matching this
project's existing pattern of documenting V1 heuristic limits rather
than silently mishandling them (see matcher.py's near-miss docstring).
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_SECTION_WORDS = 15

SECTION_ORDER = ["contact", "experience", "education", "skills"]

SECTION_KEYWORDS: dict[str, set[str]] = {
    "contact": {"kontakt", "contact"},
    "experience": {"erfahrung", "berufserfahrung", "experience", "work experience"},
    "education": {"ausbildung", "bildung", "education"},
    "skills": {"skills", "kenntnisse", "fähigkeiten", "fertigkeiten"},
}


@dataclass
class SectionResult:
    id: str
    found: bool
    word_count: int
    filled: bool


def _normalize_heading(line: str) -> str:
    return line.strip().strip(":-–—").strip().lower()


def detect_sections(resume_text: str) -> list[SectionResult]:
    lines = resume_text.splitlines()
    headings: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        normalized = _normalize_heading(line)
        if not normalized or len(normalized.split()) > 5:
            continue
        for section_id, keywords in SECTION_KEYWORDS.items():
            if normalized in keywords:
                headings.append((idx, section_id))
                break

    body_by_id: dict[str, str] = {}
    for i, (line_idx, section_id) in enumerate(headings):
        start = line_idx + 1
        end = headings[i + 1][0] if i + 1 < len(headings) else len(lines)
        body_by_id[section_id] = "\n".join(lines[start:end])

    results: list[SectionResult] = []
    for section_id in SECTION_ORDER:
        if section_id not in body_by_id:
            results.append(SectionResult(id=section_id, found=False, word_count=0, filled=False))
            continue
        word_count = len(body_by_id[section_id].split())
        results.append(
            SectionResult(
                id=section_id,
                found=True,
                word_count=word_count,
                filled=word_count >= MIN_SECTION_WORDS,
            )
        )
    return results
