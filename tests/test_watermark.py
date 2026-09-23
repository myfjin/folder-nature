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
    return WatermarkPayload(
        trademark="Aura Elements", company="Aura Elements", number=number
    )


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
    no_comments = "\n".join(
        l for l in stamped.splitlines() if not l.lstrip().startswith("#")
    )
    rep = wm.verify_text(no_comments)
    assert rep.is_marked
    assert "C" in rep.channels_valid  # structural constant carried it


@pytest.mark.skipif(
    shutil.which("black") is None
    and __import__("importlib").util.find_spec("black") is None,
    reason="black not installed",
)
def test_survives_black_reformat(tmp_path):
    import black  # noqa: F401

    f = tmp_path / "b.py"
    f.write_text(PY_HARD, encoding="utf-8")
    wm.stamp_file(f, _mark())
    subprocess.run([sys.executable, "-m", "black", "-q", str(f)], check=True)
    assert wm.verify_file(f).status == "authentic"


def _frames(text: str) -> int:
    """Count channel-A frames. Each frame carries exactly two sentinels, so the
    count needs no regex and no knowledge of the fix."""
    return text.count(wm._ZWS) // 2


def test_restamp_is_idempotent_when_a_formatter_has_indented_the_mark_line():
    """A formatter can indent the channel-A line.

    gofmt indents with tabs, and any mark that ends up inside a block gets
    indented by something. Re-stamping must replace the previous mark rather than
    leave it embedded beside the new one: two frames means the old payload is
    still in the file, and the old attribution is still extractable.
    """
    stamped = wm.stamp_text(PY_SIMPLE, _mark("1"), wm._LANGS[".py"])
    assert _frames(stamped) == 1

    indented = (
        "\n".join(
            ("\t" + ln) if wm._ZWS in ln and ln.lstrip().startswith("#") else ln
            for ln in stamped.splitlines()
        )
        + "\n"
    )
    assert _frames(indented) == 1, "the indent lost the frame itself"

    again = wm.stamp_text(indented, _mark("2"), wm._LANGS[".py"])
    assert _frames(again) == 1, "the old channel-A frame survived re-stamping"
    assert wm.verify_text(again).payload.number == "2"


def test_strip_leaves_a_line_of_code_that_merely_contains_a_frame():
    """The recogniser must be precise, not greedy.

    A frame can appear in a line that is NOT a mark line — a string literal, a
    comment with other words in it. The old character-set test would have eaten
    such a line; stripping must never remove something it did not write.
    """
    code = 'BANNER = "hello ' + wm._ZWS + wm._ZW0 + wm._ZWS + ' world"\n'
    assert wm._is_channel_a_line("# note " + wm._ZWS + wm._ZW0 + wm._ZWS + " extra", wm._LANGS[".py"]) is False
    stripped = wm.strip_marks(code, wm._LANGS[".py"])
    assert "BANNER" in stripped, "stripping removed a line of code"


def test_zero_width_alphabet_is_exactly_the_codepoints_its_comments_name():
    """The alphabet is made of invisible characters, so the source has to SAY which
    ones they are — and the codepoints are the contract.

    Written as escapes rather than as literal invisible characters: a copy/paste,
    a re-encoding, or a diff tool that eats the character can then no longer change
    the alphabet without changing something a reader can see.
    """
    assert [ord(c) for c in wm._ZW0] == [0x200B]  # ZERO WIDTH SPACE
    assert [ord(c) for c in wm._ZW1] == [0x200C]  # ZERO WIDTH NON-JOINER
    assert [ord(c) for c in wm._ZWS] == [0x2063]  # INVISIBLE SEPARATOR
    assert wm._ZW_CHARS == "\u200b\u200c\u2063"


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
    payload = WatermarkPayload(
        trademark="AURA Pattern Library", company="Reality Optimizer", number="0"
    )
    stamped = wm.stamp_text(PY_SIMPLE, payload, wm._LANGS[".py"])
    assert "AURA Pattern Library" in stamped
    assert "© Reality Optimizer" in stamped
    # and it still extracts + the label change didn't break tracing
    assert wm.verify_text(stamped).status == "authentic"


def test_go_structural_const_lands_after_package():
    # Go's grammar forbids any declaration before `package` — the structural var
    # must land after package+imports or the file won't build.
    go = 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println(1) }\n'
    out = wm.stamp_text(go, _mark("0"), wm._LANGS[".go"], "x.go")
    lines = out.splitlines()
    pkg_i = next(i for i, l in enumerate(lines) if l.strip().startswith("package "))
    var_i = next(
        i for i, l in enumerate(lines) if l.strip().startswith("var _auraMark")
    )
    assert var_i > pkg_i, "Go structural const must come after the package clause"
    assert wm.verify_text(out).status == "authentic"


@pytest.mark.skipif(shutil.which("go") is None, reason="go not installed")
def test_go_stamped_file_still_builds(tmp_path):
    f = tmp_path / "m.go"
    f.write_text(
        'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println(1) }\n',
        encoding="utf-8",
    )
    wm.stamp_file(f, _mark("0"))
    r = subprocess.run(
        ["go", "build", "-o", str(tmp_path / "out"), str(f)], capture_output=True
    )
    assert r.returncode == 0, "stamped Go must still compile"


def test_non_python_languages_stamp_and_extract():
    for ext, sample in [
        (".rs", 'fn main() { println!("hi"); }\n'),
        (".go", "package main\nfunc main() {}\n"),
        (".js", "console.log(1);\n"),
        (".r", "x <- 1\nprint(x)\n"),
    ]:
        lang = wm._LANGS[ext]
        stamped = wm.stamp_text(sample, _mark("0"), lang, "s" + ext)
        assert wm.verify_text(stamped).status == "authentic", ext
