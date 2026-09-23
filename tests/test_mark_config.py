"""Mark config: no default name, tier validation, load/save round-trip."""

import pytest

from folder_nature.mark.config import (
    MARK_CONFIG_FILENAME,
    MarkConfig,
    MarkConfigError,
    load_config,
    save_config,
)


def test_trademark_is_required_no_default():
    with pytest.raises(MarkConfigError):
        MarkConfig(trademark="")
    with pytest.raises(MarkConfigError):
        MarkConfig(trademark="   ")


def test_company_defaults_to_trademark():
    cfg = MarkConfig(trademark="Aura Elements")
    assert cfg.company == "Aura Elements"


def test_invalid_tier_rejected():
    with pytest.raises(MarkConfigError):
        MarkConfig(trademark="X", tier="platinum")


def test_save_load_roundtrip(tmp_path):
    cfg = MarkConfig(
        trademark="Aura Elements",
        company="Aura Elements Ltd",
        tier="enterprise",
        license_tier="enterprise",
    )
    save_config(tmp_path, cfg)
    assert (tmp_path / MARK_CONFIG_FILENAME).exists()
    back = load_config(tmp_path)
    assert back.trademark == "Aura Elements"
    assert back.company == "Aura Elements Ltd"
    assert back.tier == "enterprise"
    assert back.license_tier == "enterprise"


def test_load_missing_returns_none(tmp_path):
    assert load_config(tmp_path) is None
