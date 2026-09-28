# Open-Vocabulary Requirement Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let pass the bot recognize job-posting requirements outside the curated skill catalog, so postings from any industry (not just AI/ML/security/cloud) produce grounded MATCH/NEAR_MISS/MISSING results.

**Architecture:** A new structural extractor (`normalizer.extract_open_requirements`) finds requirement bullet/comma lists under a requirement-style heading in the posting text, independent of any catalog. A new matcher (`matcher.match_open_requirements`) classifies each extracted phrase against the resume via the existing `Embedder`, deduplicated against whatever the curated catalog already claimed in the posting. The pipeline runs both layers and merges their results; the report and frontend gain one new field (`MatchResult.origin`) to tell them apart.

**Tech Stack:** Python (existing `passthebot` package), the existing local `sentence-transformers` `Embedder`, vanilla JS frontend (no build step, no test framework).

**Spec:** `docs/superpowers/specs/2026-09-28-open-vocabulary-matching-design.md`

## Global Constraints

- No LLM or generative extraction anywhere in this feature — only literal text spans from the posting, only real cosine-similarity scores. No fabricated metrics.
- The curated catalogs (`hard_skills.yaml`, `soft_skills.yaml`) are not replaced or modified by this plan; open extraction only fills gaps they don't cover.
- V1 open extraction only recognizes requirement lists that are structurally a bullet list or a comma-separated line under a requirement heading. Free-text/prose extraction (e.g. via NLP) is explicitly out of scope and documented as a known limitation, not attempted.
- `MatchResult.origin` defaults to `"curated"` so every existing call site and test that constructs a `MatchResult` without passing `origin` keeps working unchanged.
- No monetization, pricing, paywall, or account feature is part of this plan.
- A skill covered by both the curated catalog and an open requirements bullet in the same posting must be reported exactly once (curated wins).

## Review Focus

- A posting with no requirement heading at all: `extract_open_requirements` returns `[]` and must not change any existing curated-only report's shape. (Task 1)
- A requirements section written as ordinary prose (no bullets, no comma list): returns `[]` per the documented V1 limitation, not a silent wrong guess. (Task 1)
- A resume genuinely unrelated to an open requirement (e.g. an accounting resume against a "welding experience" requirement): must classify as MISSING, not a false MATCH from a superficially-similar embedding neighbor. (Task 3)
- A skill appearing in both the curated catalog and the open requirements list: reported exactly once, never twice. (Task 2)
- Mixed German-heading / English-requirement-item postings (common in Austrian postings that mix English tech terms into German prose): heading detection must still find the section via whole-word keyword match. (Task 1)

---

### Task 1: Open requirement extraction (`normalizer.py`)

**Files:**
- Modify: `src/passthebot/normalizer.py`
- Test: `tests/test_normalizer.py`

**Interfaces:**
- Consumes: nothing new (pure text processing, no catalog, no embedder).
- Produces:
  - `OpenRequirement` dataclass: `phrase: str`, `source_line: int`.
  - `extract_open_requirements(posting_text: str) -> list[OpenRequirement]`.
  - Both are imported by Task 2 (`matcher.py`) and Task 3 (`pipeline.py`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_normalizer.py`:

```python
from passthebot.normalizer import extract_open_requirements


def test_extracts_bullet_requirements_under_german_heading():
    text = (
        "Anforderungen\n"
        "- Schweisskenntnisse (MIG/MAG)\n"
        "- Fuehrerschein Klasse B\n"
        "- Teamfaehigkeit\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Schweisskenntnisse (MIG/MAG)", "Fuehrerschein Klasse B", "Teamfaehigkeit"]


def test_extracts_bullet_requirements_under_english_heading():
    text = (
        "Requirements\n"
        "* 3+ years of accounting experience\n"
        "* Proficiency in Excel\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["3+ years of accounting experience", "Proficiency in Excel"]


def test_extracts_comma_separated_requirements_without_bullets():
    text = "Requirements\nPython, SQL, Excel"
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Python", "SQL", "Excel"]


def test_returns_empty_list_when_no_requirement_heading_present():
    text = "We are a great company that values people and growth."
    result = extract_open_requirements(text)
    assert result == []


def test_returns_empty_list_for_prose_only_requirements_section():
    text = (
        "Requirements\n"
        "We are looking for someone with strong accounting experience "
        "and a good command of Excel who can work independently."
    )
    result = extract_open_requirements(text)
    assert result == []


def test_multiple_requirement_headings_each_contribute_items():
    text = (
        "Must-have\n"
        "- Python\n"
        "- SQL\n"
        "\n"
        "Nice-to-have\n"
        "- Docker\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Python", "SQL", "Docker"]


def test_non_tech_industry_posting_bullets_extracted():
    text = (
        "Ihr Profil\n"
        "- Abgeschlossene Ausbildung als Elektriker\n"
        "- Erfahrung mit Schaltschrankbau\n"
        "- Fuehrerschein Klasse B\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == [
        "Abgeschlossene Ausbildung als Elektriker",
        "Erfahrung mit Schaltschrankbau",
        "Fuehrerschein Klasse B",
    ]


def test_german_heading_with_english_requirement_items_detected():
    text = (
        "Ihr Profil\n"
        "- Strong communication skills\n"
        "- Project management experience\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Strong communication skills", "Project management experience"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_normalizer.py -k open_requirement -v`
Expected: FAIL with `ImportError` / `cannot import name 'extract_open_requirements'`.

- [ ] **Step 3: Implement `extract_open_requirements` in `normalizer.py`**

Add near the top of `src/passthebot/normalizer.py` (after the existing imports, `from dataclasses import dataclass` is already imported):

```python
REQUIREMENT_HEADING_KEYWORDS: set[str] = {
    "anforderungen", "ihr profil", "profil", "qualifikationen",
    "voraussetzungen", "must-have", "must haves", "nice-to-have",
    "requirements", "qualifications", "what you'll need",
    "what we're looking for", "your profile",
}

_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


@dataclass
class OpenRequirement:
    phrase: str
    source_line: int


def _normalize_heading_line(line: str) -> str:
    return line.strip().strip(":-–—").strip().lower()


def _is_requirement_heading(normalized: str) -> bool:
    if not normalized or len(normalized.split()) > 6:
        return False
    return any(
        re.search(rf"(?<![a-zäöü]){re.escape(kw)}(?![a-zäöü])", normalized)
        for kw in REQUIREMENT_HEADING_KEYWORDS
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
    candidate phrase. If a heading's body has no bullets but a line
    contains commas, that line is split on commas into one candidate
    phrase per item instead.

    Known V1 limitation: a requirements section written as ordinary
    prose sentences (no bullets, no comma anywhere in the body) yields
    no candidate phrases. Free-text extraction (e.g. via NLP/POS
    tagging) is deferred to a future spec, not silently attempted here
    -- matching this project's existing pattern of documenting V1
    heuristic limits (see matcher.py's near-miss docstring, sections.py's
    heading-only-on-own-line limitation).
    """
    lines = posting_text.splitlines()
    heading_indices = [
        idx for idx, line in enumerate(lines)
        if _is_requirement_heading(_normalize_heading_line(line))
    ]
    if not heading_indices:
        return []

    requirements: list[OpenRequirement] = []
    for i, start_idx in enumerate(heading_indices):
        end_idx = heading_indices[i + 1] if i + 1 < len(heading_indices) else len(lines)
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
                requirements.extend(
                    OpenRequirement(phrase=item.strip().strip("."), source_line=idx)
                    for item in line.split(",")
                    if item.strip().strip(".")
                )
    return requirements
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_normalizer.py -v`
Expected: all PASS, including the pre-existing `extract_discrete_keywords` tests (unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/normalizer.py tests/test_normalizer.py
git commit -m "feat: extract open-vocabulary requirements from job postings"
```

---

### Task 2: Open requirement matching (`matcher.py`)

**Files:**
- Modify: `src/passthebot/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `OpenRequirement` and `split_sentences` from `passthebot.normalizer` (Task 1); `normalize_string` from `passthebot.validate_graph`; an `embedder` object with a `best_match(text: str, phrases: list[str]) -> tuple[str, float]` method (existing `Embedder` contract, already used by `normalizer.extract_soft_skills`).
- Produces:
  - `MatchResult` gains a new field `origin: Literal["curated", "open"] = "curated"`.
  - `match_open_requirements(open_requirements: list[OpenRequirement], resume_text: str, embedder, claimed_spans: set[str], match_threshold: float = 0.48, near_miss_threshold: float = 0.35) -> list[MatchResult]`.
  - Both are consumed by Task 3 (`pipeline.py`, `report.py`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_matcher.py` (extend the existing imports at the top: `from passthebot.normalizer import ExtractedKeyword, OpenRequirement`):

```python
from passthebot.matcher import match_open_requirements


class _StubEmbedder:
    """Returns a fixed score per requirement phrase, looked up by the
    phrase's own text, so tests can pin exact MATCH/NEAR_MISS/MISSING
    classification without loading the real sentence-transformers model."""

    def __init__(self, scores: dict[str, float]):
        self._scores = scores

    def best_match(self, text: str, phrases: list[str]):
        return phrases[0], self._scores.get(text, 0.0)


def test_open_requirement_above_match_threshold_is_match():
    reqs = [OpenRequirement(phrase="Python", source_line=1)]
    embedder = _StubEmbedder({"Python": 0.9})
    results = match_open_requirements(reqs, "Experienced Python developer.", embedder, claimed_spans=set())
    assert results[0].status == "MATCH"
    assert results[0].origin == "open"
    assert results[0].id == "Python"


def test_open_requirement_between_thresholds_is_near_miss():
    reqs = [OpenRequirement(phrase="Schweissen", source_line=1)]
    embedder = _StubEmbedder({"Schweissen": 0.40})
    results = match_open_requirements(reqs, "Some resume text.", embedder, claimed_spans=set())
    assert results[0].status == "NEAR_MISS"


def test_open_requirement_below_near_miss_threshold_is_missing():
    reqs = [OpenRequirement(phrase="Schweissen", source_line=1)]
    embedder = _StubEmbedder({"Schweissen": 0.1})
    results = match_open_requirements(reqs, "Some resume text.", embedder, claimed_spans=set())
    assert results[0].status == "MISSING"
    assert results[0].found_text is None


def test_open_requirement_already_claimed_by_curated_match_is_skipped():
    reqs = [OpenRequirement(phrase="Python", source_line=1)]
    embedder = _StubEmbedder({"Python": 0.9})
    results = match_open_requirements(
        reqs, "Experienced Python developer.", embedder, claimed_spans={"python"}
    )
    assert results == []


def test_duplicate_open_requirement_phrases_collapse_to_one_result():
    reqs = [
        OpenRequirement(phrase="Python", source_line=1),
        OpenRequirement(phrase="python", source_line=5),
    ]
    embedder = _StubEmbedder({"Python": 0.9, "python": 0.9})
    results = match_open_requirements(reqs, "Experienced Python developer.", embedder, claimed_spans=set())
    assert len(results) == 1


def test_default_origin_is_curated_for_existing_call_sites():
    results = match(POSTING, [], required_ids={"python"})
    assert all(r.origin == "curated" for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_matcher.py -k open_requirement -v`
Expected: FAIL with `ImportError` / `cannot import name 'match_open_requirements'`.

- [ ] **Step 3: Add the `origin` field and `match_open_requirements` to `matcher.py`**

Extend the existing imports at the top of `src/passthebot/matcher.py`:

```python
from passthebot.normalizer import ExtractedKeyword, OpenRequirement, split_sentences
from passthebot.validate_graph import normalize_string
```

Modify the existing `MatchResult` dataclass by adding one field at the end:

```python
@dataclass
class MatchResult:
    id: str
    category: str
    status: Status
    required: bool
    found_text: str | None = None
    suggested_alias: str | None = None
    confidence: float | None = None
    origin: Literal["curated", "open"] = "curated"
```

Add, after `enrich_near_misses`:

```python
def match_open_requirements(
    open_requirements: list[OpenRequirement],
    resume_text: str,
    embedder,
    claimed_spans: set[str],
    match_threshold: float = 0.48,
    near_miss_threshold: float = 0.35,
) -> list[MatchResult]:
    """Classify each open-vocabulary requirement phrase (from
    normalizer.extract_open_requirements, independent of any curated
    skill catalog) against the resume text by embedding similarity,
    using the same Embedder.best_match mechanism as
    normalizer.extract_soft_skills -- here with the roles reversed: the
    open requirement phrase plays the role of the "text being scored"
    and the resume's own sentences play the role of the candidate
    phrases it's compared against, so the returned best match is the
    single resume sentence closest to this requirement.

    claimed_spans holds the normalized (via validate_graph.normalize_string)
    matched_text of every curated posting-side match already found for
    this posting; an open phrase whose normalized text is already in
    claimed_spans is skipped entirely, so a skill covered by both the
    curated catalog and an open requirements bullet in the same posting
    is reported exactly once (the curated match wins). Duplicate open
    phrases within the same posting collapse to a single result the
    same way.

    Returned MatchResult.id is the requirement phrase's own literal text
    (there is no canonical id for an open phrase); origin is "open" so
    callers (report.py, the frontend) can distinguish these from
    curated, exact-alias matches without re-deriving it from confidence
    or category.
    """
    sentences = split_sentences(resume_text)
    if not sentences:
        sentences = [resume_text]

    results: list[MatchResult] = []
    seen: set[str] = set()
    for req in open_requirements:
        key = normalize_string(req.phrase)
        if not key or key in claimed_spans or key in seen:
            continue
        seen.add(key)

        best_sentence, score = embedder.best_match(req.phrase, sentences)
        if score >= match_threshold:
            status: Status = "MATCH"
        elif score >= near_miss_threshold:
            status = "NEAR_MISS"
        else:
            status = "MISSING"

        results.append(
            MatchResult(
                id=req.phrase,
                category="open_requirements",
                status=status,
                required=False,
                found_text=best_sentence if status != "MISSING" else None,
                confidence=score,
                origin="open",
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_matcher.py -v`
Expected: all PASS, including every pre-existing `matcher.py` test (unchanged — the new `origin` field's default keeps them green).

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/matcher.py tests/test_matcher.py
git commit -m "feat: classify open-vocabulary requirements by embedding similarity"
```

---

### Task 3: Pipeline wiring and report aggregation fix

**Files:**
- Modify: `src/passthebot/pipeline.py`
- Modify: `src/passthebot/report.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `extract_open_requirements` (Task 1), `match_open_requirements` (Task 2), `normalize_string` (existing, `passthebot.validate_graph`).
- Produces: `run_pipeline`'s returned report now includes open-vocabulary results in `report["results"]` (each with `"origin": "open"`); `report["metrics"]["match_breakdown"]` correctly counts `origin == "open"` results as semantic, never exact. No new public functions — this task is wiring plus one bugfix.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_run_pipeline_matches_open_requirements_outside_curated_catalog():
    """A posting requirement with no curated catalog entry (e.g. a skilled-
    trades skill) should still surface as a result via the open-vocabulary
    layer, not silently vanish."""
    posting = (
        "We need a skilled tradesperson.\n"
        "\n"
        "Requirements\n"
        "- Welding experience\n"
        "- Electrical wiring knowledge\n"
    )
    resume = "Five years of experience welding steel frames in an industrial workshop."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)
    open_results = {r["id"]: r for r in report["results"] if r["origin"] == "open"}
    assert set(open_results) == {"Welding experience", "Electrical wiring knowledge"}
    assert open_results["Welding experience"]["status"] in ("MATCH", "NEAR_MISS")


def test_run_pipeline_reports_open_requirement_as_missing_when_resume_is_unrelated():
    posting = "Requirements\n- Welding experience\n"
    resume = "Certified public accountant with ten years in corporate tax preparation."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)
    welding = next(r for r in report["results"] if r["id"] == "Welding experience")
    assert welding["status"] == "MISSING"


def test_run_pipeline_open_requirement_already_curated_is_not_duplicated():
    posting = "Requirements\n- Python\n- SQL\n"
    resume = "Experienced Python developer."
    report = run_pipeline(posting, resume, {"python"}, DATA_DIR, REPO_ROOT)
    python_results = [r for r in report["results"] if r["id"].lower() == "python"]
    assert len(python_results) == 1
    assert python_results[0]["origin"] == "curated"
```

Add to `tests/test_report.py`:

```python
def test_build_report_open_origin_results_count_as_semantic_not_exact():
    results_with_open = RESULTS + [
        MatchResult(
            id="Welding experience", category="open_requirements", status="MATCH",
            required=False, origin="open",
        ),
    ]
    report = build_report(results_with_open, RESUME_TEXT, graph_version="abc123")
    breakdown = report["metrics"]["match_breakdown"]
    assert breakdown["exact_total"] == 3
    assert breakdown["semantic_total"] == 1
    assert breakdown["semantic_matched"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py tests/test_report.py -k "open_requirement" -v`
Expected: FAIL — `test_run_pipeline_*` fail with `KeyError: 'origin'` or empty `open_results` (pipeline doesn't call the new functions yet); `test_build_report_open_origin_results_count_as_semantic_not_exact` fails on `exact_total == 4` (the bug this task fixes: `_match_breakdown` doesn't know about `origin` yet).

- [ ] **Step 3: Wire the open-vocabulary layer into `pipeline.py`**

Update the imports at the top of `src/passthebot/pipeline.py`:

```python
from passthebot.matcher import enrich_near_misses, match, match_open_requirements
from passthebot.normalizer import extract_discrete_keywords, extract_open_requirements, extract_soft_skills
from passthebot.validate_graph import normalize_string
```

In `run_pipeline`, replace:

```python
    results = match(posting_kw, resume_kw, required_ids)
    results = enrich_near_misses(results, resume_text, entries)
    return build_report(
```

with:

```python
    results = match(posting_kw, resume_kw, required_ids)
    results = enrich_near_misses(results, resume_text, entries)

    open_requirements = extract_open_requirements(posting_text)
    claimed_spans = {normalize_string(kw.matched_text) for kw in posting_kw}
    results = results + match_open_requirements(open_requirements, resume_text, embedder, claimed_spans)

    return build_report(
```

- [ ] **Step 4: Fix `_match_breakdown` in `report.py` to classify by origin**

In `src/passthebot/report.py`, replace:

```python
def _match_breakdown(results: list[MatchResult]) -> dict:
    """Split matched results into exact (discrete alias match) vs semantic
    (soft_skills embedding match). MatchResult.category already carries this
    distinction; this is pure aggregation, no new computation."""
    exact = [r for r in results if r.category != "soft_skills"]
    semantic = [r for r in results if r.category == "soft_skills"]
```

with:

```python
def _match_breakdown(results: list[MatchResult]) -> dict:
    """Split matched results into exact (curated discrete alias match) vs
    semantic (curated soft_skills embedding match, or any open-vocabulary
    match -- both are similarity-based, not exact-alias, matches).
    MatchResult.category/origin already carry this distinction; this is
    pure aggregation, no new computation."""
    exact = [r for r in results if r.category != "soft_skills" and r.origin != "open"]
    semantic = [r for r in results if r.category == "soft_skills" or r.origin == "open"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py tests/test_report.py -v`
Expected: all PASS, including every pre-existing test in both files (unchanged).

If `test_run_pipeline_matches_open_requirements_outside_curated_catalog`'s
`"Welding experience"` scores as `MISSING` instead of `MATCH`/`NEAR_MISS`
against the real embedding model, the real cosine similarity between
"Welding experience" and the welding resume sentence falls below
`near_miss_threshold` (0.35) — raise `near_miss_threshold` and/or
`match_threshold` in `match_open_requirements` (Task 2,
`src/passthebot/matcher.py`) just enough to pass on the observed score,
and re-run the full suite (`pytest`) to confirm the threshold change
doesn't flip any Task 2 unit test (those use a stub embedder with fixed
scores, so a small threshold adjustment is unlikely to affect them, but
confirm rather than assume). Do not weaken the assertion itself — the
posting's welding requirement and the resume's welding experience are
genuinely related, and the test exists to prove the classifier can tell.

- [ ] **Step 6: Run the full test suite**

Run: `pytest`
Expected: all tests PASS (this task touches shared pipeline/report code paths; confirm nothing outside this task's own tests regressed).

- [ ] **Step 7: Commit**

```bash
git add src/passthebot/pipeline.py src/passthebot/report.py tests/test_pipeline.py tests/test_report.py
git commit -m "feat: merge open-vocabulary matches into the pipeline and report"
```

---

### Task 4: Frontend marker for open-vocabulary matches

**Files:**
- Modify: `web/frontend/app.js`

**Interfaces:**
- Consumes: `report.results[].origin` (Task 3) — `"open"` or `"curated"`.
- Produces: no new interface; this is a leaf UI change.

- [ ] **Step 1: Add the tooltip translation keys**

In `web/frontend/app.js`, in the `de` block, immediately after the existing `foundLabel` line:

```javascript
    foundLabel: (text) => `gefunden: "${text}"`,
    openMatchTooltip: "Ähnlichkeitsbasiert erkannt, nicht aus dem kuratierten Katalog",
```

In the `en` block, immediately after the existing `foundLabel` line:

```javascript
    foundLabel: (text) => `found "${text}"`,
    openMatchTooltip: "Detected by similarity, not from the curated catalog",
```

- [ ] **Step 2: Replace `renderList` with a version that adds the marker safely**

`renderList` currently builds each list item with `li.innerHTML` for the
NEAR_MISS case and `li.textContent` for everything else. Adding the
open-match marker needs to happen without ever putting `item.display_name`
(which, for an open match, is the literal phrase text extracted from the
posting the user pasted in) into `innerHTML` unescaped. Replace the whole
function in `web/frontend/app.js`:

```javascript
function renderList(listEl, items, emptyText) {
  listEl.innerHTML = "";
  if (items.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    li.className = "text-gray-400 italic";
    listEl.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "bg-white/70 rounded px-3 py-2";

    const label = document.createElement("span");
    label.className = "font-medium";
    label.textContent = item.display_name;
    li.appendChild(label);

    if (item.origin === "open") {
      const marker = document.createElement("span");
      marker.className = "text-gray-400 ml-1";
      marker.title = t("openMatchTooltip");
      marker.textContent = "~";
      li.appendChild(marker);
    }

    if (item.status === "NEAR_MISS" && item.suggested_alias) {
      li.appendChild(document.createElement("br"));
      const foundSpan = document.createElement("span");
      foundSpan.className = "text-gray-500";
      foundSpan.textContent = t("foundLabel")(item.found_text);
      li.appendChild(foundSpan);
    }

    listEl.appendChild(li);
  }
}
```

- [ ] **Step 3: Verify locally against the real backend**

The frontend has no build step and no JS test framework (static
`app.js`, Tailwind via CDN) — verification is manual, against a locally
running backend, since `app.js` hardcodes the production API URL and the
backend's Task 1-3 changes are not deployed yet.

In one terminal, run the backend locally:

```bash
cd web/backend && uvicorn app.main:app --reload --port 8000
```

In `web/frontend/app.js`, temporarily change line 1 from:

```javascript
const API_BASE_URL = "https://passthebot-api.fly.dev";
```

to:

```javascript
const API_BASE_URL = "http://127.0.0.1:8000";
```

In a second terminal, serve the frontend:

```bash
cd web/frontend && python3 -m http.server 8080
```

Open `http://127.0.0.1:8080` in a browser. Paste this posting:

```
Requirements
- Welding experience
- Python
```

And this resume text (as a plain-text file uploaded, or reuse any PDF/DOCX
fixture containing this text):

```
Five years of experience welding steel frames. Experienced Python developer.
```

Submit the check. Confirm: the "Python" match shows no marker (it's
curated), the "Welding experience" match shows a small "~" next to it,
and hovering it shows the tooltip text. Confirm no browser console errors.

Revert the temporary `API_BASE_URL` change back to
`"https://passthebot-api.fly.dev"` before committing — this edit exists
only for local verification.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app.js
git commit -m "feat: mark open-vocabulary matches in the results list"
```
