# passthebot Web App — Candidate Checker (Frontend + Backend) Design

**Status:** Draft, pending user review
**Scope:** This spec covers the free, public-facing candidate checker: a static
frontend (GitHub Pages) plus a small FastAPI backend (Fly.io) that wraps the
already-built `passthebot` matching engine and adds PDF/DOCX text extraction.
The KMU/business decision-support agent is a separate, later sub-project and
is explicitly out of scope here (per the engine design spec's section 9).

## 1. Problem

The matching engine (see `2026-09-14-matching-engine-design.md`) is a Python
library with no UI. This spec builds the thing a job-seeker actually uses:
upload a CV, paste a job posting, get a score and a clear breakdown of what
matched, what's close, and what's missing — free, no artificial caps, no
resume-building/editing features (that's explicitly what distinguishes this
from competitors like Enhancv, see `docs/notes/candidate-checker-frontend-ideas.md`).

## 2. Users

Job seekers, self-service, no login. Single free-form tool: upload once, get
one report, no account, no history (V1 — accounts/history are out of scope).

## 3. Architecture

Two independently deployable pieces:

1. **Frontend** (`web/frontend/`) — a single static page (plain HTML/CSS/JS,
   Tailwind via CDN, no build step). Deployed to **GitHub Pages**. Contains:
   a textarea for pasting the job posting, a file input for the resume
   (PDF/DOCX), a submit button, and a results area that renders the score
   and per-skill breakdown returned by the backend.
2. **Backend** (`web/backend/`) — a small FastAPI app. Deployed to **Fly.io**.
   Exposes one endpoint, `POST /api/check`, that:
   - Accepts a multipart request: `resume_file` (PDF or DOCX) + `posting_text`
     (plain text).
   - Extracts plain text from the resume file (PDF via `pypdf`, DOCX via
     `python-docx`).
   - Calls `passthebot.pipeline.run_pipeline(posting_text, resume_text,
     required_ids, data_dir=None, repo_root=None)` — the engine is a local
     dependency of this backend (same repo, `web/backend/pyproject.toml`
     depends on the `passthebot` package via a relative/editable reference).
   - Returns the engine's JSON report directly as the HTTP response body.
   - Enables CORS for the GitHub Pages origin (and `localhost` for local
     dev) so the static frontend can call it cross-origin.

The frontend never talks to the engine directly — only to the backend's one
API endpoint. This is the whole integration surface.

## 4. The `required_ids` question

`run_pipeline` requires the caller to supply which posting-side skill IDs
count as "required" (see the engine's own deferred "Next steps": automatic
required-vs-optional detection from posting text was never built). A
real user cannot be expected to name skill IDs manually.

**V1 resolution:** treat every skill ID extracted from the posting text as
required. This matches the engine design spec's own stated fallback
behavior for when no required/optional signal exists ("defaulting to
required: true when no signal is found") — it is not a new heuristic, it's
the existing spec's default applied uniformly. Concretely: extract posting
keywords first (same extraction the engine already does internally), pass
`required_ids = {kw.id for kw in posting_keywords}` into `run_pipeline`.
This requires calling the extraction step once from the backend before
calling `run_pipeline` — acceptable duplication for V1; a future engine
change that returns extracted-posting-keywords as part of `run_pipeline`'s
own contract would remove the need for this, but that's a matching-engine
sub-project concern, not this one's.

## 5. API contract

**`POST /api/check`**
- Request: `multipart/form-data` with fields `resume_file` (file, PDF or
  DOCX) and `posting_text` (string).
- Response `200`: the engine's report JSON (see engine spec section 6),
  unmodified — `{engine_version, graph_version, model_version, results,
  score}`.
- Response `400`: `{"error": "<message>"}` for empty/unreadable resume file,
  empty posting text, or unsupported file type (echoes `PipelineInputError`
  and extraction failures as a clear client-facing message, never a raw
  stack trace).
- Response `413`: file too large (enforce a size limit, e.g. 5MB, to bound
  memory/processing cost on a free public endpoint).

## 6. Frontend behavior

- On submit: disable the button, show a loading state, POST to the backend
  URL (configured via a single JS constant, pointing at the Fly.io app URL).
- On success: render the score prominently (e.g. "18 / 24 required skills
  matched — 75%"), then three sections: Matched, Near-miss (once NEAR_MISS
  is wired into the engine — until then, this section stays empty/hidden,
  not fake data), Missing. Each skill shown with its display name (from the
  report — note: the engine's own report doesn't currently include display
  names, only IDs, see section 8 below for what this spec adds).
- On error: show the backend's error message plainly, no generic "something
  went wrong."
- No login, no persistence, no "save your report" — matches the diagnostic-
  only, no-friction design brief from `candidate-checker-frontend-ideas.md`.

## 7. Error handling / edge cases

- Backend must catch extraction failures (corrupt/password-protected PDF,
  unsupported format) and return a clear 400, never a 500 with a stack
  trace leaking file paths.
- Backend must enforce the file-size limit before attempting extraction
  (reject early, don't load an arbitrarily large file into memory first).
- CORS must be scoped to the actual GitHub Pages origin and localhost, not
  a wildcard `*`, so the API isn't trivially embeddable/scrapeable from
  arbitrary third-party sites.

## 8. A real gap this spec surfaces: report has no human-readable display names

The engine's report (section 6 of the engine spec) only includes each
result's canonical `id` (e.g. `"nodejs"`), not the skill graph entry's
`display` field (e.g. `{"de": "Node.js", "en": "Node.js"}"`). A frontend
cannot render a sensible UI from bare IDs like `"nodejs"` vs `"nodejs_ts"`
if such IDs were ever non-obvious. Resolution: the backend, which already
has access to the loaded skill graph (it calls `run_pipeline`, which loads
`active_entries` internally), additionally builds a small `id -> display`
lookup dict from the graph and enriches the report's `results` list with a
`display_name` field (language: `en`, matching this frontend's language,
see section 9) before returning it to the frontend. This is a backend-side
enrichment step, not a change to the engine's own JSON contract — the
engine stays exactly as specified; the web backend adds one field per
result before handing the JSON to the browser.

## 9. Language

V1 ships in English only (frontend copy + `display_name` field). The skill
graph already carries `de`/`en` display names per entry (per the engine's
own data model), so adding German later is a frontend-copy-and-`lang`-query-
param change, not a backend or engine change — deliberately deferred, not
built now (YAGNI).

## 10. Testing strategy

- Backend: unit tests for the extraction step (a real small PDF and a real
  small DOCX fixture, not mocked), and an integration test for
  `POST /api/check` using FastAPI's `TestClient` against the real engine
  (no mocking of `run_pipeline` — this is the whole point of the endpoint).
- Frontend: manual verification (upload a real resume, paste a real
  posting, confirm the rendered result) — no frontend test framework for
  a single static page with no build step; this is proportionate to scope,
  not a corner cut.

## 11. Explicitly out of scope for this spec

- Accounts, login, saved history.
- The KMU/business decision-support agent and its dashboard.
- NEAR_MISS rendering (the engine doesn't produce it yet; the frontend's
  Near-miss section stays empty until the engine's matcher is extended).
- Multi-language UI (English only, see section 9).
- Rate limiting / abuse prevention beyond the file-size cap (acceptable
  initial risk for a free public tool with no state; revisit if abused).
