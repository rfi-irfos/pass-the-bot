from passthebot.graph import SkillEntry
from passthebot.matcher import enrich_near_misses, match, match_open_requirements
from passthebot.normalizer import ExtractedKeyword, OpenRequirement

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


class _StubEmbedder:
    """Returns a fixed score per requirement phrase, looked up by the
    phrase's own text, so tests can pin exact MATCH/NEAR_MISS/MISSING
    classification without loading the real sentence-transformers model.

    `best_match` is now called with two different kinds of `phrases` lists:
    resume sentences (for the ordinary open-requirement match) and, since
    the soft-skill dedup fix, a claimed soft-skill entry's own
    anchor_phrases. `phrase_scores` (optional) lets a test pin a score for
    a specific (text, phrases) pairing by phrases content, so the two call
    sites can be distinguished precisely instead of only by phrase text."""

    def __init__(
        self,
        scores: dict[str, float],
        phrase_scores: dict[tuple[str, ...], float] | None = None,
    ):
        self._scores = scores
        self._phrase_scores = phrase_scores or {}

    def best_match(self, text: str, phrases: list[str], cache_phrases: bool = True):
        key = tuple(phrases)
        if key in self._phrase_scores:
            return phrases[0], self._phrase_scores[key]
        return phrases[0], self._scores.get(text, 0.0)


def test_open_requirement_above_match_threshold_is_match():
    reqs = [OpenRequirement(phrase="Python", source_line=1)]
    embedder = _StubEmbedder({"Python": 0.9})
    results = match_open_requirements(reqs, "Experienced Python developer.", embedder, claimed_spans=set())
    assert results[0].status == "MATCH"
    assert results[0].origin == "open"
    assert results[0].id == "Python"
    assert results[0].required is True


def test_open_requirement_between_thresholds_is_near_miss():
    reqs = [OpenRequirement(phrase="Schweissen", source_line=1)]
    embedder = _StubEmbedder({"Schweissen": 0.40})
    results = match_open_requirements(reqs, "Some resume text.", embedder, claimed_spans=set())
    assert results[0].status == "NEAR_MISS"
    assert results[0].required is True


def test_open_requirement_below_near_miss_threshold_is_missing():
    reqs = [OpenRequirement(phrase="Schweissen", source_line=1)]
    embedder = _StubEmbedder({"Schweissen": 0.1})
    results = match_open_requirements(reqs, "Some resume text.", embedder, claimed_spans=set())
    assert results[0].status == "MISSING"
    assert results[0].found_text is None
    assert results[0].required is True
    assert results[0].confidence is None


def test_open_requirement_already_claimed_by_curated_match_is_skipped():
    reqs = [OpenRequirement(phrase="Python", source_line=1)]
    embedder = _StubEmbedder({"Python": 0.9})
    results = match_open_requirements(
        reqs, "Experienced Python developer.", embedder, claimed_spans={"python"}
    )
    assert results == []


def test_open_requirement_phrase_containing_claimed_span_as_whole_word_is_skipped():
    """A realistic open-requirement bullet ('Erfahrung mit Python') should be
    recognized as already covered by a curated match on the bare skill token
    ('python'), not just an exact-string-identical phrase."""
    reqs = [OpenRequirement(phrase="Erfahrung mit Python", source_line=1)]
    embedder = _StubEmbedder({"Erfahrung mit Python": 0.9})
    results = match_open_requirements(
        reqs, "Experienced Python developer.", embedder, claimed_spans={"python"}
    )
    assert results == []


def test_open_requirement_phrase_with_unrelated_substring_is_not_falsely_claimed():
    """A claimed span must match as a whole word, not as a raw substring --
    'java' claimed must not suppress an open phrase about 'javascript'."""
    reqs = [OpenRequirement(phrase="JavaScript experience required", source_line=1)]
    embedder = _StubEmbedder({"JavaScript experience required": 0.9})
    results = match_open_requirements(
        reqs, "Experienced JavaScript developer.", embedder, claimed_spans={"java"}
    )
    assert len(results) == 1


def test_duplicate_open_requirement_phrases_collapse_to_one_result():
    reqs = [
        OpenRequirement(phrase="Python", source_line=1),
        OpenRequirement(phrase="python", source_line=5),
    ]
    embedder = _StubEmbedder({"Python": 0.9, "python": 0.9})
    results = match_open_requirements(reqs, "Experienced Python developer.", embedder, claimed_spans=set())
    assert len(results) == 1


def test_default_origin_is_curated_for_existing_call_sites():
    results = match(POSTING, [], required_ids={"python"})
    assert all(r.origin == "curated" for r in results)


def test_open_phrase_matching_a_soft_skill_entrys_anchor_is_deduped():
    """A posting phrase that differs from the curated soft-skill's own anchor
    phrasing (so the literal whole-word claimed_spans check doesn't catch it)
    must still be deduped via embedding similarity against that entry's
    anchor phrases, not double-reported under the open layer."""
    teamwork_entry = SkillEntry(
        id="teamwork", category="soft_skills", display={"en": "Team player"},
        status="curated", added="2026-09-14",
        anchor_phrases=["team player", "teamorientiert arbeiten"],
        embedding_threshold=0.48,
    )
    reqs = [OpenRequirement(phrase="Teamorientiertes Arbeiten", source_line=1)]
    embedder = _StubEmbedder(
        scores={"Teamorientiertes Arbeiten": 0.9},
        phrase_scores={tuple(teamwork_entry.anchor_phrases): 0.9},
    )
    results = match_open_requirements(
        reqs, "Some resume text.", embedder, claimed_spans=set(),
        claimed_soft_skill_entries=[teamwork_entry],
    )
    assert results == []


def test_open_phrase_not_matching_any_claimed_soft_skill_anchor_is_kept():
    """The new soft-skill dedup check must not suppress unrelated open
    phrases just because *some* soft-skill entry was claimed elsewhere."""
    teamwork_entry = SkillEntry(
        id="teamwork", category="soft_skills", display={"en": "Team player"},
        status="curated", added="2026-09-14",
        anchor_phrases=["team player", "teamorientiert arbeiten"],
        embedding_threshold=0.48,
    )
    reqs = [OpenRequirement(phrase="Schweisskenntnisse", source_line=1)]
    embedder = _StubEmbedder(
        scores={"Schweisskenntnisse": 0.9},
        phrase_scores={tuple(teamwork_entry.anchor_phrases): 0.1},
    )
    results = match_open_requirements(
        reqs, "Erfahrung mit Schweisskenntnissen.", embedder, claimed_spans=set(),
        claimed_soft_skill_entries=[teamwork_entry],
    )
    assert len(results) == 1
    assert results[0].status == "MATCH"
