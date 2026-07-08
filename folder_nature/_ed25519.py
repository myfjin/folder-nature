"""Pure-Python Ed25519 (RFC 8032) — vendored, public-domain reference.

Adapted to Python 3 from Daniel J. Bernstein's public-domain reference
implementation (https://ed25519.cr.yp.to/python/ed25519.py). Kept intentionally
close to the reference so it can be audited against the source and against the
RFC 8032 test vectors (see tests/test_ed25519_vectors.py).

Why vendored & pure-Python: file signing must be publicly verifiable with an
asymmetric key, and we want the core package to stay dependency-light (no
mandatory ``cryptography`` build, no required system ``minisign``/``gpg``). This
does a handful of sign/verify operations per manifest, where the reference's
speed is a non-issue.

Honest scope: this proves origin + integrity of files. It does NOT prevent
copying. A signature says "genuinely ours and unaltered", nothing more.

Public API:
    generate_seed() -> 32 random bytes (the private seed; keep at mode 600)
    publickey(seed) -> 32-byte public key
    sign(message, seed) -> 64-byte signature
    verify(signature, message, public_key) -> bool
"""

from __future__ import annotations

import hashlib
import os

__all__ = ["generate_seed", "publickey", "sign", "verify", "BadSignatureError"]

_b = 256
_q = 2 ** 255 - 19
_l = 2 ** 252 + 27742317777372353535851937790883648493


class BadSignatureError(Exception):
    """Raised by verify() paths on structurally invalid input."""


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _inv(x: int) -> int:
    return pow(x, _q - 2, _q)


_d = -121665 * _inv(121666) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5) % _q
_Bx = _xrecover(_By)
_B = [_Bx % _q, _By % _q]


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return [x3 % _q, y3 % _q]


def _scalarmult(P, e):
    if e == 0:
        return [0, 1]
    Q = _scalarmult(P, e // 2)
    Q = _edwards(Q, Q)
    if e & 1:
        Q = _edwards(Q, P)
    return Q


def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(_b)]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))


def _encodepoint(P) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(_b - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _secret_scalar(seed: bytes) -> int:
    h = _H(seed)
    return 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))


def _Hint(m: bytes) -> int:
    h = _H(m)
    return sum(2 ** i * _bit(h, i) for i in range(2 * _b))


def _isoncurve(P) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodeint(s: bytes) -> int:
    return sum(2 ** i * _bit(s, i) for i in range(0, _b))


def _decodepoint(s: bytes):
    y = sum(2 ** i * _bit(s, i) for i in range(0, _b - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1):
        x = _q - x
    P = [x, y]
    if not _isoncurve(P):
        raise BadSignatureError("decoding point that is not on curve")
    return P


# ── public API ───────────────────────────────────────────────────────────────


def generate_seed() -> bytes:
    """Return 32 cryptographically-random bytes — the private seed."""
    return os.urandom(32)


def publickey(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte private seed."""
    if len(seed) != 32:
        raise ValueError("seed must be exactly 32 bytes")
    a = _secret_scalar(seed)
    A = _scalarmult(_B, a)
    return _encodepoint(A)


def sign(message: bytes, seed: bytes) -> bytes:
    """Produce a 64-byte Ed25519 signature over ``message`` with ``seed``."""
    if len(seed) != 32:
        raise ValueError("seed must be exactly 32 bytes")
    h = _H(seed)
    a = _secret_scalar(seed)
    pk = _encodepoint(_scalarmult(_B, a))
    r = _Hint(h[_b // 8:_b // 4] + message)
    R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + pk + message) * a) % _l
    return _encodepoint(R) + _encodeint(S)


def verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    """Return True iff ``signature`` is a valid Ed25519 sig over ``message``."""
    try:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        R = _decodepoint(signature[:32])
        A = _decodepoint(public_key)
        S = _decodeint(signature[32:64])
        h = _Hint(_encodepoint(R) + public_key + message)
        return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))
    except (BadSignatureError, ValueError):
        return False
