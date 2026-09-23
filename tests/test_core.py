"""Tests for folder_nature.core — filesystem read/write + walk-upward."""

from __future__ import annotations

from pathlib import Path

import pytest

from folder_nature.core import (
    NATURE_FILENAME,
    find_director,
    get_folder_nature,
    read_folder_nature,
    write_folder_nature,
)
from folder_nature.schema import (
    FolderNature,
    Identity,
    SchemaError,
)

# ── Fixtures ─────────────────────────────────────────────────────────────


def _make_nature(
    name: str, being: str = "workspace", director: bool = False, tags=None
) -> FolderNature:
    return FolderNature(
        identity=Identity(name=name, being=being, purpose=f"{name} folder"),
        director=director,
        tags=tags or [],
    )


# ── write_folder_nature ──────────────────────────────────────────────────


def test_write_then_read_roundtrip(tmp_path: Path):
    nature = _make_nature("demo", tags=["t1", "t2"])
    written = write_folder_nature(tmp_path, nature)
    assert written == tmp_path / NATURE_FILENAME
    assert written.exists()

    read_back = read_folder_nature(written)
    assert read_back.identity.name == "demo"
    assert read_back.identity.being == "workspace"
    assert read_back.tags == ["t1", "t2"]


def test_write_to_nonexistent_dir_raises(tmp_path: Path):
    bad = tmp_path / "does-not-exist"
    nature = _make_nature("x")
    with pytest.raises(FileNotFoundError):
        write_folder_nature(bad, nature)


def test_write_to_file_raises(tmp_path: Path):
    f = tmp_path / "regular.txt"
    f.write_text("hello")
    nature = _make_nature("x")
    with pytest.raises(NotADirectoryError):
        write_folder_nature(f, nature)


def test_write_validates(tmp_path: Path):
    bad = FolderNature()  # no identity → invalid
    with pytest.raises(SchemaError):
        write_folder_nature(tmp_path, bad)


# ── read_folder_nature ───────────────────────────────────────────────────


def test_read_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_folder_nature(tmp_path / NATURE_FILENAME)


def test_read_invalid_yaml_raises(tmp_path: Path):
    bad = tmp_path / NATURE_FILENAME
    bad.write_text("not: valid: yaml: [unclosed")
    import yaml

    with pytest.raises(yaml.YAMLError):
        read_folder_nature(bad)


def test_read_empty_file_raises_schema_error(tmp_path: Path):
    empty = tmp_path / NATURE_FILENAME
    empty.write_text("")
    with pytest.raises(SchemaError, match="empty or contains only YAML null"):
        read_folder_nature(empty)


# ── get_folder_nature (walks upward) ────────────────────────────────────


def test_get_finds_in_own_dir(tmp_path: Path):
    nature = _make_nature("here")
    write_folder_nature(tmp_path, nature)
    found = get_folder_nature(tmp_path)
    assert found is not None
    assert found.identity.name == "here"


def test_get_walks_up(tmp_path: Path):
    """Search starting from a deep subdir finds the closest ancestor's nature."""
    write_folder_nature(tmp_path, _make_nature("root"))

    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)

    found = get_folder_nature(deep)
    assert found is not None
    assert found.identity.name == "root"


def test_get_returns_closest_ancestor(tmp_path: Path):
    """If multiple ancestors have natures, closest one wins."""
    write_folder_nature(tmp_path, _make_nature("root"))

    middle = tmp_path / "middle"
    middle.mkdir()
    write_folder_nature(middle, _make_nature("middle"))

    deep = middle / "deeper"
    deep.mkdir()

    found = get_folder_nature(deep)
    assert found is not None
    assert found.identity.name == "middle"


def test_get_returns_none_when_no_nature(tmp_path: Path):
    found = get_folder_nature(tmp_path)
    assert found is None


# ── find_director ────────────────────────────────────────────────────────


def test_find_director_self(tmp_path: Path):
    write_folder_nature(tmp_path, _make_nature("boss", director=True))
    path, nature = find_director(tmp_path)
    assert path == tmp_path.resolve()
    assert nature is not None
    assert nature.director is True


def test_find_director_walks_past_non_directors(tmp_path: Path):
    """Walks up past non-director natures to find the director."""
    write_folder_nature(tmp_path, _make_nature("boss", director=True))

    middle = tmp_path / "middle"
    middle.mkdir()
    write_folder_nature(middle, _make_nature("middle", director=False))

    deep = middle / "deep"
    deep.mkdir()

    path, nature = find_director(deep)
    assert path == tmp_path.resolve()
    assert nature.identity.name == "boss"


def test_find_director_returns_none_when_no_director(tmp_path: Path):
    write_folder_nature(tmp_path, _make_nature("plain", director=False))
    path, nature = find_director(tmp_path)
    assert path is None
    assert nature is None


def test_find_director_skips_corrupted_files(tmp_path: Path):
    """Walks past unparseable .folder-nature files without crashing."""
    # Corrupt nature in subdir
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / NATURE_FILENAME).write_text("bad: : yaml: [")

    # Valid director at root
    write_folder_nature(tmp_path, _make_nature("boss", director=True))

    deep = sub / "deeper"
    deep.mkdir()

    path, nature = find_director(deep)
    assert path == tmp_path.resolve()
    assert nature.identity.name == "boss"
