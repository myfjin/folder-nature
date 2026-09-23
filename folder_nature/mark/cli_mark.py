"""CLI wiring for the v-next *mark* layer.

Kept in its own module so the core ``folder_nature.cli`` stays essentially the
shipped 0.1.0 surface plus a single ``add_mark_subcommands(sub)`` call. Every
command here restates its honest scope in its help text.

Subcommands added:
    trademark    Show / set the per-folder mark config (name is required)
    stamp        Embed a watermark (master=0 by default) into file(s)/dir
    mark-show    Extract + verify the watermark in a file
    copy         Cooperative, tiered copy with auto-numbering
    keygen       Generate an Ed25519 signing keypair (private key mode 600)
    sign         Sign a directory (sha256 manifest + Ed25519 signature)
    verify       Verify signature + integrity of a signed directory
    scan         Leak-scan content -> trace buyer -> print copyright claim
    stamp-sale   Seller: per-customer sale stamp + registry (needs accepted license)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import copy_limiter, signing
from . import leak as leak_mod
from . import orchestrator as orch
from . import sale as sale_mod
from . import watermark as wm
from .config import TIERS, MarkConfig, MarkConfigError, load_config, save_config
from .payload import WatermarkPayload

# ── shared helpers ────────────────────────────────────────────────────────────


def _err(msg: str) -> int:
    print(f"folder-nature: error: {msg}", file=sys.stderr)
    return 2


def _resolve_config(target: Path, args: argparse.Namespace) -> MarkConfig | None:
    """Load per-folder config, letting --trademark/--tier override.

    Returns None (with a printed error) if no trademark can be resolved — the
    name has no default on purpose (Phase-0 gate).
    """
    directory = target if target.is_dir() else target.parent
    cfg = load_config(directory)
    trademark = getattr(args, "trademark", None)
    tier = getattr(args, "tier", None)
    company = getattr(args, "company", None)
    if cfg is None:
        if not trademark:
            return None
        return MarkConfig(trademark=trademark, company=company, tier=tier or "team")
    if trademark:
        cfg.trademark = trademark
    if company:
        cfg.company = company
    if tier:
        cfg.tier = tier
    return cfg


def _read_pubkey(val: str | None) -> str | None:
    if not val:
        return None
    p = Path(val).expanduser()
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return val.strip()


# ── handlers ──────────────────────────────────────────────────────────────────


def cmd_trademark(args: argparse.Namespace) -> int:
    directory = Path(args.path).resolve()
    if not directory.is_dir():
        return _err(f"not a directory: {directory}")
    if args.set:
        try:
            cfg = MarkConfig(
                trademark=args.set,
                company=args.company,
                tier=args.tier or "team",
                license_tier=args.license_tier,
            )
        except MarkConfigError as e:
            return _err(str(e))
        path = save_config(directory, cfg)
        print(f"wrote {path}")
        print(f"  trademark: {cfg.trademark}  tier: {cfg.tier}")
        return 0
    current = load_config(directory)
    if current is None:
        print(
            f"no mark config at {directory} — set one with "
            f"`folder-nature trademark . --set NAME`",
            file=sys.stderr,
        )
        return 1
    print(f"trademark: {current.trademark}")
    print(f"company:   {current.company}")
    print(f"tier:      {current.tier}")
    if current.license_tier:
        print(f"license:   {current.license_tier}")
    return 0


def cmd_stamp(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists():
        return _err(f"path does not exist: {target}")
    cfg = _resolve_config(target, args)
    if cfg is None:
        return _err(
            "no trademark configured — set one with `trademark --set` "
            "or pass --trademark (there is deliberately no default name)"
        )

    files = (
        [target]
        if target.is_file()
        else [
            p for p in sorted(target.rglob("*")) if p.is_file() and wm.is_supported(p)
        ]
    )
    stamped = skipped = 0
    for f in files:
        payload = WatermarkPayload(
            trademark=cfg.trademark,
            company=cfg.company or cfg.trademark,
            number=str(args.number),
        )
        try:
            ok = wm.stamp_file(f, payload)
        except wm.StampError as e:
            print(f"SKIP (would break parse): {f}: {e}", file=sys.stderr)
            skipped += 1
            continue
        if ok:
            stamped += 1
            if args.verbose:
                print(f"stamped {f} (number {args.number})")
        else:
            skipped += 1
    print(
        f"stamped {stamped} file(s), skipped {skipped} "
        f"[trademark={cfg.trademark}, number={args.number}]"
    )
    return 0


def cmd_mark_show(args: argparse.Namespace) -> int:
    rep = wm.verify_file(Path(args.path))
    print(f"status:   {rep.status}")
    if rep.payload:
        print(f"trademark: {rep.payload.trademark}")
        print(
            f"number:    {rep.payload.number}"
            f"{'  (MASTER original)' if rep.payload.is_master else ''}"
        )
    print(
        f"channels:  present={rep.channels_present or '-'} "
        f"valid={rep.channels_valid or '-'}"
    )
    print(f"detail:    {rep.detail}")
    return 0 if rep.status == "authentic" else 1


def cmd_copy(args: argparse.Namespace) -> int:
    src = Path(args.src).resolve()
    cfg = _resolve_config(src, args)
    if cfg is None:
        return _err(
            "no trademark configured at source — set one with "
            "`trademark --set` or pass --trademark"
        )
    try:
        result = copy_limiter.copy_tree(
            src, Path(args.dst).resolve(), cfg, number=args.number
        )
    except (FileExistsError, NotADirectoryError, MarkConfigError) as e:
        return _err(str(e))
    print(f"copied -> {result.dst}")
    print(
        f"  number {result.number}, stamped {result.files_stamped}, "
        f"skipped {result.files_skipped}  (cooperative limiter, tier={cfg.tier})"
    )
    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    seed_hex, pub_hex = signing.generate_keypair()
    out = Path(args.out).expanduser()
    try:
        path = signing.write_private_key(
            seed_hex, out, allow_in_repo=args.allow_in_repo
        )
    except signing.SigningError as e:
        return _err(str(e))
    pub_path = (
        path.with_suffix(path.suffix + ".pub")
        if path.suffix
        else Path(str(path) + ".pub")
    )
    pub_path.write_text(pub_hex + "\n", encoding="utf-8")
    print(f"private key: {path}  (mode 600 — NEVER commit this)")
    print(f"public key:  {pub_path}")
    print(f"public key hex: {pub_hex}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        return _err(f"not a directory: {directory}")
    cfg = _resolve_config(directory, args)
    trademark = cfg.trademark if cfg else getattr(args, "trademark", None)
    if not trademark:
        return _err("no trademark configured — set one or pass --trademark")
    try:
        seed_hex = signing.read_private_key(Path(args.key))
    except signing.SigningError as e:
        return _err(str(e))
    man = signing.sign_directory(directory, trademark, seed_hex)
    print(f"signed {directory}")
    print(f"  {man.name} + {signing.SIGNATURE_NAME} + {signing.PUBKEY_NAME} written")
    print("  signature proves origin + integrity, NOT prevention of copying")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    directory = Path(args.dir).resolve()
    trusted = _read_pubkey(args.pubkey)

    # ROOT mode: top-down self-validation of the whole tree, one verdict.
    if getattr(args, "root", False):
        report = orch.orchestrate(
            directory, trusted, run_selftests=getattr(args, "selftest", False)
        )
        if trusted is None:
            print(
                "WARNING: no trusted --pubkey; signatures checked against the "
                "manifest's own key (integrity, not authorship).",
                file=sys.stderr,
            )
        print(report.render())
        return 0 if report.ok else 1

    try:
        rep = signing.verify_directory(directory, trusted)
    except signing.SigningError as e:
        return _err(str(e))
    if trusted is None:
        print(
            "WARNING: no trusted public key given (--pubkey). Checking the "
            "manifest's own key = internal consistency only, not authorship.",
            file=sys.stderr,
        )
    print(f"result: {rep.summary()}")
    return 0 if rep.ok else 1


def cmd_scan(args: argparse.Namespace) -> int:
    registry = sale_mod.SaleRegistry(Path(args.registry)) if args.registry else None
    if args.text is not None:
        hit = leak_mod.scan_text(args.text, registry)
        hits = [hit] if hit else []
    else:
        hits = leak_mod.scan_path(Path(args.path), registry)
    if not hits:
        print("no watermark found in scanned content")
        return 0
    for hit in hits:
        print("=" * 60)
        print(leak_mod.generate_claim(hit))
    return 0


def cmd_stamp_sale(args: argparse.Namespace) -> int:
    src = Path(args.src).resolve()
    cfg = _resolve_config(src, args)
    if cfg is None:
        return _err("no trademark configured at source — set one or pass --trademark")
    if not args.accepted:
        return _err(
            "refusing to stamp a sale without --accepted "
            "(the enforcement chain requires an accepted license)"
        )
    licenses_dir = Path(args.licenses_dir) if args.licenses_dir else None
    acceptance = sale_mod.accept_license(
        args.customer,
        cfg.tier,
        licenses_dir=licenses_dir,
        license_tier=cfg.license_tier or cfg.tier,
    )
    registry = sale_mod.SaleRegistry(Path(args.registry))
    try:
        rec = sale_mod.stamp_sale(
            src,
            Path(args.dst).resolve(),
            config=cfg,
            customer_id=args.customer,
            number=str(args.number),
            license=acceptance,
            registry=registry,
        )
    except (sale_mod.EnforcementError, FileExistsError, ValueError) as e:
        return _err(str(e))
    print(f"sold -> {args.dst}")
    print(f"  customer {rec.customer_id}, number {rec.number}, tier {rec.tier}")
    print(
        f"  license {rec.license.license_tier} accepted "
        f"({'PLACEHOLDER text' if rec.license.is_placeholder else 'bound text'})"
    )
    print(f"  recorded in {args.registry}")
    return 0


# ── registration ──────────────────────────────────────────────────────────────


def add_mark_subcommands(sub) -> None:
    """Register all mark-layer subcommands onto an argparse subparsers object."""

    p = sub.add_parser("trademark", help="Show/set the per-folder trademark + tier")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument(
        "--set", metavar="NAME", help="Set the trademark (required to write)"
    )
    p.add_argument("--company", help="Company name (defaults to trademark)")
    p.add_argument("--tier", choices=TIERS, help="personal|team|enterprise")
    p.add_argument("--license-tier", help="Reserved license-tier slot (name only)")
    p.set_defaults(func=cmd_trademark)

    p = sub.add_parser(
        "stamp",
        help="Embed a watermark (master=0 default) — attribution, not prevention",
    )
    p.add_argument("path", help="File or directory to stamp")
    p.add_argument("--number", default="0", help="Copy number (0 = master original)")
    p.add_argument("--trademark", help="Override/supply trademark (no default name)")
    p.add_argument("--company", help="Override company")
    p.add_argument("--tier", choices=TIERS)
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=cmd_stamp)

    p = sub.add_parser("mark-show", help="Extract + verify the watermark in a file")
    p.add_argument("path")
    p.set_defaults(func=cmd_mark_show)

    p = sub.add_parser(
        "copy", help="Cooperative tiered copy with auto-numbering (honest customers)"
    )
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--number", help="Force a copy number (else auto from tier)")
    p.add_argument("--trademark", help="Override/supply trademark")
    p.add_argument("--tier", choices=TIERS)
    p.set_defaults(func=cmd_copy)

    p = sub.add_parser(
        "keygen", help="Generate an Ed25519 signing keypair (private key mode 600)"
    )
    p.add_argument(
        "--out", required=True, help="Path for the private key (outside the repo)"
    )
    p.add_argument(
        "--allow-in-repo",
        action="store_true",
        help="Override the refusal to write a key inside a git repo",
    )
    p.set_defaults(func=cmd_keygen)

    p = sub.add_parser(
        "sign", help="Sign a directory (sha256 manifest + Ed25519) — origin + integrity"
    )
    p.add_argument("dir")
    p.add_argument("--key", required=True, help="Path to the private signing key")
    p.add_argument("--trademark", help="Override/supply trademark")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser(
        "verify", help="Verify a signed directory; --root self-validates a whole tree"
    )
    p.add_argument("dir")
    p.add_argument(
        "--pubkey", help="Trusted public key (hex or file). Omit = consistency-only."
    )
    p.add_argument(
        "--root",
        action="store_true",
        help="ROOT mode: top-down orchestration (structure + folder marks + "
        "every file's signature & watermark + catalog↔disk parity) → one verdict",
    )
    p.add_argument(
        "--selftest",
        action="store_true",
        help="With --root: also run declared per-file selftests (deterministic, opt-in)",
    )
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser(
        "scan", help="Leak-scan content -> trace buyer -> copyright claim"
    )
    p.add_argument("path", nargs="?", default=".", help="File/dir to scan")
    p.add_argument("--text", help="Scan this literal text instead of a path")
    p.add_argument("--registry", help="Sale registry JSON (enables buyer tracing)")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser(
        "stamp-sale",
        help="Seller: per-customer sale stamp + registry (requires accepted license)",
    )
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--customer", required=True, help="Buyer identifier")
    p.add_argument(
        "--number", required=True, help="Per-customer watermark number (not 0)"
    )
    p.add_argument("--registry", required=True, help="Sale registry JSON path")
    p.add_argument(
        "--accepted",
        action="store_true",
        help="Assert the buyer click-accepted the license (required)",
    )
    p.add_argument(
        "--licenses-dir", help="Directory of <tier>.txt license texts (optional)"
    )
    p.add_argument("--trademark", help="Override/supply trademark")
    p.add_argument("--tier", choices=TIERS)
    p.set_defaults(func=cmd_stamp_sale)
