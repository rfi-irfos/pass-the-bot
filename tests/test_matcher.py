from passthebot.graph import SkillEntry
from passthebot.matcher import enrich_near_misses, match
from passthebot.normalizer import ExtractedKeyword

POSTING = [
    ExtractedKeyword(id="python", category="languages", matched_text="Python", confidence=1.0),
    ExtractedKeyword(id="docker", category="tools", matched_text="Docker", confidence=1.0),
    ExtractedKeyword(id="react", category="frameworks", matched_text="React", confidence=1.0),
]


def test_exact_match_when_resume_has_same_id():
    resume = [ExtractedKeyword(id="python", category="languages", matched_text="python", confidence=1.0)]
    results = match(POSTING, resume, required_ids={"python"})
    python_result = next(r for r in results if r.id == "python")
    assert python_result.status == "MATCH"
    assert python_result.required is True


def test_missing_when_resume_lacks_id_and_no_fuzzy_hit():
    results = match(POSTING, [], required_ids={"python", "docker", "react"})
    statuses = {r.id: r.status for r in results}
    assert statuses["python"] == "MISSING"
    assert statuses["docker"] == "MISSING"
    assert statuses["react"] == "MISSING"


def test_required_flag_reflects_input():
    results = match(POSTING, [], required_ids={"python"})
    by_id = {r.id: r for r in results}
    assert by_id["python"].required is True
    assert by_id["docker"].required is False


def test_java_does_not_match_javascript():
    posting = [ExtractedKeyword(id="javascript", category="languages", matched_text="JavaScript", confidence=1.0)]
    resume = [ExtractedKeyword(id="java", category="languages", matched_text="Java", confidence=1.0)]
    results = match(posting, resume, required_ids={"javascript"})
    assert results[0].status == "MISSING"


DOCKER_ENTRY = SkillEntry(
    id="docker", category="tools", display={"en": "Docker"}, status="curated",
    added="2026-09-14", aliases=["Docker", "docker"],
)
TEAMWORK_ENTRY = SkillEntry(
    id="teamwork", category="soft_skills", display={"en": "Team player"}, status="curated",
    added="2026-09-14", anchor_phrases=["team player", "works well in teams"],
)


def test_typo_in_resume_upgrades_missing_to_near_miss():
    results = match(POSTING, [], required_ids={"docker"})
    enriched = enrich_near_misses(results, "Comfortable with dockr and other tools.", [DOCKER_ENTRY])
    docker_result = next(r for r in enriched if r.id == "docker")
    assert docker_result.status == "NEAR_MISS"
    assert docker_result.found_text == "dockr"
    assert docker_result.suggested_alias in ("Docker", "docker")
    assert docker_result.confidence is not None and docker_result.confidence >= 0.75


def test_match_is_left_untouched_by_enrichment():
    results = match(POSTING, [ExtractedKeyword(id="docker", category="tools", matched_text="Docker", confidence=1.0)], required_ids={"docker"})
    enriched = enrich_near_misses(results, "irrelevant text", [DOCKER_ENTRY])
    docker_result = next(r for r in enriched if r.id == "docker")
    assert docker_result.status == "MATCH"
    assert docker_result.found_text is None


def test_missing_stays_missing_when_no_fuzzy_hit_anywhere():
    results = match(POSTING, [], required_ids={"docker"})
    enriched = enrich_near_misses(results, "We build spaceships and satellites.", [DOCKER_ENTRY])
    docker_result = next(r for r in enriched if r.id == "docker")
    assert docker_result.status == "MISSING"


def test_soft_skill_category_is_never_enriched():
    posting = [ExtractedKeyword(id="teamwork", category="soft_skills", matched_text="team player", confidence=1.0)]
    results = match(posting, [], required_ids={"teamwork"})
    enriched = enrich_near_misses(results, "teemwork is important to us", [TEAMWORK_ENTRY])
    teamwork_result = next(r for r in enriched if r.id == "teamwork")
    assert teamwork_result.status == "MISSING"
