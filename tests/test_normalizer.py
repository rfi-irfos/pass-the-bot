import pytest

from passthebot.graph import SkillEntry
from passthebot.normalizer import extract_discrete_keywords, extract_open_requirements

ENTRIES = [
    SkillEntry(
        id="nodejs", category="languages", display={"en": "Node.js"},
        status="curated", added="2026-09-14",
        aliases=["Node.js", "Node", "NodeJS", "nodejs", "node js"],
    ),
    SkillEntry(
        id="python", category="languages", display={"en": "Python"},
        status="curated", added="2026-09-14",
        aliases=["Python", "python"],
    ),
]


def test_extracts_exact_alias():
    result = extract_discrete_keywords("Requires Python and Node.js experience.", ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"python", "nodejs"}


def test_extracts_case_and_punctuation_insensitive_alias():
    result = extract_discrete_keywords("we need someone who knows nodejs well", ENTRIES)
    assert result[0].id == "nodejs"
    assert result[0].confidence == 1.0


def test_no_match_returns_empty_list():
    result = extract_discrete_keywords("We need a great communicator.", ENTRIES)
    assert result == []


def test_does_not_double_count_same_skill_mentioned_twice():
    result = extract_discrete_keywords("Python, python, PYTHON required.", ENTRIES)
    assert len(result) == 1
    assert result[0].id == "python"


JAVA_ENTRIES = [
    SkillEntry(
        id="java", category="languages", display={"en": "Java"},
        status="curated", added="2026-09-14",
        aliases=["Java", "java"],
    ),
    SkillEntry(
        id="javascript", category="languages", display={"en": "JavaScript"},
        status="curated", added="2026-09-14",
        aliases=["JavaScript", "Javascript", "javascript", "JS", "js"],
    ),
]


def test_javascript_mention_does_not_falsely_match_java():
    result = extract_discrete_keywords("We use JavaScript extensively.", JAVA_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"javascript"}
    assert "java" not in ids


CPLUSPLUS_ENTRIES = [
    SkillEntry(
        id="cplusplus", category="languages", display={"en": "C++"},
        status="curated", added="2026-09-14",
        aliases=["C++", "c++"],
    ),
]


def test_matches_alias_ending_in_punctuation():
    result = extract_discrete_keywords("Experience with C++ required.", CPLUSPLUS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"cplusplus"}


NODEJS_JS_ENTRIES = [
    SkillEntry(
        id="nodejs", category="languages", display={"en": "Node.js"},
        status="curated", added="2026-09-14",
        aliases=["Node.js", "Node", "NodeJS", "nodejs", "node js"],
    ),
    SkillEntry(
        id="javascript", category="languages", display={"en": "JavaScript"},
        status="curated", added="2026-09-14",
        aliases=["JavaScript", "Javascript", "javascript", "JS", "js"],
    ),
]


def test_nodejs_punctuation_normalization_does_not_falsely_match_javascript():
    """Regression test: normalize_string rewrites '.' to a space, so "Node.js"
    normalizes to "node js". Without span-claiming, the short "js" alias
    (owned by javascript) would also match inside that normalized text via
    the boundary regex, incorrectly extracting javascript alongside nodejs.
    Longest-alias-first matching with span-claiming must let "node js" claim
    that text region before "js" gets a chance to match inside it.
    """
    result = extract_discrete_keywords("We use Node.js in production.", NODEJS_JS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"nodejs"}
    assert "javascript" not in ids


def test_javascript_alone_still_matches_when_nodejs_not_present():
    result = extract_discrete_keywords("We use JS extensively.", NODEJS_JS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"javascript"}


def test_repeated_nodejs_mention_does_not_leak_javascript_false_positive():
    """Regression test: extract_discrete_keywords used to break out of the
    finditer loop after claiming only the FIRST occurrence of a matched
    alias. A repeated mention of "Node.js" left the second occurrence's
    span unclaimed, so the shorter "js" alias (owned by javascript) could
    still match inside it once matching moved on to shorter aliases. Every
    non-overlapping occurrence of the longest alias must be claimed, not
    just the first.
    """
    result = extract_discrete_keywords(
        "Node.js backend. Node.js everywhere.", NODEJS_JS_ENTRIES
    )
    ids = {r.id for r in result}
    assert ids == {"nodejs"}
    assert "javascript" not in ids


FOO_FOOBAR_ENTRIES = [
    SkillEntry(
        id="foo", category="languages", display={"en": "Foo"},
        status="curated", added="2026-09-14",
        aliases=["Foo"],
    ),
    SkillEntry(
        id="foobar", category="languages", display={"en": "FooBar"},
        status="curated", added="2026-09-14",
        aliases=["FooBar"],
    ),
]


def test_shorter_alias_fully_contained_in_longer_claimed_span_is_suppressed():
    """Pins the documented span-claiming semantics: when a shorter entry's
    alias is a substring of a longer, different entry's alias, and only the
    longer form appears in the text, only the longer entry is extracted -
    the shorter entry is not also reported for the same occurrence.
    """
    result = extract_discrete_keywords("We use FooBar here.", FOO_FOOBAR_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"foobar"}


def test_extracts_bullet_requirements_under_german_heading():
    text = (
        "Anforderungen\n"
        "- Schweisskenntnisse (MIG/MAG)\n"
        "- Fuehrerschein Klasse B\n"
        "- Teamfaehigkeit\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Schweisskenntnisse (MIG/MAG)", "Fuehrerschein Klasse B", "Teamfaehigkeit"]


def test_extracts_bullet_requirements_under_english_heading():
    text = (
        "Requirements\n"
        "* 3+ years of accounting experience\n"
        "* Proficiency in Excel\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["3+ years of accounting experience", "Proficiency in Excel"]


def test_extracts_comma_separated_requirements_without_bullets():
    text = "Requirements\nPython, SQL, Excel"
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Python", "SQL", "Excel"]


def test_returns_empty_list_when_no_requirement_heading_present():
    text = "We are a great company that values people and growth."
    result = extract_open_requirements(text)
    assert result == []


def test_returns_empty_list_for_prose_only_requirements_section():
    text = (
        "Requirements\n"
        "We are looking for someone with strong accounting experience "
        "and a good command of Excel who can work independently."
    )
    result = extract_open_requirements(text)
    assert result == []


def test_multiple_requirement_headings_each_contribute_items():
    text = (
        "Must-have\n"
        "- Python\n"
        "- SQL\n"
        "\n"
        "Nice-to-have\n"
        "- Docker\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Python", "SQL", "Docker"]


def test_non_tech_industry_posting_bullets_extracted():
    text = (
        "Ihr Profil\n"
        "- Abgeschlossene Ausbildung als Elektriker\n"
        "- Erfahrung mit Schaltschrankbau\n"
        "- Fuehrerschein Klasse B\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == [
        "Abgeschlossene Ausbildung als Elektriker",
        "Erfahrung mit Schaltschrankbau",
        "Fuehrerschein Klasse B",
    ]


def test_german_heading_with_english_requirement_items_detected():
    text = (
        "Ihr Profil\n"
        "- Strong communication skills\n"
        "- Project management experience\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Strong communication skills", "Project management experience"]


def test_requirements_section_stops_at_a_non_requirement_heading():
    text = (
        "Anforderungen\n"
        "- Schweisskenntnisse\n"
        "- Fuehrerschein Klasse B\n"
        "\n"
        "Wir bieten\n"
        "- Firmenwagen\n"
        "- 30 Urlaubstage\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Schweisskenntnisse", "Fuehrerschein Klasse B"]


def test_bullet_line_containing_a_heading_keyword_is_not_treated_as_a_heading():
    text = (
        "Ihr Profil\n"
        "- Requirements Engineering Erfahrung\n"
        "- Teamfaehigkeit\n"
    )
    result = extract_open_requirements(text)
    phrases = [r.phrase for r in result]
    assert phrases == ["Requirements Engineering Erfahrung", "Teamfaehigkeit"]


def test_prose_sentence_with_a_comma_is_not_shredded_into_fake_requirements():
    text = (
        "Requirements\n"
        "We are looking for someone with strong accounting experience, "
        "ideally with Excel, who can work independently.\n"
    )
    result = extract_open_requirements(text)
    assert result == []


def test_requirement_heading_containing_a_comma_is_still_recognized():
    text = "Anforderungen, die du mitbringst\n- Python\n- SQL\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python", "SQL"]


def test_requirement_heading_with_a_comma_still_terminates_a_prior_section():
    text = "Anforderungen\n- Python\n\nVorteile, die wir bieten\n- Firmenwagen\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python"]


def test_short_intro_line_before_bullets_does_not_kill_the_section():
    text = "Anforderungen\nDu bringst mit:\n- Python\n- SQL\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python", "SQL"]


def test_short_intro_line_with_a_blank_line_before_bullets_does_not_kill_the_section():
    text = "Anforderungen\n\nDu bringst mit:\n- Python\n- SQL\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python", "SQL"]


def test_comma_list_directly_after_heading_with_blank_line_is_still_extracted():
    text = "Anforderungen\n\nPython, SQL, Excel\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python", "SQL", "Excel"]


def test_multiple_comma_list_lines_in_one_section_are_all_extracted():
    text = "Anforderungen\nPython, SQL, Excel\nDeutsch, Englisch\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Python", "SQL", "Excel", "Deutsch", "Englisch"]


def test_benefits_heading_directly_after_an_empty_requirements_heading_is_still_a_boundary():
    text = "Anforderungen\nWir bieten\n- Firmenwagen\n- Obst\n"
    result = extract_open_requirements(text)
    assert result == []


def test_benefits_under_unknown_heading_are_not_requirements():
    """LinkedIn feedback 2026-10-21: a user was told to prove the "skill"
    "Modern office space in Munich enabling collaborative work" because the
    benefits heading wasn't a known section boundary."""
    posting = (
        "Your profile\n"
        "- 5+ years of Java development\n"
        "- Experience with Kubernetes\n"
        "Why you'll love it here\n"
        "- Modern office space in Munich enabling collaborative work\n"
        "- 30 days of vacation\n"
        "- Competitive salary and stock options\n"
    )
    phrases = [r.phrase for r in extract_open_requirements(posting)]
    assert phrases == ["5+ years of Java development", "Experience with Kubernetes"]


def test_microsoft_office_is_still_a_requirement():
    phrases = [r.phrase for r in extract_open_requirements("Requirements\n- Microsoft Office\n")]
    assert phrases == ["Microsoft Office"]


def test_values_and_success_measures_close_the_requirements_section():
    posting = (
        "Requirements\n- B2B marketing experience\n"
        "Success Measures\n- Pipeline generated in APAC\n"
        "Our Values\n- We work together\n"
    )
    assert [r.phrase for r in extract_open_requirements(posting)] == ["B2B marketing experience"]


def test_french_requirement_heading_is_detected():
    posting = "Vos missions\n- Gérer les menus\nVotre profil\n- BTS diététique\n- Maîtrise d'Excel\nAvantages\n- Mutuelle\n"
    assert [r.phrase for r in extract_open_requirements(posting)] == ["BTS diététique", "Maîtrise d'Excel"]


def test_short_plain_lines_under_a_heading_are_items_without_bullet_markers():
    """Job boards like the Arbeitsagentur drop the bullet glyphs, so each
    requirement arrives as a short plain line."""
    text = (
        "Ihr Profil:\n"
        "Abgeschlossene kaufmännische Ausbildung\n"
        "Gute Kenntnisse im MS Office-Paket\n"
        "Sehr gute Deutschkenntnisse in Wort und Schrift\n"
    )
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == [
        "Abgeschlossene kaufmännische Ausbildung",
        "Gute Kenntnisse im MS Office-Paket",
        "Sehr gute Deutschkenntnisse in Wort und Schrift",
    ]


def test_plain_line_intro_ending_with_a_colon_is_not_an_item():
    text = "Anforderungen\nDas solltest du mitbringen:\nErfahrung im Vertrieb\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Erfahrung im Vertrieb"]


def test_promise_heading_closes_the_requirements_section():
    text = (
        "Ihr Profil:\n- Führerschein Klasse B\n"
        "Unsere Versprechen an Dich\n- Fort- und Weiterbildungsmöglichkeiten\n"
    )
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Führerschein Klasse B"]


def test_training_opportunities_are_a_benefit_but_required_training_is_not():
    text = (
        "Anforderungen\n- Weiterbildung im Wundmanagement von Vorteil\n"
        "- Fort- und Weiterbildungsmöglichkeiten\n"
    )
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Weiterbildung im Wundmanagement von Vorteil"]


CARE_ENTRIES = [
    SkillEntry(
        id="basic_care", category="hard_skills", display={"de": "Grundpflege"},
        status="curated", added="2026-10-21", aliases=["Grundpflege"],
    ),
    SkillEntry(
        id="treatment_care", category="hard_skills", display={"de": "Behandlungspflege"},
        status="curated", added="2026-10-21", aliases=["Behandlungspflege"],
    ),
]


def test_german_suspended_compound_matches_both_words():
    """"Grund- und Behandlungspflege" means Grundpflege and Behandlungspflege,
    but only the second word is written out."""
    result = extract_discrete_keywords(
        "Durchführung der Grund- und Behandlungspflege", CARE_ENTRIES
    )
    by_id = {r.id: r for r in result}
    assert set(by_id) == {"basic_care", "treatment_care"}
    assert by_id["basic_care"].matched_text == "Grund- und Behandlungspflege"


def test_hyphen_inside_a_word_is_not_a_suspended_compound():
    result = extract_discrete_keywords("Grund-Behandlungspflege", CARE_ENTRIES)
    assert {r.id for r in result} == {"treatment_care"}


def test_detect_language_tells_german_from_english():
    from passthebot.normalizer import detect_language

    assert detect_language("Du bringst eine kaufmännische Ausbildung und Erfahrung mit.") == "de"
    assert detect_language("You bring a degree and experience with the tools.") == "en"


@pytest.mark.parametrize("heading", ["Must-haves", "Must haves", "Must have", "🎯 Must-haves:"])
def test_plural_must_have_heading_is_not_an_item(heading):
    text = f"Requirements\n{heading}\nHands-on workflow experience\nPython\n"
    phrases = [r.phrase for r in extract_open_requirements(text)]
    assert phrases == ["Hands-on workflow experience", "Python"]


@pytest.mark.parametrize("heading", ["Nice-to-haves", "Nice to haves", "Nice to have", "Von Vorteil", "Desirable"])
def test_optional_heading_marks_its_items_optional(heading):
    text = f"Requirements\nPython\n\n{heading}\nDocker\n"
    result = extract_open_requirements(text)
    assert [(r.phrase, r.optional) for r in result] == [("Python", False), ("Docker", True)]


def test_requirement_sentence_is_not_mistaken_for_a_heading():
    text = "Requirements\nMust have Python experience\nNice to have some Docker\n"
    phrases = [r.phrase for r in extract_open_requirements(text)]
    assert phrases == ["Must have Python experience", "Nice to have some Docker"]


def test_extract_discrete_keywords_records_every_alias_found():
    entry = SkillEntry(
        id="german", category="spoken_languages", display={"en": "German"},
        status="curated", added="2026-11-06", aliases=["Deutsch", "German"],
    )
    result = extract_discrete_keywords("Team spricht Deutsch. Fluent German.", [entry])
    assert sorted(result[0].mentions) == ["Deutsch", "German"]


LINKEDIN_UK_POSTING = (
    "Finance Business Partner\n"
    "What we're looking for\n"
    "Qualified accountant (ACA, ACCA or CIMA)\n"
    "Experience partnering with budget holders\n"
    "Hybrid working environment (currently one day in office)\n"
    "Cycle to work scheme\n"
    "Extensive internal and external training\n"
    "What’s In It For You\n"
    "Group healthcare and life assurance scheme\n"
    "25 days annual holiday with incremental increase up to 30 days\n"
    "Season ticket travel loan\n"
)


def test_uk_benefit_lines_right_after_requirements_are_not_requirements():
    """Issue #15: LinkedIn delivers lists as plain lines, and the benefits
    followed the requirements without a heading of their own."""
    result = extract_open_requirements(LINKEDIN_UK_POSTING)
    assert [r.phrase for r in result] == [
        "Qualified accountant (ACA, ACCA or CIMA)",
        "Experience partnering with budget holders",
    ]


def test_the_package_heading_closes_the_requirements():
    text = (
        "Requirements\n- Strong Excel skills\n"
        "The package\n- Bike to the office every Friday\n"
    )
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == ["Strong Excel skills"]


def test_comma_inside_brackets_does_not_split_a_comma_list():
    text = "Requirements\nExcel, Qualified accountant (ACA, ACCA or CIMA), SAP\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == [
        "Excel", "Qualified accountant (ACA, ACCA or CIMA)", "SAP",
    ]


def test_required_training_is_still_a_requirement():
    text = "Requirements\n- Training in first aid\n- Experience in healthcare settings\n"
    result = extract_open_requirements(text)
    assert [r.phrase for r in result] == [
        "Training in first aid", "Experience in healthcare settings",
    ]


def test_long_required_qualifications_heading_is_recognised():
    text = (
        "Job Responsibilities\n- Build services\n"
        "Required Qualifications, Capabilities, And Skills\n"
        "- Experience across the Software Development Life Cycle\n"
        "- Exposure to agile methodologies\n"
        "Preferred Qualifications, Capabilities, And Skills\n- Experience with AWS\n"
    )
    found = [(r.phrase, r.optional) for r in extract_open_requirements(text)]
    assert found == [
        ("Experience across the Software Development Life Cycle", False),
        ("Exposure to agile methodologies", False),
        ("Experience with AWS", True),
    ]


def test_linkedin_login_wall_is_not_a_requirements_section():
    text = (
        "Sign in to evaluate your skills\nSign in with Email\nor\n"
        "By clicking Continue to join or sign in, you agree to LinkedIn’s , , and .\n"
        "Base pay range\n£32,000.00/yr - £35,000.00/yr\nJoanna Nathan\n"
        "Main Responsibilities Will Include\n- Managing the offices\n"
        "Person Specification\n- Calm under pressure\n"
        "Show more\nShow less\nSeniority level\nEntry level\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == ["Calm under pressure"]


def test_whats_on_offer_closes_requirements():
    text = (
        "About You\n- Advanced Excel skills\n"
        "What's on Offer?\n- A growing business environment offering challenge\n"
        "- The chance to build a finance function\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == ["Advanced Excel skills"]


def test_prose_addressed_to_the_candidate_is_not_split_on_commas():
    text = (
        "About You\n"
        "You're someone who enjoys partnering stakeholders, influencing decisions, "
        "turning data into clear recommendations\n"
    )
    assert extract_open_requirements(text) == []


def test_what_we_would_like_from_you_opens_requirements():
    text = "What we would like from you:\n- A current NMC registration\nWhat to look forward to:\n- Birthday off\n"
    assert [r.phrase for r in extract_open_requirements(text)] == ["A current NMC registration"]


def test_experience_and_skills_required_heading():
    text = "Experience & Skills Required\n- Good working knowledge of Outlook and Excel\n- At least 3 years in a similar role\nAbout Acme\nWe do things.\n"
    assert [r.phrase for r in extract_open_requirements(text)] == [
        "Good working knowledge of Outlook and Excel",
        "At least 3 years in a similar role",
    ]


def test_plain_sentence_lines_keep_their_commas():
    text = (
        "Essential\n"
        "Experience developing ontologies, taxonomies, thesauri or business glossaries.\n"
        "Strong understanding of standards, including OWL, RDF, SKOS and SHACL.\n"
        "Experience with governance platforms such as Graphologi, PoolParty or similar tools.\n"
        "What's In It For You\nGroup pension scheme\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == [
        "Experience developing ontologies, taxonomies, thesauri or business glossaries",
        "Strong understanding of standards, including OWL, RDF, SKOS and SHACL",
        "Experience with governance platforms such as Graphologi, PoolParty or similar tools",
    ]


def test_perks_in_the_employers_voice_are_not_requirements():
    text = (
        "Requirements\n"
        "- Strong FP&A experience, including budgeting and forecasting\n"
        "- Best-in-class AI tools: Every Upvenger has 20,000 per year to spend on tools\n"
        "- Team celebrations: Participate in company-wide events\n"
        "- Impact-driven work: We’re building the infrastructure of tomorrow\n"
        "- Company car or car allowance - providing support to help you stay mobile\n"
        "- Eye Care Vouchers – free eye tests\n"
        "- Everyday Discounts – our benefits platform gives you access to retailers\n"
        "- Reward & Recognition – we recognise those who go above and beyond\n"
        "- Proficiency in Python: Django and Flask preferred\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == [
        "Strong FP&A experience, including budgeting and forecasting",
        "Proficiency in Python: Django and Flask preferred",
    ]


def test_requirements_containing_perk_words_are_kept():
    keep = [
        "Kubernetes: experience operating our production clusters",
        "Certification: each nurse has to hold a valid licence",
        "Sales experience - we need someone who has closed B2B deals",
        "Experience with discount pricing and promotions",
        "Experience in eye care optometry",
        "Handling gift vouchers and refunds at the till",
    ]
    text = "Requirements\n- Python skills\n" + "".join(f"- {c}\n" for c in keep)
    assert [r.phrase for r in extract_open_requirements(text)] == ["Python skills", *keep]


def test_short_sections_of_plain_sentences_count_but_wishes_do_not():
    text = (
        "Desirable\n"
        "Knowledge graph experience.\n"
        "Experience with modelling platforms such as PoolParty or similar tools.\n"
        "Experience in logistics would be a bonus.\n"
        "You will be someone who enjoys partnering with stakeholders.\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == [
        "Knowledge graph experience",
        "Experience with modelling platforms such as PoolParty or similar tools",
    ]


def test_employer_voice_with_a_two_word_subject_is_a_perk():
    text = "Requirements\n- Python skills\n- Best-in-class tools: Every team member has a yearly budget\n"
    assert [r.phrase for r in extract_open_requirements(text)] == ["Python skills"]


def test_unknown_subheading_with_mostly_perk_bullets_is_a_perk_block():
    text = (
        "Requirements\n- Python skills\n"
        "Come grow with us\n"
        "- Salary up to 40,000\n- Group pension scheme\n- Free parking on site\n- Dog-friendly teams\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == ["Python skills"]


def test_unknown_subheading_with_requirement_bullets_is_kept():
    text = (
        "Requirements\n- Python skills\n"
        "Technical skills\n- Experience with ERP systems\n- Knowledge of stock control\n"
        "Soft skills\n- Clear written communication\n- Free parking management experience\n"
    )
    assert [r.phrase for r in extract_open_requirements(text)] == [
        "Python skills",
        "Experience with ERP systems",
        "Knowledge of stock control",
        "Clear written communication",
        "Free parking management experience",
    ]


def test_a_single_perk_bullet_under_an_unknown_subheading_does_not_drop_its_block():
    text = "Requirements\n- Python skills\nOther\n- Salary expectations in your cover letter\n- Experience with SQL\n"
    assert "Experience with SQL" in [r.phrase for r in extract_open_requirements(text)]
