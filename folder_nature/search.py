"""Search + list operations over a directory tree.

These functions walk the filesystem looking for ``.folder-nature`` files and
filter/sort by tag, being, or schema-validity. Walking respects standard
exclude patterns (hidden dirs starting with ``.`` other than the user's
content roots, virtual environments, build artifacts).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml

from .core import NATURE_FILENAME, read_folder_nature
from .schema import FolderNature, SchemaError

# Directory names skipped during search/list — performance + sanity.
# Hidden directories (starting with ``.``) are also skipped EXCEPT this list
# (which lets the tool find folders that intentionally start with a dot).
_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".pytest_cache",
        "build",
        "dist",
        ".eggs",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def _iter_nature_files(root: Path) -> Iterator[Path]:
    """Yield every ``.folder-nature`` file under ``root``, depth-first.

    Skips directories in :data:`_SKIP_DIRS` and hidden directories (starting
    with ``.`` and length > 1) for performance + cleanliness. The root itself
    is always searched even if it starts with a dot.
    """
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        return

    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except (OSError, PermissionError):
            continue

        # First, check this directory itself for a folder-nature file
        nature_file = current / NATURE_FILENAME
        if nature_file.exists() and nature_file.is_file():
            yield nature_file

        # Then descend into subdirectories
        for child in children:
            if not child.is_dir():
                continue
            name = child.name
            if name in _SKIP_DIRS:
                continue
            # Skip hidden dirs unless this is the search root
            if name.startswith(".") and len(name) > 1:
                continue
            stack.append(child)


def list_all(root: Path) -> list[FolderNature]:
    """Return every valid FolderNature found under ``root`` (depth-first).

    Invalid YAML or schema violations are silently skipped — use
    :func:`folder_nature.cli.validate_tree` to report errors explicitly.
    """
    out: list[FolderNature] = []
    for nf in _iter_nature_files(root):
        try:
            out.append(read_folder_nature(nf))
        except (SchemaError, yaml.YAMLError, OSError):
            continue
    return out


def search(
    root: Path,
    *,
    tag: str | None = None,
    being: str | None = None,
    name: str | None = None,
) -> list[FolderNature]:
    """Filter folder-natures under ``root`` by tag / being / name.

    All filters are AND-combined. ``None`` for a filter means "don't filter".
    Tag/name matching is substring + case-insensitive; ``being`` is exact match.

    Returns the matching natures in walk order (depth-first).
    """
    out: list[FolderNature] = []
    tag_lower = tag.lower() if tag else None
    name_lower = name.lower() if name else None

    for nature in list_all(root):
        if being is not None and nature.identity is not None:
            if nature.identity.being != being:
                continue
        if tag_lower is not None:
            if not any(tag_lower in t.lower() for t in nature.tags):
                continue
        if name_lower is not None and nature.identity is not None:
            if name_lower not in nature.identity.name.lower():
                continue
        out.append(nature)

    return out


def iter_nature_file_paths(root: Path) -> Iterator[Path]:
    """Public iterator over .folder-nature file paths (no validation).

    Useful for the ``list`` and ``validate`` CLI commands which need paths
    even for invalid files.
    """
    yield from _iter_nature_files(root)
