"""Command-line interface — the ``folder-nature`` binary.

Subcommands (MVP):
    init        Create a new .folder-nature in the target directory
    show        Print the closest .folder-nature (walks up from target)
    query       Find the director ancestor of target
    search      Find folders matching --tag/--being/--name
    validate    Check schema-validity of all .folder-nature files in tree
    list        Tree-view of every .folder-nature
    version     Print tool + schema versions

Phase 2 (post-MVP) subcommands: ai-suggest, watch, migrate, export, import.
"""

from __future__ import annotations

import argparse
import importlib.resources as pkg_resources
import sys
from pathlib import Path

import yaml

from . import __schema_version__, __version__
from .core import (
    NATURE_FILENAME,
    find_director,
    get_folder_nature,
    read_folder_nature,
    write_folder_nature,
)
from .schema import (
    BEING_TYPES,
    FolderNature,
    Identity,
    SchemaError,
    from_dict,
)
from .search import iter_nature_file_paths, list_all, search

# Default templates ship in the package; user-selectable via ``--template``.
DEFAULT_TEMPLATES = (
    "workspace",
    "client-project",
    "archive",
    "deployment",
    "documentation",
)


# ── Template loading ────────────────────────────────────────────────────────


def _load_template(name: str) -> dict:
    """Load a template from the packaged templates dir.

    Returns the parsed YAML dict. Raises :class:`FileNotFoundError` if name
    isn't a known template.
    """
    try:
        # importlib.resources for Python 3.9+; falls back to traversable
        files = pkg_resources.files("folder_nature.templates")
        candidate = files / f"{name}.yaml"
        if not candidate.is_file():
            raise FileNotFoundError(
                f"unknown template {name!r}. "
                f"Available: {', '.join(sorted(DEFAULT_TEMPLATES))}"
            )
        return yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise


# ── Subcommand handlers ────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    """folder-nature init [PATH] [--template NAME]"""
    target = Path(args.path).resolve()
    if not target.exists():
        print(
            f"folder-nature: error: directory does not exist: {target}", file=sys.stderr
        )
        return 2
    if not target.is_dir():
        print(f"folder-nature: error: not a directory: {target}", file=sys.stderr)
        return 2

    nature_file = target / NATURE_FILENAME
    if nature_file.exists() and not args.force:
        print(
            f"folder-nature: error: {NATURE_FILENAME} already exists at {target}. "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    if args.template:
        try:
            data = _load_template(args.template)
        except FileNotFoundError as e:
            print(f"folder-nature: error: {e}", file=sys.stderr)
            return 2
        # If --name is provided, override the template's identity.name with
        # the actual directory name (templates use placeholder).
        if "identity" in data and isinstance(data["identity"], dict):
            data["identity"].setdefault("name", target.name)
            if args.name:
                data["identity"]["name"] = args.name
        try:
            nature = from_dict(data)
        except SchemaError as e:
            print(
                f"folder-nature: error: template {args.template!r} invalid: {e}",
                file=sys.stderr,
            )
            return 1
    else:
        # Minimal nature without template — user provides name/being/purpose
        if not (args.name and args.being and args.purpose):
            print(
                "folder-nature: error: without --template, you must provide "
                "--name, --being, and --purpose",
                file=sys.stderr,
            )
            print(
                f"  Or pick a template with --template (one of: "
                f"{', '.join(sorted(DEFAULT_TEMPLATES))})",
                file=sys.stderr,
            )
            return 2
        nature = FolderNature(
            identity=Identity(
                name=args.name,
                being=args.being,
                purpose=args.purpose,
            ),
            director=args.director,
            tags=args.tag or [],
        )

    try:
        written_path = write_folder_nature(target, nature)
    except SchemaError as e:
        print(f"folder-nature: error: validation failed: {e}", file=sys.stderr)
        return 1
    print(f"created {written_path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """folder-nature show [PATH] — print closest .folder-nature."""
    target = Path(args.path).resolve()
    nature = get_folder_nature(target)
    if nature is None:
        print(
            f"folder-nature: no {NATURE_FILENAME} found in {target} or any ancestor",
            file=sys.stderr,
        )
        return 1
    print(
        yaml.safe_dump(
            nature.to_dict(),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip()
    )
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """folder-nature query [PATH] — find director ancestor."""
    target = Path(args.path).resolve()
    director_path, nature = find_director(target)
    if director_path is None or nature is None:
        print(
            f"folder-nature: no director found walking up from {target}",
            file=sys.stderr,
        )
        return 1
    print(f"{director_path}")
    if args.verbose:
        print()
        print(
            yaml.safe_dump(
                nature.to_dict(),
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            ).rstrip()
        )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """folder-nature search [--tag X] [--being Y] [--name Z] [ROOT]"""
    root = Path(args.root).resolve()
    results = search(root, tag=args.tag, being=args.being, name=args.name)
    if not results:
        print(f"folder-nature: no matches under {root}", file=sys.stderr)
        return 1
    for nature in results:
        if nature.identity is None:
            continue
        tags = ",".join(nature.tags) if nature.tags else "-"
        print(f"{nature.identity.being:14s}  {nature.identity.name:30s}  tags=[{tags}]")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """folder-nature validate [ROOT] — schema-check all .folder-nature files."""
    root = Path(args.root).resolve()
    total = 0
    errors = 0
    for nf in iter_nature_file_paths(root):
        total += 1
        try:
            read_folder_nature(nf)
        except SchemaError as e:
            errors += 1
            print(f"INVALID  {nf}: {e}")
        except yaml.YAMLError as e:
            errors += 1
            print(f"BAD-YAML {nf}: {e}")
        except OSError as e:
            errors += 1
            print(f"IO-ERROR {nf}: {e}")
    print(f"\nchecked {total} file(s), {errors} error(s)")
    return 0 if errors == 0 else 1


def cmd_list(args: argparse.Namespace) -> int:
    """folder-nature list [ROOT] — tree-view of all .folder-nature files."""
    root = Path(args.root).resolve()
    natures = list_all(root)
    if not natures:
        print(f"folder-nature: no .folder-nature files under {root}", file=sys.stderr)
        return 1
    for nature in natures:
        if nature.identity is None:
            continue
        tags = ",".join(nature.tags) if nature.tags else "-"
        marker = "*" if nature.director else " "
        print(
            f"{marker} {nature.identity.being:14s}  {nature.identity.name:30s}  "
            f"tags=[{tags}]"
        )
    print(f"\n{len(natures)} folder-nature file(s) under {root}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """folder-nature version"""
    print(f"folder-nature {__version__}  (schema v{__schema_version__})")
    return 0


# ── argparse plumbing ──────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folder-nature",
        description="Semantic identity for filesystem folders.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a new .folder-nature in directory")
    p_init.add_argument(
        "path", nargs="?", default=".", help="Target directory (default: cwd)"
    )
    p_init.add_argument(
        "--template", choices=sorted(DEFAULT_TEMPLATES), help="Use a packaged template"
    )
    p_init.add_argument("--name", help="identity.name (overrides template default)")
    p_init.add_argument(
        "--being",
        choices=sorted(BEING_TYPES),
        help="identity.being (required without --template)",
    )
    p_init.add_argument(
        "--purpose", help="identity.purpose (required without --template)"
    )
    p_init.add_argument("--tag", action="append", help="Add a tag (repeatable)")
    p_init.add_argument("--director", action="store_true", help="Mark as director")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="Print closest .folder-nature")
    p_show.add_argument("path", nargs="?", default=".")
    p_show.set_defaults(func=cmd_show)

    p_query = sub.add_parser("query", help="Find director ancestor")
    p_query.add_argument("path", nargs="?", default=".")
    p_query.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Also print the director's .folder-nature content",
    )
    p_query.set_defaults(func=cmd_query)

    p_search = sub.add_parser("search", help="Find folders matching criteria")
    p_search.add_argument("root", nargs="?", default=".")
    p_search.add_argument("--tag", help="Substring match against tags")
    p_search.add_argument("--being", choices=sorted(BEING_TYPES))
    p_search.add_argument("--name", help="Substring match against name")
    p_search.set_defaults(func=cmd_search)

    p_validate = sub.add_parser("validate", help="Schema-check tree")
    p_validate.add_argument("root", nargs="?", default=".")
    p_validate.set_defaults(func=cmd_validate)

    p_list = sub.add_parser("list", help="Tree-view of all .folder-nature files")
    p_list.add_argument("root", nargs="?", default=".")
    p_list.set_defaults(func=cmd_list)

    sub.add_parser("version", help="Print version").set_defaults(func=cmd_version)

    # v-next: the mark layer (trademark / watermark / copy / sign / verify / scan).
    # Attribution + authenticity, never prevention. See folder_nature.mark.
    from .mark.cli_mark import add_mark_subcommands

    add_mark_subcommands(sub)

    return parser


def main(argv: list | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
