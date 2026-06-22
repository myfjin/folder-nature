"""Schema v1.0 — defines the shape of a ``.folder-nature`` file.

A folder-nature is structured YAML with required + optional fields and a
controlled vocabulary for the ``identity.being`` field. Schema is versioned
so future bumps can migrate cleanly via :mod:`folder_nature.migrate`.

This module is pure — no filesystem I/O, no YAML parsing. Just dataclasses
and validation. Use :mod:`folder_nature.core` for read/write.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"

# Controlled vocabulary for `identity.being`. Extensible — unknown values
# log a warning during validation but don't reject the file.
BEING_TYPES = frozenset({
    "director",       # root/boss folder, children inherit
    "collector",      # archive/historical storage
    "workspace",      # active working space
    "assets",         # non-code resources (images, fonts, media)
    "configs",        # system/app configuration
    "documentation",  # docs, references, guides
    "ideas",          # unstructured exploration
    "external",       # third-party content (vendored, downloaded)
    "legal",          # contracts, agreements, compliance
    "team-shared",    # multi-person collaboration
    "private",        # sensitive/restricted
    "system",         # system-managed (don't manually edit)
})

# Field-level constraints
MAX_NAME_LEN = 100
MAX_PURPOSE_LEN = 500
MAX_TAG_LEN = 30
MAX_RULE_LEN = 500
MAX_TAGS_COUNT = 50
MAX_RULES_COUNT = 100


class SchemaError(ValueError):
    """Raised on validation failure. Message names the offending field."""


@dataclass
class Identity:
    """The mandatory identity block of a folder-nature."""
    name: str
    being: str
    purpose: str


@dataclass
class Memory:
    """Optional historical context. All fields optional within the block."""
    created: Optional[str] = None                      # ISO date YYYY-MM-DD
    last_significant_change: Optional[str] = None       # ISO date
    notable_events: List[str] = field(default_factory=list)


@dataclass
class FolderNature:
    """A parsed, validated folder-nature record.

    Construct via :func:`folder_nature.schema.from_dict` (does validation) or
    by manual instantiation + explicit :meth:`validate` call.
    """
    schema_version: str = SCHEMA_VERSION
    identity: Optional[Identity] = None
    director: bool = False
    tags: List[str] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)
    memory: Optional[Memory] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a YAML-friendly dict. Drops None values for cleanliness."""
        out: Dict[str, Any] = {"schema_version": self.schema_version}
        if self.identity is not None:
            out["identity"] = {
                "name": self.identity.name,
                "being": self.identity.being,
                "purpose": self.identity.purpose,
            }
        out["director"] = self.director
        if self.tags:
            out["tags"] = list(self.tags)
        if self.rules:
            out["rules"] = list(self.rules)
        if self.memory is not None:
            mem: Dict[str, Any] = {}
            if self.memory.created:
                mem["created"] = self.memory.created
            if self.memory.last_significant_change:
                mem["last_significant_change"] = self.memory.last_significant_change
            if self.memory.notable_events:
                mem["notable_events"] = list(self.memory.notable_events)
            if mem:
                out["memory"] = mem
        return out

    def validate(self) -> None:
        """Run all schema checks. Raises SchemaError on first violation."""
        validate(self.to_dict())


def from_dict(data: Dict[str, Any]) -> FolderNature:
    """Construct + validate a FolderNature from a parsed YAML dict.

    Raises :class:`SchemaError` if the dict doesn't conform.
    """
    validate(data)

    identity_raw = data["identity"]
    identity = Identity(
        name=identity_raw["name"],
        being=identity_raw["being"],
        purpose=identity_raw["purpose"],
    )

    memory: Optional[Memory] = None
    if "memory" in data:
        mem_raw = data["memory"]
        memory = Memory(
            created=mem_raw.get("created"),
            last_significant_change=mem_raw.get("last_significant_change"),
            notable_events=list(mem_raw.get("notable_events", [])),
        )

    return FolderNature(
        schema_version=data.get("schema_version", SCHEMA_VERSION),
        identity=identity,
        director=bool(data.get("director", False)),
        tags=list(data.get("tags", [])),
        rules=list(data.get("rules", [])),
        memory=memory,
    )


def validate(data: Dict[str, Any]) -> None:
    """Validate a parsed YAML dict against schema v1.0.

    Raises :class:`SchemaError` with a descriptive message on first violation.
    Returns None on success.
    """
    if not isinstance(data, dict):
        raise SchemaError("root must be a mapping/dict")

    # schema_version
    version = data.get("schema_version")
    if version is None:
        raise SchemaError("schema_version is required")
    if not isinstance(version, str):
        raise SchemaError(f"schema_version must be a string, got {type(version).__name__}")
    if version != SCHEMA_VERSION:
        raise SchemaError(
            f"unsupported schema_version {version!r}; "
            f"this build supports {SCHEMA_VERSION!r} only. "
            "Use `folder-nature migrate` for older versions."
        )

    # identity (required)
    if "identity" not in data:
        raise SchemaError("identity block is required")
    identity = data["identity"]
    if not isinstance(identity, dict):
        raise SchemaError("identity must be a mapping/dict")

    for fname in ("name", "being", "purpose"):
        if fname not in identity:
            raise SchemaError(f"identity.{fname} is required")
        val = identity[fname]
        if not isinstance(val, str):
            raise SchemaError(f"identity.{fname} must be a string")
        if not val.strip():
            raise SchemaError(f"identity.{fname} must be non-empty")

    if len(identity["name"]) > MAX_NAME_LEN:
        raise SchemaError(f"identity.name exceeds {MAX_NAME_LEN} chars")
    if len(identity["purpose"]) > MAX_PURPOSE_LEN:
        raise SchemaError(f"identity.purpose exceeds {MAX_PURPOSE_LEN} chars")

    being = identity["being"]
    if being not in BEING_TYPES:
        # Unknown but not rejected — extensibility hatch. Soft warning only.
        # (Validation passes; a callable warning hook could be added later.)
        pass

    # director (optional, bool)
    if "director" in data and not isinstance(data["director"], bool):
        raise SchemaError("director must be a boolean")

    # tags (optional, list of short strings)
    if "tags" in data:
        tags = data["tags"]
        if not isinstance(tags, list):
            raise SchemaError("tags must be a list")
        if len(tags) > MAX_TAGS_COUNT:
            raise SchemaError(f"tags count exceeds {MAX_TAGS_COUNT}")
        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                raise SchemaError(f"tags[{i}] must be a string")
            if len(tag) > MAX_TAG_LEN:
                raise SchemaError(f"tags[{i}] exceeds {MAX_TAG_LEN} chars")
            if not tag.strip():
                raise SchemaError(f"tags[{i}] must be non-empty")

    # rules (optional, list of strings)
    if "rules" in data:
        rules = data["rules"]
        if not isinstance(rules, list):
            raise SchemaError("rules must be a list")
        if len(rules) > MAX_RULES_COUNT:
            raise SchemaError(f"rules count exceeds {MAX_RULES_COUNT}")
        for i, rule in enumerate(rules):
            if not isinstance(rule, str):
                raise SchemaError(f"rules[{i}] must be a string")
            if len(rule) > MAX_RULE_LEN:
                raise SchemaError(f"rules[{i}] exceeds {MAX_RULE_LEN} chars")

    # memory (optional, dict)
    if "memory" in data:
        mem = data["memory"]
        if not isinstance(mem, dict):
            raise SchemaError("memory must be a mapping/dict")
        for date_field in ("created", "last_significant_change"):
            if date_field in mem and mem[date_field] is not None:
                if not isinstance(mem[date_field], str):
                    raise SchemaError(f"memory.{date_field} must be a string (ISO date)")
                # Light date format check — YYYY-MM-DD
                val = mem[date_field]
                if len(val) >= 10 and val[4] == "-" and val[7] == "-":
                    try:
                        date.fromisoformat(val[:10])
                    except ValueError as e:
                        raise SchemaError(f"memory.{date_field} not a valid ISO date: {e}")
        if "notable_events" in mem:
            events = mem["notable_events"]
            if not isinstance(events, list):
                raise SchemaError("memory.notable_events must be a list")
            for i, ev in enumerate(events):
                if not isinstance(ev, str):
                    raise SchemaError(f"memory.notable_events[{i}] must be a string")
