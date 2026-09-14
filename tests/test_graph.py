from pathlib import Path
import tempfile
import pytest

from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph

DATA_DIR = DEFAULT_DATA_DIR


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
    assert teamwork.embedding_threshold == 0.48


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


def test_load_skill_graph_raises_on_non_list_top_level():
    """A YAML file whose top level is a mapping (not a list) must raise a clear
    ValueError naming the file, instead of a TypeError leaking out of the
    per-item iteration (item["id"] on a string key)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        malformed_yaml = tmp_path / "mapping.yaml"
        malformed_yaml.write_text(
            """id: test_skill
category: languages
status: curated
"""
        )

        with pytest.raises(ValueError) as exc_info:
            load_skill_graph(tmp_path)

        error_msg = str(exc_info.value)
        assert "mapping.yaml" in error_msg
        assert "list" in error_msg.lower()


def test_load_skill_graph_raises_on_empty_mapping_top_level():
    """A YAML file whose top level is an empty mapping ('{}') must still raise
    the non-list ValueError, not silently pass through as zero entries. Before
    the fix, `yaml.safe_load(...) or []` ran before the isinstance check, so
    an empty dict (falsy) was coerced to [] and the guard never fired."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        malformed_yaml = tmp_path / "empty_mapping.yaml"
        malformed_yaml.write_text("{}\n")

        with pytest.raises(ValueError) as exc_info:
            load_skill_graph(tmp_path)

        error_msg = str(exc_info.value)
        assert "empty_mapping.yaml" in error_msg
        assert "list" in error_msg.lower()


def test_load_skill_graph_empty_file_yields_no_entries():
    """A genuinely empty YAML file (safe_load returns None) is not a malformed
    top level - it should load as zero entries, not raise."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")

        assert load_skill_graph(tmp_path) == []
