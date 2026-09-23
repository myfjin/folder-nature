"""File signing — authenticity + integrity, distinct from the watermark.

The watermark answers WHO bought a copy. The signature answers a different
question: are these files GENUINELY from us, and UNALTERED since we signed them?

Mechanism (industry-standard, kept simple):

  1. ``keygen``  -> a 32-byte Ed25519 private seed written at mode 600 OUTSIDE
     the repo, plus its public key. The private key is NEVER committed.
  2. ``sign``    -> hash every file (sha256), write a JSON ``MANIFEST.aura``
     binding {trademark, created, public_key, file hashes}, and a detached
     Ed25519 signature ``MANIFEST.aura.sig`` over the canonical manifest bytes.
  3. ``verify``  -> check the signature with a TRUSTED published public key, then
     re-hash the tree and report "authentic + unaltered", or name exactly what
     differs (modified / missing / added files, or a bad signature).

Honest scope: this proves origin + integrity. It does NOT prevent copying. A
valid signature on a leaked copy still says only "genuinely ours, unaltered" —
which is precisely what makes the *watermark's* buyer-attribution trustworthy.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import _ed25519 as ed

MANIFEST_NAME = "MANIFEST.aura"
SIGNATURE_NAME = "MANIFEST.aura.sig"
PUBKEY_NAME = "aura-signing.pub"
MANIFEST_VERSION = 1

# Never hash our own signing artifacts, VCS internals, or caches.
_DEFAULT_EXCLUDES = {
    MANIFEST_NAME,
    SIGNATURE_NAME,
    PUBKEY_NAME,
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
    ".venv",
}


class SigningError(RuntimeError):
    """Raised on key I/O, missing manifest, or malformed signing artifacts."""


# ── keys ──────────────────────────────────────────────────────────────────────


def generate_keypair() -> tuple[str, str]:
    """Return ``(private_seed_hex, public_key_hex)``. Seed is 32 random bytes."""
    seed = ed.generate_seed()
    return seed.hex(), ed.publickey(seed).hex()


def write_private_key(
    seed_hex: str, path: Path, *, allow_in_repo: bool = False
) -> Path:
    """Write the private seed to ``path`` at mode 600. Refuses a repo by default.

    A private signing key inside a version-controlled tree is the classic leak.
    We refuse unless explicitly overridden.
    """
    path = Path(path).expanduser()
    if not allow_in_repo:
        for parent in [path.resolve().parent, *path.resolve().parents]:
            if (parent / ".git").exists():
                raise SigningError(
                    f"refusing to write a private key inside a git repo ({parent}). "
                    "Put it under ~/.config or pass allow_in_repo=True deliberately."
                )
    bytes.fromhex(seed_hex)  # validate hex
    path.parent.mkdir(parents=True, exist_ok=True)
    # create with 600 from the start (avoid a readable window)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(seed_hex + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600, belt-and-suspenders
    return path


def read_private_key(path: Path) -> str:
    path = Path(path).expanduser()
    if not path.exists():
        raise SigningError(f"no private key at {path}")
    return path.read_text(encoding="utf-8").strip()


# ── manifest ──────────────────────────────────────────────────────────────────


def _iter_files(root: Path, excludes: set) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in excludes for part in rel_parts):
            continue
        out.append(p)
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    root: Path, trademark: str, public_key_hex: str, *, excludes: set | None = None
) -> dict:
    """Build the manifest dict for ``root`` (does not sign)."""
    root = Path(root)
    ex = set(_DEFAULT_EXCLUDES) | (excludes or set())
    files = []
    for p in _iter_files(root, ex):
        files.append(
            {
                "path": p.relative_to(root).as_posix(),
                "sha256": _sha256(p),
                "bytes": p.stat().st_size,
            }
        )
    return {
        "manifest_version": MANIFEST_VERSION,
        "trademark": trademark,
        "created": datetime.now(timezone.utc).date().isoformat(),
        "algorithm": "ed25519",
        "public_key": public_key_hex,
        "files": files,
    }


def canonical_bytes(manifest: dict) -> bytes:
    """Deterministic bytes signed/verified (sorted keys, compact)."""
    return json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign_directory(
    root: Path, trademark: str, private_seed_hex: str, *, excludes: set | None = None
) -> Path:
    """Build + sign a manifest for ``root``. Writes manifest, sig, pubkey.

    Returns the manifest path. The public key is also written next to it so
    verifiers have a copy to compare against a trusted published key.
    """
    root = Path(root)
    seed = bytes.fromhex(private_seed_hex)
    pub_hex = ed.publickey(seed).hex()
    manifest = build_manifest(root, trademark, pub_hex, excludes=excludes)
    body = canonical_bytes(manifest)
    sig = ed.sign(body, seed)

    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / SIGNATURE_NAME).write_text(sig.hex() + "\n", encoding="utf-8")
    (root / PUBKEY_NAME).write_text(pub_hex + "\n", encoding="utf-8")
    return root / MANIFEST_NAME


# ── verification ──────────────────────────────────────────────────────────────


@dataclass
class VerifyReport:
    """Outcome of verifying a signed directory."""

    ok: bool
    signature_valid: bool
    key_matches: bool
    modified: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    detail: str = ""

    def summary(self) -> str:
        if self.ok:
            return "authentic + unaltered"
        parts = []
        if not self.signature_valid:
            parts.append("SIGNATURE INVALID (not genuinely from this key)")
        if not self.key_matches:
            parts.append("public key does not match the trusted key")
        if self.modified:
            parts.append(f"modified: {', '.join(self.modified)}")
        if self.missing:
            parts.append(f"missing: {', '.join(self.missing)}")
        if self.added:
            parts.append(f"added (unsigned): {', '.join(self.added)}")
        return "; ".join(parts) or (self.detail or "verification failed")


def verify_directory(
    root: Path,
    trusted_public_key_hex: str | None = None,
    *,
    excludes: set | None = None,
) -> VerifyReport:
    """Verify signature + integrity of a signed ``root``.

    If ``trusted_public_key_hex`` is given, the signature is checked against it
    (and the manifest's embedded key must match). If omitted, the manifest's
    embedded key is used — which proves *internal consistency* only, not that
    the key is the real publisher's. The CLI warns about this distinction.
    """
    root = Path(root)
    man_path = root / MANIFEST_NAME
    sig_path = root / SIGNATURE_NAME
    if not man_path.exists() or not sig_path.exists():
        raise SigningError(f"no signed manifest in {root} (run `sign` first)")

    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    body = canonical_bytes(manifest)
    sig_hex = sig_path.read_text(encoding="utf-8").strip()
    embedded_key = manifest.get("public_key", "")

    verify_key = trusted_public_key_hex or embedded_key
    key_matches = (
        trusted_public_key_hex is None or trusted_public_key_hex == embedded_key
    )
    try:
        sig_valid = ed.verify(bytes.fromhex(sig_hex), body, bytes.fromhex(verify_key))
    except ValueError:
        sig_valid = False

    # re-hash the tree
    ex = set(_DEFAULT_EXCLUDES) | (excludes or set())
    on_disk = {
        p.relative_to(root).as_posix(): _sha256(p) for p in _iter_files(root, ex)
    }
    recorded = {f["path"]: f["sha256"] for f in manifest.get("files", [])}

    modified, missing = [], []
    for path, want in recorded.items():
        got = on_disk.get(path)
        if got is None:
            missing.append(path)
        elif got != want:
            modified.append(path)
    added = sorted(set(on_disk) - set(recorded))

    ok = sig_valid and key_matches and not modified and not missing and not added
    return VerifyReport(
        ok=ok,
        signature_valid=sig_valid,
        key_matches=key_matches,
        modified=sorted(modified),
        missing=sorted(missing),
        added=added,
    )
