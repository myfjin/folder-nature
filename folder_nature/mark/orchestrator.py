"""Root orchestration — a folder-nature tree that self-validates, top-down.

`folder-nature verify <root> --root` turns the tree into an ORCHESTRATOR that
signs off with ONE green/red verdict only if EVERYTHING checks:

  STRUCTURE   every folder's `.folder-nature` is schema-valid (tags/being valid),
              the tree matches its declared layout, and counts are reported.
  FOLDER MARKS every folder that should carry a mark has a valid `.folder-mark.yaml`.
  FILES       every FILE's Ed25519 signature verifies (via the signed manifest) AND
              every watermark-supported file's watermark verifies — files, not just folders.
  PARITY      the signed manifest matches disk EXACTLY — no added/missing/modified
              (the wave-16 law: catalog ↔ disk).
  SELFTESTS   optional, deterministic, opt-in: the root runs a declared per-file
              run-gate (e.g. `python3 <f>`) and expects exit 0.

This GENERALIZES the library's `library_verify.py` into a reusable capability: any
folder-nature root can self-validate. It discovers signed subtrees by finding
`MANIFEST.aura` — nothing is hard-coded.

Honest scope: this validates AUTHENTICITY + INTEGRITY + STRUCTURE. It does NOT
prevent copying (nothing can). A green verdict means "genuinely this tree,
unaltered, correctly shaped" — not "uncopyable".

Optional root declaration `.folder-nature-root.yaml` (all fields optional):
    orchestrator: true
    expect_dirs: [python, r]          # these paths must exist
    require_nature: false             # every folder must carry a .folder-nature
    require_mark: false               # every signed subtree must carry a .folder-mark.yaml
    require_watermark: true           # every watermark-supported file must be authentic
    selftest: {".py": "python3", ".R": "Rscript"}   # opt-in via --selftest
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..core import NATURE_FILENAME, read_folder_nature
from ..schema import SchemaError
from . import signing
from . import watermark as wm
from .config import MARK_CONFIG_FILENAME, MarkConfigError, load_config

ROOT_SPEC_FILENAME = ".folder-nature-root.yaml"

# directories never walked; artifacts never counted as content
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "node_modules",
    ".mypy_cache",
}
_SKIP_FILES = {
    signing.MANIFEST_NAME,
    signing.SIGNATURE_NAME,
    signing.PUBKEY_NAME,
    NATURE_FILENAME,
    MARK_CONFIG_FILENAME,
    ROOT_SPEC_FILENAME,
    ".DS_Store",
}


@dataclass
class RootSpec:
    expect_dirs: list[str] = field(default_factory=list)
    require_nature: bool = False
    require_mark: bool = False
    require_watermark: bool = True
    selftest: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> RootSpec:
        p = Path(root) / ROOT_SPEC_FILENAME
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(
            expect_dirs=list(data.get("expect_dirs", [])),
            require_nature=bool(data.get("require_nature", False)),
            require_mark=bool(data.get("require_mark", False)),
            require_watermark=bool(data.get("require_watermark", True)),
            selftest=dict(data.get("selftest", {})),
        )


@dataclass
class RootReport:
    ok: bool = True
    folders: int = 0
    files: int = 0
    natures_valid: int = 0
    marks_valid: int = 0
    signed_subtrees: list[str] = field(default_factory=list)
    files_signed: int = 0
    files_watermarked: int = 0
    selftests_run: int = 0
    selftests_passed: int = 0
    failures: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.failures.append(msg)

    def render(self) -> str:
        lines = [
            f"folders: {self.folders}   files: {self.files}",
            f"folder-nature valid: {self.natures_valid}   folder-marks valid: {self.marks_valid}",
            (
                f"signed subtrees: {len(self.signed_subtrees)} "
                f"({', '.join(self.signed_subtrees) or 'none'})"
            ),
            f"files signed: {self.files_signed}   watermarks verified: {self.files_watermarked}",
        ]
        if self.selftests_run:
            lines.append(
                f"selftests: {self.selftests_passed}/{self.selftests_run} passed"
            )
        lines.append("-" * 60)
        if self.ok:
            lines.append(
                "GREEN — the tree is valid, structured, marked and signed. "
                "(authenticity + integrity + structure; NOT copy-prevention)"
            )
        else:
            lines.append(f"RED — {len(self.failures)} problem(s):")
            lines += [f"  - {f}" for f in self.failures[:40]]
        return "\n".join(lines)


def _walk(root: Path):
    """Yield (dirs, files) below root, skipping VCS/caches/hidden dirs."""
    for p in root.rglob("*"):
        parts = p.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in parts):
            continue
        if any(part.startswith(".") and part not in (".",) for part in parts[:-1]):
            # inside a hidden dir
            continue
        yield p


def orchestrate(
    root: Path, pubkey: str | None = None, run_selftests: bool = False
) -> RootReport:
    """Validate a folder-nature root top-down. Returns a single-verdict report."""
    root = Path(root).resolve()
    spec = RootSpec.load(root)
    rep = RootReport()

    # ── STRUCTURE + COUNTS + TAG VALIDITY ────────────────────────────────────
    all_dirs = [root] + [p for p in _walk(root) if p.is_dir()]
    rep.folders = len(all_dirs)
    for f in _walk(root):
        if f.is_file() and f.name not in _SKIP_FILES and not f.name.endswith(".pyc"):
            rep.files += 1

    for d in all_dirs:
        nf = d / NATURE_FILENAME
        if nf.exists():
            try:
                read_folder_nature(nf)  # schema-validates being + tags
                rep.natures_valid += 1
            except (SchemaError, yaml.YAMLError, OSError) as e:
                rep.fail(f"{d.relative_to(root)}/{NATURE_FILENAME}: invalid — {e}")
        elif spec.require_nature:
            rep.fail(
                f"{d.relative_to(root) or '.'}: missing {NATURE_FILENAME} "
                "(require_nature)"
            )

    for want in spec.expect_dirs:
        if not (root / want).is_dir():
            rep.fail(f"declared expect_dir missing: {want}")

    # ── FOLDER MARKS ─────────────────────────────────────────────────────────
    for d in all_dirs:
        if (d / MARK_CONFIG_FILENAME).exists():
            try:
                if load_config(d) is not None:
                    rep.marks_valid += 1
            except MarkConfigError as e:
                rep.fail(f"{d.relative_to(root)}/{MARK_CONFIG_FILENAME}: invalid — {e}")

    # ── FILE SIGNATURES + WATERMARKS + PARITY ────────────────────────────────
    signed_dirs = sorted({m.parent for m in root.rglob(signing.MANIFEST_NAME)})
    for sdir in signed_dirs:
        rel = sdir.relative_to(root).as_posix() or "."
        rep.signed_subtrees.append(rel)
        if spec.require_mark and not (sdir / MARK_CONFIG_FILENAME).exists():
            rep.fail(
                f"{rel}: signed subtree missing {MARK_CONFIG_FILENAME} (require_mark)"
            )
        try:
            vr = signing.verify_directory(sdir, pubkey)
        except signing.SigningError as e:
            rep.fail(f"{rel}: {e}")
            continue
        if not vr.ok:
            rep.fail(f"{rel}: signature/parity — {vr.summary()}")
        # per-FILE watermark (files, not just folders)
        for p in sdir.rglob("*"):
            if not p.is_file() or not wm.is_supported(p):
                continue
            rep.files_signed += 1
            mr = wm.verify_file(p)
            if mr.status == "authentic":
                rep.files_watermarked += 1
            elif mr.status == "tampered":
                rep.fail(f"{p.relative_to(root)}: watermark TAMPERED — {mr.detail}")
            elif spec.require_watermark:
                rep.fail(
                    f"{p.relative_to(root)}: watermark missing (require_watermark)"
                )

    # ── SELFTESTS (opt-in, deterministic) ────────────────────────────────────
    if run_selftests and spec.selftest:
        for f in _walk(root):
            if not f.is_file():
                continue
            runner = spec.selftest.get(f.suffix)
            if not runner:
                continue
            rep.selftests_run += 1
            try:
                rc = subprocess.run(
                    [runner, str(f)], capture_output=True, timeout=120, check=False
                ).returncode
            except (OSError, subprocess.TimeoutExpired) as e:
                rc = -1
                rep.fail(f"{f.relative_to(root)}: selftest error — {e}")
                continue
            if rc == 0:
                rep.selftests_passed += 1
            else:
                rep.fail(f"{f.relative_to(root)}: selftest FAILED (exit {rc})")

    return rep
