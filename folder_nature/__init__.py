"""folder-nature — semantic identity for filesystem folders.

A directory becomes a conversation partner: it has identity, purpose, rules,
and history, all captured in a hidden ``.folder-nature`` YAML file.

Public API:

    from folder_nature import (
        FolderNature,
        SchemaError,
        find_director,
        get_folder_nature,
        write_folder_nature,
        search,
        validate,
    )

CLI entry point: ``folder-nature`` (see ``folder_nature.cli``).
"""

from __future__ import annotations

__version__ = "0.1.0"
__schema_version__ = "1.0"

from .schema import (
    FolderNature,
    SchemaError,
    SCHEMA_VERSION,
    BEING_TYPES,
    validate as validate_data,
)
from .core import (
    find_director,
    get_folder_nature,
    read_folder_nature,
    write_folder_nature,
    NATURE_FILENAME,
)
from .search import search, list_all

__all__ = [
    "__version__",
    "__schema_version__",
    "FolderNature",
    "SchemaError",
    "SCHEMA_VERSION",
    "BEING_TYPES",
    "NATURE_FILENAME",
    "validate_data",
    "find_director",
    "get_folder_nature",
    "read_folder_nature",
    "write_folder_nature",
    "search",
    "list_all",
]
