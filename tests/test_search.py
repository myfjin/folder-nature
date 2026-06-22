"""Tests for folder_nature.search — tree-walking + filtering."""

from __future__ import annotations

from pathlib import Path

import pytest

from folder_nature.core import write_folder_nature
from folder_nature.schema import FolderNature, Identity
from folder_nature.search import iter_nature_file_paths, list_all, search


def _make(name: str, being: str = "workspace", tags=None) -> FolderNature:
    return FolderNature(
        identity=Identity(name=name, being=being, purpose=f"{name} folder"),
        tags=tags or [],
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Build a small tree with multiple .folder-nature files."""
    # tmp_path/
    # ├── .folder-nature                 (root, workspace, [work])
    # ├── clients/
    # │   ├── .folder-nature             (workspace, [client, active])
    # │   ├── acme/
    # │   │   └── .folder-nature         (workspace, [client, acme])
    # │   └── startup/
    # │       └── .folder-nature         (workspace, [client, startup])
    # ├── archive/
    # │   └── .folder-nature             (collector, [archive])
    # └── docs/
    #     └── .folder-nature             (documentation, [docs])
    write_folder_nature(tmp_path, _make("root", tags=["work"]))

    clients = tmp_path / "clients"
    clients.mkdir()
    write_folder_nature(clients, _make("clients", tags=["client", "active"]))

    acme = clients / "acme"
    acme.mkdir()
    write_folder_nature(acme, _make("acme", tags=["client", "acme"]))

    startup = clients / "startup"
    startup.mkdir()
    write_folder_nature(startup, _make("startup", tags=["client", "startup"]))

    archive = tmp_path / "archive"
    archive.mkdir()
    write_folder_nature(archive, _make("archive", being="collector", tags=["archive"]))

    docs = tmp_path / "docs"
    docs.mkdir()
    write_folder_nature(docs, _make("docs", being="documentation", tags=["docs"]))

    return tmp_path


# ── list_all ─────────────────────────────────────────────────────────────


def test_list_all_finds_every_nature(tree: Path):
    natures = list_all(tree)
    names = {n.identity.name for n in natures}
    assert names == {"root", "clients", "acme", "startup", "archive", "docs"}


def test_list_all_empty_root(tmp_path: Path):
    natures = list_all(tmp_path)
    assert natures == []


def test_list_all_skips_skip_dirs(tmp_path: Path):
    """Folder-natures inside .git, node_modules etc. are skipped."""
    write_folder_nature(tmp_path, _make("root"))

    for skip in (".git", "node_modules", "__pycache__"):
        d = tmp_path / skip
        d.mkdir()
        write_folder_nature(d, _make(skip))

    natures = list_all(tmp_path)
    names = {n.identity.name for n in natures}
    assert names == {"root"}


def test_list_all_skips_hidden_dirs(tmp_path: Path):
    """Other hidden directories (.foo) are also skipped."""
    write_folder_nature(tmp_path, _make("root"))

    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    write_folder_nature(hidden, _make("hidden"))

    natures = list_all(tmp_path)
    names = {n.identity.name for n in natures}
    assert names == {"root"}


# ── search ───────────────────────────────────────────────────────────────


def test_search_by_tag(tree: Path):
    results = search(tree, tag="client")
    names = {n.identity.name for n in results}
    assert names == {"clients", "acme", "startup"}


def test_search_by_tag_case_insensitive(tree: Path):
    results = search(tree, tag="CLIENT")
    names = {n.identity.name for n in results}
    assert names == {"clients", "acme", "startup"}


def test_search_by_being(tree: Path):
    results = search(tree, being="collector")
    names = {n.identity.name for n in results}
    assert names == {"archive"}


def test_search_by_name(tree: Path):
    results = search(tree, name="acme")
    names = {n.identity.name for n in results}
    assert names == {"acme"}


def test_search_combined_filters(tree: Path):
    """Tag AND being AND name combine as AND."""
    results = search(tree, being="workspace", tag="client")
    names = {n.identity.name for n in results}
    assert names == {"clients", "acme", "startup"}

    results = search(tree, being="documentation", tag="client")
    assert results == []


def test_search_no_filters_returns_all(tree: Path):
    """No filters == list_all."""
    all_n = list_all(tree)
    searched = search(tree)
    assert len(searched) == len(all_n)


# ── iter_nature_file_paths ──────────────────────────────────────────────


def test_iter_paths(tree: Path):
    paths = list(iter_nature_file_paths(tree))
    assert len(paths) == 6
    for p in paths:
        assert p.name == ".folder-nature"
