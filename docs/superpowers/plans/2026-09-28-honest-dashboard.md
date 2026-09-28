# Honest Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend passthebot's report with transparently-computed metrics (readability, resume section detection, exact/semantic match breakdown, a 5-axis radar) and redesign the results UI into a richer dashboard with staggered reveal animation and a client-side PDF export.

**Architecture:** Two new pure engine modules (`readability.py`, `sections.py`) plus an aggregation step in `report.py` add a new additive `metrics` field to the existing report JSON. The frontend (`web/frontend`, no build step) grows three new result cards fed by `metrics`, a hand-rolled inline-SVG radar chart, a staggered CSS reveal, and `html2pdf.js` (CDN) for PDF export.

**Tech Stack:** Python 3.11, pytest, FastAPI (untouched by this plan), vanilla JS + Tailwind CDN (frontend, no bundler), html2pdf.js (new CDN dependency).

**Spec:** `docs/superpowers/specs/2026-09-28-honest-dashboard-design.md`

## Global Constraints

- No fabricated metrics — every new number must be computed from `posting_text`/`resume_text`, never a hardcoded or guessed value.
- No build step introduced in `web/frontend` — Tailwind stays CDN-loaded, JS stays a single `app.js`, any new frontend dependency (html2pdf.js) is a CDN `<script>` tag.
- Existing report fields (`results`, `score`, `engine_version`, `graph_version`, `model_version`) are unchanged; `metrics` is purely additive.
- `build_report`'s new `resume_text` parameter is a deliberate, visible signature change — all existing call sites and tests must be updated, not defaulted around.
- All new engine code is pure (no I/O, no network), matching the existing style of `normalizer.py`/`matcher.py`/`requirement.py`.
- i18n: every new user-facing string gets both a `de` and an `en` entry in `TRANSLATIONS` in `web/frontend/app.js`, following the existing key-naming pattern.

## Review Focus

- A resume whose extracted text has no recognizable section headings (e.g. a scanned/garbled PDF) — all four `sections` entries must come back `found: false`, and the radar/section-analysis UI must render a clean "0%" state, not crash or show `undefined`.
- A very short resume (fewer than 5 words or fewer than 2 sentences) — `readability.score` must be `None`/`null`, not a fabricated 0 or 100, and the radar must render with 4 axes (skip the null one) without breaking the polygon math.
- A posting/resume pair with zero `soft_skills`-category results — `soft_skills_pct` must be `100.0`, not a division-by-zero error or `NaN`.
- A results list with zero entries — `wording_accuracy_pct` must default to `100.0`, not divide by zero (this can't happen via the real pipeline today since posting/resume text is required non-empty, but `build_report` is a public function other tests call directly with arbitrary fixtures, so it must not crash on an empty list).
- Section heading detection must be case-insensitive and tolerant of trailing punctuation (e.g. "AUSBILDUNG:", "Skills -") since real resumes format headings inconsistently.

---

## Task 1: Readability metric (`readability.py`)

**Files:**
- Create: `src/passthebot/readability.py`
- Test: `tests/test_readability.py`

**Interfaces:**
- Consumes: `passthebot.normalizer.split_sentences(text: str) -> list[str]` (existing).
- Produces: `passthebot.readability.compute_readability(text: str) -> ReadabilityResult`, where `ReadabilityResult` has fields `score: float | None`, `grade_level: float | None`, `avg_words_per_sentence: float`, `avg_word_length_chars: float`. Consumed by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_readability.py`:

```python
from passthebot.readability import compute_readability


def test_short_simple_sentences_score_near_the_maximum():
    text = "The cat sat on the mat. It was warm and cozy inside the house today."
    result = compute_readability(text)
    assert result.score == 100.0
    assert result.avg_words_per_sentence == 7.5


def test_long_complex_sentences_score_near_the_minimum():
    text = (
        "Notwithstanding the aforementioned circumstances, the multifaceted "
        "implementation necessitated comprehensive reconsideration of the "
        "previously established methodological framework. Consequently, "
        "stakeholders recommended substantial reorganization of the "
        "interdisciplinary collaborative infrastructure."
    )
    result = compute_readability(text)
    assert result.score == 0.0
    assert result.grade_level > 20


def test_too_short_text_returns_none_score_but_keeps_raw_counts():
    result = compute_readability("Python.")
    assert result.score is None
    assert result.grade_level is None
    assert result.avg_words_per_sentence == 1.0
    assert result.avg_word_length_chars == 6.0


def test_punctuation_attached_to_words_does_not_inflate_length():
    # "cat," and "cat" must count as the same length for this metric.
    result = compute_readability("The cat, the dog, and the bird all played. They ran around the yard together.")
    assert result.avg_word_length_chars < 4.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_readability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.readability'`

- [ ] **Step 3: Write the implementation**

Create `src/passthebot/readability.py`:

```python
"""Readability metric for resume text, per the honest-dashboard design spec.

Uses the Automated Readability Index (ARI), a real, named formula that
needs no syllable-counting step, so it works the same way for German and
English text without a per-language heuristic:

    ARI = 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43

ARI produces a US school grade-level number. For display, that grade
level is linearly rescaled to a 0-100 "readability score" (grade 0 -> 100,
grade 20 -> 0, clamped): score = clamp(100 - grade_level * 5, 0, 100).
This is a display rescale of a real formula, not an invented multi-factor
score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from passthebot.normalizer import split_sentences

MIN_WORDS_FOR_SCORE = 5
MIN_SENTENCES_FOR_SCORE = 2

_NON_WORD_CHARS = re.compile(r"[^\w]", re.UNICODE)


@dataclass
class ReadabilityResult:
    score: float | None
    grade_level: float | None
    avg_words_per_sentence: float
    avg_word_length_chars: float


def _word_length(word: str) -> int:
    """Character length of a word with surrounding punctuation stripped,
    so a trailing comma or period doesn't inflate the average word length."""
    return len(_NON_WORD_CHARS.sub("", word))


def compute_readability(text: str) -> ReadabilityResult:
    sentences = split_sentences(text)
    words = text.split()
    word_count = len(words)
    sentence_count = len(sentences)

    avg_words_per_sentence = round(word_count / sentence_count, 1) if sentence_count else 0.0
    char_count = sum(_word_length(w) for w in words)
    avg_word_length_chars = round(char_count / word_count, 1) if word_count else 0.0

    if word_count < MIN_WORDS_FOR_SCORE or sentence_count < MIN_SENTENCES_FOR_SCORE:
        return ReadabilityResult(
            score=None,
            grade_level=None,
            avg_words_per_sentence=avg_words_per_sentence,
            avg_word_length_chars=avg_word_length_chars,
        )

    grade_level = 4.71 * avg_word_length_chars + 0.5 * avg_words_per_sentence - 21.43
    score = max(0.0, min(100.0, 100 - grade_level * 5))

    return ReadabilityResult(
        score=round(score, 1),
        grade_level=round(grade_level, 1),
        avg_words_per_sentence=avg_words_per_sentence,
        avg_word_length_chars=avg_word_length_chars,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_readability.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/readability.py tests/test_readability.py
git commit -m "feat: add readability metric (Automated Readability Index)"
```

---

## Task 2: Resume section detection (`sections.py`)

**Files:**
- Create: `src/passthebot/sections.py`
- Test: `tests/test_sections.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure text processing).
- Produces: `passthebot.sections.detect_sections(resume_text: str) -> list[SectionResult]`, where `SectionResult` has fields `id: str`, `found: bool`, `word_count: int`, `filled: bool`. Always returns exactly 4 results, in the fixed order `["contact", "experience", "education", "skills"]`. Consumed by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sections.py`:

```python
from passthebot.sections import detect_sections

DE_RESUME_ALL_SECTIONS = """Kontakt
Max Mustermann, max@example.com, +43 000 000000

Erfahrung
Fünf Jahre Erfahrung als Backend-Entwickler bei einer großen Firma mit Fokus auf Python und Datenbanken und Cloud-Infrastruktur und Teamführung und Projektmanagement.

Ausbildung
Bachelor in Informatik von der Universität Wien abgeschlossen im Jahr zweitausendachtzehn mit Auszeichnung und Schwerpunkt Softwaretechnik.

Skills
Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, Kommunikation, Problemlösung, Zeitmanagement, Flexibilität, Lernbereitschaft, Eigeninitiative, Zuverlässigkeit
"""

EN_RESUME_ALL_SECTIONS = """Contact
Jane Doe, jane@example.com

Experience
Five years of experience as a backend developer at a large company focused on Python and databases and cloud infrastructure and team leadership and project management.

Education
Bachelor of Science in Computer Science from State University completed with honors and a focus on software engineering practices.

Skills
Python, Docker, Kubernetes, AWS, PostgreSQL
"""

DE_RESUME_MISSING_SKILLS = """Kontakt
Max Mustermann, max@example.com

Erfahrung
Fünf Jahre Erfahrung als Backend-Entwickler bei einer großen Firma mit Fokus auf Python und Datenbanken.

Ausbildung
Bachelor in Informatik von der Universität Wien.
"""


def test_detects_all_four_sections_in_german_resume():
    results = detect_sections(DE_RESUME_ALL_SECTIONS)
    by_id = {r.id: r for r in results}
    assert set(by_id) == {"contact", "experience", "education", "skills"}
    assert by_id["contact"].found is True
    assert by_id["experience"].found is True
    assert by_id["education"].found is True
    assert by_id["skills"].found is True


def test_detects_all_four_sections_in_english_resume():
    results = detect_sections(EN_RESUME_ALL_SECTIONS)
    assert all(r.found for r in results)


def test_missing_section_reports_found_false_with_zero_word_count():
    results = detect_sections(DE_RESUME_MISSING_SKILLS)
    by_id = {r.id: r for r in results}
    assert by_id["skills"].found is False
    assert by_id["skills"].word_count == 0
    assert by_id["skills"].filled is False


def test_result_order_is_always_contact_experience_education_skills():
    results = detect_sections(DE_RESUME_MISSING_SKILLS)
    assert [r.id for r in results] == ["contact", "experience", "education", "skills"]


def test_section_with_15_words_is_filled():
    # The "Skills" body below has exactly 15 comma-separated items.
    text = (
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, "
        "Kommunikation, Problemloesung, Zeitmanagement, Flexibilitaet, "
        "Lernbereitschaft, Eigeninitiative, Zuverlaessigkeit"
    )
    results = detect_sections(text)
    skills = next(r for r in results if r.id == "skills")
    assert skills.word_count == 15
    assert skills.filled is True


def test_section_with_14_words_is_not_filled():
    text = (
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, "
        "Kommunikation, Problemloesung, Zeitmanagement, Flexibilitaet, "
        "Lernbereitschaft, Eigeninitiative"
    )
    results = detect_sections(text)
    skills = next(r for r in results if r.id == "skills")
    assert skills.word_count == 14
    assert skills.filled is False


def test_heading_detection_is_case_insensitive_and_tolerates_punctuation():
    text = "AUSBILDUNG:\nBachelor in Informatik von der Universitaet Wien."
    results = detect_sections(text)
    education = next(r for r in results if r.id == "education")
    assert education.found is True


def test_resume_with_no_recognizable_headings_returns_all_not_found():
    text = "Just a paragraph of text with no section headings anywhere in it at all."
    results = detect_sections(text)
    assert all(not r.found for r in results)
    assert all(r.word_count == 0 for r in results)
    assert all(not r.filled for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sections.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.sections'`

- [ ] **Step 3: Write the implementation**

Create `src/passthebot/sections.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sections.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/sections.py tests/test_sections.py
git commit -m "feat: add resume section detection"
```

---

## Task 3: Wire metrics into `report.py`

**Files:**
- Modify: `src/passthebot/report.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: `compute_readability` (Task 1), `detect_sections` (Task 2), `passthebot.matcher.MatchResult` (existing, has `.category`, `.status`, `.required`).
- Produces: `build_report(results, resume_text, graph_version, engine_version="0.1.0", model_version="unknown") -> dict` now with a new signature (added required `resume_text: str` as the second positional parameter) and a new `"metrics"` key in its return dict, shaped exactly as in the spec's "Report schema" section. Consumed by Task 4.

- [ ] **Step 1: Update existing tests for the new required parameter and write new failing tests**

Replace the full contents of `tests/test_report.py`:

```python
from pathlib import Path

from passthebot.matcher import MatchResult
from passthebot.report import build_report, get_graph_version

RESULTS = [
    MatchResult(id="python", category="languages", status="MATCH", required=True),
    MatchResult(id="docker", category="tools", status="MISSING", required=True),
    MatchResult(
        id="kubernetes", category="tools", status="NEAR_MISS", required=False,
        found_text="k8s", suggested_alias="Kubernetes", confidence=0.8,
    ),
]

RESUME_TEXT = (
    "Experience\n"
    "Five years of experience as a backend developer at a large company "
    "focused on Python and databases and cloud infrastructure and team leadership.\n"
    "\n"
    "Skills\n"
    "Python, Docker, Kubernetes"
)


def test_build_report_shape():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["engine_version"] == "0.1.0"
    assert report["graph_version"] == "abc123"
    assert report["model_version"] == "unknown"
    assert len(report["results"]) == 3


def test_build_report_includes_provided_model_version():
    report = build_report(
        RESULTS, RESUME_TEXT, graph_version="abc123", model_version="all-MiniLM-L6-v2"
    )
    assert report["model_version"] == "all-MiniLM-L6-v2"


def test_build_report_score_counts_only_required():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 1
    assert report["score"]["coverage_pct"] == 50.0


def test_build_report_includes_metrics_match_breakdown():
    results_with_soft_skill = RESULTS + [
        MatchResult(id="teamwork", category="soft_skills", status="MATCH", required=False),
    ]
    report = build_report(results_with_soft_skill, RESUME_TEXT, graph_version="abc123")
    breakdown = report["metrics"]["match_breakdown"]
    assert breakdown == {
        "exact_matched": 1,
        "exact_total": 3,
        "semantic_matched": 1,
        "semantic_total": 1,
    }


def test_build_report_includes_metrics_sections_and_readability():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    metrics = report["metrics"]
    section_ids = {s["id"] for s in metrics["sections"]}
    assert section_ids == {"contact", "experience", "education", "skills"}
    experience = next(s for s in metrics["sections"] if s["id"] == "experience")
    assert experience["found"] is True
    assert metrics["readability"]["score"] is not None


def test_build_report_radar_has_five_axes():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    radar = report["metrics"]["radar"]
    assert set(radar.keys()) == {
        "required_skills_pct",
        "soft_skills_pct",
        "wording_accuracy_pct",
        "readability_pct",
        "section_completeness_pct",
    }
    assert radar["required_skills_pct"] == 50.0


def test_build_report_radar_defaults_soft_skills_to_100_when_none_present():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["metrics"]["radar"]["soft_skills_pct"] == 100.0


def test_build_report_handles_empty_results_without_crashing():
    report = build_report([], RESUME_TEXT, graph_version="abc123")
    assert report["metrics"]["radar"]["wording_accuracy_pct"] == 100.0
    assert report["score"]["coverage_pct"] == 100.0


def test_get_graph_version_returns_a_git_hash_in_a_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    expected_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    version = get_graph_version(tmp_path)
    assert len(version) == 40
    assert version == expected_hash


def test_get_graph_version_returns_unknown_outside_git_repo(tmp_path):
    version = get_graph_version(tmp_path)
    assert version == "unknown"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: the three pre-existing tests now FAIL with a `TypeError` (missing `resume_text` argument doesn't apply here since the test file itself was just rewritten to pass it — instead expect FAIL because `build_report` doesn't yet accept `resume_text` or produce `"metrics"`), and the four new metrics tests FAIL with `KeyError: 'metrics'`.

- [ ] **Step 3: Write the implementation**

Replace the full contents of `src/passthebot/report.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from passthebot.matcher import MatchResult
from passthebot.readability import compute_readability
from passthebot.sections import SectionResult, detect_sections


def get_graph_version(repo_root: Path) -> str:
    """Return the current HEAD commit hash of the entire repository.

    This returns the repository-wide HEAD commit, not a hash scoped to any
    specific subdirectory (e.g. data/skills/). This is intentional: it captures
    both the skill data AND the matching-code version together for full
    reproducibility and auditability. Two reports with identical skill data but
    different matcher-code logic will have different graph_version values,
    preserving audit trail integrity.

    Returns 'unknown' if repo_root is not inside a git repository (e.g. a fresh
    checkout without history, or a non-git deployment) or if the git binary is
    not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _match_breakdown(results: list[MatchResult]) -> dict:
    """Split matched results into exact (discrete alias match) vs semantic
    (soft_skills embedding match). MatchResult.category already carries this
    distinction; this is pure aggregation, no new computation."""
    exact = [r for r in results if r.category != "soft_skills"]
    semantic = [r for r in results if r.category == "soft_skills"]
    return {
        "exact_matched": sum(1 for r in exact if r.status == "MATCH"),
        "exact_total": len(exact),
        "semantic_matched": sum(1 for r in semantic if r.status == "MATCH"),
        "semantic_total": len(semantic),
    }


def _build_radar(
    results: list[MatchResult],
    required_matched: int,
    required_total: int,
    readability_score: float | None,
    sections: list[SectionResult],
) -> dict:
    """Assemble the 5-axis radar from values already computed elsewhere.
    Every axis is a plain percentage a user could recompute by hand."""
    required_skills_pct = (
        round(100.0 * required_matched / required_total, 1) if required_total else 100.0
    )

    soft_skill_results = [r for r in results if r.category == "soft_skills"]
    soft_skills_pct = (
        round(100.0 * sum(1 for r in soft_skill_results if r.status == "MATCH") / len(soft_skill_results), 1)
        if soft_skill_results
        else 100.0
    )

    near_miss_count = sum(1 for r in results if r.status == "NEAR_MISS")
    wording_accuracy_pct = (
        round(100.0 - 100.0 * near_miss_count / len(results), 1) if results else 100.0
    )

    filled_sections = sum(1 for s in sections if s.filled)
    section_completeness_pct = (
        round(100.0 * filled_sections / len(sections), 1) if sections else 100.0
    )

    return {
        "required_skills_pct": required_skills_pct,
        "soft_skills_pct": soft_skills_pct,
        "wording_accuracy_pct": wording_accuracy_pct,
        "readability_pct": readability_score,
        "section_completeness_pct": section_completeness_pct,
    }


def build_report(
    results: list[MatchResult],
    resume_text: str,
    graph_version: str,
    engine_version: str = "0.1.0",
    model_version: str = "unknown",
) -> dict:
    required_results = [r for r in results if r.required]
    required_total = len(required_results)
    required_matched = sum(1 for r in required_results if r.status == "MATCH")
    coverage_pct = (
        round(100.0 * required_matched / required_total, 1) if required_total else 100.0
    )

    readability = compute_readability(resume_text)
    sections = detect_sections(resume_text)

    return {
        "engine_version": engine_version,
        "graph_version": graph_version,
        "model_version": model_version,
        "results": [asdict(r) for r in results],
        "score": {
            "required_matched": required_matched,
            "required_total": required_total,
            "coverage_pct": coverage_pct,
        },
        "metrics": {
            "readability": asdict(readability),
            "sections": [asdict(s) for s in sections],
            "match_breakdown": _match_breakdown(results),
            "radar": _build_radar(
                results, required_matched, required_total, readability.score, sections
            ),
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/report.py tests/test_report.py
git commit -m "feat: add metrics (readability, sections, match breakdown, radar) to build_report"
```

---

## Task 4: Wire `resume_text` through `pipeline.py`

**Files:**
- Modify: `src/passthebot/pipeline.py:68-72`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `build_report(results, resume_text, graph_version=..., model_version=...)` (Task 3's new signature).
- Produces: `run_pipeline(...) -> dict` whose return value now includes `report["metrics"]`. Consumed by Task 5's manual browser verification and by `web/backend/app/main.py` (unchanged, it already just forwards whatever `run_pipeline` returns).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py` (append at the end of the file):

```python
def test_run_pipeline_includes_metrics_with_all_sections_detected():
    resume_text = (
        "Contact\n"
        "jane@example.com\n"
        "\n"
        "Experience\n"
        "Five years of experience as a backend developer at a large company "
        "focused on Python and databases and cloud infrastructure and team leadership.\n"
        "\n"
        "Education\n"
        "Bachelor of Science in Computer Science from State University completed "
        "with honors and a focus on software engineering practices.\n"
        "\n"
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL"
    )
    report = run_pipeline(
        "Requires Python and Docker.", resume_text, {"python", "docker"}, DATA_DIR, REPO_ROOT
    )
    section_ids = {s["id"] for s in report["metrics"]["sections"]}
    assert section_ids == {"contact", "experience", "education", "skills"}
    assert all(s["found"] for s in report["metrics"]["sections"])
    assert report["metrics"]["readability"]["score"] is not None
    assert set(report["metrics"]["radar"].keys()) == {
        "required_skills_pct",
        "soft_skills_pct",
        "wording_accuracy_pct",
        "readability_pct",
        "section_completeness_pct",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline.py::test_run_pipeline_includes_metrics_with_all_sections_detected -v`
Expected: FAIL with `KeyError: 'metrics'` (pipeline.py still calls the old `build_report` signature)

- [ ] **Step 3: Update the implementation**

In `src/passthebot/pipeline.py`, replace the final `return build_report(...)` call (currently lines 68-72):

```python
    return build_report(
        results,
        resume_text,
        graph_version=get_graph_version(repo_root),
        model_version=getattr(embedder, "model_name", "unknown"),
    )
```

- [ ] **Step 4: Run all engine tests to verify they pass**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all tests, including the pre-existing pipeline/report/readability/sections tests)

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire resume_text through to build_report in run_pipeline"
```

---

## Task 5: Keyword Coverage card (exact vs semantic)

**Files:**
- Modify: `web/frontend/index.html` (insert after line 228, the `</div>` closing the matched/near-miss/missing grid, before line 230's `<div id="tips-section">`)
- Modify: `web/frontend/app.js` (add i18n keys to both `de`/`en` blocks; add DOM refs near line 165; extend `renderResults` after line ~391, right after the `countMissing.textContent = missing.length;` line)

**Interfaces:**
- Consumes: `report.metrics.match_breakdown` (Task 3/4's new report field): `{exact_matched, exact_total, semantic_matched, semantic_total}`.
- Produces: nothing new consumed by later tasks; this card is self-contained. Introduces DOM ids `exact-match-count`, `exact-match-bar`, `semantic-match-count`, `semantic-match-bar` that Task 9 (staggered reveal) will include via the wrapping `data-reveal` grid container, not individually.

- [ ] **Step 1: Add the HTML card**

In `web/frontend/index.html`, insert this new grid immediately after the matched/near-miss/missing grid's closing `</div>` (after `</div>` that closes the `grid md:grid-cols-3` block containing `matched-list`/`nearmiss-list`/`missing-list`, currently followed by a blank line and `<div id="tips-section">`):

```html
      <div class="grid md:grid-cols-3 gap-4 mb-8" data-reveal>
        <section class="bg-white border border-gray-200 rounded-xl p-4">
          <h3 class="font-semibold mb-3" data-i18n="keywordCoverageHeading"></h3>
          <div class="space-y-3 text-sm">
            <div>
              <div class="flex justify-between mb-1">
                <span data-i18n="exactMatchLabel"></span>
                <span id="exact-match-count"></span>
              </div>
              <div class="w-full bg-gray-100 rounded-full h-2">
                <div id="exact-match-bar" class="bg-green-600 h-2 rounded-full" style="width: 0%"></div>
              </div>
            </div>
            <div>
              <div class="flex justify-between mb-1">
                <span data-i18n="semanticMatchLabel"></span>
                <span id="semantic-match-count"></span>
              </div>
              <div class="w-full bg-gray-100 rounded-full h-2">
                <div id="semantic-match-bar" class="bg-blue-600 h-2 rounded-full" style="width: 0%"></div>
              </div>
            </div>
          </div>
        </section>
        <section class="bg-white border border-gray-200 rounded-xl p-4" id="section-analysis-card">
          <h3 class="font-semibold mb-3" data-i18n="sectionAnalysisHeading"></h3>
          <ul id="section-analysis-list" class="space-y-2 text-sm"></ul>
        </section>
        <section class="bg-white border border-gray-200 rounded-xl p-4" id="radar-card">
          <h3 class="font-semibold mb-3" data-i18n="radarHeading"></h3>
          <div id="radar-container" class="relative mx-auto" style="width: 200px; height: 200px;">
            <svg viewBox="0 0 200 200" width="200" height="200">
              <polygon id="radar-grid" points="" fill="#f3f4f6" stroke="#d1d5db" stroke-width="1"></polygon>
              <polygon id="radar-polygon" points="" fill="rgba(22,163,74,0.35)" stroke="#16a34a" stroke-width="2"></polygon>
            </svg>
            <div id="radar-labels" class="absolute inset-0 pointer-events-none"></div>
          </div>
        </section>
      </div>
```

(The `section-analysis-list` and `radar-*` elements are also created here, in the same grid, since all three cards are one visual row; Tasks 6 and 7 fill in their JS rendering logic. Leaving unused-but-present elements between tasks is fine since nothing consumes them yet.)

- [ ] **Step 2: Add i18n keys**

In `web/frontend/app.js`, inside the `de:` block (after the existing `privacyNote:` entry, before the block's closing `},`), add:

```javascript
    keywordCoverageHeading: "Keyword-Abdeckung",
    exactMatchLabel: "Exakte Treffer",
    semanticMatchLabel: "Sinngemäße Treffer",
```

Inside the `en:` block (after its `privacyNote:` entry, before that block's closing `},`), add:

```javascript
    keywordCoverageHeading: "Keyword Coverage",
    exactMatchLabel: "Exact Matches",
    semanticMatchLabel: "Semantic Matches",
```

- [ ] **Step 3: Add DOM refs**

In `web/frontend/app.js`, after the existing `const tipsList = document.getElementById("tips-list");` line, add:

```javascript
const exactMatchCount = document.getElementById("exact-match-count");
const exactMatchBar = document.getElementById("exact-match-bar");
const semanticMatchCount = document.getElementById("semantic-match-count");
const semanticMatchBar = document.getElementById("semantic-match-bar");
```

- [ ] **Step 4: Render the card in `renderResults`**

In `web/frontend/app.js`, inside `renderResults(report, ...)`, immediately after the existing line `countMissing.textContent = missing.length;`, add:

```javascript
  const breakdown = report.metrics.match_breakdown;
  const exactPct = breakdown.exact_total ? Math.round((breakdown.exact_matched / breakdown.exact_total) * 100) : 0;
  const semanticPct = breakdown.semantic_total ? Math.round((breakdown.semantic_matched / breakdown.semantic_total) * 100) : 0;
  exactMatchCount.textContent = `${breakdown.exact_matched} / ${breakdown.exact_total}`;
  exactMatchBar.style.width = `${exactPct}%`;
  semanticMatchCount.textContent = `${breakdown.semantic_matched} / ${breakdown.semantic_total}`;
  semanticMatchBar.style.width = `${semanticPct}%`;
```

- [ ] **Step 5: Manual verification**

Start a local server and check the card renders with real percentages:

```bash
cd web/frontend && python3 -m http.server 5500
```

Open `http://localhost:5500`, upload a resume PDF, paste a posting with at least one required skill, submit. Confirm the new "Keyword Coverage" / "Keyword-Abdeckung" card shows non-empty `N / M` counts and the two bars have non-zero width matching those counts. Also toggle the DE/EN language switch and confirm both new labels translate.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/index.html web/frontend/app.js
git commit -m "feat: add keyword coverage card (exact vs semantic matches)"
```

---

## Task 6: Resume Section Analysis card

**Files:**
- Modify: `web/frontend/app.js`

**Interfaces:**
- Consumes: `report.metrics.sections` (list of `{id, found, word_count, filled}`), the `section-analysis-list` DOM element created in Task 5's HTML.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Add i18n keys**

In the `de:` block, after the keys added in Task 5, add:

```javascript
    sectionAnalysisHeading: "Abschnitts-Analyse",
    sectionNames: {
      contact: "Kontakt",
      experience: "Erfahrung",
      education: "Ausbildung",
      skills: "Skills",
    },
    sectionFound: "vorhanden",
    sectionMissing: "nicht gefunden",
```

In the `en:` block, after the keys added in Task 5, add:

```javascript
    sectionAnalysisHeading: "Resume Section Analysis",
    sectionNames: {
      contact: "Contact",
      experience: "Experience",
      education: "Education",
      skills: "Skills",
    },
    sectionFound: "found",
    sectionMissing: "not found",
```

- [ ] **Step 2: Add DOM ref**

In `web/frontend/app.js`, alongside the refs added in Task 5, add:

```javascript
const sectionAnalysisList = document.getElementById("section-analysis-list");
```

- [ ] **Step 3: Render the card in `renderResults`**

Immediately after the match-breakdown block added in Task 5, add:

```javascript
  sectionAnalysisList.innerHTML = "";
  for (const section of report.metrics.sections) {
    const li = document.createElement("li");
    const name = t("sectionNames")[section.id] || section.id;
    if (!section.found) {
      li.className = "flex justify-between text-gray-400";
      li.innerHTML = `<span>${name}</span><span>${t("sectionMissing")}</span>`;
    } else {
      const pct = Math.min(100, Math.round((section.word_count / 15) * 100));
      li.className = "space-y-1";
      li.innerHTML = `
        <div class="flex justify-between"><span>${name}</span><span>${section.word_count} ${section.filled ? "✓" : ""}</span></div>
        <div class="w-full bg-gray-100 rounded-full h-1.5"><div class="bg-green-600 h-1.5 rounded-full" style="width: ${pct}%"></div></div>
      `;
    }
    sectionAnalysisList.appendChild(li);
  }
```

- [ ] **Step 4: Manual verification**

Reload the local server from Task 5, submit the same test resume. Confirm the "Resume Section Analysis" / "Abschnitts-Analyse" card lists all four sections, shows a filled green bar for sections with enough content, and shows "not found" / "nicht gefunden" in grey for any section your test resume doesn't include (e.g. omit a "Contact" heading from the test resume text file and confirm it shows as missing).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app.js
git commit -m "feat: add resume section analysis card"
```

---

## Task 7: Honest radar chart

**Files:**
- Modify: `web/frontend/app.js`

**Interfaces:**
- Consumes: `report.metrics.radar` (5 keys, `readability_pct` possibly `null`), the `radar-polygon`/`radar-grid`/`radar-labels` DOM elements created in Task 5's HTML.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Add i18n keys**

In the `de:` block, add:

```javascript
    radarHeading: "ATS-Radar",
    radarRequiredSkills: "Pflicht-Skills",
    radarSoftSkills: "Soft Skills",
    radarWordingAccuracy: "Formulierungsgenauigkeit",
    radarReadability: "Lesbarkeit",
    radarSectionCompleteness: "Abschnitts-Vollständigkeit",
```

In the `en:` block, add:

```javascript
    radarHeading: "ATS Radar",
    radarRequiredSkills: "Required Skills",
    radarSoftSkills: "Soft Skills",
    radarWordingAccuracy: "Wording Accuracy",
    radarReadability: "Readability",
    radarSectionCompleteness: "Section Completeness",
```

- [ ] **Step 2: Add DOM refs and the radar axis config**

In `web/frontend/app.js`, alongside the other refs, add:

```javascript
const radarPolygon = document.getElementById("radar-polygon");
const radarGrid = document.getElementById("radar-grid");
const radarLabelsEl = document.getElementById("radar-labels");

const RADAR_AXES = [
  { key: "required_skills_pct", labelKey: "radarRequiredSkills" },
  { key: "soft_skills_pct", labelKey: "radarSoftSkills" },
  { key: "wording_accuracy_pct", labelKey: "radarWordingAccuracy" },
  { key: "readability_pct", labelKey: "radarReadability" },
  { key: "section_completeness_pct", labelKey: "radarSectionCompleteness" },
];
```

- [ ] **Step 3: Write the render function**

Add this function near `renderResults` (e.g. directly above it):

```javascript
function renderRadar(radar) {
  const axes = RADAR_AXES.filter((a) => radar[a.key] !== null && radar[a.key] !== undefined);
  const centerX = 100;
  const centerY = 100;
  const maxRadius = 70;
  const angleStep = (2 * Math.PI) / axes.length;

  function pointFor(index, valuePct) {
    const angle = -Math.PI / 2 + index * angleStep;
    const r = (valuePct / 100) * maxRadius;
    return [centerX + r * Math.cos(angle), centerY + r * Math.sin(angle)];
  }

  radarPolygon.setAttribute(
    "points",
    axes.map((axis, i) => pointFor(i, radar[axis.key]).join(",")).join(" ")
  );
  radarGrid.setAttribute(
    "points",
    axes.map((axis, i) => pointFor(i, 100).join(",")).join(" ")
  );

  radarLabelsEl.innerHTML = "";
  axes.forEach((axis, i) => {
    const [x, y] = pointFor(i, 90);
    const label = document.createElement("div");
    label.className = "absolute text-[10px] font-medium text-gray-600 -translate-x-1/2 -translate-y-1/2 text-center leading-tight w-16";
    label.style.left = `${x}px`;
    label.style.top = `${y}px`;
    label.textContent = `${t(axis.labelKey)} (${Math.round(radar[axis.key])}%)`;
    radarLabelsEl.appendChild(label);
  });
}
```

- [ ] **Step 4: Call it from `renderResults`**

Immediately after the section-analysis block added in Task 6, add:

```javascript
  renderRadar(report.metrics.radar);
```

- [ ] **Step 5: Manual verification**

Reload the local server, submit a test resume. Confirm a green pentagon (or smaller polygon if fewer than 5 axes) renders inside the "ATS Radar" card, with 5 labels each showing a name and a percentage. Test the null-readability edge case by submitting a resume with a resume file containing only 1-2 words of extracted text (e.g. a PDF containing just "Python") and confirm the radar renders with 4 labels, not 5, and does not throw a console error (check via the browser's console).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/app.js
git commit -m "feat: add honest 5-axis radar chart"
```

---

## Task 8: Download Report button (client-side PDF export)

**Files:**
- Modify: `web/frontend/index.html:6` (add CDN script tag before `app.js`), `index.html:205` (wrap the `atsResultHeading` h2 with a flex row containing the new button)
- Modify: `web/frontend/app.js`

**Interfaces:**
- Consumes: the global `html2pdf` function provided by the CDN script; the `resultsCard` DOM element (existing).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the CDN script**

In `web/frontend/index.html`, immediately before the closing `<script src="app.js"></script>` line, add:

```html
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
```

- [ ] **Step 2: Add the button to the heading row**

In `web/frontend/index.html`, replace:

```html
          <h2 class="text-lg font-semibold mb-1" data-i18n="atsResultHeading"></h2>
```

with:

```html
          <div class="flex items-center justify-between gap-3 mb-1">
            <h2 class="text-lg font-semibold" data-i18n="atsResultHeading"></h2>
            <button type="button" id="download-report-btn"
              class="hidden shrink-0 text-sm font-medium text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg px-3 py-1.5 items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
                <path d="M10 3v10m0 0l-4-4m4 4l4-4M4 16h12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span data-i18n="downloadReportBtn"></span>
            </button>
          </div>
```

- [ ] **Step 3: Add i18n keys**

In the `de:` block, add: `downloadReportBtn: "Bericht herunterladen",`

In the `en:` block, add: `downloadReportBtn: "Download Report",`

- [ ] **Step 4: Wire the button**

In `web/frontend/app.js`, add a DOM ref alongside the others:

```javascript
const downloadReportBtn = document.getElementById("download-report-btn");
```

At the end of `renderResults` (after the existing `resultsCard.classList.remove("opacity-40");` and the `if (scroll) { ... }` block, i.e. the last lines of the function), add:

```javascript
  downloadReportBtn.classList.remove("hidden");
  downloadReportBtn.classList.add("flex");
```

Add a click handler near the other event listeners (e.g. right after the `form.addEventListener("submit", ...)` block ends):

```javascript
downloadReportBtn.addEventListener("click", () => {
  html2pdf().from(resultsCard).save("pass-the-bot-report.pdf");
});
```

- [ ] **Step 5: Manual verification**

Reload the local server, submit a test resume, click "Download Report" / "Bericht herunterladen". Confirm a `pass-the-bot-report.pdf` file downloads and, opened, shows a reasonably legible snapshot of the results card (some CSS gradient/shadow loss in the PDF is acceptable; the content and numbers must be readable).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/index.html web/frontend/app.js
git commit -m "feat: add client-side PDF export of the results dashboard"
```

---

## Task 9: Staggered reveal animation

**Files:**
- Modify: `web/frontend/index.html` (add `data-reveal` to the two pre-existing top-level children of `#results-card` that don't already have it, and to `#tips-section`)
- Modify: `web/frontend/app.js`

**Interfaces:**
- Consumes: any element with a `data-reveal` attribute inside `#results-card`.
- Produces: nothing consumed by later tasks. Terminal task for the visual redesign.

- [ ] **Step 1: Mark the remaining result sections**

In `web/frontend/index.html`, add `data-reveal` to:
- The gauge/summary row: `<div class="flex flex-col md:flex-row items-center gap-8 mb-8">` → `<div class="flex flex-col md:flex-row items-center gap-8 mb-8" data-reveal>`
- The matched/near-miss/missing grid: `<div class="grid md:grid-cols-3 gap-4 mb-8">` (the one containing `matched-list`) → add `data-reveal` to it too.
- The tips section: `<div id="tips-section">` → `<div id="tips-section" data-reveal>`

(The Task 5 grid already has `data-reveal` from that task.)

- [ ] **Step 2: Add reveal CSS**

In `web/frontend/index.html`, inside the existing `<style>` block (the one starting `html { scroll-behavior: smooth; ... }`), add:

```css
  [data-reveal] { opacity: 0; transform: translateY(8px); transition: opacity 0.35s ease, transform 0.35s ease; }
  [data-reveal].revealed { opacity: 1; transform: translateY(0); }
```

- [ ] **Step 3: Write the stagger helper**

In `web/frontend/app.js`, add this function near `renderResults`:

```javascript
function revealResultSections() {
  const sections = resultsCard.querySelectorAll("[data-reveal]");
  sections.forEach((el) => el.classList.remove("revealed"));
  sections.forEach((el, i) => {
    setTimeout(() => el.classList.add("revealed"), i * 90);
  });
}
```

- [ ] **Step 4: Call it from `renderResults`**

At the very end of `renderResults`, after the `downloadReportBtn.classList.add("flex");` line added in Task 8, add:

```javascript
  revealResultSections();
```

- [ ] **Step 5: Manual verification**

Reload the local server, submit a test resume, and visually confirm the result sections fade/slide in one after another (gauge row, then matched/near-miss/missing, then keyword-coverage/sections/radar, then tips) rather than all appearing simultaneously. Submit a second time (without reloading the page) and confirm the reveal replays correctly rather than staying stuck in the "revealed" state from the first run (this is why Step 3's helper removes `revealed` before re-adding it).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/index.html web/frontend/app.js
git commit -m "feat: add staggered reveal animation for result sections"
```

---

## Task 10: Full end-to-end verification

**Files:** none (verification only)

**Interfaces:** none.

- [ ] **Step 1: Run the full Python test suite**

```bash
cd /home/eri-irfos/projects/passthebot && python3 -m pytest tests/ -v
cd web/backend && python3 -m pytest -v
```

Expected: all tests pass (existing `web/backend/tests/test_api.py` tests must still pass unmodified, since `metrics` is additive and those tests only assert `"results"`/`"score"` presence plus specific result fields).

- [ ] **Step 2: Full browser walkthrough against the local backend**

```bash
cd web/backend && uvicorn app.main:app --reload &
cd web/frontend && python3 -m http.server 5500
```

Open `http://localhost:5500`. Using a realistic multi-section, multi-paragraph resume PDF (not a one-line toy fixture) and a realistic job posting, verify:
- The staggered reveal plays smoothly (Task 9).
- Keyword Coverage, Resume Section Analysis, and the Radar all show non-placeholder, plausible numbers (Task 5-7).
- Switching the language toggle re-renders every new label (all new cards) in the other language.
- "Download Report" produces a readable PDF (Task 8).
- Upload a deliberately short/garbled resume (e.g. a PDF containing only "Python.") and confirm: no console errors, the radar shows 4 axes (readability omitted), and the Section Analysis card shows all four sections as "not found" without crashing.

- [ ] **Step 3: Stop local servers**

```bash
pkill -f "uvicorn app.main:app"
pkill -f "http.server 5500"
```

No commit for this task (verification only, no file changes).
