from passthebot.sections import detect_sections

DE_RESUME_ALL_SECTIONS = """Kontakt
Max Mustermann, max@example.com, +43 000 000000

Erfahrung
Fünf Jahre Erfahrung als Backend-Entwickler bei einer großen Firma mit Fokus auf Python und Datenbanken und Cloud-Infrastruktur und Teamführung und Projektmanagement.

Ausbildung
Bachelor in Informatik von der Universität Wien abgeschlossen im Jahr zweitausendachtzehn mit Auszeichnung und Schwerpunkt Softwaretechnik.

Skills
Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, Kommunikation, Problemlösung, Zeitmanagement, Flexibilität, Lernbereitschaft, Eigeninitiative, Zuverlässigkeit
"""

EN_RESUME_ALL_SECTIONS = """Contact
Jane Doe, jane@example.com

Experience
Five years of experience as a backend developer at a large company focused on Python and databases and cloud infrastructure and team leadership and project management.

Education
Bachelor of Science in Computer Science from State University completed with honors and a focus on software engineering practices.

Skills
Python, Docker, Kubernetes, AWS, PostgreSQL
"""

DE_RESUME_MISSING_SKILLS = """Kontakt
Max Mustermann, max@example.com

Erfahrung
Fünf Jahre Erfahrung als Backend-Entwickler bei einer großen Firma mit Fokus auf Python und Datenbanken.

Ausbildung
Bachelor in Informatik von der Universität Wien.
"""


def test_detects_all_four_sections_in_german_resume():
    results = detect_sections(DE_RESUME_ALL_SECTIONS)
    by_id = {r.id: r for r in results}
    assert set(by_id) == {"contact", "experience", "education", "skills"}
    assert by_id["contact"].found is True
    assert by_id["experience"].found is True
    assert by_id["education"].found is True
    assert by_id["skills"].found is True


def test_detects_all_four_sections_in_english_resume():
    results = detect_sections(EN_RESUME_ALL_SECTIONS)
    assert all(r.found for r in results)


def test_missing_section_reports_found_false_with_zero_word_count():
    results = detect_sections(DE_RESUME_MISSING_SKILLS)
    by_id = {r.id: r for r in results}
    assert by_id["skills"].found is False
    assert by_id["skills"].word_count == 0
    assert by_id["skills"].filled is False


def test_result_order_is_always_contact_experience_education_skills():
    results = detect_sections(DE_RESUME_MISSING_SKILLS)
    assert [r.id for r in results] == ["contact", "experience", "education", "skills"]


def test_section_with_15_words_is_filled():
    # The "Skills" body below has exactly 15 comma-separated items.
    text = (
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, "
        "Kommunikation, Problemloesung, Zeitmanagement, Flexibilitaet, "
        "Lernbereitschaft, Eigeninitiative, Zuverlaessigkeit"
    )
    results = detect_sections(text)
    skills = next(r for r in results if r.id == "skills")
    assert skills.word_count == 15
    assert skills.filled is True


def test_section_with_14_words_is_not_filled():
    text = (
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, "
        "Kommunikation, Problemloesung, Zeitmanagement, Flexibilitaet, "
        "Lernbereitschaft, Eigeninitiative"
    )
    results = detect_sections(text)
    skills = next(r for r in results if r.id == "skills")
    assert skills.word_count == 14
    assert skills.filled is False


def test_heading_detection_is_case_insensitive_and_tolerates_punctuation():
    text = "AUSBILDUNG:\nBachelor in Informatik von der Universitaet Wien."
    results = detect_sections(text)
    education = next(r for r in results if r.id == "education")
    assert education.found is True


def test_resume_with_no_recognizable_headings_returns_all_not_found():
    text = "Just a paragraph of text with no section headings anywhere in it at all."
    results = detect_sections(text)
    assert all(not r.found for r in results)
    assert all(r.word_count == 0 for r in results)
    assert all(not r.filled for r in results)


def test_compound_heading_combining_two_synonyms_is_detected():
    # Real resumes often combine synonyms into one heading line, e.g.
    # "Kernkompetenzen / Skills" -- a strict full-line match would miss
    # this since neither "kernkompetenzen / skills" alone matches any
    # known keyword exactly.
    text = (
        "Kernkompetenzen / Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL, Git, CI/CD, Teamarbeit, "
        "Kommunikation, Problemloesung, Zeitmanagement, Flexibilitaet, "
        "Lernbereitschaft, Eigeninitiative, Zuverlaessigkeit"
    )
    results = detect_sections(text)
    skills = next(r for r in results if r.id == "skills")
    assert skills.found is True
    assert skills.filled is True


def test_contact_without_a_heading_is_detected_via_email_in_header():
    # Many single-page/ATS-style resumes put contact details directly
    # under the name with no "Kontakt"/"Contact" heading at all.
    text = (
        "Jane Doe\n"
        "Senior Backend Engineer\n"
        "Graz, Austria | jane.doe@example.com | linkedin.com/in/janedoe\n"
        "\n"
        "Erfahrung\n"
        "Fünf Jahre Erfahrung als Backend-Entwickler bei einer großen Firma mit Fokus auf Python."
    )
    results = detect_sections(text)
    contact = next(r for r in results if r.id == "contact")
    assert contact.found is True
    assert contact.word_count > 0


def test_contact_stays_not_found_when_no_email_appears_near_the_top():
    text = "Just a paragraph of text with no section headings and no email address anywhere."
    results = detect_sections(text)
    contact = next(r for r in results if r.id == "contact")
    assert contact.found is False
