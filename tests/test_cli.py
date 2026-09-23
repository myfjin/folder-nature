"""Tests for folder_nature.cli — argparse + subcommand integration."""

from __future__ import annotations

from pathlib import Path

from folder_nature.cli import main as cli_main
from folder_nature.core import NATURE_FILENAME, read_folder_nature
from folder_nature.schema import SCHEMA_VERSION

# Each cli call goes via cli_main(argv) — argv is the args list AFTER the
# program name (i.e. matches what argparse would see in sys.argv[1:]).


# ── init ─────────────────────────────────────────────────────────────────


def test_init_with_template(tmp_path: Path, capsys):
    rc = cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "demo"])
    assert rc == 0
    nature_file = tmp_path / NATURE_FILENAME
    assert nature_file.exists()
    nature = read_folder_nature(nature_file)
    assert nature.identity.name == "demo"
    assert nature.identity.being == "workspace"

    out = capsys.readouterr().out
    assert "created" in out


def test_init_without_template_requires_fields(tmp_path: Path, capsys):
    rc = cli_main(["init", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "must provide" in err


def test_init_minimal_manual(tmp_path: Path):
    rc = cli_main(
        [
            "init",
            str(tmp_path),
            "--name",
            "myproj",
            "--being",
            "workspace",
            "--purpose",
            "my project",
        ]
    )
    assert rc == 0
    nature = read_folder_nature(tmp_path / NATURE_FILENAME)
    assert nature.identity.name == "myproj"


def test_init_refuses_overwrite_without_force(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "first"])
    rc = cli_main(
        ["init", str(tmp_path), "--template", "workspace", "--name", "second"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err


def test_init_force_overwrites(tmp_path: Path):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "first"])
    rc = cli_main(
        [
            "init",
            str(tmp_path),
            "--template",
            "workspace",
            "--name",
            "second",
            "--force",
        ]
    )
    assert rc == 0
    nature = read_folder_nature(tmp_path / NATURE_FILENAME)
    assert nature.identity.name == "second"


def test_init_nonexistent_dir(tmp_path: Path, capsys):
    rc = cli_main(
        [
            "init",
            str(tmp_path / "no-such-dir"),
            "--template",
            "workspace",
            "--name",
            "x",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "does not exist" in err


# ── show ─────────────────────────────────────────────────────────────────


def test_show_existing(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "demo"])
    rc = cli_main(["show", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo" in out
    assert "workspace" in out


def test_show_missing(tmp_path: Path, capsys):
    rc = cli_main(["show", str(tmp_path)])
    assert rc == 1


# ── query ────────────────────────────────────────────────────────────────


def test_query_finds_director(tmp_path: Path, capsys):
    cli_main(
        [
            "init",
            str(tmp_path),
            "--name",
            "boss",
            "--being",
            "director",
            "--purpose",
            "root",
            "--director",
        ]
    )
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)

    rc = cli_main(["query", str(deep)])
    assert rc == 0
    out = capsys.readouterr().out
    assert str(tmp_path.resolve()) in out


def test_query_no_director(tmp_path: Path, capsys):
    rc = cli_main(["query", str(tmp_path)])
    assert rc == 1


# ── search ───────────────────────────────────────────────────────────────


def test_search_by_tag(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "client-project", "--name", "demo"])
    rc = cli_main(["search", str(tmp_path), "--tag", "client"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo" in out


def test_search_no_matches(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "demo"])
    rc = cli_main(["search", str(tmp_path), "--tag", "nonexistent"])
    assert rc == 1


# ── validate ─────────────────────────────────────────────────────────────


def test_validate_clean_tree(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "demo"])
    rc = cli_main(["validate", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 error" in out


def test_validate_catches_bad_file(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "demo"])
    # Corrupt the file
    (tmp_path / NATURE_FILENAME).write_text(
        "schema_version: '99.9'\nidentity:\n  name: x\n  being: workspace\n  purpose: y\n"
    )
    rc = cli_main(["validate", str(tmp_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "INVALID" in out or "BAD" in out


# ── list ─────────────────────────────────────────────────────────────────


def test_list_shows_tree(tmp_path: Path, capsys):
    cli_main(["init", str(tmp_path), "--template", "workspace", "--name", "root"])
    sub = tmp_path / "sub"
    sub.mkdir()
    cli_main(["init", str(sub), "--template", "archive", "--name", "old-stuff"])

    rc = cli_main(["list", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "root" in out
    assert "old-stuff" in out
    assert "2 folder-nature" in out


# ── version ──────────────────────────────────────────────────────────────


def test_version(capsys):
    rc = cli_main(["version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "folder-nature" in out
    assert SCHEMA_VERSION in out
