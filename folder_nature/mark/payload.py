"""The watermark payload — what gets embedded, and how it is made checkable.

A payload carries: a fixed pyramid/signature magic, the trademark, the company,
and the copy number (master = ``0``; per-customer number stamped at sale). It is
serialised canonically and CRC-tagged so a tampered or truncated mark is
*detectable* — not preventable, detectable. Extraction re-derives the CRC and
flags a mismatch.

Encoding is deliberately plain (base32, no compression, no crypto here): the
watermark's job is attribution + detectability. Authenticity/integrity of the
*files* is a separate, cryptographic concern handled by
:mod:`folder_nature.mark.signing`.
"""

from __future__ import annotations

import base64
import binascii
import json
import zlib
from dataclasses import dataclass
from typing import Optional


# Fixed signature magic — the "invisible pyramid" marker used to locate a mark.
# The delta is the pyramid; "AE" is the layer tag; "1" is the payload version.
PYRAMID = "△"          # △
MAGIC = "AEMARK1"
PAYLOAD_VERSION = 1


class PayloadError(ValueError):
    """Raised when a payload cannot be parsed or fails its CRC."""


@dataclass
class WatermarkPayload:
    """A decoded watermark.

    ``number`` is a string token so it can be a decimal char (``"0".."9"``) or a
    base36 enterprise token. ``number == "0"`` means the master original.
    """

    trademark: str
    company: str
    number: str = "0"
    pattern_id: Optional[str] = None
    version: int = PAYLOAD_VERSION

    @property
    def is_master(self) -> bool:
        return str(self.number) == "0"

    # ── canonical bytes ──────────────────────────────────────────────────────

    def _canonical(self) -> bytes:
        """Deterministic serialisation (sorted keys, no whitespace)."""
        obj = {
            "m": MAGIC,
            "tm": self.trademark,
            "co": self.company,
            "n": str(self.number),
            "pid": self.pattern_id or "",
            "v": int(self.version),
        }
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")

    def encode(self) -> str:
        """Encode to a compact, CRC-tagged base32 string (channel-agnostic).

        Layout before base32:  canonical-utf8  ||  4-byte big-endian CRC32.
        base32 (no padding, uppercase) keeps it comment- and identifier-safe.
        """
        body = self._canonical()
        crc = zlib.crc32(body) & 0xFFFFFFFF
        blob = body + crc.to_bytes(4, "big")
        return base64.b32encode(blob).decode("ascii").rstrip("=")

    # ── decoding ─────────────────────────────────────────────────────────────

    @classmethod
    def decode(cls, token: str) -> "WatermarkPayload":
        """Decode a base32 token, verifying the CRC. Raises PayloadError."""
        token = token.strip()
        # restore base32 padding to a multiple of 8
        pad = (-len(token)) % 8
        try:
            blob = base64.b32decode(token + "=" * pad)
        except (binascii.Error, ValueError) as e:
            raise PayloadError(f"not valid base32: {e}")
        if len(blob) < 5:
            raise PayloadError("payload too short")
        body, crc_bytes = blob[:-4], blob[-4:]
        want = int.from_bytes(crc_bytes, "big")
        got = zlib.crc32(body) & 0xFFFFFFFF
        if want != got:
            raise PayloadError(
                f"CRC mismatch (tampered or truncated): want {want:08x}, got {got:08x}"
            )
        try:
            obj = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise PayloadError(f"payload body not valid JSON: {e}")
        if obj.get("m") != MAGIC:
            raise PayloadError(f"bad magic {obj.get('m')!r}; expected {MAGIC!r}")
        return cls(
            trademark=obj.get("tm", ""),
            company=obj.get("co", ""),
            number=str(obj.get("n", "0")),
            pattern_id=(obj.get("pid") or None),
            version=int(obj.get("v", PAYLOAD_VERSION)),
        )
