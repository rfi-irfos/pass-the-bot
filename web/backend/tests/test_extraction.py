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


# --- limits against small files that expand into huge work ----------------------


def _docx_with_xml_of(size_bytes: int) -> bytes:
    """A valid DOCX whose document.xml is `size_bytes` of repeated paragraphs.
    Deflate shrinks that to a few hundred KB, like a real zip bomb."""
    import io
    import zipfile

    base = io.BytesIO()
    document = Document()
    document.add_paragraph("Python")
    document.save(base)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base.getvalue())) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            data = zin.read(name)
            if name == "word/document.xml":
                head, tail = data.split(b"<w:body>")
                end = tail.rindex(b"</w:body>")
                filler = b"<w:p><w:r><w:t>a</w:t></w:r></w:p>"
                marker = b"<w:p><w:r><w:t>Python</w:t></w:r></w:p>"
                data = head + b"<w:body>" + marker + filler * (size_bytes // len(filler)) + tail[end:]
            zout.writestr(name, data)
    return out.getvalue()


def test_docx_zip_bomb_is_rejected_before_it_is_parsed():
    import time

    raw = _docx_with_xml_of(40 * 1024 * 1024)
    assert len(raw) < 1024 * 1024  # small upload, huge content
    started = time.monotonic()
    with pytest.raises(ExtractionError, match="too large"):
        extract_text(raw, "bomb.docx")
    assert time.monotonic() - started < 2  # header check only, nothing unpacked


def test_docx_of_normal_size_still_works():
    assert "Python" in extract_text(_docx_with_xml_of(200 * 1024), "ok.docx")


def test_pdf_with_too_many_pages_is_rejected():
    from app.extraction import MAX_PDF_PAGES

    path = FIXTURES / "many_pages.pdf"
    c = canvas.Canvas(str(path))
    for i in range(MAX_PDF_PAGES + 1):
        c.drawString(100, 750, f"Page {i} Python")
        c.showPage()
    c.save()
    with pytest.raises(ExtractionError, match="more than"):
        extract_text(path.read_bytes(), "long.pdf")


def test_resume_with_too_much_text_is_rejected(monkeypatch):
    monkeypatch.setattr("app.extraction.MAX_RESUME_CHARS", 20)
    with pytest.raises(ExtractionError, match="too much text"):
        extract_text((FIXTURES / "sample_resume.pdf").read_bytes(), "r.pdf")
