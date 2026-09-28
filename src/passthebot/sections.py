"""Resume section detection for the honest-dashboard metrics.

Detects four standard resume sections in German and English using two
combined strategies:

1. Heading-based: a line on its own, five words or fewer, that CONTAINS
   one of a section's known keywords as a whole word (not just an exact
   full-line match) -- real resumes commonly combine synonyms into one
   heading line (e.g. "Kernkompetenzen / Skills", "Ausbildung & Bildung"),
   so a strict full-line match misses these.
2. Contact fallback: many single-page/ATS-style resumes put contact
   details (email, phone, location) directly under the name with no
   "Kontakt"/"Contact" heading at all. If no contact heading is found,
   scan the first few lines for an email address as a structural signal
   that contact info is present, and use that block as the contact
   section's body instead of reporting a false "not found".

Known V1 limitation: only catches headings that sit alone on their own
line (e.g. "Skills\\nPython, Docker") -- a single-line format like
"Skills: Python, Docker" is not detected, matching this project's
existing pattern of documenting V1 heuristic limits rather than silently
mishandling them (see matcher.py's near-miss docstring).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_SECTION_WORDS = 15
CONTACT_SCAN_LINES = 10

SECTION_ORDER = ["contact", "experience", "education", "skills"]

SECTION_KEYWORDS: dict[str, set[str]] = {
    "contact": {
        "kontakt",
        "contact",
        "contact information",
        "contact details",
        "personal details",
        "get in touch",
        "kontaktdaten",
    },
    "experience": {
        "erfahrung",
        "berufserfahrung",
        "beruflicher werdegang",
        "werdegang",
        "praxiserfahrung",
        "experience",
        "work experience",
        "work history",
        "employment history",
        "employment",
        "professional experience",
        "career history",
    },
    "education": {
        "ausbildung",
        "bildung",
        "bildungsweg",
        "schulbildung",
        "akademischer werdegang",
        "education",
        "qualifications",
        "academic background",
        "academic qualifications",
    },
    "skills": {
        "skills",
        "kenntnisse",
        "fähigkeiten",
        "fertigkeiten",
        "kernkompetenzen",
        "kompetenzen",
        "qualifikationen",
        "technical skills",
        "technical proficiencies",
        "core competencies",
        "areas of expertise",
        "proficiencies",
        "expertise",
    },
}

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class SectionResult:
    id: str
    found: bool
    word_count: int
    filled: bool


def _normalize_heading(line: str) -> str:
    return line.strip().strip(":-–—").strip().lower()


def _heading_matches(normalized: str, keywords: set[str]) -> bool:
    """True if any keyword appears as a whole word inside the heading
    line, not just as the line's entire content."""
    return any(
        re.search(rf"(?<![a-zäöü]){re.escape(kw)}(?![a-zäöü])", normalized)
        for kw in keywords
    )


def detect_sections(resume_text: str) -> list[SectionResult]:
    lines = resume_text.splitlines()
    headings: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        normalized = _normalize_heading(line)
        if not normalized or len(normalized.split()) > 5:
            continue
        for section_id, keywords in SECTION_KEYWORDS.items():
            if _heading_matches(normalized, keywords):
                headings.append((idx, section_id))
                break

    body_by_id: dict[str, str] = {}
    for i, (line_idx, section_id) in enumerate(headings):
        start = line_idx + 1
        end = headings[i + 1][0] if i + 1 < len(headings) else len(lines)
        body_by_id[section_id] = "\n".join(lines[start:end])

    if "contact" not in body_by_id:
        head_block = "\n".join(lines[:CONTACT_SCAN_LINES])
        if EMAIL_PATTERN.search(head_block):
            body_by_id["contact"] = head_block

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
