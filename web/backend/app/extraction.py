"""Extracts plain text from an uploaded resume file (PDF or DOCX).

This lives in the web backend, not the matching engine, per the engine's
design spec section 9 ("PDF/DOCX text extraction" is explicitly out of
scope for the engine itself -- the engine only ever consumes plain text).
"""

from __future__ import annotations

import io

import pypdf
from docx import Document


class ExtractionError(Exception):
    """Raised when a resume file cannot be parsed into plain text (corrupt,
    password-protected, or an unsupported format)."""


def extract_text(raw: bytes, filename: str) -> str:
    """Extract plain text from raw file bytes, dispatching on the filename's
    extension. Raises ExtractionError with a client-facing message on any
    failure -- never lets a raw parser exception (stack trace, file paths)
    propagate to the API layer.
    """
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return _extract_pdf(raw)
    if lower_name.endswith(".docx"):
        return _extract_docx(raw)
    raise ExtractionError(
        f"Unsupported file type for '{filename}'. Please upload a PDF or DOCX file."
    )


def _extract_pdf(raw: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise ExtractionError("This PDF is password-protected and cannot be read.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("Could not read this PDF file. It may be corrupt.") from exc

    if not text.strip():
        raise ExtractionError("No readable text found in this PDF (it may be a scanned image).")
    return text


def _extract_docx(raw: bytes) -> str:
    try:
        document = Document(io.BytesIO(raw))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise ExtractionError("Could not read this DOCX file. It may be corrupt.") from exc

    if not text.strip():
        raise ExtractionError("No readable text found in this DOCX file.")
    return text
