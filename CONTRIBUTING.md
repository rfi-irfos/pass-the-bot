# Contributing to Pass The Bot!

Thanks for wanting to help. Pass The Bot is a free, open-source tool that
shows job seekers how an Applicant Tracking System (ATS) reads their resume.
Every bug report, idea and pull request makes it better for people who are
trying to get hired.

## Ways to help

- **Report a bug.** Open an [issue](https://github.com/rfi-irfos/pass-the-bot/issues/new)
  and describe what you did, what you expected and what you saw. A job
  posting link or text that reproduces the problem helps the most.
  Please **don't attach your real resume**; describe it or use a made-up one.
- **Suggest an idea.** Open an issue and tell us what problem it solves for
  job seekers.
- **Add or fix skills.** Missing a skill, alias or soft skill? That is the
  easiest place to start (see [Adding skills](#adding-skills)).
- **Pick up an issue.** Issues labelled
  [`good first issue`](https://github.com/rfi-irfos/pass-the-bot/labels/good%20first%20issue)
  or [`help wanted`](https://github.com/rfi-irfos/pass-the-bot/labels/help%20wanted)
  are a good start. Leave a comment so nobody does the same work twice.

## Project layout

| Path | What it is |
|---|---|
| `src/passthebot/` | The matching engine (skill graph, keyword extraction, fuzzy near-misses, scoring) |
| `src/passthebot/data/skills/*.yaml` | The skill graph, one file per category |
| `tests/` | Engine tests |
| `web/backend/` | FastAPI service: file upload, link reading, wraps the engine |
| `web/frontend/` | Static frontend, no build step (`index.html` + `app.js`) |
| `docs/` | Design specs and notes |

## Local setup

You need Python 3.11+.

```bash
git clone https://github.com/rfi-irfos/pass-the-bot.git
cd pass-the-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # engine
pip install -e "web/backend[dev]"  # web backend
```

The first run downloads a small sentence-embedding model for soft-skill
matching, so it takes a moment.

### Run the tests

```bash
python3 -m passthebot.validate_graph   # skill graph checks
pytest -q                              # engine tests
cd web/backend && pytest -q            # backend tests
```

CI runs the same three commands on every push and pull request.

### Run the web app

```bash
# Backend
uvicorn app.main:app --app-dir web/backend --reload --port 8000

# Frontend, in a second terminal
cd web/frontend && python3 -m http.server 5500
```

The frontend talks to the live API by default. To use your local backend,
temporarily change the first line of `web/frontend/app.js` to
`const API_BASE_URL = "http://localhost:8000";` and don't commit that change.

## Adding skills

Skills live in `src/passthebot/data/skills/*.yaml`. The schema is described
in section 4 ("Data model") of
`docs/superpowers/specs/2026-09-14-matching-engine-design.md`.

- Discrete skills (programming languages, tools, certifications, spoken
  languages, ...) are matched by
  their `aliases`.
- Soft skills are matched by meaning, using `anchor_phrases` and an
  `embedding_threshold`.
- Add new entries with `status: curated`. Entries marked
  `ai-suggested-pending` are ignored until a human reviews them.
- Run `python3 -m passthebot.validate_graph` before you open the PR. It
  rejects duplicate ids and aliases that collide with another skill.

Skills outside tech (finance, marketing, healthcare, trades) and German or
French terms are especially welcome. `tests/data/postings/` holds labelled
example postings; `python3 scripts/measure_postings.py` shows how many of
their skills are found, and `python3 scripts/measure_soft_skills.py` does the
same for soft skills. Add a posting with a `.expected.yaml` file when you add
skills for a new field (write it yourself, don't copy a real ad).

## Pull requests

1. Fork the repo and create a branch from `master`.
2. Keep the change focused: one fix or feature per PR.
3. Add or update tests for engine and backend changes.
4. Make sure the tests above pass.
5. Use [Conventional Commits](https://www.conventionalcommits.org/) for
   commit messages and the PR title, for example
   `fix: stop matching "Java" inside "JavaScript"` or
   `feat: add accounting skills`.
6. In the PR description, say what changed, why, and how you tested it.
   Link the issue with `Closes #123`. Add a screenshot for UI changes.

A maintainer reviews every PR. Small, well-described PRs get merged fastest.

## Ground rules

These keep the promises the tool makes to its users:

- **No user data is stored.** Resumes and postings are processed for one
  check and then discarded. No logging of their content, no tracking, no
  cookies. Features that need to store anything must be discussed in an
  issue first.
- **Explainable, not a black box.** Matching decisions must be traceable to
  the skill graph or a documented rule. No LLM decides whether a skill matches.
- **Safe with third-party content.** Text from uploaded files or fetched job
  pages is inserted into the page with `textContent`, never `innerHTML`.
  Link fetching goes through `web/backend/app/fetch_posting.py`, which blocks
  private and internal addresses. Keep it that way.
- **German and English.** Every user-facing string in the frontend exists in
  both languages.
- **No new dependencies without a reason.** Explain in the PR why it is needed.

## Security issues

Please don't open a public issue for security problems. Email
**security@rfi-irfos.com** instead, and we'll get back to you.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE) of this project.
