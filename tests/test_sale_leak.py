"""Sale-time stamping, the enforcement chain, and leak trace -> claim."""

import pytest

from folder_nature.mark import leak as leak_mod
from folder_nature.mark import sale as sale_mod
from folder_nature.mark.config import MarkConfig, MarkConfigError


def _src(tmp_path):
    src = tmp_path / "lib"
    src.mkdir()
    (src / "p.py").write_text("def p():\n    return 42\nprint(p())\n", encoding="utf-8")
    return src


def test_no_default_trademark():
    with pytest.raises(MarkConfigError):
        MarkConfig(trademark="")


def test_sale_requires_matching_accepted_license(tmp_path):
    src = _src(tmp_path)
    cfg = MarkConfig(trademark="Aura Elements", tier="team")
    reg = sale_mod.SaleRegistry(tmp_path / "sales.json")
    wrong = sale_mod.accept_license("someone-else", "team")
    with pytest.raises(sale_mod.EnforcementError):
        sale_mod.stamp_sale(
            src,
            tmp_path / "out",
            config=cfg,
            customer_id="acme",
            number="5",
            license=wrong,
            registry=reg,
        )


def test_master_number_is_not_a_sale(tmp_path):
    src = _src(tmp_path)
    cfg = MarkConfig(trademark="Aura Elements", tier="team")
    reg = sale_mod.SaleRegistry(tmp_path / "sales.json")
    acc = sale_mod.accept_license("acme", "team")
    with pytest.raises(sale_mod.EnforcementError):
        sale_mod.stamp_sale(
            src,
            tmp_path / "out",
            config=cfg,
            customer_id="acme",
            number="0",
            license=acc,
            registry=reg,
        )


def test_full_sale_then_leak_traces_and_claims(tmp_path):
    src = _src(tmp_path)
    cfg = MarkConfig(trademark="Aura Elements", tier="team")
    reg = sale_mod.SaleRegistry(tmp_path / "sales.json")
    acc = sale_mod.accept_license("acme-corp", "team", license_tier="team")
    sale_mod.stamp_sale(
        src,
        tmp_path / "sold",
        config=cfg,
        customer_id="acme-corp",
        number="5",
        license=acc,
        registry=reg,
    )

    # a fresh registry loaded from disk still traces (persistence)
    reg2 = sale_mod.SaleRegistry(tmp_path / "sales.json")
    hits = leak_mod.scan_path(tmp_path / "sold", reg2)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.number == "5" and hit.traced
    assert hit.buyer["customer_id"] == "acme-corp"

    claim = leak_mod.generate_claim(hit)
    assert "COPYRIGHT DEPARTURE CLAIM" in claim
    assert "acme-corp" in claim
    assert "not a prevention claim" in claim  # honesty boundary present


def test_master_leak_is_not_a_customer_claim(tmp_path):
    from folder_nature.mark.payload import WatermarkPayload
    from folder_nature.mark.watermark import stamp_file

    src = _src(tmp_path)
    stamp_file(src / "p.py", WatermarkPayload("Aura Elements", "Aura Elements", "0"))
    hits = leak_mod.scan_path(src, None)
    claim = leak_mod.generate_claim(hits[0])
    assert "NO CLAIM" in claim and "MASTER" in claim


def test_untraceable_number_makes_no_claim(tmp_path):
    from folder_nature.mark.payload import WatermarkPayload
    from folder_nature.mark.watermark import stamp_file

    src = _src(tmp_path)
    stamp_file(src / "p.py", WatermarkPayload("Aura Elements", "Aura Elements", "8"))
    reg = sale_mod.SaleRegistry(tmp_path / "empty.json")
    hits = leak_mod.scan_path(src, reg)
    claim = leak_mod.generate_claim(hits[0])
    assert "NO CLAIM" in claim and "not in the sale registry" in claim


def test_duplicate_number_rejected(tmp_path):
    src = _src(tmp_path)
    cfg = MarkConfig(trademark="Aura Elements", tier="team")
    reg = sale_mod.SaleRegistry(tmp_path / "sales.json")
    acc = sale_mod.accept_license("a", "team")
    sale_mod.stamp_sale(
        src,
        tmp_path / "o1",
        config=cfg,
        customer_id="a",
        number="5",
        license=acc,
        registry=reg,
    )
    acc2 = sale_mod.accept_license("b", "team")
    with pytest.raises(ValueError):
        sale_mod.stamp_sale(
            src,
            tmp_path / "o2",
            config=cfg,
            customer_id="b",
            number="5",
            license=acc2,
            registry=reg,
        )
