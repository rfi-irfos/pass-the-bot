import pytest

from passthebot.graph import SkillEntry
from passthebot.validate_graph import GraphValidationError, validate_graph


def _entry(**overrides):
    base = dict(
        id="python", category="languages", display={"en": "Python"},
        status="curated", added="2026-09-14", aliases=["Python", "python"],
    )
    base.update(overrides)
    return SkillEntry(**base)


def test_valid_graph_passes():
    validate_graph([_entry()])  # should not raise


def test_duplicate_id_across_categories_rejected():
    entries = [_entry(), _entry(category="frameworks")]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_alias_collision_across_ids_rejected():
    entries = [
        _entry(id="python", aliases=["Python", "py"]),
        _entry(id="pytorch", aliases=["PyTorch", "py"]),
    ]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_alias_collision_is_case_and_space_insensitive():
    entries = [
        _entry(id="a", aliases=["Node JS"]),
        _entry(id="b", aliases=["node  js"]),
    ]
    with pytest.raises(GraphValidationError):
        validate_graph(entries)


def test_invalid_category_rejected():
    with pytest.raises(GraphValidationError):
        validate_graph([_entry(category="not_a_real_category")])


def test_invalid_status_rejected():
    with pytest.raises(GraphValidationError):
        validate_graph([_entry(status="not_a_real_status")])
