"""FastAPI backend for the passthebot candidate checker (web app design spec).

One endpoint: POST /api/check. Accepts a resume file (PDF/DOCX) + posting
text, extracts the resume text, runs the real matching engine, enriches the
report with human-readable display names, and returns it as-is. If the
posting field holds a single link instead of text, the posting is fetched
from that page first (app/fetch_posting.py) and the report gains a
posting_source field describing where the text came from.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from passthebot.embeddings import Embedder
from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.pipeline import PipelineInputError, run_pipeline

from .enrichment import add_display_names
from .extraction import ExtractionError, extract_text
from .fetch_posting import PostingFetchError, fetch_posting, looks_like_url

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB, bounds memory/processing on a free public endpoint
# Whole request incl. multipart framing and the posting field. Enforced while
# the body streams in, before Starlette spools it to memory or disk.
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 512 * 1024
# Real postings are under ~15k characters. Pipeline time grows with length:
# 20k chars took 1 s, 400k chars 9 s while holding one of two pipeline slots.
MAX_POSTING_CHARS = 40_000

app = FastAPI(title="passthebot web backend")

# Loaded once at process startup and reused across requests -- without this,
# run_pipeline's `embedder or Embedder()` default reloads the sentence-
# transformers model from disk on every single request (~3-15s each).
EMBEDDER = Embedder()

# The Fly machine backing this service has 2 vCPUs (scaled up 2026-09-29
# after a single-vCPU machine got OOM-killed and starved under real traffic).
# Two concurrent /api/check calls each spend real wall-clock time in
# CPU-bound embedding inference; with only one vCPU, running them together
# starves the event loop's own thread of CPU for long enough that the health
# check GET times out, and Fly's edge proxy then rejects incoming
# connections -- including unrelated ones -- until the machine reports
# healthy again. With 2 vCPUs there's a real second core to absorb this, so
# the limit matches the machine's own concurrency headroom instead of
# serializing every request through a single core.
PIPELINE_CONCURRENCY = asyncio.Semaphore(2)

_FETCH_ERROR_MESSAGES = {
    "de": {
        "gone": "Diese Stellenanzeige ist nicht mehr online. Falls du den Text noch hast, füge ihn bitte direkt ein.",
        "unreadable": "Diese Seite konnten wir nicht auslesen (sie lädt die Anzeige erst im Browser). Bitte kopiere den Text der Stellenanzeige und füge ihn ein.",
        "timeout": "Die Seite hat zu lange nicht geantwortet. Bitte füge den Text der Stellenanzeige direkt ein.",
        "unsafe_url": "Dieser Link kann nicht geladen werden. Bitte füge einen öffentlichen Link zur Stellenanzeige oder ihren Text ein.",
        "default": "Die Seite konnte nicht geladen werden. Bitte füge den Text der Stellenanzeige direkt ein.",
    },
    "en": {
        "gone": "This job posting is no longer online. If you still have its text, please paste it instead.",
        "unreadable": "We couldn't read this page (it only loads the posting in the browser). Please copy the posting's text and paste it instead.",
        "timeout": "The page took too long to respond. Please paste the posting's text instead.",
        "unsafe_url": "This link can't be loaded. Please paste a public link to the posting, or its text.",
        "default": "The page couldn't be loaded. Please paste the posting's text instead.",
    },
}


_POSTING_TOO_LONG = {
    "en": f"The posting is too long (more than {MAX_POSTING_CHARS:,} characters). Please paste only the job description.",
    "de": f"Die Anzeige ist zu lang (mehr als {MAX_POSTING_CHARS:_} Zeichen). Bitte füge nur die Stellenbeschreibung ein.".replace("_", "."),
}


def _fetch_error_message(code: str, lang: str) -> str:
    messages = _FETCH_ERROR_MESSAGES.get(lang, _FETCH_ERROR_MESSAGES["en"])
    return messages.get(code, messages["default"])

class BodyLimitMiddleware:
    """Answers 413 as soon as the request body exceeds `max_bytes`: by the
    Content-Length header when there is one, otherwise while counting the
    streamed chunks. Without it the whole upload is read before any size
    check runs (150 MB upload: +450 MB RSS in the probe).

    On overflow the 413 is sent right away and the app sees a disconnect.
    Raising from `receive` would not work: FastAPI turns every body-parsing
    exception into a 400."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await self._reject(send)
                return

        received = 0
        rejected = False

        async def limited_receive():
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    await self._reject(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message) -> None:
            if not rejected:
                await send(message)

        await self.app(scope, limited_receive, guarded_send)

    @staticmethod
    async def _reject(send) -> None:
        body = b'{"detail":"The upload exceeds the 5MB limit."}'
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})


# Added before CORS so CORS stays outermost and 413 answers carry its headers.
app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
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
async def check(
    resume_file: UploadFile = File(...),
    posting_text: str = Form(...),
    lang: str = Form("en"),
) -> dict:
    raw = await resume_file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="resume_file exceeds the 5MB limit.")

    try:
        # CPU-bound parsing: off the event loop so /health keeps answering.
        resume_text = await run_in_threadpool(extract_text, raw, resume_file.filename or "")
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    posting_source = None
    if looks_like_url(posting_text):
        # Network I/O, deliberately outside PIPELINE_CONCURRENCY: a slow
        # page must not hold one of the two embedding slots.
        try:
            posting_source = await run_in_threadpool(fetch_posting, posting_text)
        except PostingFetchError as exc:
            status = 504 if exc.code == "timeout" else 400
            raise HTTPException(status_code=status, detail=_fetch_error_message(exc.code, lang)) from exc
        posting_text = posting_source.text

    if len(posting_text) > MAX_POSTING_CHARS:
        raise HTTPException(status_code=400, detail=_POSTING_TOO_LONG.get(lang, _POSTING_TOO_LONG["en"]))

    try:
        # Offload the CPU-bound embedding computation to a worker thread so
        # it doesn't block the event loop for the request's duration -- an
        # async endpoint that ran this inline previously starved concurrent
        # requests (e.g. the health check) for several seconds at a time.
        async with PIPELINE_CONCURRENCY:
            report = await run_in_threadpool(run_pipeline, posting_text, resume_text, embedder=EMBEDDER)
    except PipelineInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = active_entries(load_skill_graph(DEFAULT_DATA_DIR))
    report = add_display_names(report, entries, lang=lang)
    if posting_source is not None:
        report["posting_source"] = posting_source.to_dict()
    return report
