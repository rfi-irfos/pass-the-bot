"""Detects whether each posting-side extracted skill is stated as required or
merely nice-to-have, via proximity to signal phrases in the posting text
(design spec section 5 step 3), and via the posting section each occurrence
stands in. Defaults to required when the posting has no recognizable sections
and no signal is found near a keyword's matched occurrence.

Scoping is per-sentence (reusing passthebot.normalizer.split_sentences), not
a fixed character window: an earlier fixed-width-window version leaked
signal words across adjacent sentences on short texts (e.g. "Python is
required. Docker is nice to have." incorrectly saw "required" inside
Docker's window too, since the window radius exceeded the sentence
boundary). Scoping to the actual sentence containing each occurrence fixes
this and is also more semantically correct: a requirement/optional signal
almost always applies to the clause it appears in, not a fixed span of
characters around it.

Negated signals ("kein Muss", "not required") read as optional. The phrase
list is a first, plausible pass, not a validated value - see the plan's Next-steps
note for the calibration this needs once more real postings are run
through the engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from passthebot.normalizer import ExtractedKeyword, heading_kind, split_sentences, strip_item_marker
from passthebot.validate_graph import normalize_string

# Matched at word starts. "muss" and "pflicht" also open unrelated words
# ("Pflichtbewusstsein"), so those two stay whole words.
_REQUIRED_SIGNAL = re.compile(
    r"(?<![a-zäöüß])(?:erforderlich|zwingend|voraussetzung|must have|must\b|required\b|mandatory"
    r"|essential\b|verpflichtend|obligatoire|exigé|(?:muss|musst|müssen|pflicht)(?![a-zäöüß]))"
)
_OPTIONAL_SIGNAL = re.compile(
    r"(?<![a-zäöüß])(?:von vorteil|wuenschenswert|wünschenswert|nice to have|optional|plus\b|bonus\b"
    r"|ideally|idealerweise|vorzugsweise|preferred|preferably|advantageous|souhaité|apprécié)"
)
# "kein Muss", "not required": the bare word would say the opposite.
_NEGATED_REQUIRED = re.compile(
    r"(?<![a-zäöüß])(?:kein|keine|keinen|nicht|not|no|pas|non)\s+(?:\w+\s+)?"
    r"(?:muss\b|must\b|voraussetzung\w*|pflicht\b|erforderlich\w*|zwingend\w*|required\b"
    r"|mandatory|essential\b|obligatoire)"
)
_CLAUSE_BREAK = re.compile(r"[,;]|\b(?:but|aber|however|jedoch|mais)\b")

EVIDENCE_MAX_CHARS = 160

Level = Literal["required", "task", "optional", "mentioned"]
COUNTS_TOWARD_SCORE: frozenset[str] = frozenset({"required", "task"})
_RANK: dict[str, int] = {"mentioned": 0, "optional": 1, "task": 2, "required": 3}


@dataclass
class KeywordImportance:
    level: Level
    evidence: str | None


def _posting_sentences(posting_text: str) -> list[tuple[str, Level]]:
    """Each sentence of the posting with the level its section implies.

    Company intro and benefits are only "mentioned": issue #13's "190K+ GitHub
    stars" and "SAP's recent strategic investment" name a skill without asking
    for it. Text before the first heading only counts as intro if the posting
    has a requirements section somewhere; otherwise it may be all there is,
    and the documented required default applies to it.
    """
    lines = [(line, heading_kind(line)) for line in posting_text.splitlines()]
    has_section = any(kind in ("required", "optional") for _, kind in lines)
    sentences: list[tuple[str, Level]] = []
    zone: Level = "mentioned" if has_section else "required"
    for line, kind in lines:
        if kind == "other":
            zone = "mentioned"
        elif kind is not None:
            zone = kind
        sentences.extend((sentence, zone) for sentence in split_sentences(line))
    return sentences


def _shorten(sentence: str) -> str:
    sentence = strip_item_marker(sentence)
    if len(sentence) <= EVIDENCE_MAX_CHARS:
        return sentence
    return sentence[:EVIDENCE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _signal_level(text: str) -> Level | None:
    if _NEGATED_REQUIRED.search(text):
        return "optional"
    if _REQUIRED_SIGNAL.search(text):
        return "required"
    if _OPTIONAL_SIGNAL.search(text):
        return "optional"
    return None


def _sentence_level(sentence: str, pattern: re.Pattern, zone: Level) -> Level:
    """A signal phrase outranks the section. The keyword's own clause is
    looked at first, so "Python required, Docker a plus" tells the two apart;
    a clause without a signal takes the sentence's ("Python, SQL are required")."""
    own = [
        level
        for clause in _CLAUSE_BREAK.split(sentence)
        if pattern.search(clause) and (level := _signal_level(clause))
    ]
    if own:
        return max(own, key=_RANK.__getitem__)
    return _signal_level(sentence) or zone


def classify_importance(
    posting_text: str, posting_keywords: list[ExtractedKeyword]
) -> dict[str, KeywordImportance]:
    """For each extracted posting keyword, find every sentence naming it and
    keep the highest level among them, along with that sentence as evidence
    the user can check. A keyword whose text isn't found in any sentence is
    required, per the design spec's documented default.

    If a posting without requirements section ends up with nothing to score
    (only company headings), the required default applies to everything
    instead: a guess at the requirements beats no answer on a posting that
    has no other structure to go on.
    """
    sentences = _posting_sentences(posting_text)
    normalized = [(normalize_string(s), s, zone) for s, zone in sentences]

    importance: dict[str, KeywordImportance] = {}
    for kw in posting_keywords:
        needles = [n for n in map(normalize_string, kw.mentions or [kw.matched_text]) if n]
        patterns = [re.compile(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])") for n in needles]

        best: Level | None = None
        evidence: str | None = None
        for text, original, zone in normalized:
            for pattern in patterns:
                if not pattern.search(text):
                    continue
                level = _sentence_level(text, pattern, zone)
                if best is None or _RANK[level] > _RANK[best]:
                    best, evidence = level, _shorten(original)

        importance[kw.id] = KeywordImportance(level=best or "required", evidence=evidence)

    if all(item.level == "mentioned" for item in importance.values()) and not any(
        zone == "optional" or zone == "required" for _, zone in sentences
    ):
        for item in importance.values():
            item.level = "required"
    return importance


def detect_required_ids(
    posting_text: str, posting_keywords: list[ExtractedKeyword]
) -> set[str]:
    return {
        kw_id
        for kw_id, item in classify_importance(posting_text, posting_keywords).items()
        if item.level in COUNTS_TOWARD_SCORE
    }
