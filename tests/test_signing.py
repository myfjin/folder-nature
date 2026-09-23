"""Signing: sign/verify round-trip, tamper-fails-verify, key handling."""

import os
import time

import pytest

from folder_nature.mark import signing


def _make_lib(root):
    (root / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.py").write_text("x = 2\n", encoding="utf-8")


def test_the_manifest_date_does_not_follow_the_local_clock(tmp_path):
    """A signed artifact must not carry a locale-dependent date.

    ``Etc/GMT+12`` is UTC-12 and ``Pacific/Kiritimati`` is UTC+14. They are 26
    hours apart, so their LOCAL DATES differ at every instant of every day. If the
    manifest's date follows the local clock, these two runs cannot agree — and they
    cannot agree by luck, either, which is what makes this deterministic rather
    than a flake that only bites near midnight.

    Two machines signing the same folder should not disagree about what day it was.
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)

    original = os.environ.get("TZ")
    try:
        dates = {}
        for label, tz in (("UTC-12", "Etc/GMT+12"), ("UTC+14", "Pacific/Kiritimati")):
            os.environ["TZ"] = tz
            time.tzset()
            dates[label] = signing.build_manifest(lib, "Test", "ab" * 32)["created"]
    finally:
        # TZ is process-global state: restore it, or the next test inherits it.
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()

    assert dates["UTC-12"] == dates["UTC+14"], (
        f"the manifest date followed the local clock: {dates['UTC-12']} under UTC-12, "
        f"{dates['UTC+14']} under UTC+14"
    )


def test_sign_verify_roundtrip(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)
    seed, pub = signing.generate_keypair()
    signing.sign_directory(lib, "Aura Elements", seed)
    rep = signing.verify_directory(lib, pub)
    assert rep.ok
    assert rep.summary() == "authentic + unaltered"


def test_modified_file_fails_verify(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)
    seed, pub = signing.generate_keypair()
    signing.sign_directory(lib, "Aura Elements", seed)
    (lib / "a.py").write_text("def a():\n    return 999\n", encoding="utf-8")
    rep = signing.verify_directory(lib, pub)
    assert not rep.ok
    assert rep.modified == ["a.py"]
    assert rep.signature_valid  # signature itself is fine; the file changed


def test_added_and_missing_detected(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)
    seed, pub = signing.generate_keypair()
    signing.sign_directory(lib, "Aura Elements", seed)
    (lib / "c.py").write_text("y = 3\n", encoding="utf-8")  # added
    (lib / "a.py").unlink()  # missing
    rep = signing.verify_directory(lib, pub)
    assert not rep.ok
    assert "c.py" in rep.added
    assert "a.py" in rep.missing


def test_wrong_trusted_key_fails(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)
    seed, _ = signing.generate_keypair()
    _, other_pub = signing.generate_keypair()
    signing.sign_directory(lib, "Aura Elements", seed)
    rep = signing.verify_directory(lib, other_pub)
    assert not rep.ok
    assert not rep.key_matches


def test_forged_signature_fails(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    _make_lib(lib)
    seed, pub = signing.generate_keypair()
    signing.sign_directory(lib, "Aura Elements", seed)
    sig_path = lib / signing.SIGNATURE_NAME
    sig = bytearray.fromhex(sig_path.read_text().strip())
    sig[0] ^= 1
    sig_path.write_text(sig.hex() + "\n", encoding="utf-8")
    rep = signing.verify_directory(lib, pub)
    assert not rep.ok
    assert not rep.signature_valid


def test_private_key_written_mode_600(tmp_path):
    seed, _ = signing.generate_keypair()
    key = tmp_path / "signing.key"
    signing.write_private_key(seed, key)
    import stat

    mode = stat.S_IMODE(key.stat().st_mode)
    assert mode == 0o600


def test_refuses_key_inside_git_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    seed, _ = signing.generate_keypair()
    with pytest.raises(signing.SigningError):
        signing.write_private_key(seed, tmp_path / "signing.key")
