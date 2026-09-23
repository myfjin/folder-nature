"""Tests for folder_nature.schema — pure data validation, no filesystem."""

from __future__ import annotations

import pytest

from folder_nature.schema import (
    BEING_TYPES,
    SCHEMA_VERSION,
    FolderNature,
    SchemaError,
    from_dict,
    validate,
)

# ── Minimal valid sample ─────────────────────────────────────────────────


def _minimal_valid() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "name": "demo",
            "being": "workspace",
            "purpose": "demo folder",
        },
    }


def test_minimal_valid_passes():
    validate(_minimal_valid())  # no raise


def test_from_dict_produces_folder_nature():
    data = _minimal_valid()
    nature = from_dict(data)
    assert isinstance(nature, FolderNature)
    assert nature.schema_version == SCHEMA_VERSION
    assert nature.identity.name == "demo"
    assert nature.identity.being == "workspace"
    assert nature.director is False
    assert nature.tags == []
    assert nature.rules == []
    assert nature.memory is None


# ── schema_version checks ────────────────────────────────────────────────


def test_missing_schema_version_rejected():
    data = _minimal_valid()
    del data["schema_version"]
    with pytest.raises(SchemaError, match="schema_version is required"):
        validate(data)


def test_wrong_schema_version_rejected():
    data = _minimal_valid()
    data["schema_version"] = "0.9"
    with pytest.raises(SchemaError, match="unsupported schema_version"):
        validate(data)


def test_non_string_schema_version_rejected():
    data = _minimal_valid()
    data["schema_version"] = 1.0
    with pytest.raises(SchemaError, match="schema_version must be a string"):
        validate(data)


# ── identity checks ──────────────────────────────────────────────────────


def test_missing_identity_rejected():
    with pytest.raises(SchemaError, match="identity block is required"):
        validate({"schema_version": SCHEMA_VERSION})


def test_identity_must_be_dict():
    data = _minimal_valid()
    data["identity"] = "not a dict"
    with pytest.raises(SchemaError, match="identity must be a mapping"):
        validate(data)


@pytest.mark.parametrize("missing", ["name", "being", "purpose"])
def test_identity_required_subfields(missing: str):
    data = _minimal_valid()
    del data["identity"][missing]
    with pytest.raises(SchemaError, match=f"identity.{missing} is required"):
        validate(data)


def test_empty_identity_name_rejected():
    data = _minimal_valid()
    data["identity"]["name"] = "  "
    with pytest.raises(SchemaError, match="identity.name must be non-empty"):
        validate(data)


def test_identity_name_too_long_rejected():
    data = _minimal_valid()
    data["identity"]["name"] = "x" * 101
    with pytest.raises(SchemaError, match="identity.name exceeds"):
        validate(data)


def test_unknown_being_does_not_reject():
    """Unknown being types are allowed (extensibility hatch). No raise."""
    data = _minimal_valid()
    data["identity"]["being"] = "custom-business-type"
    validate(data)


def test_all_known_being_types_pass():
    """Sanity: every type in BEING_TYPES validates."""
    for being in BEING_TYPES:
        data = _minimal_valid()
        data["identity"]["being"] = being
        validate(data)


# ── director / tags / rules ──────────────────────────────────────────────


def test_director_must_be_bool():
    data = _minimal_valid()
    data["director"] = "true"
    with pytest.raises(SchemaError, match="director must be a boolean"):
        validate(data)


def test_tags_must_be_list():
    data = _minimal_valid()
    data["tags"] = "single-tag"
    with pytest.raises(SchemaError, match="tags must be a list"):
        validate(data)


def test_tag_too_long_rejected():
    data = _minimal_valid()
    data["tags"] = ["x" * 31]
    with pytest.raises(SchemaError, match="exceeds"):
        validate(data)


def test_tags_count_limit():
    data = _minimal_valid()
    data["tags"] = [f"t{i}" for i in range(51)]
    with pytest.raises(SchemaError, match="tags count exceeds"):
        validate(data)


def test_rules_must_be_list():
    data = _minimal_valid()
    data["rules"] = "single rule"
    with pytest.raises(SchemaError, match="rules must be a list"):
        validate(data)


# ── memory block ─────────────────────────────────────────────────────────


def test_memory_valid_iso_date_passes():
    data = _minimal_valid()
    data["memory"] = {"created": "2026-06-22"}
    validate(data)


def test_memory_bad_date_rejected():
    data = _minimal_valid()
    data["memory"] = {"created": "2026-13-99"}
    with pytest.raises(SchemaError, match="not a valid ISO date"):
        validate(data)


def test_memory_notable_events_must_be_list():
    data = _minimal_valid()
    data["memory"] = {"notable_events": "single event"}
    with pytest.raises(SchemaError, match="notable_events must be a list"):
        validate(data)


# ── Roundtrip ────────────────────────────────────────────────────────────


def test_roundtrip_minimal():
    """from_dict → to_dict produces equivalent data."""
    data = _minimal_valid()
    nature = from_dict(data)
    again = nature.to_dict()
    # director defaults to False; explicitly present in to_dict output
    assert again["identity"] == data["identity"]
    assert again["schema_version"] == data["schema_version"]


def test_roundtrip_full():
    data = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "name": "projects",
            "being": "director",
            "purpose": "canonical work root",
        },
        "director": True,
        "tags": ["work", "active"],
        "rules": ["only deployed code lives here"],
        "memory": {
            "created": "2026-05-09",
            "last_significant_change": "2026-06-22",
            "notable_events": ["2026-05-09: initial setup"],
        },
    }
    nature = from_dict(data)
    rebuilt = nature.to_dict()
    assert rebuilt["identity"] == data["identity"]
    assert rebuilt["director"] is True
    assert rebuilt["tags"] == data["tags"]
    assert rebuilt["rules"] == data["rules"]
    assert rebuilt["memory"]["created"] == "2026-05-09"
    assert rebuilt["memory"]["notable_events"] == data["memory"]["notable_events"]
