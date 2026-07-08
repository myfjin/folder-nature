"""Mark configuration — the *configurable* trademark + tier per folder.

The trademark is NEVER hard-coded (REQ-1). A folder is marked under whatever
name its config supplies; there is deliberately no default trademark string,
so no contested name can leak into output by accident. The mark layer refuses
to stamp until a trademark is explicitly configured.

Config lives in a small YAML file (``.folder-mark.yaml``) at the marked
directory's root, or is supplied ad hoc via the CLI. PyYAML is already a
dependency of the core package, so this adds nothing new.

Tiers (REQ-3) define the numbering vocabulary for copies:

    personal    numbers 1..3     (single decimal char; up to 3 copies)
    team        numbers 0..9     (single decimal char; up to 10, master=0)
    enterprise  base36 >= 10     (alphanumeric; per-seat / effectively unbounded)

The *master* original is always number ``0``. Per-customer numbers are stamped
at sale time (see :mod:`folder_nature.mark.sale`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


MARK_CONFIG_FILENAME = ".folder-mark.yaml"

# The master original is always numbered 0, regardless of tier.
MASTER_NUMBER = "0"


class MarkConfigError(ValueError):
    """Raised when mark configuration is missing or invalid."""


# ── Tiers ───────────────────────────────────────────────────────────────────

# tier -> (allowed copy numbers as an ordered list of string tokens).
# Master (0) is excluded from the *copy* allocation of personal (personal
# copies start at 1); team includes 0..9; enterprise allocates base36 from 10 up.
_PERSONAL_COPY_NUMBERS = [str(n) for n in range(1, 4)]        # 1,2,3
_TEAM_COPY_NUMBERS = [str(n) for n in range(0, 10)]           # 0..9

TIERS = ("personal", "team", "enterprise")

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def base36(n: int) -> str:
    """Encode a non-negative int as lowercase base36 (enterprise numbering)."""
    if n < 0:
        raise ValueError("base36 is for non-negative integers")
    if n == 0:
        return "0"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(_BASE36[r])
    return "".join(reversed(out))


def copy_capacity(tier: str) -> Optional[int]:
    """Max number of *copies* a tier may allocate (excluding the master).

    Returns ``None`` for enterprise (effectively unbounded / per-seat).
    """
    if tier == "personal":
        return len(_PERSONAL_COPY_NUMBERS)      # 3
    if tier == "team":
        return len(_TEAM_COPY_NUMBERS)          # 10 (0..9, incl. master slot)
    if tier == "enterprise":
        return None
    raise MarkConfigError(f"unknown tier {tier!r}; expected one of {TIERS}")


def allocate_copy_number(tier: str, already_issued: list) -> str:
    """Return the next copy number token for ``tier`` given issued tokens.

    Cooperative allocation for honest customers. Raises :class:`MarkConfigError`
    when the tier's capacity is exhausted (personal/team) — this is a limit, not
    an enforcement claim.
    """
    issued = set(already_issued)
    if tier == "personal":
        pool = _PERSONAL_COPY_NUMBERS
    elif tier == "team":
        pool = _TEAM_COPY_NUMBERS
    elif tier == "enterprise":
        # base36 starting at 10 ("a"), skipping anything already issued.
        n = 10
        while base36(n) in issued:
            n += 1
        return base36(n)
    else:
        raise MarkConfigError(f"unknown tier {tier!r}; expected one of {TIERS}")

    for tok in pool:
        if tok not in issued:
            return tok
    raise MarkConfigError(
        f"tier {tier!r} copy capacity exhausted ({len(pool)} numbers). "
        "This is a cooperative limit for honest customers, not anti-piracy."
    )


# ── Config record ───────────────────────────────────────────────────────────


@dataclass
class MarkConfig:
    """Per-folder mark configuration.

    ``trademark`` has no default: it must be supplied. ``license_tier`` is a
    reserved slot for the enforcement chain (REQ-5) — the license *text* is a
    later decision, so only the tier name is carried here.
    """

    trademark: str
    company: Optional[str] = None
    tier: str = "team"
    license_tier: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.trademark or not str(self.trademark).strip():
            raise MarkConfigError(
                "trademark is required and has no default — set it explicitly "
                "(the name is a deliberate human gate; see Phase-0 clearance)."
            )
        if self.tier not in TIERS:
            raise MarkConfigError(
                f"tier {self.tier!r} invalid; expected one of {TIERS}"
            )
        if self.company is None:
            self.company = self.trademark

    def to_dict(self) -> dict:
        out = {"trademark": self.trademark, "company": self.company, "tier": self.tier}
        if self.license_tier is not None:
            out["license_tier"] = self.license_tier
        return out


def load_config(directory: Path) -> Optional[MarkConfig]:
    """Load ``.folder-mark.yaml`` from ``directory`` if present, else None."""
    path = Path(directory) / MARK_CONFIG_FILENAME
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MarkConfigError(f"{path}: expected a YAML mapping")
    return MarkConfig(
        trademark=data.get("trademark", ""),
        company=data.get("company"),
        tier=data.get("tier", "team"),
        license_tier=data.get("license_tier"),
    )


def save_config(directory: Path, config: MarkConfig) -> Path:
    """Write ``config`` to ``directory/.folder-mark.yaml``. Returns the path."""
    path = Path(directory) / MARK_CONFIG_FILENAME
    path.write_text(
        yaml.safe_dump(config.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path
