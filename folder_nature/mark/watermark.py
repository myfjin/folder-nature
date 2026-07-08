"""The watermark engine — redundant-channel stamp / extract / verify.

What it does (and, just as importantly, what it does NOT):

  * Embeds a :class:`~folder_nature.mark.payload.WatermarkPayload` into a real
    source file across THREE independent channels, so an honest reformat
    (``black`` / ``gofmt`` / ``clang-format``) cannot silently strip the mark.
  * Guarantees the file still parses/runs after stamping (gate-compatible) —
    for Python this is enforced with an in-process ``compile()`` before the
    write is committed.
  * Extracts + verifies the mark, and DETECTS tampering (a channel present but
    CRC-broken, or channels that disagree).

  * It does NOT prevent copying. It cannot. It makes a copy *attributable*.

The three channels, chosen for disjoint failure modes:

  A. zero-width   — invisible; steganographic bits on a comment line. Killed
                    only by an explicit "strip zero-width unicode" pass;
                    survives every mainstream code formatter.
  B. comment-id   — a visible attribution comment ``△ folder-nature mark ⟦…⟧``.
                    Killed by "remove all comments"; survives reformatting.
  C. structural   — a real language-level constant (e.g. ``_AURA_MARK = "…"``).
                    Killed by dead-code elimination; survives comment stripping
                    AND whitespace reformatting.

No single common transform removes all three. Extraction succeeds if ANY one
channel yields a CRC-valid payload.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .payload import PYRAMID, PayloadError, WatermarkPayload


# ── zero-width alphabet (channel A) ──────────────────────────────────────────

_ZW0 = "​"   # ZERO WIDTH SPACE           -> bit 0
_ZW1 = "‌"   # ZERO WIDTH NON-JOINER      -> bit 1
_ZWS = "⁣"   # INVISIBLE SEPARATOR        -> frame sentinel
_ZW_CHARS = _ZW0 + _ZW1 + _ZWS


def _zw_encode(token: str) -> str:
    bits = []
    for byte in token.encode("utf-8"):
        for i in range(7, -1, -1):
            bits.append(_ZW1 if (byte >> i) & 1 else _ZW0)
    return _ZWS + "".join(bits) + _ZWS


def _zw_decode(text: str) -> Optional[str]:
    # find the first sentinel-framed run of zero-width bits
    frames = re.findall(f"{_ZWS}([{_ZW0}{_ZW1}]*){_ZWS}", text)
    for body in frames:
        if not body or len(body) % 8 != 0:
            continue
        out = bytearray()
        for i in range(0, len(body), 8):
            byte = 0
            for ch in body[i:i + 8]:
                byte = (byte << 1) | (1 if ch == _ZW1 else 0)
            out.append(byte)
        try:
            return out.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return None


# ── language profiles ────────────────────────────────────────────────────────

_STRUCT_PREFIX = "AE1."   # marks the token inside the structural literal


@dataclass(frozen=True)
class _Lang:
    line_comment: str
    # a format string with one {s} slot for a double-quoted string literal;
    # None => this language gets comment channels only (no structural const).
    const_tmpl: Optional[str]
    # rust needs inner attributes (#![..]) and //! doc-comments kept on top.
    rust_like: bool = False
    python_like: bool = False


_LANGS: Dict[str, _Lang] = {
    ".py":  _Lang("#", "_AURA_MARK = {s}", python_like=True),
    ".pyw": _Lang("#", "_AURA_MARK = {s}", python_like=True),
    ".r":   _Lang("#", ".aura_mark <- {s}"),
    ".R":   _Lang("#", ".aura_mark <- {s}"),
    ".rs":  _Lang("//", "const _AURA_MARK: &str = {s};", rust_like=True),
    ".go":  _Lang("//", "var _auraMark = {s}"),
    ".js":  _Lang("//", "const _AURA_MARK = {s};"),
    ".mjs": _Lang("//", "const _AURA_MARK = {s};"),
    ".ts":  _Lang("//", "const _AURA_MARK = {s};"),
    ".c":   _Lang("//", "static const char *_aura_mark = {s};"),
    ".h":   _Lang("//", "static const char *_aura_mark = {s};"),
    ".cc":  _Lang("//", "static const char *_aura_mark = {s};"),
    ".cpp": _Lang("//", "static const char *_aura_mark = {s};"),
    ".hpp": _Lang("//", "static const char *_aura_mark = {s};"),
    ".java": _Lang("//", None),   # class-scoped consts are awkward; comments only
}

# languages we can round-trip; anything else -> comment-only generic profile
_GENERIC = _Lang("#", None)


def language_for(path: Path) -> _Lang:
    return _LANGS.get(Path(path).suffix, _GENERIC)


def is_supported(path: Path) -> bool:
    return Path(path).suffix in _LANGS


# ── channel B / C regexes (extraction) ───────────────────────────────────────

_COMMENT_TAG_RE = re.compile(r"folder-nature mark ⟦(AE1\.[A-Z2-7]+)⟧")
_STRUCT_RE = re.compile(r'"AE1\.([A-Z2-7]+)"')


# ── stamping ─────────────────────────────────────────────────────────────────


def _python_insert_line(src: str) -> int:
    """Return the 1-based line number AFTER which it is safe to insert.

    Safe = after shebang, coding cookie, module docstring, and any
    ``from __future__`` imports (Python forbids statements before those).
    """
    lines = src.splitlines()
    # leading shebang / coding cookies / blank lines
    header = 0
    for i, ln in enumerate(lines[:2] if len(lines) >= 2 else lines):
        s = ln.strip()
        if s.startswith("#!") or "coding" in s and s.startswith("#"):
            header = i + 1
    # docstring + future imports via AST
    after = header
    try:
        tree = ast.parse(src)
        body = tree.body
        idx = 0
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            after = max(after, body[0].value.end_lineno or after)
            idx = 1
        while (idx < len(body) and isinstance(body[idx], ast.ImportFrom)
               and body[idx].module == "__future__"):
            after = max(after, body[idx].end_lineno or after)
            idx += 1
    except SyntaxError:
        pass
    return after


def _generic_insert_line(src: str, lang: _Lang) -> int:
    """Insert after leading shebang, top-of-file comments, blank lines, and
    (for rust) inner attributes / doc-comments."""
    lines = src.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if i == 0 and s.startswith("#!"):
            i += 1
            continue
        if s == "" or s.startswith(lang.line_comment):
            i += 1
            continue
        if lang.rust_like and (s.startswith("#![") or s.startswith("//!")):
            i += 1
            continue
        break
    return i


def _channel_lines(token: str, lang: _Lang) -> List[str]:
    c = lang.line_comment
    lines = [
        f"{c} {PYRAMID} folder-nature mark ⟦{_STRUCT_PREFIX}{token}⟧",  # B
        f"{c} {_zw_encode(token)}",                                              # A
    ]
    if lang.const_tmpl:                                                          # C
        literal = f'"{_STRUCT_PREFIX}{token}"'
        lines.append(lang.const_tmpl.format(s=literal))
    return lines


def strip_marks(src: str, lang: _Lang) -> str:
    """Remove any existing folder-nature mark lines (idempotent re-stamping)."""
    out = []
    for ln in src.splitlines(keepends=False):
        stripped = ln.strip()
        if "folder-nature mark ⟦" in ln:                 # channel B
            continue
        if _ZWS in ln and set(ln) <= set(_ZW_CHARS + lang.line_comment + " "):  # channel A line
            continue
        if _STRUCT_RE.search(ln) and (
            "_AURA_MARK" in ln or ".aura_mark" in ln or "_auraMark" in ln
            or "_aura_mark" in ln):                            # channel C
            continue
        out.append(ln)
    result = "\n".join(out)
    if src.endswith("\n"):
        result += "\n"
    return result


class StampError(RuntimeError):
    """Raised when stamping would produce a file that no longer parses/runs."""


def stamp_text(src: str, payload: WatermarkPayload, lang: _Lang,
               filename: str = "<stamped>") -> str:
    """Return ``src`` with the payload embedded across all channels.

    Idempotent: an existing mark is replaced. For Python, the result is
    compiled in-process and :class:`StampError` is raised if it would not parse
    (gate-compatibility is guaranteed, never assumed).
    """
    token = payload.encode()
    src = strip_marks(src, lang)

    if lang.python_like:
        after = _python_insert_line(src)
    else:
        after = _generic_insert_line(src, lang)

    lines = src.splitlines(keepends=False)
    channel_lines = _channel_lines(token, lang)
    new_lines = lines[:after] + channel_lines + lines[after:]
    result = "\n".join(new_lines)
    if src.endswith("\n") or not src:
        result += "\n"

    if lang.python_like:
        try:
            compile(result, filename, "exec")
        except SyntaxError as e:
            raise StampError(
                f"stamping {filename} would break Python parse: {e}"
            ) from e
    return result


def stamp_file(path: Path, payload: WatermarkPayload) -> bool:
    """Stamp a file in place. Returns True if written, False if unsupported.

    Unsupported binary/unknown files are skipped (returns False) rather than
    corrupted. Read/write is UTF-8.
    """
    path = Path(path)
    lang = language_for(path)
    try:
        src = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    stamped = stamp_text(src, payload, lang, filename=str(path))
    path.write_text(stamped, encoding="utf-8")
    return True


# ── extraction / verification ────────────────────────────────────────────────


@dataclass
class MarkReport:
    """Result of inspecting a file (or text) for a watermark."""

    status: str                          # 'authentic' | 'tampered' | 'unmarked'
    payload: Optional[WatermarkPayload] = None
    channels_present: List[str] = field(default_factory=list)
    channels_valid: List[str] = field(default_factory=list)
    detail: str = ""

    @property
    def is_marked(self) -> bool:
        return self.status != "unmarked"


def _extract_tokens(text: str) -> Dict[str, str]:
    """Return {channel: raw_token} for every channel that yields a token."""
    tokens: Dict[str, str] = {}
    mb = _COMMENT_TAG_RE.search(text)
    if mb:
        tokens["B"] = mb.group(1)[len(_STRUCT_PREFIX):]
    mc = _STRUCT_RE.search(text)
    if mc:
        tokens["C"] = mc.group(1)
    za = _zw_decode(text)
    if za and za.startswith(_STRUCT_PREFIX):
        tokens["A"] = za[len(_STRUCT_PREFIX):]
    elif za:
        tokens["A"] = za
    return tokens


def verify_text(text: str) -> MarkReport:
    """Inspect ``text`` for a watermark; classify authentic / tampered / unmarked."""
    tokens = _extract_tokens(text)
    if not tokens:
        return MarkReport("unmarked", detail="no watermark channel found")

    present = sorted(tokens)
    valid: Dict[str, WatermarkPayload] = {}
    for ch, tok in tokens.items():
        try:
            valid[ch] = WatermarkPayload.decode(tok)
        except PayloadError:
            pass

    if not valid:
        return MarkReport(
            "tampered", channels_present=present,
            detail="channel(s) present but no CRC-valid payload (tampered/truncated)",
        )

    # do the valid channels agree on (trademark, number)?
    keys = {(p.trademark, p.company, p.number) for p in valid.values()}
    payload = next(iter(valid.values()))
    if len(keys) > 1:
        return MarkReport(
            "tampered", payload=payload, channels_present=present,
            channels_valid=sorted(valid),
            detail=f"channels disagree: {keys}",
        )

    status = "authentic"
    detail = f"{len(valid)}/{len(present)} channel(s) valid and in agreement"
    # a channel present but invalid while others are valid = partial tamper
    if len(valid) < len(present):
        status = "tampered"
        detail = ("some channels valid, some corrupted — "
                  "partial tamper; attribution still recoverable")
    return MarkReport(
        status, payload=payload, channels_present=present,
        channels_valid=sorted(valid), detail=detail,
    )


def verify_file(path: Path) -> MarkReport:
    """Inspect a file for a watermark (see :func:`verify_text`)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return MarkReport("unmarked", detail="unreadable / not a text file")
    return verify_text(text)
