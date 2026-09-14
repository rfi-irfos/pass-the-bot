"""Detects whether each posting-side extracted skill is stated as required or
merely nice-to-have, via proximity to signal phrases in the posting text
(design spec section 5 step 3). Defaults to required=True when no signal
is found near a keyword's matched occurrence.

Scoping is per-sentence (reusing passthebot.normalizer.split_sentences), not
a fixed character window: an earlier fixed-width-window version leaked
signal words across adjacent sentences on short texts (e.g. "Python is
required. Docker is nice to have." incorrectly saw "required" inside
Docker's window too, since the window radius exceeded the sentence
boundary). Scoping to the actual sentence containing each occurrence fixes
this and is also more semantically correct: a requirement/optional signal
almost always applies to the clause it appears in, not a fixed span of
characters around it.

Known V1 limitation: this is still a naive substring-proximity heuristic
with no negation handling. A phrase like "kein Muss" (NOT a must) contains
the substring "muss" and will be read as a required-signal, overriding a
correctly-detected optional signal in the same sentence. The phrase list is
a first, plausible pass, not a validated value - see the plan's Next-steps
note for the calibration this needs once more real postings are run
through the engine.
"""

from __future__ import annotations

from passthebot.normalizer import ExtractedKeyword, split_sentences
from passthebot.validate_graph import normalize_string

_REQUIRED_PHRASES = [
    "erforderlich", "zwingend", "muss", "voraussetzung", "pflicht",
    "must have", "required", "mandatory",
]
_OPTIONAL_PHRASES = [
    "von vorteil", "wuenschenswert", "wünschenswert", "nice to have",
    "optional", "plus", "bonus",
]

_REQUIRED_SIGNALS = [normalize_string(p) for p in _REQUIRED_PHRASES]
_OPTIONAL_SIGNALS = [normalize_string(p) for p in _OPTIONAL_PHRASES]


def detect_required_ids(
    posting_text: str, posting_keywords: list[ExtractedKeyword]
) -> set[str]:
    """For each extracted posting keyword, look at every sentence in
    posting_text that contains an occurrence of its matched_text. If any such
    sentence has a required-signal phrase, the id is required. If every such
    sentence has an optional-signal phrase and no required signal is seen in
    any of them, the id is optional. Otherwise (no signal at all, or an
    ambiguous mix, or the keyword's text was never found in any sentence) the
    id is required, per the design spec's documented default.
    """
    sentences = [normalize_string(s) for s in split_sentences(posting_text)]
    required_ids: set[str] = set()

    for kw in posting_keywords:
        needle = normalize_string(kw.matched_text)
        if not needle:
            required_ids.add(kw.id)
            continue

        saw_required = False
        saw_optional = False
        saw_any_occurrence = False
        for sentence in sentences:
            if needle not in sentence:
                continue
            saw_any_occurrence = True
            if any(sig in sentence for sig in _REQUIRED_SIGNALS):
                saw_required = True
            if any(sig in sentence for sig in _OPTIONAL_SIGNALS):
                saw_optional = True

        if saw_required or not saw_any_occurrence or not saw_optional:
            required_ids.add(kw.id)

    return required_ids
