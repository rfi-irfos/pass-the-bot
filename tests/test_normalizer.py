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
