"""Extracts plain text from an uploaded resume file (PDF or DOCX).

This lives in the web backend, not the matching engine, per the engine's
design spec section 9 ("PDF/DOCX text extraction" is explicitly out of
scope for the engine itself -- the engine only ever consumes plain text).
"""

from __future__ import annotations

import io
import zipfile

import pypdf
from docx import Document


# A real resume is a few pages and well under a megabyte of XML. These limits
# stop small files that expand into huge work: a 185 KB DOCX with 50 MB of XML
# took 60 s and 1 GB of memory to parse (measured on the Colony).
MAX_PDF_PAGES = 30
MAX_DOCX_XML_BYTES = 8 * 1024 * 1024
MAX_DOCX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_DOCX_MEMBERS = 1000
MAX_RESUME_CHARS = 150_000


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
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError(
                f"This PDF has more than {MAX_PDF_PAGES} pages. Please upload your resume as a shorter file."
            )
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("Could not read this PDF file. It may be corrupt.") from exc

    if not text.strip():
        raise ExtractionError("No readable text found in this PDF (it may be a scanned image).")
    return _limit_text(text)


def _check_docx_size(raw: bytes) -> None:
    """Rejects zip bombs from the headers alone, before any content is
    unpacked. Declared sizes are reliable: zipfile never reads past them."""
    try:
        members = zipfile.ZipFile(io.BytesIO(raw)).infolist()
    except zipfile.BadZipFile as exc:
        raise ExtractionError("Could not read this DOCX file. It may be corrupt.") from exc
    xml_bytes = sum(m.file_size for m in members if m.filename.endswith((".xml", ".rels")))
    total_bytes = sum(m.file_size for m in members)
    if len(members) > MAX_DOCX_MEMBERS or xml_bytes > MAX_DOCX_XML_BYTES or total_bytes > MAX_DOCX_TOTAL_BYTES:
        raise ExtractionError("This DOCX file is too large to process. Please upload a normal resume.")


def _limit_text(text: str) -> str:
    if len(text) > MAX_RESUME_CHARS:
        raise ExtractionError("This resume contains too much text to process. Please upload a normal resume.")
    return text


def _extract_docx(raw: bytes) -> str:
    _check_docx_size(raw)
    try:
        document = Document(io.BytesIO(raw))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise ExtractionError("Could not read this DOCX file. It may be corrupt.") from exc

    if not text.strip():
        raise ExtractionError("No readable text found in this DOCX file.")
    return _limit_text(text)
