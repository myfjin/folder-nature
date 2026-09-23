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

__version__ = "0.2.1"
__schema_version__ = "1.0"

from .core import (
    NATURE_FILENAME,
    find_director,
    get_folder_nature,
    read_folder_nature,
    write_folder_nature,
)
from .schema import (
    BEING_TYPES,
    SCHEMA_VERSION,
    FolderNature,
    SchemaError,
)
from .schema import (
    validate as validate_data,
)
from .search import list_all, search

__all__ = [
    "BEING_TYPES",
    "NATURE_FILENAME",
    "SCHEMA_VERSION",
    "FolderNature",
    "SchemaError",
    "__schema_version__",
    "__version__",
    "find_director",
    "get_folder_nature",
    "list_all",
    "read_folder_nature",
    "search",
    "validate_data",
    "write_folder_nature",
]
