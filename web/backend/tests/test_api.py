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


def test_check_returns_open_origin_result_with_literal_phrase_display_name():
    """An open-vocabulary requirement (not in the curated skill catalog) has
    no display-name lookup entry, so add_display_names's fallback path must
    kick in and use the literal phrase text as its own display_name -- this
    exercises that fallback through a real API response, not just a manual
    pipeline run."""
    pdf_path = FIXTURES / "api_test_resume_open.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Five years of experience welding steel frames.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "Requirements\n- Welding experience\n"},
        )

    assert response.status_code == 200
    body = response.json()
    welding_result = next(r for r in body["results"] if r["origin"] == "open")
    assert welding_result["id"] == "Welding experience"
    assert welding_result["display_name"] == "Welding experience"


def test_check_rejects_unsupported_file_type():
    response = client.post(
        "/api/check",
        files={"resume_file": ("resume.txt", b"plain text resume", "text/plain")},
        data={"posting_text": "Python is required."},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_check_reads_posting_from_a_pasted_link(monkeypatch):
    """A link in the posting field is fetched first (network mocked here,
    see test_fetch_posting.py) and the report says where the text came
    from."""
    from app import main
    from app.fetch_posting import PostingSource

    def fake_fetch(url):
        return PostingSource(
            url=url.strip(), host="jobs.example.com", title="Python Dev", company="ACME",
            method="jsonld", text="Python Dev\nPython is required for this role.",
        )

    monkeypatch.setattr(main, "fetch_posting", fake_fetch)
    pdf_path = FIXTURES / "api_test_resume_link.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": " https://jobs.example.com/123 "},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["posting_source"]["host"] == "jobs.example.com"
    assert body["posting_source"]["chars"] == len("Python Dev\nPython is required for this role.")
    assert next(r for r in body["results"] if r["id"] == "python")["status"] == "MATCH"


def test_check_explains_an_unreadable_link_in_the_requested_language(monkeypatch):
    from app import main
    from app.fetch_posting import PostingFetchError

    def fake_fetch(url):
        raise PostingFetchError("unreadable")

    monkeypatch.setattr(main, "fetch_posting", fake_fetch)
    pdf_path = FIXTURES / "api_test_resume_link2.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "https://careers.example.com/job/1", "lang": "de"},
        )

    assert response.status_code == 400
    assert "Text der Stellenanzeige" in response.json()["detail"]


def test_check_returns_no_score_when_posting_has_no_requirements():
    pdf_path = FIXTURES / "api_test_resume_noscore.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "We are a friendly company in Graz."},
        )

    assert response.status_code == 200
    assert response.json()["score"]["coverage_pct"] is None


def test_check_says_an_expired_link_is_no_longer_online(monkeypatch):
    from app import main
    from app.fetch_posting import PostingFetchError

    def fake_fetch(url):
        raise PostingFetchError("gone", "HTTP 410")

    monkeypatch.setattr(main, "fetch_posting", fake_fetch)
    pdf_path = FIXTURES / "api_test_resume_link3.pdf"
    FIXTURES.mkdir(exist_ok=True)
    _make_resume_pdf(pdf_path, "Experienced Python developer.")

    with pdf_path.open("rb") as f:
        response = client.post(
            "/api/check",
            files={"resume_file": ("resume.pdf", f, "application/pdf")},
            data={"posting_text": "https://careers.example.com/job/2", "lang": "en"},
        )

    assert response.status_code == 400
    assert "no longer online" in response.json()["detail"]
