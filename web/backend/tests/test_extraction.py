from pathlib import Path

import pytest
from docx import Document
from reportlab.pdfgen import canvas

from app.extraction import ExtractionError, extract_text

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def build_fixtures():
    """Generate real, tiny PDF/DOCX fixtures once (not mocked/hand-crafted
    binary blobs) so extract_text is tested against genuinely valid files."""
    FIXTURES.mkdir(exist_ok=True)

    pdf_path = FIXTURES / "sample_resume.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Experienced Python developer with Docker skills.")
    c.save()

    docx_path = FIXTURES / "sample_resume.docx"
    document = Document()
    document.add_paragraph("Experienced Python developer with Docker skills.")
    document.save(docx_path)

    empty_pdf_path = FIXTURES / "empty.pdf"
    c = canvas.Canvas(str(empty_pdf_path))
    c.save()

    yield


def test_extract_text_from_pdf():
    raw = (FIXTURES / "sample_resume.pdf").read_bytes()
    text = extract_text(raw, "sample_resume.pdf")
    assert "Python" in text
    assert "Docker" in text


def test_extract_text_from_docx():
    raw = (FIXTURES / "sample_resume.docx").read_bytes()
    text = extract_text(raw, "sample_resume.docx")
    assert "Python" in text
    assert "Docker" in text


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(ExtractionError, match="Unsupported file type"):
        extract_text(b"not a real file", "resume.txt")


def test_extract_text_rejects_corrupt_pdf():
    with pytest.raises(ExtractionError, match="Could not read this PDF"):
        extract_text(b"this is not a valid pdf file at all", "resume.pdf")


def test_extract_text_rejects_empty_pdf():
    raw = (FIXTURES / "empty.pdf").read_bytes()
    with pytest.raises(ExtractionError, match="No readable text"):
        extract_text(raw, "empty.pdf")


def test_extract_text_rejects_corrupt_docx():
    with pytest.raises(ExtractionError, match="Could not read this DOCX"):
        extract_text(b"this is not a valid docx file at all", "resume.docx")
