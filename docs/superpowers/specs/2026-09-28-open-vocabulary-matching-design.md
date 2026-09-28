# Open-Vocabulary Requirement Matching — Design Spec

Date: 2026-09-28

## Purpose

pass the bot currently only recognizes requirements that exist as a
curated entry in `hard_skills.yaml` (17 entries) or `soft_skills.yaml`
(~10 entries). Every curated entry is AI/ML/security/cloud/DevOps-focused.
A job posting audit (2026-09-28) confirmed that postings outside this
niche — general software roles, and every non-tech industry — produce
few or zero extracted requirements, which looks like a good or neutral
match while actually meaning the tool never understood the posting.

Goal: let pass the bot assess job postings from any industry, not just
the current AI/ML/security niche, so it can be marketed as a
general-purpose tool rather than a niche one. This is a business-scope
decision, not a technical requirement in itself; this spec covers only
the technical mechanism that makes broader coverage possible.

Success criteria: a job posting for a non-curated skill or industry
(e.g. accounting, skilled trades, sales, healthcare, or a general
software role like "Python backend developer") produces MATCH/NEAR_MISS/
MISSING results grounded in the posting's actual text, with the same
honesty guarantee as the rest of the report — no invented or
LLM-hallucinated skills, only phrases traceable to a literal span of the
posting text and a real, reproducible similarity score.

## Scope

In scope:
- A new open-vocabulary requirement extractor that finds candidate
  requirement phrases in posting text using structural cues (headings +
  bullet lists + comma-separated lists), independent of any curated
  skill catalog.
- Embedding-based matching of each open candidate phrase against the
  resume text, reusing the existing `Embedder`.
- Deduplication against the existing curated-catalog matches, so a
  skill already caught by the curated layer is never also reported as
  an open match.
- Merging open matches into the existing `MatchResult` list and
  dashboard cards, with a visual marker distinguishing similarity-based
  matches from exact curated matches.
- Test fixtures covering multiple non-tech industries.

Out of scope (deferred, noted for a future spec):
- Free-text (non-listed) requirement extraction via NLP/POS tagging
  (e.g. spaCy). V1 only extracts requirements that appear in a
  structurally recognizable list; a posting written as unstructured
  prose with no bullet/comma list will still under-extract. This is a
  known V1 limitation, not silently mishandled.
- Any LLM-based extraction. Rejected: violates the project's existing
  no-fabricated-metrics constraint, since a generative model can name a
  skill that is not actually present in the text.
- Monetization, pricing, paywall, or account features. Out of scope for
  this spec entirely — a business decision independent of this
  technical mechanism.
- Replacing or retiring the curated catalogs. They remain the precise
  first layer; open extraction only fills gaps they don't cover.

## Engine additions (`src/passthebot`)

### `normalizer.py`: `extract_open_requirements`

```python
@dataclass
class OpenRequirement:
    phrase: str          # verbatim text span from the posting
    source_line: int      # line index in the posting, for dedup/debugging
```

```python
REQUIREMENT_HEADING_KEYWORDS = {
    "anforderungen", "ihr profil", "profil", "qualifikationen",
    "voraussetzungen", "must-have", "must haves", "nice-to-have",
    "requirements", "qualifications", "what you'll need",
    "what we're looking for", "your profile",
}

def extract_open_requirements(posting_text: str) -> list[OpenRequirement]:
    """Find requirement list items under a requirement-style heading.

    Reuses the heading-detection approach from sections.py (short
    standalone line containing a known heading keyword as a whole word).
    Once a requirement heading is found, every subsequent bullet line
    (leading -, *, •, or digit-dot) until the next heading is one
    candidate phrase. A heading's body with no bullet markers but a
    comma-separated single line (e.g. "Requirements: Python, SQL, Excel")
    is split on commas into one candidate phrase per item instead.

    Known V1 limitation: a requirements section written as ordinary
    prose sentences (no bullets, no comma list) is not decomposed into
    candidate phrases — matches this project's existing pattern of
    documenting V1 heuristic limits (see matcher.py's near-miss
    docstring, sections.py's heading-only-on-own-line limitation).
    """
```

### `normalizer.py`: `match_open_requirements`

```python
def match_open_requirements(
    open_requirements: list[OpenRequirement],
    resume_text: str,
    embedder,
    claimed_spans: set[str],  # normalized text already matched by the curated layer
    match_threshold: float = 0.48,
    near_miss_threshold: float = 0.35,
) -> list[MatchResult]:
    """For each open requirement phrase not already covered by a curated
    match (checked via normalize_string against claimed_spans), find the
    resume's best-matching sentence via embedder.best_match (same
    mechanism as extract_soft_skills) and classify:

    - score >= match_threshold -> MATCH
    - near_miss_threshold <= score < match_threshold -> NEAR_MISS
    - score < near_miss_threshold -> MISSING

    Returned MatchResult.id is the normalized phrase text (no canonical
    id exists for an open phrase). MatchResult gets a new field
    `origin: Literal["curated", "open"]` (default "curated" for existing
    call sites) so the frontend can render the similarity-match marker
    without re-deriving origin from confidence alone.

    match_threshold/near_miss_threshold start at the existing soft-skill
    default (0.48) and a near-miss band 13 points below it, mirroring
    the existing MIN_SECTION_WORDS-style "documented starting heuristic,
    calibrate against fixtures" pattern from sections.py. Calibration
    happens during implementation against the new multi-industry test
    fixtures (Review Focus below), not as a guess baked in without
    verification.
    """
```

### `matcher.py`: pipeline wiring

The pipeline (`pipeline.py`, not shown here as it's an existing file)
calls, after the existing curated `match()` call:

1. Build `claimed_spans` from the curated `MatchResult` list's
   `found_text`/`matched_text` values (normalized).
2. Call `extract_open_requirements(posting_text)`.
3. Call `match_open_requirements(...)` with the curated claimed spans.
4. Append the open `MatchResult` list to the curated one before scoring/
   report assembly. Existing score computation already iterates over
   the full `MatchResult` list, so no change needed there as long as
   `origin` defaults safely.

## Frontend changes (`web/frontend`)

Each match card (`app.js`'s existing MATCH/NEAR_MISS/MISSING rendering)
checks `result.origin === "open"` and appends a small "~" marker plus a
`title` tooltip ("Ähnlichkeitsbasiert erkannt, nicht aus dem kuratierten
Katalog") to that entry. No new card, no new section — open and curated
results render in the same three existing cards per the approved
design, keeping one coherent picture of the posting's requirements
instead of splitting precision tiers into separate UI regions.

## Review Focus

- A posting with zero recognizable requirement heading (very informally
  written): `extract_open_requirements` must return an empty list, not
  raise or degrade the curated results already found. Test this
  explicitly — an empty return here should never affect existing
  curated-only postings' report shape.
- A posting whose requirements section is a single unbulleted prose
  paragraph, not a list: per the documented V1 limitation, no candidate
  phrases extracted — the task's tests must assert this limitation, not
  cover the deferred spaCy fallback (that is a separate, future spec).
- A resume with zero relevant content for an open requirement (e.g.
  posting wants "Schweißen" [welding], resume is a pure office-admin
  CV): must classify as MISSING at the calibrated threshold, not a false
  MATCH from an unrelated but superficially-similar embedding neighbor.
- A skill covered by BOTH the curated catalog and the open requirements
  list in the same posting (e.g. "Python" appears in `hard_skills.yaml`
  AND as an open-list bullet): must be reported exactly once (curated
  wins), never twice.
- Non-Latin or mixed DE/EN heading phrasing in the same posting (common
  in Austrian job postings that mix English tech terms into German
  prose): heading detection must still find the requirements section via
  the existing whole-word keyword match used by `sections.py`.

## Testing

New test fixtures spanning multiple non-tech industries (skilled trades,
office/administration, sales, healthcare) plus one general (non-AI/ML)
software posting, each with a resume that should MATCH some open
requirements and MISS others — verifying the classification is grounded
in genuine similarity, not coincidence. Existing curated-skill test
suite must stay green unchanged (open extraction is strictly additive).
