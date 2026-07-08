"""Cooperative copy-limiter — a tool for HONEST customers, not anti-piracy.

``folder-nature copy SRC DST`` duplicates a marked folder and stamps every
supported file with the next copy number for the folder's tier, tracking issued
numbers in a small ledger so it can auto-increment and honour the tier's cap.

This is explicitly cooperative: a customer who wants to defeat it can just use
``cp``. It does not pretend otherwise. Its value is helping the honest majority
keep their allotted copies numbered and attributable — the same reason people
keep serial numbers on tools they own.

Tiers (from :mod:`folder_nature.mark.config`):
    personal   1..3       team  0..9       enterprise  base36 >= 10
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from .config import MarkConfig, allocate_copy_number
from .payload import WatermarkPayload
from .watermark import is_supported, stamp_file


COPY_LEDGER_FILENAME = ".folder-mark-ledger.yaml"


@dataclass
class CopyLedger:
    """Records which copy numbers have been issued for a source folder."""

    trademark: str
    tier: str
    issued: List[str]

    @classmethod
    def load_or_new(cls, path: Path, config: MarkConfig) -> "CopyLedger":
        path = Path(path)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return cls(
                trademark=data.get("trademark", config.trademark),
                tier=data.get("tier", config.tier),
                issued=list(data.get("issued", [])),
            )
        return cls(trademark=config.trademark, tier=config.tier, issued=[])

    def save(self, path: Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(
                {"trademark": self.trademark, "tier": self.tier, "issued": self.issued},
                sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


@dataclass
class CopyResult:
    number: str
    files_stamped: int
    files_skipped: int
    dst: Path


def copy_tree(src: Path, dst: Path, config: MarkConfig,
              *, number: Optional[str] = None,
              ledger_path: Optional[Path] = None) -> CopyResult:
    """Copy ``src`` -> ``dst`` and stamp every supported file with a copy number.

    ``number`` may be forced; otherwise the next number for the tier is
    allocated from the ledger (raising if the cooperative cap is reached).
    The ledger lives beside the source by default.
    """
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        raise NotADirectoryError(f"source is not a directory: {src}")
    if dst.exists():
        raise FileExistsError(f"destination already exists: {dst}")

    ledger_file = Path(ledger_path) if ledger_path else src / COPY_LEDGER_FILENAME
    ledger = CopyLedger.load_or_new(ledger_file, config)

    if number is None:
        number = allocate_copy_number(config.tier, ledger.issued)
    # else: honour a forced number (still recorded for cap accounting)

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        COPY_LEDGER_FILENAME, ".git", "__pycache__", ".venv", "*.pyc"))

    stamped = skipped = 0
    for p in sorted(dst.rglob("*")):
        if not p.is_file():
            continue
        if not is_supported(p):
            skipped += 1
            continue
        payload = WatermarkPayload(
            trademark=config.trademark, company=config.company or config.trademark,
            number=number)
        if stamp_file(p, payload):
            stamped += 1
        else:
            skipped += 1

    ledger.issued.append(number)
    ledger.save(ledger_file)
    return CopyResult(number=number, files_stamped=stamped,
                      files_skipped=skipped, dst=dst)
