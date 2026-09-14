from pathlib import Path
import tempfile
import pytest

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


def test_load_skill_graph_raises_on_missing_required_field():
    """Test that missing required fields raise a descriptive ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create a malformed YAML file with missing 'added' field
        malformed_yaml = tmp_path / "malformed.yaml"
        malformed_yaml.write_text(
            """- id: test_skill
  category: languages
  display: { de: "Test", en: "Test" }
  status: curated
"""
        )

        # Should raise ValueError with descriptive message
        with pytest.raises(ValueError) as exc_info:
            load_skill_graph(tmp_path)

        error_msg = str(exc_info.value)
        assert "malformed.yaml" in error_msg
        assert "test_skill" in error_msg
        assert "'added'" in error_msg


def test_load_skill_graph_raises_on_missing_id():
    """Test that missing id field raises a descriptive ValueError with entry index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create a YAML file with missing 'id' field
        malformed_yaml = tmp_path / "no_id.yaml"
        malformed_yaml.write_text(
            """- category: languages
  display: { de: "Test", en: "Test" }
  status: curated
  added: "2026-09-14"
"""
        )

        # Should raise ValueError with descriptive message
        with pytest.raises(ValueError) as exc_info:
            load_skill_graph(tmp_path)

        error_msg = str(exc_info.value)
        assert "no_id.yaml" in error_msg
        assert "index 0" in error_msg
        assert "'id'" in error_msg
