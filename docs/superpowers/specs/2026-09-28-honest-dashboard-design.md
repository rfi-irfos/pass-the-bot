# Honest Dashboard Redesign — Design Spec

Date: 2026-09-28

## Purpose

Redesign the passthebot results UI into a richer, more visually engaging
dashboard (inspired by a reference mockup showing a score gauge, skill
match bars, keyword coverage, a resume section breakdown, a category
radar chart, and a downloadable report), while adding zero fabricated
metrics. Every number shown must be traceable to a real computation over
the actual posting/resume text — no invented "AI category scores."

Success criteria: the dashboard looks and feels like the reference
mockup's level of polish, every new number has a documented formula or
heuristic a user could verify by hand, and the existing report contract
(`results`, `score`) is unchanged for backward compatibility.

## Scope

In scope: new engine metrics (readability, section detection, match
breakdown), a new additive `metrics` field on the report, a frontend
dashboard redesign consuming it, staggered reveal animation, and a
client-side PDF export of the results.

Out of scope: any metric that can't be computed transparently (the
mockup's "ATS Category Compliance"/"Format" scores are replaced by real
axes, not built as-is). No backend PDF generation. No change to the
existing skill-matching logic itself.

## Engine additions (`src/passthebot`)

### `readability.py`

Computes the Automated Readability Index (ARI) over `resume_text`, a
named, real formula that needs no syllable counting (so it works
consistently for German and English without a per-language syllable
heuristic):

```
ARI = 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43
```

`characters` excludes whitespace. Sentence splitting reuses
`normalizer.split_sentences` (already handles bullet lists without
terminal punctuation, per the existing regression test). Word splitting
is whitespace-based.

ARI produces a US grade-level number (roughly 0-20+). For display, map
grade level linearly to a 0-100 "readability score" where grade 0 → 100
and grade 20 → 0 (clamped to [0, 100]):

```
score = clamp(100 - grade_level * 5, 0, 100)
```

Returns:

```python
@dataclass
class ReadabilityResult:
    score: float               # 0-100, higher = easier to read
    grade_level: float         # raw ARI grade level
    avg_words_per_sentence: float
    avg_word_length_chars: float
```

Edge case: fewer than 2 sentences or fewer than 5 words → return
`score=None` (not a fabricated 0 or 100) with the raw counts still
populated; the frontend shows "not enough text to evaluate" instead of a
number.

### `sections.py`

Detects four standard resume sections by scanning for heading lines
(short lines, ≤5 words, matching a known keyword list) in both German and
English:

- `contact`: "Kontakt", "Contact"
- `experience`: "Erfahrung", "Berufserfahrung", "Experience", "Work Experience"
- `education`: "Ausbildung", "Bildung", "Education"
- `skills`: "Skills", "Kenntnisse", "Fähigkeiten", "Fertigkeiten"

A heading line is matched case-insensitively against these keyword lists
after stripping punctuation. The section's content is the text between
that heading and the next detected heading (or end of document). Word
count of that span determines `filled` (≥15 words, a documented,
adjustable constant, not a hidden magic number — defined as
`MIN_SECTION_WORDS = 15` at module level).

```python
@dataclass
class SectionResult:
    id: str            # "contact" | "experience" | "education" | "skills"
    found: bool
    word_count: int
    filled: bool        # found and word_count >= MIN_SECTION_WORDS
```

Returns `list[SectionResult]`, always all four ids present (found=False,
word_count=0, filled=False for undetected ones).

### Match breakdown (no new module)

`MatchResult.category` already distinguishes `soft_skills` (embedding/
semantic match) from discrete categories (exact alias match). Add a pure
aggregation function in `report.py`:

```python
def _match_breakdown(results: list[MatchResult]) -> dict:
    exact = [r for r in results if r.category != "soft_skills"]
    semantic = [r for r in results if r.category == "soft_skills"]
    return {
        "exact_matched": sum(1 for r in exact if r.status == "MATCH"),
        "exact_total": len(exact),
        "semantic_matched": sum(1 for r in semantic if r.status == "MATCH"),
        "semantic_total": len(semantic),
    }
```

### Radar (no new module)

Five axes, each a plain percentage derived from already-computed values,
assembled in `report.py`:

- `required_skills_pct`: existing `score.coverage_pct`
- `soft_skills_pct`: MATCH / total among `category == "soft_skills"` results (0-100; 100 if total is 0 — no soft skills required means nothing to penalize)
- `wording_accuracy_pct`: `100 - (near_miss_count / total_results * 100)` (100 if total_results is 0)
- `readability_pct`: `readability.score`, or `None` if not enough text
- `section_completeness_pct`: `filled` sections / 4 * 100

If `readability_pct` is `None`, the radar renders with 4 axes and the
frontend shows a note instead of guessing a 5th value.

## Report schema (additive)

```json
"metrics": {
  "readability": {
    "score": 78.4,
    "grade_level": 6.2,
    "avg_words_per_sentence": 14.3,
    "avg_word_length_chars": 5.1
  },
  "sections": [
    {"id": "contact", "found": true, "word_count": 12, "filled": false},
    {"id": "experience", "found": true, "word_count": 210, "filled": true},
    {"id": "education", "found": true, "word_count": 8, "filled": false},
    {"id": "skills", "found": false, "word_count": 0, "filled": false}
  ],
  "match_breakdown": {
    "exact_matched": 5, "exact_total": 6,
    "semantic_matched": 2, "semantic_total": 3
  },
  "radar": {
    "required_skills_pct": 88.9,
    "soft_skills_pct": 66.7,
    "wording_accuracy_pct": 90.0,
    "readability_pct": 78.4,
    "section_completeness_pct": 75.0
  }
}
```

Computed only over `resume_text` (not the posting). `build_report` gains
two new required parameters, `resume_text: str` and `entries:
list[SkillEntry]` (both already in scope at its one call site in
`pipeline.py`). This is a deliberate, visible signature change to
`report.py`'s public function, not a silent default — the three existing
calls in `tests/test_report.py` that construct a report from a bare
`RESULTS` fixture must be updated to also pass a `resume_text` and
`entries` fixture as part of this work, not left to break.

Existing fields (`results`, `score`, `engine_version`, `graph_version`,
`model_version`) are unchanged. `web/backend/app/enrichment.py`'s
`add_display_names` is untouched; section id → localized label mapping
happens in the frontend's existing i18n dictionaries, the same pattern
already used for skill category labels.

## Frontend (`web/frontend`)

No build step is introduced (the project is deliberately static/
no-bundler). New pieces:

- **Radar chart**: hand-rolled inline SVG pentagon, points computed in
  JS from the 5 (or 4, if readability is null) percentages. No charting
  library dependency.
- **New cards**: Keyword Coverage (exact/semantic split as two bars),
  Resume Section Analysis (one bar per section, greyed out if not
  found), Radar card. Existing Skill Match / matched-near miss-missing
  cards keep their current data, restyled to match the denser mockup
  layout.
- **Staggered reveal**: each dashboard card gets a `data-reveal`
  attribute. After `renderResults()` populates the DOM, a small helper
  loops over `[data-reveal]` elements and toggles
  `opacity-0 translate-y-2` → `opacity-100 translate-y-0` with a Tailwind
  transition class, staggered ~80ms apart via `setTimeout`.
- **PDF export**: `html2pdf.js` via CDN `<script>` tag (matches the
  existing Tailwind-via-CDN, no-build approach). "Download Report"
  button calls `html2pdf().from(resultsCard).save()`.
- i18n: new labels (section names, "not enough text to evaluate",
  "Exact"/"Semantic", radar axis labels, "Download Report") added to
  both `de` and `en` blocks in `TRANSLATIONS`, following the existing
  pattern.

## Testing

- `tests/test_readability.py`: ARI formula against hand-computed
  examples (a known short simple sentence vs. a long complex one),
  the `score=None` edge case for very short input, whitespace/character
  counting correctness.
- `tests/test_sections.py`: detects each section in German and English
  resume fixtures, correctly reports `found=False` for a missing
  section, `filled` threshold boundary (14 vs 15 words).
- `tests/test_report.py` (extend existing): `build_report` output
  contains a well-formed `metrics` key with all four sub-keys.
- `tests/test_pipeline.py` (extend existing): `run_pipeline` end-to-end
  output includes `metrics.sections` with all 4 ids present for a
  realistic multi-section resume fixture.
- Frontend: manual browser verification only, consistent with the
  project's existing testing approach (no frontend test suite currently
  exists; `ci.yml` only runs Python tests).

## Non-goals / explicitly rejected

- No syllable-based, per-language readability formula (Flesch-Kincaid/
  Amstad) — rejected in favor of the simpler, single, language-neutral
  ARI formula per explicit decision during design.
- No fabricated "Format & ATS Compliance" or "Content Structure" radar
  axes from the reference mockup — replaced with the 5 real axes above.
- No server-side PDF rendering — client-side snapshot only.
