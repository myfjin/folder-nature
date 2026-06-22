"""Filesystem operations on ``.folder-nature`` files.

Read, write, walk-upward-to-director. All paths are :class:`pathlib.Path`.
YAML I/O via PyYAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional, Tuple

import yaml

from .schema import FolderNature, from_dict, SchemaError, SCHEMA_VERSION


NATURE_FILENAME = ".folder-nature"


def _walk_upward(start: Path) -> Iterator[Path]:
    """Yield ancestor directories of ``start`` (inclusive), stopping at root.

    Ensures the walk always terminates — yields each ancestor exactly once,
    stops when ``current.parent == current`` (filesystem root).
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent
    seen = set()
    while True:
        if current in seen:
            return
        seen.add(current)
        yield current
        parent = current.parent
        if parent == current:
            return
        current = parent


def read_folder_nature(path: Path) -> FolderNature:
    """Read + validate a single ``.folder-nature`` file at ``path``.

    Raises :class:`FileNotFoundError` if path doesn't exist.
    Raises :class:`SchemaError` if file content fails validation.
    Raises :class:`yaml.YAMLError` if file isn't valid YAML.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no such file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise SchemaError(f"{path}: file is empty or contains only YAML null")
    return from_dict(data)


def write_folder_nature(directory: Path, nature: FolderNature) -> Path:
    """Write a FolderNature to ``directory/.folder-nature``.

    Validates the nature before writing. Returns the path written.
    Overwrites existing file (caller's responsibility to confirm).
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"not a directory: {directory}")

    nature.validate()
    target = directory / NATURE_FILENAME
    with target.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            nature.to_dict(),
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    return target


def get_folder_nature(path: Path) -> Optional[FolderNature]:
    """Return the closest ``.folder-nature`` walking upward from ``path``.

    Returns ``None`` if no ``.folder-nature`` exists in any ancestor.
    Raises :class:`SchemaError` if the closest file is invalid (caller can
    catch + try the next ancestor if desired).
    """
    for ancestor in _walk_upward(Path(path)):
        nature_file = ancestor / NATURE_FILENAME
        if nature_file.exists():
            return read_folder_nature(nature_file)
    return None


def find_director(path: Path) -> Tuple[Optional[Path], Optional[FolderNature]]:
    """Walk upward until finding a folder-nature with ``director: true``.

    Returns ``(director_path, nature)`` or ``(None, None)`` if no director
    is found in any ancestor.

    Skips ancestors with invalid folder-nature files (logs nothing — caller
    can run ``validate`` to find broken files explicitly).
    """
    for ancestor in _walk_upward(Path(path)):
        nature_file = ancestor / NATURE_FILENAME
        if not nature_file.exists():
            continue
        try:
            nature = read_folder_nature(nature_file)
        except (SchemaError, yaml.YAMLError):
            continue
        if nature.director:
            return ancestor, nature
    return None, None
