# Pass The Bot!

[![CI](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/ci.yml)
[![Deploy frontend to GitHub Pages](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/pages.yml/badge.svg)](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/pages.yml)
[![Live demo](https://img.shields.io/badge/demo-live-16a34a)](https://rfi-irfos.github.io/pass-the-bot/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)

**See your resume the way an ATS reads it.**

▶ **[Try it now](https://rfi-irfos.github.io/pass-the-bot/)** — paste a job posting, upload your CV, get an instant, transparent breakdown. Free, no account required.

Applicant Tracking Systems reject qualified candidates over pure
surface-form keyword mismatches — "Node" vs "Node.js", "Python" vs
"python", a typo in "Docker". **passthebot** is a deterministic,
explainable matching engine that answers "is skill X the same as skill Y"
with a versioned, inspectable skill graph instead of an opaque model call.
No AI black box, no résumé rewriting — just a diagnostic that tells you
exactly which required skills matched, which were near-misses caught by
typos, and which are genuinely missing, before a recruiter (or a bot)
ever sees your application.

## What's in this repo

- **`src/passthebot/`** — the matching engine: skill graph loader,
  keyword extraction, fuzzy near-miss detection, required/optional
  auto-detection, and report builder. See
  `docs/superpowers/specs/2026-09-14-matching-engine-design.md` for the
  full design spec.
- **`web/backend/`** — a small FastAPI service wrapping the engine (PDF/DOCX
  text extraction, display-name localization) — deployed at
  `passthebot-api.fly.dev`.
- **`web/frontend/`** — the static, no-build-step frontend served at
  [rfi-irfos.github.io/pass-the-bot](https://rfi-irfos.github.io/pass-the-bot/).

Discrete skills (languages, frameworks, tools, certifications, job
titles, hard skills) are matched by normalized alias lookup with
longest-match-first span-claiming (so "Node.js" never falsely triggers a
"JS" match). Soft skills are matched by embedding similarity against
curated anchor phrases, sentence-scoped to avoid whole-document dilution.

## Using the engine directly

The single entry point is `run_pipeline`:

```python
from passthebot.pipeline import run_pipeline

report = run_pipeline(
    posting_text="Requires Python and Docker experience.",
    resume_text="Experienced Python developer, Docker in production.",
)

print(report["score"]["coverage_pct"])
print(report["results"])
```

`required_ids` is optional — if omitted, the engine auto-detects which
posting keywords are required vs. "nice to have" from the posting text
itself. `data_dir` and `repo_root` are optional and default to the skill
graph bundled inside the installed package and this repo's root,
respectively. An optional `embedder` (`passthebot.embeddings.Embedder`)
can be passed in to reuse an already-loaded model across calls.

The returned report is a plain JSON-serializable `dict` containing
`engine_version`, `graph_version` (the repo's git HEAD commit, for audit
trail), `model_version` (the embedding model identity used for soft-skill
matching), per-keyword `results` (with `status`: `MATCH` / `NEAR_MISS` /
`MISSING`), and a `score` summary.

Validate the skill graph on its own (also run in CI on every PR):

```bash
python3 -m passthebot.validate_graph
```

## Running the web app locally

```bash
# Backend
cd web/backend
pip install -e ".[dev]"        # also needs the root passthebot package installed
uvicorn app.main:app --reload  # http://localhost:8000

# Frontend (separate terminal)
cd web/frontend
python3 -m http.server 5500    # http://localhost:5500
```

## Adding a new skill graph entry

Skill data lives in `src/passthebot/data/skills/*.yaml`, one file per
category. See the design spec's section 4 ("Data model") for the exact
YAML schema for discrete categories (`aliases`, matched by exact
normalized substring) versus `soft_skills` (`anchor_phrases` +
`embedding_threshold`, matched by embedding similarity).

New entries should generally be added with `status: curated` via a normal
PR. Entries with `status: ai-suggested-pending` are inert — loaded but
excluded from matching (see `passthebot.graph.active_entries`) — until a
human reviews and flips the status to `ai-suggested-approved`, per the
design spec's human-in-the-loop requirement. CI validates every PR via
`python3 -m passthebot.validate_graph`, which rejects duplicate ids,
invalid categories/statuses, and alias/anchor-phrase collisions across
different ids.
