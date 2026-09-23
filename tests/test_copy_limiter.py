"""Copy-limiter tiers + the config numbering rules."""

import pytest

from folder_nature.mark import copy_limiter
from folder_nature.mark.config import (
    MarkConfig,
    MarkConfigError,
    allocate_copy_number,
    base36,
    copy_capacity,
)


def test_tier_capacities():
    assert copy_capacity("personal") == 3
    assert copy_capacity("team") == 10
    assert copy_capacity("enterprise") is None


def test_personal_allocates_1_to_3_then_exhausts():
    issued = []
    for expected in ["1", "2", "3"]:
        n = allocate_copy_number("personal", issued)
        assert n == expected
        issued.append(n)
    with pytest.raises(MarkConfigError):
        allocate_copy_number("personal", issued)


def test_team_allocates_0_to_9():
    issued = []
    for _ in range(10):
        issued.append(allocate_copy_number("team", issued))
    assert issued == [str(i) for i in range(10)]
    with pytest.raises(MarkConfigError):
        allocate_copy_number("team", issued)


def test_enterprise_is_base36_from_10_unbounded():
    assert allocate_copy_number("enterprise", []) == "a"  # 10
    assert allocate_copy_number("enterprise", ["a"]) == "b"  # 11
    assert base36(10) == "a" and base36(35) == "z" and base36(36) == "10"


def test_copy_tree_auto_numbers_and_stamps(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text("print(1)\n", encoding="utf-8")
    cfg = MarkConfig(trademark="Aura Elements", tier="personal")

    r1 = copy_limiter.copy_tree(src, tmp_path / "c1", cfg)
    r2 = copy_limiter.copy_tree(src, tmp_path / "c2", cfg)
    assert (r1.number, r2.number) == ("1", "2")
    assert r1.files_stamped == 1

    # the copies carry the number in their watermark
    from folder_nature.mark.watermark import verify_file

    assert verify_file(tmp_path / "c1" / "m.py").payload.number == "1"
    assert verify_file(tmp_path / "c2" / "m.py").payload.number == "2"


def test_copy_tree_honours_cooperative_cap(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text("print(1)\n", encoding="utf-8")
    cfg = MarkConfig(trademark="Aura Elements", tier="personal")
    for i in range(3):
        copy_limiter.copy_tree(src, tmp_path / f"c{i}", cfg)
    with pytest.raises(MarkConfigError):
        copy_limiter.copy_tree(src, tmp_path / "c_over", cfg)
