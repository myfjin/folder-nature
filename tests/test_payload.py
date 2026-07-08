"""Payload encode/decode + CRC tamper detection."""

import pytest

from folder_nature.mark.payload import PayloadError, WatermarkPayload


def test_roundtrip_preserves_fields():
    p = WatermarkPayload(trademark="Aura Elements", company="Aura Elements",
                         number="7", pattern_id="ds.kalman")
    back = WatermarkPayload.decode(p.encode())
    assert back.trademark == "Aura Elements"
    assert back.company == "Aura Elements"
    assert back.number == "7"
    assert back.pattern_id == "ds.kalman"


def test_master_flag():
    assert WatermarkPayload("X", "X", "0").is_master
    assert not WatermarkPayload("X", "X", "3").is_master


def test_crc_catches_single_char_corruption():
    token = WatermarkPayload("X", "X", "1").encode()
    # flip a character in the middle of the base32 token
    i = len(token) // 2
    corrupt = token[:i] + ("A" if token[i] != "A" else "B") + token[i + 1:]
    with pytest.raises(PayloadError):
        WatermarkPayload.decode(corrupt)


def test_truncation_detected():
    token = WatermarkPayload("X", "X", "1").encode()
    with pytest.raises(PayloadError):
        WatermarkPayload.decode(token[:-4])


def test_garbage_rejected():
    with pytest.raises(PayloadError):
        WatermarkPayload.decode("!!!! not base32 !!!!")
