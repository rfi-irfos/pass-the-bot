from pathlib import Path

from passthebot.graph import active_entries, load_skill_graph

DATA_DIR = Path(__file__).parent.parent / "data" / "skills"


def test_load_skill_graph_finds_seed_entries():
    entries = load_skill_graph(DATA_DIR)
    ids = {e.id for e in entries}
    assert "python" in ids
    assert "nodejs" in ids
    assert "teamwork" in ids


def test_load_skill_graph_parses_soft_skill_fields():
    entries = load_skill_graph(DATA_DIR)
    teamwork = next(e for e in entries if e.id == "teamwork")
    assert teamwork.category == "soft_skills"
    assert "team player" in teamwork.anchor_phrases
    assert teamwork.embedding_threshold == 0.75


def test_active_entries_filters_by_status():
    entries = load_skill_graph(DATA_DIR)
    assert all(e.status in {"curated", "ai-suggested-approved"} for e in active_entries(entries))
