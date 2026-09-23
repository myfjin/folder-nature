"""Ed25519 correctness — checked against the authoritative RFC 8032 vectors.

This is what makes the signing feature honest: the primitive is not merely
self-consistent, it reproduces the published test vectors byte-for-byte.
"""

from folder_nature import _ed25519 as ed

# RFC 8032, section 7.1 — (seed_hex, pubkey_hex, message_hex, signature_hex)
RFC8032_VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a"
        "33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15"
        "996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
]


def test_rfc8032_public_keys_and_signatures():
    for seed_hex, pub_hex, msg_hex, sig_hex in RFC8032_VECTORS:
        seed = bytes.fromhex(seed_hex)
        msg = bytes.fromhex(msg_hex)
        assert ed.publickey(seed).hex() == pub_hex
        assert ed.sign(msg, seed).hex() == sig_hex
        assert ed.verify(bytes.fromhex(sig_hex), msg, bytes.fromhex(pub_hex))


def test_roundtrip_and_tamper():
    seed = ed.generate_seed()
    pk = ed.publickey(seed)
    msg = b"the library is folder-nature's live proof"
    sig = ed.sign(msg, seed)
    assert ed.verify(sig, msg, pk)
    assert not ed.verify(sig, msg + b"!", pk)  # message tamper
    bad = bytearray(sig)
    bad[0] ^= 1
    assert not ed.verify(bytes(bad), msg, pk)  # signature tamper
    assert not ed.verify(sig, msg, ed.publickey(ed.generate_seed()))  # wrong key
