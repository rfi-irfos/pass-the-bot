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
    # added 2026-10-21 from postings read via pasted links (issue #4)
    "what you need", "who you are", "about you", "you bring", "you have",
    "mandatory experience", "essential", "desirable", "strongly preferred",
    "hard skills", "how you work", "skills", "du bringst mit", "das bringst du mit",
    "sie bringen mit", "dein profil", "kenntnisse", "compétences", "prérequis",
    "votre profil",
}

OTHER_SECTION_HEADING_KEYWORDS: set[str] = {
    "wir bieten", "we offer", "was wir bieten", "was wir dir bieten",
    "benefits", "perks", "vorteile", "das bieten wir", "unser angebot",
    "über uns", "about us", "kontakt", "contact", "bewerbung",
    "how to apply", "jetzt bewerben",
    # added 2026-10-21: benefits/values/KPI/responsibility sections whose
    # bullets bled into a preceding requirements section (a LinkedIn user
    # was told to prove "Modern office space in Munich")
    "what you get", "our offer", "why join", "why us", "what's in it for you",
    "life at", "working at", "our values", "values", "success measures",
    "how success", "what success looks like", "kpis", "equal employment",
    "about the role", "about the company", "responsibilities", "what you will do",
    "what you'll do", "your role", "deine aufgaben", "ihre aufgaben", "aufgaben",
    "deine vorteile", "warum wir", "nous offrons", "ce que nous offrons",
    "ce que l'on vous propose", "avantages", "pourquoi nous rejoindre",
    "à propos", "qui sommes-nous", "missions",
    # added 2026-10-21 from non-tech postings (issue #7)
    "versprechen", "das erwartet dich", "das erwartet sie", "was dich erwartet",
    "was sie erwartet", "aufgabengebiet", "ihr aufgabengebiet", "dein aufgabengebiet",
    "deine benefits", "ihre benefits", "zusatzleistungen",
}

# Bullet phrases that describe what the employer offers, not what the
# candidate needs. Dropped from open requirements even when their section
# heading is an as-yet-unknown phrasing that doesn't close the section.
# Deliberately specific (e.g. "office space", not "office", which would
# also drop "Microsoft Office").
_BENEFIT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\boffice (?:space|location)s?\b", r"\bmodern (?:office|workplace)s?\b",
        r"\bsalary\b", r"\bcompensation\b", r"\bvacation\b", r"\bpaid time off\b",
        r"\bparental leave\b", r"\bhealth insurance\b", r"\bpension\b",
        r"\bstock options?\b", r"\bgym\b", r"\bfitness\b", r"\bteam events?\b",
        r"\bfree (?:lunch|drinks|snacks|coffee|fruit)\b",
        r"\bflexible (?:working|work|hours)\b",
        r"\bgehalt\b", r"\bvergütung\b", r"\burlaub", r"\bjobticket\b", r"\bjobrad\b",
        r"\baltersvorsorge\b", r"\bteamevents?\b", r"\bfirmenevents?\b",
        r"\bmodernes? büro", r"\bflexible arbeitszeiten\b",
        r"\bmutuelle\b", r"\btickets? restaurant\b", r"\btitres? restaurant\b",
        r"\bsalaire\b", r"\bcongés\b", r"\brtt\b",
        r"weiterbildungsmöglichkeit", r"\bsinnstiftend", r"\bfirmenwagen\b",
        r"\bdienstwagen\b", r"\bdienstauto\b", r"\bfirmenfahrzeug\b",
        r"\büberzahlung\b", r"\blearning budget\b", r"\btraining budget\b",
    )
]


def _is_benefit_phrase(phrase: str) -> bool:
    return any(p.search(phrase) for p in _BENEFIT_PATTERNS)

PLAIN_LINE_MAX_WORDS = 12

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
    """Single-word keywords ("kenntnisse", "skills", "profil") also occur
    inside ordinary requirement lines ("Gute Kenntnisse im MS Office-Paket"),
    so they only count as a heading when the line is at most three words
    long or starts with the keyword ("Anforderungen, die du mitbringst")."""
    words = normalized.split()
    if not normalized or len(words) > 6:
        return False
    for kw in keywords:
        if " " not in kw and len(words) > 3 and not normalized.startswith(kw):
            continue
        if re.search(rf"(?<![a-zäöü]){re.escape(kw)}(?![a-zäöü])", normalized):
            return True
    return False


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
    from all of them. A bullet-less line that is not such a comma list
    counts as one item when it is short and has no closing sentence
    punctuation (_is_plain_line_item), because some job boards strip the
    bullet glyphs and deliver each requirement as a plain line.

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
    surface new phrasings. Bullets that clearly describe an employer
    benefit (_BENEFIT_PATTERNS, e.g. "office space", "Gehalt", "mutuelle")
    are dropped regardless of section, as a second line of defence for
    exactly that case; the pattern list is a first plausible pass, like the
    heading sets, not a validated classifier.
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
                if phrase and not _is_benefit_phrase(phrase)
            )
            continue

        for idx, line in section_lines:
            if "," in line:
                fragments = [item.strip().strip(".") for item in line.split(",")]
                fragments = [f for f in fragments if f]
                if fragments and all(len(f.split()) <= 8 for f in fragments):
                    requirements.extend(
                        OpenRequirement(phrase=f, source_line=idx)
                        for f in fragments
                        if not _is_benefit_phrase(f)
                    )
                    continue
            phrase = line.strip()
            if _is_plain_line_item(phrase) and not _is_benefit_phrase(phrase):
                requirements.append(OpenRequirement(phrase=phrase, source_line=idx))
    return requirements


def _is_plain_line_item(line: str) -> bool:
    """A short line with no bullet glyph that reads like a list item rather
    than a sentence: at most PLAIN_LINE_MAX_WORDS words and no closing
    sentence punctuation. Intro lines ("Das solltest du mitbringen:") end
    with a colon and are skipped. Job boards that strip bullet glyphs
    (e.g. the Arbeitsagentur) deliver requirements in exactly this shape."""
    return (
        bool(line)
        and len(line.split()) <= PLAIN_LINE_MAX_WORDS
        and not line.endswith((".", ":", "?", "!"))
    )


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
    # Hidden words of German suspended compounds are appended after the text,
    # each remembering the phrase it came from (reported as matched_text).
    expansion_sources: list[tuple[int, str]] = []
    for word, source in _suspended_compound_expansions(text):
        normalized_text += " | "
        expansion_sources.append((len(normalized_text), source))
        normalized_text += normalize_string(word)
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
                matched_text = next(
                    (src for pos, src in reversed(expansion_sources) if start >= pos), alias
                )
                found[entry.id] = ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=matched_text,
                    confidence=1.0,
                )
    return list(found.values())


# "Grund- und Behandlungspflege": the first word drops the part it shares
# with the second ("pflege"). The shared tail is unknown, so every tail of
# at least MIN_SHARED_TAIL letters is tried; only real aliases ever match.
_SUSPENDED_COMPOUND = re.compile(r"(\w+)-\s+(?:und|oder|bzw\.?|sowie|&)\s+(\w+)")
MIN_SHARED_TAIL = 4


def _suspended_compound_expansions(text: str) -> list[tuple[str, str]]:
    expansions: list[tuple[str, str]] = []
    for m in _SUSPENDED_COMPOUND.finditer(text):
        head, full = m.group(1), m.group(2)
        for cut in range(1, len(full) - MIN_SHARED_TAIL + 1):
            expansions.append((head + full[cut:], m.group(0)))
    return expansions


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


GERMAN_TEXT_MIN_THRESHOLD = 0.60

_GERMAN_FUNCTION_WORDS = {
    "und", "der", "die", "das", "mit", "für", "von", "im", "in", "eine", "ein",
    "wir", "sie", "du", "ihr", "dein", "deine", "ihre", "unsere", "oder", "zu",
}
_ENGLISH_FUNCTION_WORDS = {
    "and", "the", "with", "for", "of", "in", "a", "an", "we", "you", "your",
    "our", "or", "to", "is", "are",
}


def detect_language(text: str) -> str:
    """"de" or "en", by counting common function words. Good enough to pick
    a soft-skill threshold; not a general language detector."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    german = sum(w in _GERMAN_FUNCTION_WORDS for w in words)
    english = sum(w in _ENGLISH_FUNCTION_WORDS for w in words)
    return "de" if german > english else "en"


_LIST_SEPARATOR = re.compile(r"\s*(?:,|;|\bund\b|\band\b|\bsowie\b|&)\s*", re.IGNORECASE)
LIST_ITEM_MAX_WORDS = 1


def _short_list_items(sentence: str) -> list[str]:
    """Items of an enumeration of single words ("Einfühlsam, zuverlässig und
    teamfähig"), scored on their own as well: as one sentence, each item's
    similarity is diluted by the others (0.54 instead of 1.0 for
    "zuverlässig"). Multi-word items are left alone: generic shared words
    ("Arbeitsweise", "skills") made "selbstständige Arbeitsweise" score 0.70
    against "strukturierte Arbeitsweise". The single words of a mixed list
    are still used ("Empathetic, reliable and responsible team player"
    yields "Empathetic" and "reliable")."""
    items = [i.strip(" .-") for i in _LIST_SEPARATOR.split(sentence)]
    items = [i for i in items if i]
    if len(items) < 2:
        return []
    return [i for i in items if len(i.split()) <= LIST_ITEM_MAX_WORDS]


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
    sentences) clears its own embedding_threshold. On German text the
    threshold is at least GERMAN_TEXT_MIN_THRESHOLD: the English model
    scores unrelated German sentences around 0.50-0.60, while German anchor
    phrases that really occur score 0.65 and up (measured on
    tests/data/postings with scripts/measure_soft_skills.py, issue #7).
    """
    sentences = split_sentences(text)
    if not sentences:
        sentences = [text]
    sentences = sentences + [f for s in sentences for f in _short_list_items(s)]
    is_german = detect_language(text) == "de"

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
        if is_german:
            threshold = max(threshold, GERMAN_TEXT_MIN_THRESHOLD)
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
