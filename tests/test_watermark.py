"""Watermark engine: gate-compatibility, extractability, reformat survival,
tamper detection — the properties the mark layer lives or dies on."""

import shutil
import subprocess
import sys

import pytest

from folder_nature.mark import watermark as wm
from folder_nature.mark.payload import WatermarkPayload


PY_HARD = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module docstring must stay first."""
from __future__ import annotations

import math


def area(r):
    return math.pi * r * r


if __name__ == "__main__":
    print(round(area(2), 4))
'''

PY_SIMPLE = "x = 41\nprint(x + 1)\n"


def _mark(number="0"):
    return WatermarkPayload(trademark="Aura Elements", company="Aura Elements",
                            number=number)


def test_stamp_keeps_python_parseable():
    stamped = wm.stamp_text(PY_HARD, _mark(), wm._LANGS[".py"], "hard.py")
    # in-process compile is the gate check
    compile(stamped, "hard.py", "exec")
    # the mark landed AFTER the future import (else SyntaxError)
    assert "from __future__ import annotations" in stamped


def test_stamped_file_still_runs(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(PY_HARD, encoding="utf-8")
    wm.stamp_file(f, _mark())
    r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout.strip() == "12.5664"


def test_all_three_channels_extract():
    stamped = wm.stamp_text(PY_SIMPLE, _mark("0"), wm._LANGS[".py"])
    rep = wm.verify_text(stamped)
    assert rep.status == "authentic"
    assert set(rep.channels_valid) == {"A", "B", "C"}
    assert rep.payload.trademark == "Aura Elements"
    assert rep.payload.is_master


def test_survives_whitespace_reformat():
    stamped = wm.stamp_text(PY_HARD, _mark(), wm._LANGS[".py"], "hard.py")
    reflow = "\n".join(ln.rstrip() for ln in stamped.splitlines() if ln.strip()) + "\n"
    assert wm.verify_text(reflow).status == "authentic"


def test_survives_comment_stripping_via_structural_channel():
    stamped = wm.stamp_text(PY_SIMPLE, _mark(), wm._LANGS[".py"])
    no_comments = "\n".join(l for l in stamped.splitlines()
                            if not l.lstrip().startswith("#"))
    rep = wm.verify_text(no_comments)
    assert rep.is_marked
    assert "C" in rep.channels_valid   # structural constant carried it


@pytest.mark.skipif(shutil.which("black") is None and
                    __import__("importlib").util.find_spec("black") is None,
                    reason="black not installed")
def test_survives_black_reformat(tmp_path):
    import black  # noqa: F401
    f = tmp_path / "b.py"
    f.write_text(PY_HARD, encoding="utf-8")
    wm.stamp_file(f, _mark())
    subprocess.run([sys.executable, "-m", "black", "-q", str(f)], check=True)
    assert wm.verify_file(f).status == "authentic"


def test_tamper_detected():
    stamped = wm.stamp_text(PY_SIMPLE, _mark("2"), wm._LANGS[".py"])
    tampered = stamped.replace("AE1.", "AE1.Z", 1)  # corrupt structural token
    assert wm.verify_text(tampered).status == "tampered"


def test_unmarked_reports_unmarked():
    assert wm.verify_text(PY_SIMPLE).status == "unmarked"


def test_idempotent_restamp_does_not_accumulate():
    once = wm.stamp_text(PY_SIMPLE, _mark("1"), wm._LANGS[".py"])
    twice = wm.stamp_text(once, _mark("2"), wm._LANGS[".py"])
    # only one mark block; re-stamp replaced rather than appended
    assert twice.count("⟦AE1.") == 1
    assert wm.verify_text(twice).payload.number == "2"


def test_visible_attribution_label_is_human_readable():
    # Steward's flag: the honest majority must SEE who it belongs to, no tooling.
    payload = WatermarkPayload(trademark="AURA Pattern Library",
                               company="Reality Optimizer", number="0")
    stamped = wm.stamp_text(PY_SIMPLE, payload, wm._LANGS[".py"])
    assert "AURA Pattern Library" in stamped
    assert "© Reality Optimizer" in stamped
    # and it still extracts + the label change didn't break tracing
    assert wm.verify_text(stamped).status == "authentic"


def test_non_python_languages_stamp_and_extract():
    for ext, sample in [(".rs", "fn main() { println!(\"hi\"); }\n"),
                        (".go", "package main\nfunc main() {}\n"),
                        (".js", "console.log(1);\n"),
                        (".r", "x <- 1\nprint(x)\n")]:
        lang = wm._LANGS[ext]
        stamped = wm.stamp_text(sample, _mark("0"), lang, "s" + ext)
        assert wm.verify_text(stamped).status == "authentic", ext
