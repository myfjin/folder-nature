"""Root orchestrator: a green tree passes; each defect fails loudly and names itself."""

import sys

from folder_nature.core import write_folder_nature
from folder_nature.mark import orchestrator as orch
from folder_nature.mark import signing
from folder_nature.mark.config import MarkConfig, save_config
from folder_nature.mark.payload import WatermarkPayload
from folder_nature.mark.watermark import stamp_file
from folder_nature.schema import FolderNature, Identity

TM, CO = "Test Library", "Reality Optimizer"


def _green_tree(root, *, root_spec=None, selftest_bad=False):
    """Build a valid signed folder-nature tree; return the trusted pubkey."""
    root.mkdir(parents=True, exist_ok=True)
    if root_spec is not None:
        (root / orch.ROOT_SPEC_FILENAME).write_text(root_spec, encoding="utf-8")

    lib = root / "lib"
    lib.mkdir()
    write_folder_nature(
        lib,
        FolderNature(
            identity=Identity(name="lib", being="workspace", purpose="patterns")
        ),
    )
    save_config(lib, MarkConfig(trademark=TM, company=CO, tier="team"))
    (lib / "a.py").write_text(
        "def a():\n    return 1\nassert a() == 1\n", encoding="utf-8"
    )
    (lib / "b.py").write_text("x = 2\nassert x == 2\n", encoding="utf-8")
    if selftest_bad:
        (lib / "c.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    for f in ("a.py", "b.py") + (("c.py",) if selftest_bad else ()):
        stamp_file(lib / f, WatermarkPayload(trademark=TM, company=CO, number="0"))

    seed, pub = signing.generate_keypair()
    signing.sign_directory(lib, TM, seed)
    return pub


def test_green_tree_passes(tmp_path):
    pub = _green_tree(tmp_path / "t")
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert rep.ok, rep.render()
    assert rep.signed_subtrees == ["lib"]
    assert rep.files_signed == 2 and rep.files_watermarked == 2
    assert rep.folders >= 2 and rep.files >= 2  # counts reported


def test_tampered_file_fails_and_names_itself(tmp_path):
    pub = _green_tree(tmp_path / "t")
    (tmp_path / "t" / "lib" / "a.py").write_text(
        "def a():\n    return 999\n", encoding="utf-8"
    )
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any("a.py" in f for f in rep.failures)


def test_missing_signature_fails(tmp_path):
    pub = _green_tree(tmp_path / "t")
    (tmp_path / "t" / "lib" / signing.SIGNATURE_NAME).unlink()
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any("lib" in f for f in rep.failures)


def test_catalog_drift_added_file_fails(tmp_path):
    """A file added after signing = manifest↔disk parity break (the wave-16 law)."""
    pub = _green_tree(tmp_path / "t")
    (tmp_path / "t" / "lib" / "sneaky.py").write_text("z = 3\n", encoding="utf-8")
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any("added" in f.lower() or "parity" in f.lower() for f in rep.failures)


def test_tampered_watermark_fails_even_when_resigned(tmp_path):
    """Corrupt the watermark, then re-sign so the signature passes — the orchestrator
    must still catch the watermark tamper (files, not just folders)."""
    _green_tree(tmp_path / "t")
    a = tmp_path / "t" / "lib" / "a.py"
    a.write_text(
        a.read_text(encoding="utf-8").replace("AE1.", "AE1.Z", 1), encoding="utf-8"
    )
    seed, pub = signing.generate_keypair()
    signing.sign_directory(
        tmp_path / "t" / "lib", TM, seed
    )  # signature now valid again
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any("TAMPERED" in f or "watermark" in f for f in rep.failures)


def test_invalid_folder_nature_tag_fails(tmp_path):
    pub = _green_tree(tmp_path / "t")
    # write a schema-invalid .folder-nature (tags must be a list of strings)
    bad = tmp_path / "t" / "lib" / ".folder-nature"
    bad.write_text(
        'schema_version: "1.0"\nidentity:\n  name: x\n  being: workspace\n'
        '  purpose: y\ntags: "not-a-list"\n',
        encoding="utf-8",
    )
    # re-sign so only the tag-validity check trips, not parity
    seed, pub = signing.generate_keypair()
    signing.sign_directory(tmp_path / "t" / "lib", TM, seed)
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any(".folder-nature" in f for f in rep.failures)


def test_require_nature_flags_missing(tmp_path):
    pub = _green_tree(
        tmp_path / "t", root_spec="orchestrator: true\nrequire_nature: true\n"
    )
    # the root itself has no .folder-nature -> require_nature trips
    rep = orch.orchestrate(tmp_path / "t", pub)
    assert not rep.ok
    assert any("missing .folder-nature" in f for f in rep.failures)


def test_selftest_failure_named(tmp_path):
    pub = _green_tree(
        tmp_path / "t",
        selftest_bad=True,
        root_spec=f'orchestrator: true\nselftest:\n  ".py": "{sys.executable}"\n',
    )
    # re-sign to include c.py cleanly
    seed, pub = signing.generate_keypair()
    signing.sign_directory(tmp_path / "t" / "lib", TM, seed)
    rep = orch.orchestrate(tmp_path / "t", pub, run_selftests=True)
    assert not rep.ok
    assert rep.selftests_run >= 1
    assert any("c.py" in f and "selftest" in f.lower() for f in rep.failures)


def test_selftests_pass_on_green(tmp_path):
    pub = _green_tree(
        tmp_path / "t",
        root_spec=f'orchestrator: true\nselftest:\n  ".py": "{sys.executable}"\n',
    )
    rep = orch.orchestrate(tmp_path / "t", pub, run_selftests=True)
    assert rep.ok
    assert rep.selftests_run == 2 and rep.selftests_passed == 2
