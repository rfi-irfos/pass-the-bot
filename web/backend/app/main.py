"""FastAPI backend for the passthebot candidate checker (web app design spec).

One endpoint: POST /api/check. Accepts a resume file (PDF/DOCX) + posting
text, extracts the resume text, runs the real matching engine, enriches the
report with human-readable display names, and returns it as-is.
"""

from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from passthebot.embeddings import Embedder
from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.pipeline import PipelineInputError, run_pipeline

from .enrichment import add_display_names
from .extraction import ExtractionError, extract_text

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB, bounds memory/processing on a free public endpoint

app = FastAPI(title="passthebot web backend")

# Loaded once at process startup and reused across requests -- without this,
# run_pipeline's `embedder or Embedder()` default reloads the sentence-
# transformers model from disk on every single request (~3-15s each).
EMBEDDER = Embedder()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rfi-irfos.github.io",
        "http://localhost:8000",
        "http://localhost:5500",
    ],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/api/check")
def check(
    resume_file: UploadFile = File(...),
    posting_text: str = Form(...),
    lang: str = Form("en"),
) -> dict:
    # A plain (non-async) endpoint: FastAPI runs it in a threadpool instead
    # of on the event loop, so the CPU-bound embedding computation in
    # run_pipeline doesn't block other requests (e.g. the health check) for
    # the duration of the analysis. UploadFile.read() is async-only, so read
    # the underlying SpooledTemporaryFile directly.
    raw = resume_file.file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="resume_file exceeds the 5MB limit.")

    try:
        resume_text = extract_text(raw, resume_file.filename or "")
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        report = run_pipeline(posting_text, resume_text, embedder=EMBEDDER)
    except PipelineInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = active_entries(load_skill_graph(DEFAULT_DATA_DIR))
    return add_display_names(report, entries, lang=lang)
