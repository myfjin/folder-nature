"""Leak detection -> trace to buyer -> cite the accepted license.

The chain (REQ-4 + REQ-5), fired ONLY on a detected leak, NEVER on a customer's
local copying (which is invisible to us and not our business):

    found content  ->  extract watermark  ->  look up number in the sale
    registry  ->  name the buyer  ->  generate a copyright "departure" claim
    that cites the license THAT BUYER accepted.

Honest scope, stated plainly:
  * We detect a leak only in content we can actually see. Automated crawling of
    GitHub / pastebin is a thin *adapter* around this core — you point the
    scanner at content (a file, a directory, or text you already found). The
    value is the trace + cited-license claim, which needs the seller-side
    registry and works on any content handed to it.
  * A master (number 0) hit is NOT a customer leak — it is our own original,
    and is reported as such, never as a buyer breach.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .sale import SaleRegistry
from .watermark import MarkReport, verify_file, verify_text


@dataclass
class LeakHit:
    source: str  # path or "<text>"
    number: str
    trademark: str
    report: MarkReport
    buyer: dict | None = None  # sale record dict, if traced

    @property
    def is_master(self) -> bool:
        return str(self.number) == "0"

    @property
    def traced(self) -> bool:
        return self.buyer is not None


def _hit_from_report(
    source: str, rep: MarkReport, registry: SaleRegistry | None
) -> LeakHit | None:
    if not rep.is_marked or rep.payload is None:
        return None
    buyer = None
    if registry is not None and str(rep.payload.number) != "0":
        buyer = registry.lookup(rep.payload.number)
    return LeakHit(
        source=source,
        number=str(rep.payload.number),
        trademark=rep.payload.trademark,
        report=rep,
        buyer=buyer,
    )


def scan_text(
    text: str, registry: SaleRegistry | None = None, source: str = "<text>"
) -> LeakHit | None:
    """Scan a blob of text for a watermark; trace if a registry is given."""
    return _hit_from_report(source, verify_text(text), registry)


def scan_path(path: Path, registry: SaleRegistry | None = None) -> list[LeakHit]:
    """Scan a file or a directory tree; return every watermark hit found."""
    path = Path(path)
    hits: list[LeakHit] = []
    files = (
        [path]
        if path.is_file()
        else [p for p in sorted(path.rglob("*")) if p.is_file()]
    )
    for f in files:
        hit = _hit_from_report(str(f), verify_file(f), registry)
        if hit is not None:
            hits.append(hit)
    return hits


def generate_claim(hit: LeakHit) -> str:
    """Render a copyright 'departure' claim for a traced leak.

    Requires a traced buyer with an accepted license — a claim with teeth cites
    the terms the buyer accepted. Untraced or master hits return an honest
    non-claim explaining why no claim is issued.
    """
    if hit.is_master:
        return (
            f"NO CLAIM: watermark number 0 is the MASTER original of "
            f"'{hit.trademark}'. This is our own file, not a customer leak."
        )
    if not hit.traced:
        return (
            f"NO CLAIM (untraceable): found a copy of '{hit.trademark}' marked "
            f"number {hit.number}, but that number is not in the sale registry. "
            "Without a recorded, license-accepted sale there is nothing to cite."
        )

    buyer = hit.buyer or {}
    lic = buyer.get("license", {})
    pending = (
        " (placeholder — bind real license text before enforcing)"
        if lic.get("is_placeholder")
        else ""
    )
    return (
        "COPYRIGHT DEPARTURE CLAIM\n"
        f"  work:            {hit.trademark}\n"
        f"  watermark:       number {hit.number}\n"
        f"  found at:        {hit.source}\n"
        f"  traced buyer:    {buyer.get('customer_id', '?')}\n"
        f"  sold at:         {buyer.get('sold_at', '?')}\n"
        f"  license tier:    {lic.get('license_tier', '?')}\n"
        f"  license sha256:  {lic.get('license_sha256', '?')}{pending}\n"
        f"  accepted at:     {lic.get('accepted_at', '?')}\n"
        "  basis:           the buyer accepted the above license at purchase; "
        "this copy, uniquely watermarked to them, appears outside its terms.\n"
        "  note:            attribution evidence, not a prevention claim."
    )
