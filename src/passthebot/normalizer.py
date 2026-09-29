from __future__ import annotations

import re
from dataclasses import dataclass

from passthebot.graph import SkillEntry
from passthebot.validate_graph import normalize_string


REQUIREMENT_HEADING_KEYWORDS: set[str] = {
    "anforderungen", "ihr profil", "profil", "qualifikationen",
    "voraussetzungen", "must-have", "must haves", "nice-to-have",
    "requirements", "qualifications", "what you'll need",
    "what we're looking for", "your profile",
}

OTHER_SECTION_HEADING_KEYWORDS: set[str] = {
    "wir bieten", "we offer", "was wir bieten", "was wir dir bieten",
    "benefits", "perks", "vorteile", "das bieten wir", "unser angebot",
    "über uns", "about us", "kontakt", "contact", "bewerbung",
    "how to apply", "jetzt bewerben",
}

_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


@dataclass
class OpenRequirement:
    phrase: str
    source_line: int


@dataclass
class ExtractedKeyword:
    id: str
    category: str
    matched_text: str
    confidence: float


def _normalize_heading_line(line: str) -> str:
    return line.strip().strip(":-–—").strip().lower()


def _matches_keyword_set(normalized: str, keywords: set[str]) -> bool:
    if not normalized or len(normalized.split()) > 6:
        return False
    return any(
        re.search(rf"(?<![a-zäöü]){re.escape(kw)}(?![a-zäöü])", normalized)
        for kw in keywords
    )


def _is_requirement_heading(line: str) -> bool:
    if _BULLET_PREFIX.match(line):
        return False
    return _matches_keyword_set(_normalize_heading_line(line), REQUIREMENT_HEADING_KEYWORDS)


def _is_any_recognized_heading(line: str) -> bool:
    """True if `line` matches a known requirement heading OR a known
    non-requirement section heading (benefits/company-info sections that
    commonly follow a requirements section, e.g. "Wir bieten" / "About
    us"). Used only to find where a requirements section's body ends.

    Deliberately keyword-based, not shape-based: an earlier version of
    this module treated any short, standalone, non-bullet line as a
    boundary candidate ("heading-shaped"), which is the wrong property to
    check. A blank line before a heading, a second comma-list line in the
    same section, and an unrecognized short line right after the opening
    heading (e.g. "Du bringst mit:") are all "heading-shaped" by that
    definition, but none of them are actually headings -- so shape-based
    detection either wrongly closes a section (blank line before a
    comma-list, or a non-heading intro line) or fails to close one (a
    second, unprotected comma-list line). Matching only a known keyword
    set sidesteps all of that: an unrecognized line simply never matches,
    with no positional heuristics needed."""
    if _BULLET_PREFIX.match(line):
        return False
    normalized = _normalize_heading_line(line)
    return (
        _matches_keyword_set(normalized, REQUIREMENT_HEADING_KEYWORDS)
        or _matches_keyword_set(normalized, OTHER_SECTION_HEADING_KEYWORDS)
    )


def extract_open_requirements(posting_text: str) -> list[OpenRequirement]:
    """Find requirement-list items under a requirement-style heading in a
    job posting, independent of any curated skill catalog.

    Heading detection follows the same whole-word substring approach as
    sections.py's resume-heading detection (a short standalone line
    containing a known keyword as a whole word), but against
    REQUIREMENT_HEADING_KEYWORDS instead of resume-section names --
    postings and resumes use different vocabularies for structurally
    similar things, so this is a separate, independently-evolving
    keyword set, not a shared import from sections.py.

    Once a requirement heading is found, every following bulleted line
    (leading -, *, •, or "1." / "1)") up to the next heading is one
    candidate phrase. A section's body ends at the next line that matches
    a KNOWN heading keyword -- either REQUIREMENT_HEADING_KEYWORDS (the
    next requirements section) or OTHER_SECTION_HEADING_KEYWORDS (a
    following non-requirement section, e.g. "Wir bieten" / "We offer"
    benefits, "About us", "How to apply") -- never merely because a line
    "looks like" a heading by shape (short, standalone, non-bullet).
    An unrecognized short line (a blank line, a comma-list line, or a
    plain intro sentence like "Du bringst mit:") never matches either
    keyword set, so it's never mistaken for a boundary and never
    prematurely closes the section.

    If a heading's body has no bullets but a line contains commas, that
    line is split on commas into one candidate phrase per item instead,
    but only when every resulting fragment is short (<=8 words): a full
    prose sentence that merely happens to contain a comma (e.g. "...
    experience, ideally with Excel, who can work independently.") is not
    list structure and must not be shredded into fake requirements. Every
    comma-bearing line in the section body is processed this way (not
    just the first), so a section with multiple comma-list lines (e.g.
    "Python, SQL, Excel" followed by "Deutsch, Englisch") extracts items
    from all of them.

    Known V1 limitation: a requirements section written as ordinary
    prose sentences (no bullets, no comma anywhere in the body, or a
    comma-bearing line whose fragments are not all short) yields no
    candidate phrases. Free-text extraction (e.g. via NLP/POS tagging)
    is deferred to a future spec, not silently attempted here -- matching
    this project's existing pattern of documenting V1 heuristic limits
    (see matcher.py's near-miss docstring, sections.py's
    heading-only-on-own-line limitation). Another known limitation: a
    non-requirement section whose heading isn't in
    OTHER_SECTION_HEADING_KEYWORDS (an as-yet-unseen phrasing) won't be
    recognized as a boundary and its bullets could bleed into a
    preceding requirements section -- this keyword set, like
    REQUIREMENT_HEADING_KEYWORDS, is expected to grow as new postings
    surface new phrasings.
    """
    lines = posting_text.splitlines()
    heading_indices = [idx for idx, line in enumerate(lines) if _is_requirement_heading(line)]
    if not heading_indices:
        return []

    boundary_indices = [idx for idx, line in enumerate(lines) if _is_any_recognized_heading(line)]

    requirements: list[OpenRequirement] = []
    for start_idx in heading_indices:
        end_idx = next((idx for idx in boundary_indices if idx > start_idx), len(lines))
        section_lines = [
            (idx, lines[idx]) for idx in range(start_idx + 1, end_idx) if lines[idx].strip()
        ]

        bullet_items = [
            (idx, _BULLET_PREFIX.sub("", line).strip())
            for idx, line in section_lines
            if _BULLET_PREFIX.match(line)
        ]
        if bullet_items:
            requirements.extend(
                OpenRequirement(phrase=phrase, source_line=idx)
                for idx, phrase in bullet_items
                if phrase
            )
            continue

        for idx, line in section_lines:
            if "," in line:
                fragments = [item.strip().strip(".") for item in line.split(",")]
                fragments = [f for f in fragments if f]
                if fragments and all(len(f.split()) <= 8 for f in fragments):
                    requirements.extend(
                        OpenRequirement(phrase=f, source_line=idx) for f in fragments
                    )
    return requirements


def extract_discrete_keywords(text: str, entries: list[SkillEntry]) -> list[ExtractedKeyword]:
    """Scan text for any known alias of any discrete-category entry.

    Matching is on normalized substrings (see normalize_string): case-insensitive,
    punctuation/whitespace-collapsed. Each skill id is reported at most once, even
    if multiple of its aliases (or the same alias multiple times) appear in the text.

    Uses longest-alias-first matching with span-claiming: normalization turns
    punctuation like "." into a space (e.g. "Node.js" -> "node js"), which means
    a short alias belonging to a *different* entry (e.g. "js" for javascript) can
    accidentally match as a standalone token inside a longer alias's normalized
    text ("node js"). To avoid this, all (alias, entry) pairs are tried longest-
    normalized-alias-first, and once a span of the normalized text is claimed by
    a match, no shorter alias is allowed to match inside that span. This is the
    same failure class as the Java/JavaScript regression case (design spec
    section 8), just reached via punctuation normalization instead of a raw
    substring collision.

    Span-claiming semantics: overlapping aliases from different entries
    resolve to the longest match. If a shorter entry's alias falls fully
    inside a span already claimed by a longer, different entry's alias, the
    shorter entry is NOT also extracted for that occurrence (e.g. once a
    "React Native" entry exists alongside a "react" entry, the text "React
    Native experience" extracts only react_native, not react, for that
    occurrence). This is an intentional design choice, not a bug: a single
    mention is not double-counted as both the specific and the more general
    skill it happens to contain as a substring.
    """
    normalized_text = normalize_string(text)
    claimed = [False] * len(normalized_text)

    pairs: list[tuple[str, str, SkillEntry]] = []
    for entry in entries:
        for alias in entry.aliases:
            needle = normalize_string(alias)
            if needle:
                pairs.append((needle, alias, entry))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    found: dict[str, ExtractedKeyword] = {}
    for needle, alias, entry in pairs:
        for m in re.finditer(
            rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", normalized_text
        ):
            start, end = m.start(), m.end()
            if any(claimed[start:end]):
                continue
            for i in range(start, end):
                claimed[i] = True
            if entry.id not in found:
                found[entry.id] = ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=alias, confidence=1.0
                )
    return list(found.values())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries and newlines, dropping
    empty fragments.

    A simple regex split is sufficient for V1 - no NLP library needed. Embedding
    the whole document as one vector dilutes short soft-skill mentions buried in
    a multi-sentence posting/resume, so callers should score sentence-by-sentence
    instead of scoring the whole text at once. Splitting also on newlines is
    required because real job postings are commonly formatted as bullet lists
    with no terminal punctuation per line (e.g. "- Python\\n- Teamfaehigkeit"),
    which would otherwise collapse into one large fragment and reintroduce the
    same dilution problem.

    Public (no leading underscore) because passthebot.requirement reuses this
    exact sentence-scoping logic for its own proximity heuristic, instead of
    re-deriving a second sentence splitter with potentially different edge-case
    behavior.
    """
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in sentences if s.strip()]


def extract_soft_skills(
    text: str, entries: list[SkillEntry], embedder
) -> list[ExtractedKeyword]:
    """Match soft_skills entries by embedding similarity against anchor_phrases.

    The input text is split into sentences and each sentence is scored
    independently against an entry's anchor_phrases; the highest-scoring
    (phrase, score) pair across all sentences is used. Scoring the whole
    document as a single embedding dilutes short soft-skill mentions buried
    in longer multi-sentence text, so per-sentence scoring is required to
    detect them reliably.

    An entry is included if the best-matching anchor phrase (across all
    sentences) clears its own embedding_threshold.
    """
    sentences = split_sentences(text)
    if not sentences:
        sentences = [text]

    found: list[ExtractedKeyword] = []
    for entry in entries:
        if not entry.anchor_phrases:
            continue
        best_phrase: str | None = None
        best_score = float("-inf")
        for sentence in sentences:
            phrase, score = embedder.best_match(sentence, entry.anchor_phrases)
            if score > best_score:
                best_phrase, best_score = phrase, score
        threshold = entry.embedding_threshold if entry.embedding_threshold is not None else 0.48
        if best_score >= threshold:
            found.append(
                ExtractedKeyword(
                    id=entry.id,
                    category=entry.category,
                    matched_text=best_phrase,
                    confidence=best_score,
                )
            )
    return found
