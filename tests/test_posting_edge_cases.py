"""Posting shapes that broke or could break requirement detection, one line
per shape. Each row states which level a skill must end up on."""

import pytest

from passthebot.graph import SkillEntry
from passthebot.normalizer import ExtractedKeyword, extract_discrete_keywords, extract_open_requirements
from passthebot.requirement import classify_importance


def _level(posting: str, text: str = "Docker") -> str:
    kw = ExtractedKeyword(id="x", category="tools", matched_text=text, confidence=1.0, mentions=[text])
    return classify_importance(posting, [kw])["x"].level


@pytest.mark.parametrize(
    "posting, expected",
    [
        # section decides
        ("Requirements\n- Docker\n", "required"),
        ("**Requirements**\n- Docker\n", "required"),
        ("### Must-haves ###\n- Docker\n", "required"),
        ("🎯 MUST-HAVES:\n- Docker\n", "required"),
        ("Must-haves for this role\n- Docker\n", "required"),
        ("- Must-haves\n  - Docker\n", "required"),
        ("Dein Profil\nDocker\n", "required"),
        ("Was du mitbringst\n- Docker\n", "required"),
        ("Exigences\n- Docker\n", "required"),
        ("What we’re looking for\n- Docker\n", "required"),
        ("What you’ll bring\n- Docker\n", "required"),
        ("Qualifikation\n- Docker\n", "required"),
        ("Wat breng je mee?\n- Docker\n", "required"),
        ("Nice-to-haves\n- Docker\n", "optional"),
        ("Nice to have (bonus)\n- Docker\n", "optional"),
        ("An ideal candidate also has\n- Docker\n", "optional"),
        ("**Nice to have:**\n- Docker\n", "optional"),
        ("Requirements\n- Python\nPreferred\n- Docker\n", "optional"),
        ("Preferred qualifications\n- Docker\n", "optional"),
        ("Good to have\n- Docker\n", "optional"),
        ("Pluspunkte\n- Docker\n", "optional"),
        ("Von Vorteil wäre\n- Docker\n", "optional"),
        ("Idealerweise bringst du mit\n- Docker\n", "optional"),
        ("Atouts\n- Docker\n", "optional"),
        # work the job actually involves
        ("Requirements\n- Python\nResponsibilities\n- Run Docker\n", "task"),
        ("Deine Aufgaben\n- Docker betreuen\n\nDein Profil\n- Python\n", "task"),
        ("What you'll be doing\n- Run Docker\n\nRequirements\n- Python\n", "task"),
        ("Das machst du\n- Docker betreuen\n\nDein Profil\n- Python\n", "task"),
        ("What you’ll do\n- Run Docker\n\nRequirements\n- Python\n", "task"),
        ("In this role, you will\n- Run Docker\n\nRequirements\n- Python\n", "task"),
        # company talk, wherever it stands
        ("Our investors love Docker.\n\nRequirements\n- Python\n", "mentioned"),
        ("Requirements\n- Python\nAbout Acme\nAcme built Docker.\n", "mentioned"),
        ("Requirements\n- Python\nWho we are\nWe built Docker.\n", "mentioned"),
        ("Requirements\n- Python\nBenefits\n- Docker stickers\n", "mentioned"),
        ("Requirements\n- Python\nIndustries\nDocker\n", "mentioned"),
        ("Requirements\n- Python\nSimilar jobs\nDocker Engineer\n", "mentioned"),
        ("Requirements\n- Python\nInterview process\n- Docker quiz\n", "mentioned"),
        ("Requirements\n- Python\nThis role is not for\n- Docker fans\n", "mentioned"),
        # the sentence itself outranks the section
        ("Requirements\n- Docker would be a plus\n", "optional"),
        ("Requirements\n- Ideally Docker\n", "optional"),
        ("Requirements\n- Docker preferred\n", "optional"),
        ("About us\nYou must know Docker.\n\nRequirements\n- Python\n", "required"),
        # negated signals say the opposite of the bare word
        ("Docker ist von Vorteil, aber kein Muss.", "optional"),
        ("Requirements\n- Docker is not required\n", "optional"),
        ("Dein Profil\n- Docker nicht zwingend erforderlich\n", "optional"),
        ("Requirements\n- Docker: keine Voraussetzung\n", "optional"),
        # a signal in another clause of the sentence belongs to that clause
        ("Requirements\n- Python required, Docker a plus\n", "optional"),
        ("Requirements\n- Docker required, Python a plus\n", "required"),
        ("Python, Docker and SQL are required.", "required"),
        ("Nice to have: React, Docker, and SQL.", "optional"),
        # words that merely contain a signal
        ("Requirements\n- Python\nAbout us\nPflichtbewusstes Docker-Team.\n", "mentioned"),
        ("Requirements\n- Python\nAbout us\nA surplus of Docker.\n", "mentioned"),
        ("Requirements\n- Python\nAbout us\nOur requirements-free Docker.\n", "mentioned"),
        # no structure at all: documented default
        ("We run Docker in production.", "required"),
        ("Docker is nice to have.", "optional"),
    ],
)
def test_level_by_posting_shape(posting, expected):
    assert _level(posting) == expected


def test_posting_with_only_company_headings_still_gets_a_score():
    posting = "About us\nWe love Docker.\n\nBenefits\nDocker stickers.\n"
    assert _level(posting) == "required"


def test_company_heading_without_requirement_heading_still_filters():
    posting = "We need Python engineers.\n\nAbout us\nSAP invested in us.\n"
    keywords = [
        ExtractedKeyword(id=i, category="tools", matched_text=i, confidence=1.0, mentions=[i])
        for i in ("Python", "SAP")
    ]
    levels = classify_importance(posting, keywords)
    assert levels["Python"].level == "required"
    assert levels["SAP"].level == "mentioned"


def test_soft_skill_uses_every_sentence_it_was_found_in():
    posting = "We value teamwork.\n\nRequirements\n- Strong team player\n"
    kw = ExtractedKeyword(
        id="teamwork", category="soft_skills", matched_text="team player", confidence=0.9,
        mentions=["We value teamwork.", "- Strong team player"],
    )
    assert classify_importance(posting, [kw])["teamwork"].level == "required"


def test_suspended_compound_is_found_through_its_source_phrase():
    entry = SkillEntry(
        id="basic_care", category="hard_skills", display={"de": "Grundpflege"},
        status="curated", added="2026-11-06", aliases=["Grundpflege"],
    )
    posting = "Dein Profil\n- Grund- und Behandlungspflege\n"
    keywords = extract_discrete_keywords(posting, [entry])
    assert classify_importance(posting, keywords)["basic_care"].level == "required"


@pytest.mark.parametrize("glyph", ["-", "*", "•", "·", "–", "—", "▪", "●", "✓", "✔", "→", "►"])
def test_bullet_glyphs_are_stripped_from_items(glyph):
    result = extract_open_requirements(f"Requirements\n{glyph} Python\n{glyph} SQL\n")
    assert [r.phrase for r in result] == ["Python", "SQL"]


def test_leading_emoji_is_stripped_from_items():
    result = extract_open_requirements("Requirements\n- 🧠 Knowledge systems\n- ⚙️ SaaS fluency\n")
    assert [r.phrase for r in result] == ["Knowledge systems", "SaaS fluency"]


def test_bulleted_subheading_is_not_an_item():
    text = "Requirements\n- Must-haves\n  - Python\n- Nice-to-haves\n  - Docker\n"
    assert [(r.phrase, r.optional) for r in extract_open_requirements(text)] == [
        ("Python", False), ("Docker", True),
    ]


def test_bare_subheading_inside_comma_section_is_not_an_item():
    text = "Requirements\nMust-haves:\nPython, SQL\nNice-to-haves:\nDocker, Terraform\n"
    assert [(r.phrase, r.optional) for r in extract_open_requirements(text)] == [
        ("Python", False), ("SQL", False), ("Docker", True), ("Terraform", True),
    ]
