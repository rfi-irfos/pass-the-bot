# Pass The Bot!

[![CI](https://img.shields.io/github/actions/workflow/status/rfi-irfos/pass-the-bot/ci.yml?branch=master&style=flat-square&label=CI&logo=github)](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/ci.yml)
[![Pages Deploy](https://img.shields.io/github/actions/workflow/status/rfi-irfos/pass-the-bot/pages.yml?branch=master&style=flat-square&label=pages&logo=githubpages&logoColor=white)](https://github.com/rfi-irfos/pass-the-bot/actions/workflows/pages.yml)
[![Live Demo](https://img.shields.io/badge/demo-live-16a34a?style=flat-square)](https://rfi-irfos.github.io/pass-the-bot/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Stars](https://img.shields.io/github/stars/rfi-irfos/pass-the-bot?style=flat-square&logo=github&color=yellow)](https://github.com/rfi-irfos/pass-the-bot/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/rfi-irfos/pass-the-bot?style=flat-square&logo=git&logoColor=white)](https://github.com/rfi-irfos/pass-the-bot/commits/master)

**See your resume the way an ATS reads it.**

▶ **[Try it now](https://rfi-irfos.github.io/pass-the-bot/)**: paste a job posting (text or link), upload your CV and get an instant, transparent breakdown. Free, no account, nothing stored.

Applicant Tracking Systems reject qualified candidates over surface-level
keyword mismatches: "Node" vs "Node.js", "Python" vs "python", a typo in
"Docker". **Pass The Bot** is a deterministic, explainable matching engine.
It decides whether skill X is the same as skill Y with a versioned,
inspectable skill graph instead of an opaque model call. It doesn't rewrite
your resume. It tells you which required skills matched, which were
near-misses caused by typos, and which are really missing, before a
recruiter (or a bot) ever sees your application.

## How to use it

1. Paste the job posting into the left field: the full text, or a link to
   the posting. For links, the posting is read from the page and the text
   appears in the field so you can check it. Some career sites only load
   the job in the browser; for those you'll be asked to paste the text.
2. Upload your resume as PDF or DOCX (max. 5 MB).
3. Get your result: an ATS score for the required skills, matched,
   near-miss and missing skills, keyword coverage, a section check of your
   resume and concrete tips. Download it as a PDF if you like.

It works for tech and non-tech jobs alike: finance and bookkeeping, office,
care and nursing, sales, marketing and the trades, in German and English.
Spoken languages ("sehr gute Deutschkenntnisse") count as skills too.

If the posting has no recognizable requirements, you get a clear "no score"
instead of a misleading 100%.

**Privacy:** your resume and the posting are processed for this one check
and then discarded. Nothing is stored, nothing is used for training, and the
page sets no cookies.

## How it works

Discrete skills (programming languages, frameworks, tools, certifications,
job titles, hard skills, spoken languages) are matched by normalized alias
lookup with longest-match-first span-claiming, so "Node.js" never falsely
triggers a "JS" match. German shortened compounds like "Grund- und
Behandlungspflege" count as both words. Typos are caught as near-misses by fuzzy matching. Soft skills
are matched by embedding similarity against curated anchor phrases,
sentence by sentence to avoid whole-document dilution, with a stricter
threshold on German text. Required and
"nice to have" skills are detected from the posting's own wording and
section headings.

## What's in this repo

- **`src/passthebot/`**: the matching engine (skill graph loader, keyword
  extraction, fuzzy near-miss detection, required/optional auto-detection
  and report builder). See
  `docs/superpowers/specs/2026-09-14-matching-engine-design.md` for the
  full design spec.
- **`web/backend/`**: a small FastAPI service around the engine (PDF/DOCX
  text extraction, safe job-link reading, display-name localization),
  deployed at `passthebot-api.fly.dev`.
- **`web/frontend/`**: the static, no-build-step frontend (German and
  English) served at
  [rfi-irfos.github.io/pass-the-bot](https://rfi-irfos.github.io/pass-the-bot/).

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

`required_ids` is optional: if omitted, the engine auto-detects which
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
pip install -e ".[dev]" && pip install -e "web/backend[dev]"

# Backend
uvicorn app.main:app --app-dir web/backend --reload --port 8000

# Frontend (separate terminal)
cd web/frontend && python3 -m http.server 5500   # http://localhost:5500
```

The frontend uses the live API by default. Point `API_BASE_URL` at the top
of `web/frontend/app.js` to `http://localhost:8000` to use your local
backend. More details are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Adding a new skill graph entry

Skill data lives in `src/passthebot/data/skills/*.yaml`, one file per
category. See the design spec's section 4 ("Data model") for the exact
YAML schema for discrete categories (`aliases`, matched by exact
normalized substring) versus `soft_skills` (`anchor_phrases` +
`embedding_threshold`, matched by embedding similarity).

New entries should generally be added with `status: curated` via a normal
PR. Entries with `status: ai-suggested-pending` are inert. They are loaded but
excluded from matching (see `passthebot.graph.active_entries`) until a
human reviews and flips the status to `ai-suggested-approved`, per the
design spec's human-in-the-loop requirement. CI validates every PR via
`python3 -m passthebot.validate_graph`, which rejects duplicate ids,
invalid categories/statuses, and alias/anchor-phrase collisions across
different ids.

## Contributing

Bug reports, ideas and pull requests are very welcome, especially new
skills for non-tech jobs and German or French terms. Start with
[CONTRIBUTING.md](CONTRIBUTING.md), or just
[open an issue](https://github.com/rfi-irfos/pass-the-bot/issues/new).

## License

[MIT](LICENSE) © RFI-IRFOS
