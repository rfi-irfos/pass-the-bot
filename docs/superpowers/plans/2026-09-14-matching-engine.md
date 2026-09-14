# passthebot Matching Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic keyword-matching kernel described in the design spec: load a versioned skill-graph, extract keywords from job-posting/resume text, match them by canonical ID (exact, fuzzy, or embedding-based depending on category), and produce a versioned, auditable JSON report.

**Architecture:** A small Python package (`passthebot`) with one module per pipeline stage (graph loading/validation, text normalization/extraction, matching, reporting). No web server, no CLI beyond a validation script in this plan — this plan builds the importable library the two future frontend projects will call.

**Tech Stack:** Python 3.11+, PyYAML (graph loading), rapidfuzz (fuzzy string matching), sentence-transformers with the `all-MiniLM-L6-v2` model (soft-skill embedding similarity, small/offline-capable), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-14-matching-engine-design.md`

## Global Constraints

- No LLM/model call anywhere in the matching decision path (embeddings for soft-skills are a fixed local model, not a generative call, and are still deterministic given the same input).
- Every report includes `graph_version` (git commit hash of `data/skills/`).
- `id` unique across the WHOLE graph, not just per-category. No alias/anchor-phrase string shared by two different `id`s (case/punctuation-normalized comparison).
- Only `status: curated` or `status: ai-suggested-approved` entries participate in matching.
- Every module gets unit tests; the full pipeline gets at least one golden-file regression test (Task 8).

---

## Task 1: Project scaffolding, skill-graph data model, and loader

**Files:**
- Create: `pyproject.toml`
- Create: `src/passthebot/__init__.py`
- Create: `src/passthebot/graph.py`
- Create: `data/skills/languages.yaml`
- Create: `data/skills/frameworks.yaml`
- Create: `data/skills/tools.yaml`
- Create: `data/skills/soft_skills.yaml`
- Test: `tests/test_graph.py`

**Interfaces:**
- Produces: `SkillEntry` dataclass, `Category` / `Status` literals, `DISCRETE_CATEGORIES: set[str]`, `load_skill_graph(data_dir: Path) -> list[SkillEntry]`, `active_entries(entries: list[SkillEntry]) -> list[SkillEntry]`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "passthebot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "rapidfuzz>=3.9",
    "sentence-transformers>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Write seed skill-graph data files**

`data/skills/languages.yaml`:
```yaml
- id: python
  category: languages
  display: { de: "Python", en: "Python" }
  aliases: ["Python", "python", "Python3", "Python 3"]
  status: curated
  added: "2026-09-14"
- id: javascript
  category: languages
  display: { de: "JavaScript", en: "JavaScript" }
  aliases: ["JavaScript", "Javascript", "javascript", "JS", "js"]
  status: curated
  added: "2026-09-14"
- id: nodejs
  category: languages
  display: { de: "Node.js", en: "Node.js" }
  aliases: ["Node.js", "Node", "NodeJS", "nodejs", "node js"]
  status: curated
  added: "2026-09-14"
```

`data/skills/frameworks.yaml`:
```yaml
- id: react
  category: frameworks
  display: { de: "React", en: "React" }
  aliases: ["React", "React.js", "ReactJS", "react"]
  status: curated
  added: "2026-09-14"
```

`data/skills/tools.yaml`:
```yaml
- id: docker
  category: tools
  display: { de: "Docker", en: "Docker" }
  aliases: ["Docker", "docker"]
  status: curated
  added: "2026-09-14"
```

`data/skills/soft_skills.yaml`:
```yaml
- id: teamwork
  category: soft_skills
  display: { de: "Teamfähigkeit", en: "Team player" }
  anchor_phrases: ["Teamfähigkeit", "teamorientiert arbeiten", "team player", "works well in teams", "collaborative"]
  embedding_threshold: 0.75
  status: curated
  added: "2026-09-14"
```

(`certifications.yaml`, `job_titles.yaml`, `hard_skills.yaml` are created empty as `[]` in this task; they are populated by later curation, not by this plan.)

```bash
mkdir -p data/skills
echo "[]" > data/skills/certifications.yaml
echo "[]" > data/skills/job_titles.yaml
echo "[]" > data/skills/hard_skills.yaml
```

- [ ] **Step 3: Write `src/passthebot/graph.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

Category = Literal[
    "languages", "frameworks", "tools", "certifications",
    "job_titles", "hard_skills", "soft_skills",
]
Status = Literal["curated", "ai-suggested-pending", "ai-suggested-approved"]

DISCRETE_CATEGORIES: set[str] = {
    "languages", "frameworks", "tools", "certifications", "job_titles", "hard_skills",
}
ACTIVE_STATUSES: set[str] = {"curated", "ai-suggested-approved"}


@dataclass
class SkillEntry:
    id: str
    category: Category
    display: dict[str, str]
    status: Status
    added: str
    aliases: list[str] = field(default_factory=list)
    anchor_phrases: list[str] = field(default_factory=list)
    embedding_threshold: float | None = None


def load_skill_graph(data_dir: Path) -> list[SkillEntry]:
    """Load every *.yaml file directly under data_dir into a flat list of SkillEntry."""
    entries: list[SkillEntry] = []
    for yaml_file in sorted(data_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or []
        for item in raw:
            entries.append(
                SkillEntry(
                    id=item["id"],
                    category=item["category"],
                    display=item["display"],
                    status=item["status"],
                    added=item["added"],
                    aliases=item.get("aliases", []),
                    anchor_phrases=item.get("anchor_phrases", []),
                    embedding_threshold=item.get("embedding_threshold"),
                )
            )
    return entries


def active_entries(entries: list[SkillEntry]) -> list[SkillEntry]:
    """Filter to entries eligible for matching (curated or ai-suggested-approved)."""
    return [e for e in entries if e.status in ACTIVE_STATUSES]
```

- [ ] **Step 4: Write `tests/test_graph.py`**

```python
from pathlib import Path

from passthebot.graph import active_entries, load_skill_graph

DATA_DIR = Path(__file__).parent.parent / "data" / "skills"


def test_load_skill_graph_finds_seed_entries():
    entries = load_skill_graph(DATA_DIR)
    ids = {e.id for e in entries}
    assert "python" in ids
    assert "nodejs" in ids
    assert "teamwork" in ids


def test_load_skill_graph_parses_soft_skill_fields():
    entries = load_skill_graph(DATA_DIR)
    teamwork = next(e for e in entries if e.id == "teamwork")
    assert teamwork.category == "soft_skills"
    assert "team player" in teamwork.anchor_phrases
    assert teamwork.embedding_threshold == 0.75


def test_active_entries_filters_by_status():
    entries = load_skill_graph(DATA_DIR)
    assert all(e.status in {"curated", "ai-suggested-approved"} for e in active_entries(entries))
```

- [ ] **Step 5: Install package in editable mode and run tests**

```bash
cd ~/projects/passthebot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_graph.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ data/ tests/test_graph.py .venv 2>/dev/null; git add pyproject.toml src/ data/ tests/test_graph.py
echo ".venv/\n__pycache__/\n*.egg-info/" > .gitignore
git add .gitignore
git commit -m "Add skill graph data model, loader, and seed data"
```

---

## Task 2: Graph validation (invariants) + CI script

**Files:**
- Create: `src/passthebot/validate_graph.py`
- Test: `tests/test_validate_graph.py`

**Interfaces:**
- Consumes: `SkillEntry`, `load_skill_graph` from Task 1.
- Produces: `GraphValidationError` exception, `validate_graph(entries: list[SkillEntry]) -> None` (raises on any invariant violation), `normalize_string(s: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validate_graph.py
import pytest

from passthebot.graph import SkillEntry
from passthebot.validate_graph import GraphValidationError, validate_graph


def _entry(**overrides):
    base = dict(
        id="python", category="languages", display={"en": "Python"},
        status="curated", added="2026-09-14", aliases=["Python", "python"],
    )
    base.update(overrides)
    return SkillEntry(**base)


def test_valid_graph_passes():
    validate_graph([_entry()])  # should not raise


def test_duplicate_id_across_categories_rejected():
    entries = [_entry(), _entry(category="frameworks")]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_alias_collision_across_ids_rejected():
    entries = [
        _entry(id="python", aliases=["Python", "py"]),
        _entry(id="pytorch", aliases=["PyTorch", "py"]),
    ]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_alias_collision_is_case_and_space_insensitive():
    entries = [
        _entry(id="a", aliases=["Node JS"]),
        _entry(id="b", aliases=["node  js"]),
    ]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_invalid_category_rejected():
    with pytest.raises(GraphValidationError):
        validate_graph([_entry(category="not_a_real_category")])


def test_invalid_status_rejected():
    with pytest.raises(GraphValidationError):
        validate_graph([_entry(status="not_a_real_status")])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_validate_graph.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.validate_graph'`.

- [ ] **Step 3: Write `src/passthebot/validate_graph.py`**

```python
from __future__ import annotations

import re
import sys
from pathlib import Path

from passthebot.graph import DISCRETE_CATEGORIES, SkillEntry, load_skill_graph

VALID_CATEGORIES = DISCRETE_CATEGORIES | {"soft_skills"}
VALID_STATUSES = {"curated", "ai-suggested-pending", "ai-suggested-approved"}


class GraphValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def normalize_string(s: str) -> str:
    """Lowercase and collapse whitespace/punctuation for alias-collision comparison."""
    return re.sub(r"[\s\.\-_]+", " ", s.strip().lower()).strip()


def validate_graph(entries: list[SkillEntry]) -> None:
    errors: list[str] = []

    seen_ids: dict[str, int] = {}
    for e in entries:
        seen_ids[e.id] = seen_ids.get(e.id, 0) + 1
    for id_, count in seen_ids.items():
        if count > 1:
            errors.append(f"duplicate id '{id_}' appears {count} times")

    for e in entries:
        if e.category not in VALID_CATEGORIES:
            errors.append(f"entry '{e.id}' has invalid category '{e.category}'")
        if e.status not in VALID_STATUSES:
            errors.append(f"entry '{e.id}' has invalid status '{e.status}'")

    alias_owner: dict[str, str] = {}
    for e in entries:
        strings = e.aliases if e.category in DISCRETE_CATEGORIES else e.anchor_phrases
        for raw in strings:
            key = normalize_string(raw)
            if key in alias_owner and alias_owner[key] != e.id:
                errors.append(
                    f"alias/phrase '{raw}' (normalized '{key}') claimed by both "
                    f"'{alias_owner[key]}' and '{e.id}'"
                )
            else:
                alias_owner[key] = e.id

    if errors:
        raise GraphValidationError(errors)


def main() -> int:
    data_dir = Path(__file__).parent.parent.parent / "data" / "skills"
    entries = load_skill_graph(data_dir)
    try:
        validate_graph(entries)
    except GraphValidationError as exc:
        print("Skill graph validation FAILED:", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"Skill graph validation passed ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_validate_graph.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Run the validation script against the real seed data**

```bash
python3 -m passthebot.validate_graph
```
Expected: `Skill graph validation passed (5 entries).`

- [ ] **Step 6: Commit**

```bash
git add src/passthebot/validate_graph.py tests/test_validate_graph.py
git commit -m "Add skill graph validation (duplicate ID / alias collision checks)"
```

---

## Task 3: Text normalization and discrete-category keyword extraction

**Files:**
- Create: `src/passthebot/normalizer.py`
- Test: `tests/test_normalizer.py`

**Interfaces:**
- Consumes: `SkillEntry`, `DISCRETE_CATEGORIES` from Task 1; `normalize_string` from Task 2.
- Produces: `ExtractedKeyword` dataclass, `extract_discrete_keywords(text: str, entries: list[SkillEntry]) -> list[ExtractedKeyword]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalizer.py
from passthebot.graph import SkillEntry
from passthebot.normalizer import extract_discrete_keywords

ENTRIES = [
    SkillEntry(
        id="nodejs", category="languages", display={"en": "Node.js"},
        status="curated", added="2026-09-14",
        aliases=["Node.js", "Node", "NodeJS", "nodejs", "node js"],
    ),
    SkillEntry(
        id="python", category="languages", display={"en": "Python"},
        status="curated", added="2026-09-14",
        aliases=["Python", "python"],
    ),
]


def test_extracts_exact_alias():
    result = extract_discrete_keywords("Requires Python and Node.js experience.", ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"python", "nodejs"}


def test_extracts_case_and_punctuation_insensitive_alias():
    result = extract_discrete_keywords("we need someone who knows nodejs well", ENTRIES)
    assert result[0].id == "nodejs"
    assert result[0].confidence == 1.0


def test_no_match_returns_empty_list():
    result = extract_discrete_keywords("We need a great communicator.", ENTRIES)
    assert result == []


def test_does_not_double_count_same_skill_mentioned_twice():
    result = extract_discrete_keywords("Python, python, PYTHON required.", ENTRIES)
    assert len(result) == 1
    assert result[0].id == "python"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_normalizer.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.normalizer'`.

- [ ] **Step 3: Write `src/passthebot/normalizer.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from passthebot.graph import SkillEntry
from passthebot.validate_graph import normalize_string


@dataclass
class ExtractedKeyword:
    id: str
    category: str
    matched_text: str
    confidence: float


def extract_discrete_keywords(text: str, entries: list[SkillEntry]) -> list[ExtractedKeyword]:
    """Scan text for any known alias of any discrete-category entry.

    Matching is on normalized substrings (see normalize_string): case-insensitive,
    punctuation/whitespace-collapsed. Each skill id is reported at most once, even
    if multiple of its aliases (or the same alias multiple times) appear in the text.
    """
    normalized_text = normalize_string(text)
    found: dict[str, ExtractedKeyword] = {}
    for entry in entries:
        if entry.id in found:
            continue
        for alias in entry.aliases:
            needle = normalize_string(alias)
            if needle and re.search(rf"\b{re.escape(needle)}\b", normalized_text):
                found[entry.id] = ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=alias, confidence=1.0
                )
                break
    return list(found.values())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_normalizer.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/normalizer.py tests/test_normalizer.py
git commit -m "Add discrete-category keyword extraction via alias dictionary scan"
```

---

## Task 4: Fuzzy fallback matching for near-misses

**Files:**
- Create: `src/passthebot/fuzzy.py`
- Test: `tests/test_fuzzy.py`

**Interfaces:**
- Produces: `fuzzy_best_match(term: str, candidates: list[str], threshold: float = 0.75) -> tuple[str, float] | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fuzzy.py
from passthebot.fuzzy import fuzzy_best_match


def test_close_typo_matches_above_threshold():
    result = fuzzy_best_match("dockr", ["Docker", "Kubernetes"])
    assert result is not None
    candidate, score = result
    assert candidate == "Docker"
    assert score >= 0.75


def test_unrelated_term_returns_none():
    result = fuzzy_best_match("banana", ["Docker", "Kubernetes"])
    assert result is None


def test_exact_match_scores_1():
    result = fuzzy_best_match("Docker", ["Docker", "Kubernetes"])
    assert result == ("Docker", 1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fuzzy.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.fuzzy'`.

- [ ] **Step 3: Write `src/passthebot/fuzzy.py`**

```python
from __future__ import annotations

from rapidfuzz import fuzz


def fuzzy_best_match(
    term: str, candidates: list[str], threshold: float = 0.75
) -> tuple[str, float] | None:
    """Return the best-matching candidate string and its similarity (0..1) if it
    clears `threshold`, else None. Uses rapidfuzz's normalized Levenshtein ratio.
    """
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzz.ratio(term.lower(), candidate.lower()) / 100.0
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_candidate is not None and best_score >= threshold:
        return best_candidate, best_score
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fuzzy.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/fuzzy.py tests/test_fuzzy.py
git commit -m "Add fuzzy-string fallback matcher for near-miss detection"
```

---

## Task 5: Soft-skill embedding extraction

**Files:**
- Create: `src/passthebot/embeddings.py`
- Modify: `src/passthebot/normalizer.py` (add `extract_soft_skills`)
- Test: `tests/test_embeddings.py`

**Interfaces:**
- Consumes: `SkillEntry`, `ExtractedKeyword` from Tasks 1 and 3.
- Produces: `Embedder` class with `.best_match(text: str, phrases: list[str]) -> tuple[str, float]`; `extract_soft_skills(text: str, entries: list[SkillEntry], embedder: Embedder) -> list[ExtractedKeyword]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_embeddings.py
from passthebot.embeddings import Embedder
from passthebot.graph import SkillEntry
from passthebot.normalizer import extract_soft_skills

SOFT_SKILL_ENTRIES = [
    SkillEntry(
        id="teamwork", category="soft_skills", display={"en": "Team player"},
        status="curated", added="2026-09-14",
        anchor_phrases=["team player", "works well in teams", "collaborative"],
        embedding_threshold=0.6,
    ),
]


def test_embedder_scores_similar_phrases_higher():
    embedder = Embedder()
    high = embedder.best_match("great team player who collaborates well", ["team player"])
    low = embedder.best_match("expert in database indexing", ["team player"])
    assert high[1] > low[1]


def test_extract_soft_skills_matches_close_phrase():
    embedder = Embedder()
    result = extract_soft_skills(
        "Looking for someone who works well in teams.", SOFT_SKILL_ENTRIES, embedder
    )
    assert len(result) == 1
    assert result[0].id == "teamwork"
    assert result[0].confidence >= 0.6


def test_extract_soft_skills_below_threshold_excluded():
    embedder = Embedder()
    result = extract_soft_skills(
        "We build embedded firmware for industrial sensors.", SOFT_SKILL_ENTRIES, embedder
    )
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_embeddings.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.embeddings'`.

- [ ] **Step 3: Write `src/passthebot/embeddings.py`**

```python
from __future__ import annotations

from sentence_transformers import SentenceTransformer, util


class Embedder:
    """Thin wrapper around a small local sentence-embedding model. No network
    calls at inference time once the model is cached locally; no generative
    model involved, so results are deterministic for a fixed model + input.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def best_match(self, text: str, phrases: list[str]) -> tuple[str, float]:
        text_emb = self._model.encode(text, convert_to_tensor=True)
        phrase_embs = self._model.encode(phrases, convert_to_tensor=True)
        scores = util.cos_sim(text_emb, phrase_embs)[0]
        best_idx = int(scores.argmax())
        return phrases[best_idx], float(scores[best_idx])
```

- [ ] **Step 4: Add `extract_soft_skills` to `src/passthebot/normalizer.py`**

```python
# append to src/passthebot/normalizer.py

def extract_soft_skills(
    text: str, entries: list[SkillEntry], embedder
) -> list[ExtractedKeyword]:
    """Match soft_skills entries by embedding similarity against anchor_phrases.
    An entry is included if the best-matching anchor phrase clears its own
    embedding_threshold.
    """
    found: list[ExtractedKeyword] = []
    for entry in entries:
        if not entry.anchor_phrases:
            continue
        phrase, score = embedder.best_match(text, entry.anchor_phrases)
        if score >= (entry.embedding_threshold or 0.75):
            found.append(
                ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=phrase, confidence=score
                )
            )
    return found
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_embeddings.py -v
```
Expected: 3 passed. (First run downloads the `all-MiniLM-L6-v2` model, ~90MB; subsequent runs use the local cache.)

- [ ] **Step 6: Commit**

```bash
git add src/passthebot/embeddings.py src/passthebot/normalizer.py tests/test_embeddings.py
git commit -m "Add embedding-based soft-skill extraction"
```

---

## Task 6: Matcher/Scorer kernel

**Files:**
- Create: `src/passthebot/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `ExtractedKeyword` from Task 3/5; `fuzzy_best_match` from Task 4.
- Produces: `MatchResult` dataclass, `match(posting_keywords: list[ExtractedKeyword], resume_keywords: list[ExtractedKeyword], required_ids: set[str]) -> list[MatchResult]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_matcher.py
from passthebot.matcher import match
from passthebot.normalizer import ExtractedKeyword

POSTING = [
    ExtractedKeyword(id="python", category="languages", matched_text="Python", confidence=1.0),
    ExtractedKeyword(id="docker", category="tools", matched_text="Docker", confidence=1.0),
    ExtractedKeyword(id="react", category="frameworks", matched_text="React", confidence=1.0),
]


def test_exact_match_when_resume_has_same_id():
    resume = [ExtractedKeyword(id="python", category="languages", matched_text="python", confidence=1.0)]
    results = match(POSTING, resume, required_ids={"python"})
    python_result = next(r for r in results if r.id == "python")
    assert python_result.status == "MATCH"
    assert python_result.required is True


def test_missing_when_resume_lacks_id_and_no_fuzzy_hit():
    results = match(POSTING, [], required_ids={"python", "docker", "react"})
    statuses = {r.id: r.status for r in results}
    assert statuses["python"] == "MISSING"
    assert statuses["docker"] == "MISSING"
    assert statuses["react"] == "MISSING"


def test_required_flag_reflects_input():
    results = match(POSTING, [], required_ids={"python"})
    by_id = {r.id: r for r in results}
    assert by_id["python"].required is True
    assert by_id["docker"].required is False


def test_java_does_not_match_javascript():
    posting = [ExtractedKeyword(id="javascript", category="languages", matched_text="JavaScript", confidence=1.0)]
    resume = [ExtractedKeyword(id="java", category="languages", matched_text="Java", confidence=1.0)]
    results = match(posting, resume, required_ids={"javascript"})
    assert results[0].status == "MISSING"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_matcher.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.matcher'`.

- [ ] **Step 3: Write `src/passthebot/matcher.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from passthebot.normalizer import ExtractedKeyword

Status = Literal["MATCH", "NEAR_MISS", "MISSING"]


@dataclass
class MatchResult:
    id: str
    category: str
    status: Status
    required: bool
    found_text: str | None = None
    suggested_alias: str | None = None
    confidence: float | None = None


def match(
    posting_keywords: list[ExtractedKeyword],
    resume_keywords: list[ExtractedKeyword],
    required_ids: set[str],
) -> list[MatchResult]:
    """For every keyword found in the posting, decide whether the resume
    satisfies it by canonical id (never by raw text). No fuzzy fallback across
    different ids happens here (fuzzy matching is used inside extraction for a
    single skill's own aliases, Task 4, not to conflate two different ids).
    """
    resume_ids = {k.id for k in resume_keywords}
    results: list[MatchResult] = []
    for posting_kw in posting_keywords:
        if posting_kw.id in resume_ids:
            results.append(
                MatchResult(
                    id=posting_kw.id,
                    category=posting_kw.category,
                    status="MATCH",
                    required=posting_kw.id in required_ids,
                )
            )
        else:
            results.append(
                MatchResult(
                    id=posting_kw.id,
                    category=posting_kw.category,
                    status="MISSING",
                    required=posting_kw.id in required_ids,
                )
            )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_matcher.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/matcher.py tests/test_matcher.py
git commit -m "Add deterministic matcher/scorer kernel"
```

---

## Task 7: Report Builder with graph versioning

**Files:**
- Create: `src/passthebot/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `MatchResult` from Task 6.
- Produces: `get_graph_version(repo_root: Path) -> str`, `build_report(results: list[MatchResult], graph_version: str, engine_version: str = "0.1.0") -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_report.py
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


def test_build_report_shape():
    report = build_report(RESULTS, graph_version="abc123")
    assert report["engine_version"] == "0.1.0"
    assert report["graph_version"] == "abc123"
    assert len(report["results"]) == 3


def test_build_report_score_counts_only_required():
    report = build_report(RESULTS, graph_version="abc123")
    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 1
    assert report["score"]["coverage_pct"] == 50.0


def test_get_graph_version_returns_a_git_hash_in_a_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    version = get_graph_version(tmp_path)
    assert len(version) == 40  # full git SHA


def test_get_graph_version_returns_unknown_outside_git_repo(tmp_path):
    version = get_graph_version(tmp_path)
    assert version == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_report.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.report'`.

- [ ] **Step 3: Write `src/passthebot/report.py`**

```python
from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from passthebot.matcher import MatchResult


def get_graph_version(repo_root: Path) -> str:
    """Return the current HEAD commit hash of repo_root, or 'unknown' if
    repo_root is not inside a git repository (e.g. a fresh checkout without
    history, or a non-git deployment)."""
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


def build_report(
    results: list[MatchResult], graph_version: str, engine_version: str = "0.1.0"
) -> dict:
    required_results = [r for r in results if r.required]
    required_total = len(required_results)
    required_matched = sum(1 for r in required_results if r.status == "MATCH")
    coverage_pct = (
        round(100.0 * required_matched / required_total, 1) if required_total else 100.0
    )
    return {
        "engine_version": engine_version,
        "graph_version": graph_version,
        "results": [asdict(r) for r in results],
        "score": {
            "required_matched": required_matched,
            "required_total": required_total,
            "coverage_pct": coverage_pct,
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_report.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/passthebot/report.py tests/test_report.py
git commit -m "Add report builder with git-based graph versioning"
```

---

## Task 8: Pipeline entry point, end-to-end golden-file test, and CI wiring

**Files:**
- Create: `src/passthebot/pipeline.py`
- Create: `tests/test_pipeline.py`
- Create: `tests/golden/posting_1.txt`
- Create: `tests/golden/resume_1.txt`
- Create: `tests/test_golden.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `load_skill_graph`/`active_entries` (Task 1), `validate_graph` (Task 2), `extract_discrete_keywords`/`extract_soft_skills` (Tasks 3/5), `Embedder` (Task 5), `match` (Task 6), `build_report`/`get_graph_version` (Task 7).
- Produces: `PipelineInputError` exception, `run_pipeline(posting_text: str, resume_text: str, required_ids: set[str], data_dir: Path, repo_root: Path, embedder: Embedder | None = None) -> dict` — the single entry point both future frontend projects (candidate checker, KMU agent) will call instead of hand-wiring the six modules themselves.

- [ ] **Step 1: Write the failing tests for the pipeline entry point**

```python
# tests/test_pipeline.py
from pathlib import Path

import pytest

from passthebot.pipeline import PipelineInputError, run_pipeline

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data" / "skills"


def test_run_pipeline_rejects_empty_posting_text():
    with pytest.raises(PipelineInputError, match="posting_text"):
        run_pipeline("", "Some resume text.", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_rejects_empty_resume_text():
    with pytest.raises(PipelineInputError, match="resume_text"):
        run_pipeline("Some posting text.", "", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_rejects_whitespace_only_text():
    with pytest.raises(PipelineInputError):
        run_pipeline("   \n  ", "Some resume text.", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_returns_valid_report_shape():
    report = run_pipeline(
        "Requires Python.", "Experienced Python developer.", {"python"}, DATA_DIR, REPO_ROOT
    )
    assert "engine_version" in report
    assert "graph_version" in report
    assert "results" in report
    assert "score" in report
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_pipeline.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'passthebot.pipeline'`.

- [ ] **Step 3: Write `src/passthebot/pipeline.py`**

```python
from __future__ import annotations

from pathlib import Path

from passthebot.embeddings import Embedder
from passthebot.graph import active_entries, load_skill_graph
from passthebot.matcher import match
from passthebot.normalizer import extract_discrete_keywords, extract_soft_skills
from passthebot.report import build_report, get_graph_version
from passthebot.validate_graph import validate_graph


class PipelineInputError(Exception):
    """Raised when posting_text or resume_text is empty/unparseable, per spec
    section 7: never silently return a zero-signal report for bad input."""


def run_pipeline(
    posting_text: str,
    resume_text: str,
    required_ids: set[str],
    data_dir: Path,
    repo_root: Path,
    embedder: Embedder | None = None,
) -> dict:
    """The single entry point downstream products (candidate checker, KMU
    agent) call. Loads the graph, validates it, extracts keywords from both
    texts, matches them, and returns the versioned JSON-shaped report dict.
    """
    if not posting_text.strip():
        raise PipelineInputError("posting_text is empty or whitespace-only")
    if not resume_text.strip():
        raise PipelineInputError("resume_text is empty or whitespace-only")

    entries = active_entries(load_skill_graph(data_dir))
    validate_graph(entries)
    embedder = embedder or Embedder()

    posting_kw = extract_discrete_keywords(posting_text, entries) + extract_soft_skills(
        posting_text, entries, embedder
    )
    resume_kw = extract_discrete_keywords(resume_text, entries) + extract_soft_skills(
        resume_text, entries, embedder
    )

    results = match(posting_kw, resume_kw, required_ids)
    return build_report(results, graph_version=get_graph_version(repo_root))
```

- [ ] **Step 4: Run pipeline tests to verify they pass**

```bash
pytest tests/test_pipeline.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Write the golden input files**

`tests/golden/posting_1.txt`:
```
We are looking for a backend engineer.
Required: Python, Docker experience.
Nice to have: React, and someone who is a strong team player.
```

`tests/golden/resume_1.txt`:
```
Experienced backend developer. Strong Python background.
Comfortable with Docker and Kubernetes in production.
Works well in teams and enjoys mentoring juniors.
```

- [ ] **Step 6: Write the failing end-to-end golden test**

```python
# tests/test_golden.py
from pathlib import Path

from passthebot.pipeline import run_pipeline

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data" / "skills"
GOLDEN_DIR = Path(__file__).parent / "golden"


def test_golden_posting_1_resume_1():
    posting_text = (GOLDEN_DIR / "posting_1.txt").read_text()
    resume_text = (GOLDEN_DIR / "resume_1.txt").read_text()
    required_ids = {"python", "docker"}  # matches "Required:" line in posting_1.txt

    report = run_pipeline(posting_text, resume_text, required_ids, DATA_DIR, REPO_ROOT)

    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["python"]["status"] == "MATCH"
    assert by_id["docker"]["status"] == "MATCH"
    assert by_id["react"]["status"] == "MISSING"
    assert by_id["teamwork"]["status"] == "MATCH"

    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 2
    assert report["score"]["coverage_pct"] == 100.0
```

- [ ] **Step 7: Run the golden test to verify it passes**

```bash
pytest tests/test_golden.py -v
```
Expected: 1 passed.

- [ ] **Step 8: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - name: Validate skill graph
        run: python3 -m passthebot.validate_graph
      - name: Run tests
        run: pytest -v
```

- [ ] **Step 9: Run the full test suite locally one more time**

```bash
pytest -v
```
Expected: all tests across every task pass.

- [ ] **Step 10: Commit**

```bash
git add src/passthebot/pipeline.py tests/test_pipeline.py tests/golden tests/test_golden.py .github/workflows/ci.yml
git commit -m "Add pipeline entry point, end-to-end golden-file test, and CI workflow"
```

---

## Next steps (explicitly not part of this plan)

- Wire the fuzzy fallback (Task 4) into `extract_discrete_keywords` so misspelled/near-miss terms produce `NEAR_MISS` instead of being silently absent from extraction entirely. This plan built the fuzzy matcher and the matcher's `NEAR_MISS` status, but did not yet connect them end-to-end, deliberately keeping this plan bounded to the exact-match path plus the pieces (fuzzy, embeddings) needed for the next iteration.
- Requirement-level detection heuristic (spec section 5, step 3) for parsing "required" vs "nice to have" out of raw posting text — this plan hardcodes `required_ids` as a parameter for now.
- The candidate-facing checker and the KMU agent (separate specs/plans, per the design doc's section 9).
- Curation-queue logging for frequently-unmatched terms (spec section 7) was not built in this plan. This is a declared deferral, not an oversight: there is no tokenizer/unmatched-term concept yet in the dictionary-based extraction approach used here, and this work is naturally coupled to the fuzzy-fallback/`NEAR_MISS` wiring deferral above — both should land together in a future iteration.
- The soft-skill embedding threshold (currently 0.45 default, see `passthebot.normalizer.extract_soft_skills`) was calibrated from exactly one matching example and one non-matching example. This is a placeholder, not a validated value. A proper multi-phrase calibration harness (a labeled set of matching/non-matching sentences per soft-skill entry, scored to pick a threshold that balances false positives/negatives) should be built once more soft-skill entries are curated.
