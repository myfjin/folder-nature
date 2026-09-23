"""Sale-time per-customer stamping + the license-acceptance registry.

This is the seller side of attribution + the enforcement chain (REQ-2 slot,
REQ-5). Three linked ideas:

  1. A per-customer NUMBER encodes WHO bought a copy. It is stamped at SALE
     (never at harvest), so a leaked file traces back to one buyer.
  2. A mark only has TEETH if a license was ACCEPTED. The registry refuses to
     stamp a sale unless a click-accepted license record exists for the buyer.
  3. The registry is the seller's ledger. A later leak (see :mod:`leak`) looks
     the number up here to name the buyer and cite the accepted license.

IMPORTANT (matches the current build gate): the real library is stamped MASTER
(number ``0``) for now. ``stamp_sale`` builds and tests the per-customer path,
but is only fired at an actual point of sale.

The license TEXT is deliberately a placeholder slot. The words come after the
offer decision; the MECHANISM (present -> accept -> hash -> cite) is what ships.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import MarkConfig
from .payload import WatermarkPayload
from .watermark import is_supported, stamp_file


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── license slot (texts are a later gate; the mechanism ships now) ────────────


def license_text(tier: str, licenses_dir: Path | None = None) -> tuple[str, bool]:
    """Return ``(text, is_placeholder)`` for a tier.

    If ``licenses_dir/<tier>.txt`` exists it is used; otherwise a clearly-marked
    placeholder is returned so the chain is testable before the words are
    finalised. ``is_placeholder`` is True in the latter case.
    """
    if licenses_dir:
        p = Path(licenses_dir) / f"{tier}.txt"
        if p.exists():
            return p.read_text(encoding="utf-8"), False
    return (
        (
            f"[LICENSE TEXT PENDING — tier={tier}]\n"
            "This is a reserved slot. The binding license text is set before sale.\n"
        ),
        True,
    )


def license_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class LicenseAcceptance:
    customer_id: str
    tier: str
    license_tier: str
    license_sha256: str
    is_placeholder: bool
    accepted_at: str = field(default_factory=_now)


def accept_license(
    customer_id: str,
    tier: str,
    *,
    licenses_dir: Path | None = None,
    license_tier: str | None = None,
) -> LicenseAcceptance:
    """Record a buyer clicking 'accept' on the presented license.

    This is what a future leak claim cites. The license text is hashed so the
    exact terms accepted are pinned, even once the placeholder is replaced.
    """
    text, placeholder = license_text(tier, licenses_dir)
    return LicenseAcceptance(
        customer_id=customer_id,
        tier=tier,
        license_tier=license_tier or tier,
        license_sha256=license_hash(text),
        is_placeholder=placeholder,
    )


# ── sale records + registry ───────────────────────────────────────────────────


@dataclass
class SaleRecord:
    number: str
    customer_id: str
    trademark: str
    tier: str
    license: LicenseAcceptance
    sold_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class SaleRegistry:
    """Seller-side JSON ledger mapping copy number -> sale record.

    Lives OUTSIDE the sold product (on the seller's machine). Never shipped to
    customers — it is the private map from watermark number to buyer identity.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._by_number: dict[str, dict] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._by_number = {r["number"]: r for r in data.get("sales", [])}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"sales": list(self._by_number.values())}, indent=2, ensure_ascii=False
            )
            + "\n",
            encoding="utf-8",
        )

    def record(self, sale: SaleRecord) -> None:
        if sale.number in self._by_number:
            raise ValueError(
                f"number {sale.number!r} already sold to "
                f"{self._by_number[sale.number]['customer_id']!r}"
            )
        self._by_number[sale.number] = sale.to_dict()
        self.save()

    def lookup(self, number: str) -> dict | None:
        return self._by_number.get(str(number))

    def all(self) -> list[dict]:
        return list(self._by_number.values())


class EnforcementError(RuntimeError):
    """Raised when a sale is attempted without an accepted license."""


def stamp_sale(
    src: Path,
    dst: Path,
    *,
    config: MarkConfig,
    customer_id: str,
    number: str,
    license: LicenseAcceptance,
    registry: SaleRegistry,
) -> SaleRecord:
    """Stamp a per-customer copy at point of sale and record it.

    Enforcement chain: refuses unless ``license`` is an acceptance for the same
    customer (the mark has teeth only because terms were accepted). Copies the
    tree to ``dst``, stamps every supported file with ``number``, and writes the
    sale to the registry so a future leak can be traced + claimed.
    """
    import shutil

    if license.customer_id != customer_id:
        raise EnforcementError(
            "license acceptance customer does not match sale customer — "
            "no accepted license, no enforceable sale"
        )
    if str(number) == "0":
        raise EnforcementError("number 0 is the master original, not a sale")

    src, dst = Path(src), Path(dst)
    if dst.exists():
        raise FileExistsError(f"destination already exists: {dst}")
    shutil.copytree(
        src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.pyc")
    )

    for p in sorted(dst.rglob("*")):
        if p.is_file() and is_supported(p):
            stamp_file(
                p,
                WatermarkPayload(
                    trademark=config.trademark,
                    company=config.company or config.trademark,
                    number=number,
                ),
            )

    sale = SaleRecord(
        number=str(number),
        customer_id=customer_id,
        trademark=config.trademark,
        tier=config.tier,
        license=license,
    )
    registry.record(sale)
    return sale
