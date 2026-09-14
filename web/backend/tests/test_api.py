from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


def _make_resume_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path))
    c.drawString(100, 750, text)
    c.save()


def test_check_returns_real_report_with_display_names():
    """Integration test against the REAL engine (run_pipeline is not mocked)
    -- this is the whole point of this endpoint."""
    pdf_path = FIXTURES / "api_test_resume.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "Python is required for this role."},
        )

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "score" in body
    python_result = next(r for r in body["results"] if r["id"] == "python")
    assert python_result["status"] == "MATCH"
    assert python_result["display_name"] == "Python"


def test_check_returns_german_display_names_when_lang_is_de():
    pdf_path = FIXTURES / "api_test_resume_de.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Strong communication and teamwork skills.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "Good communication skills required.", "lang": "de"},
        )

    assert response.status_code == 200
    body = response.json()
    communication_result = next(r for r in body["results"] if r["id"] == "communication")
    assert communication_result["display_name"] == "Kommunikationsfähigkeit"


def test_check_rejects_empty_posting_text():
    pdf_path = FIXTURES / "api_test_resume2.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "   "},
        )

    assert response.status_code == 400
    assert "posting_text" in response.json()["detail"]


def test_check_rejects_oversized_file():
    oversized = b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024)
    response = client.post(
        "/api/check",
        files={"resume_file": ("resume.pdf", oversized, "application/pdf")},
        data={"posting_text": "Python is required."},
    )
    assert response.status_code == 413


def test_check_rejects_unsupported_file_type():
    response = client.post(
        "/api/check",
        files={"resume_file": ("resume.txt", b"plain text resume", "text/plain")},
        data={"posting_text": "Python is required."},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
