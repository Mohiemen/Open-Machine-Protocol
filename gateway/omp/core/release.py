"""Release artifact verification - Hardening Guide s6 [Required].

    Install OMP releases only from GitHub Releases with signature
    verification (`omp-gateway verify-release` or manual minisign check per
    release notes). Never `pip install` onto a production gateway from a
    branch.

This implements the minisign format, because that is what the guide names
and what a maintainer can produce without this project inventing a scheme.
No new dependency: Ed25519 comes from `cryptography`, which the gateway
already requires for envelope signing, and BLAKE2b from the standard
library.

What this module refuses to do is as important as what it does:

* It never fetches a key. A signature checked against a key that travelled
  with the artifact proves only that one person controlled both, which is
  exactly the position an attacker who replaced the artifact is in. The key
  is pinned in the installation or passed explicitly by the operator.
* It verifies minisign's global signature too, so the trusted comment - the
  only human-readable text an operator is likely to believe - cannot be
  edited without detection.
* It never reports success for a check it did not perform. A checksum file
  with no signature over it is reported as unverified provenance, not as a
  pass, because anyone who can replace the artifact can replace SHA256SUMS
  beside it.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import pathlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

LEGACY, PREHASHED = b"Ed", b"ED"

# Where a packaged release key would live. Absent until the project cuts a
# signed release and pins one - see the "no key pinned" path below, which
# must never degrade into "verified".
PINNED_KEY = pathlib.Path(__file__).resolve().parent.parent / "release-key.pub"


class VerifyError(Exception):
    """Verification did not succeed. The message is written for an operator
    deciding whether to install something, so it says which check failed."""


@dataclass
class PublicKey:
    key_id: bytes
    key: Ed25519PublicKey
    untrusted_comment: str = ""

    def key_id_hex(self) -> str:
        # minisign prints key IDs byte-reversed; match it so an operator can
        # compare against `minisign -p` output without transposing digits.
        return self.key_id[::-1].hex().upper()


@dataclass
class Signature:
    algorithm: bytes
    key_id: bytes
    sig: bytes
    trusted_comment: str
    global_sig: bytes


def _b64(line: str, what: str) -> bytes:
    try:
        return base64.b64decode(line.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VerifyError(f"{what} is not valid base64: {exc}") from exc


def parse_public_key(text: str) -> PublicKey:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise VerifyError("public key file is empty")
    comment = ""
    if lines[0].startswith("untrusted comment:"):
        comment = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    if not lines:
        raise VerifyError("public key file has a comment but no key")
    raw = _b64(lines[0], "public key")
    if len(raw) != 42:
        raise VerifyError(
            f"public key is {len(raw)} bytes, expected 42 "
            "(2-byte algorithm + 8-byte key id + 32-byte Ed25519 key)")
    if raw[:2] != LEGACY:
        raise VerifyError(
            f"unsupported public key algorithm {raw[:2]!r}; only Ed25519 "
            "minisign keys are understood")
    return PublicKey(key_id=raw[2:10],
                     key=Ed25519PublicKey.from_public_bytes(raw[10:]),
                     untrusted_comment=comment)


def parse_signature(text: str) -> Signature:
    lines = text.splitlines()
    if len(lines) < 4:
        raise VerifyError(
            f"signature file has {len(lines)} line(s), expected 4 "
            "(comment, signature, trusted comment, global signature)")
    raw = _b64(lines[1], "signature")
    if len(raw) != 74:
        raise VerifyError(f"signature is {len(raw)} bytes, expected 74")
    algorithm = raw[:2]
    if algorithm not in (LEGACY, PREHASHED):
        raise VerifyError(f"unsupported signature algorithm {algorithm!r}")
    if not lines[2].startswith("trusted comment:"):
        raise VerifyError("third line is not a trusted comment")
    trusted = lines[2].split(":", 1)[1].strip()
    return Signature(algorithm=algorithm, key_id=raw[2:10], sig=raw[10:],
                     trusted_comment=trusted,
                     global_sig=_b64(lines[3], "global signature"))


def _signed_bytes(path: pathlib.Path, algorithm: bytes) -> bytes:
    """What the signature actually covers.

    Read in chunks: a release tarball is not something to hold in the RAM of
    a Pi that is also running a floor.
    """
    if algorithm == PREHASHED:
        h = hashlib.blake2b(digest_size=64)
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.digest()
    with open(path, "rb") as fh:
        return fh.read()


def verify_artifact(artifact: pathlib.Path, signature: Signature,
                    pubkey: PublicKey) -> str:
    """Return the trusted comment on success; raise VerifyError otherwise."""
    if signature.key_id != pubkey.key_id:
        raise VerifyError(
            "this signature was made by a different key "
            f"(signature {signature.key_id[::-1].hex().upper()}, "
            f"trusted key {pubkey.key_id_hex()}) - do not install this "
            "artifact until you know why")
    try:
        pubkey.key.verify(signature.sig, _signed_bytes(artifact, signature.algorithm))
    except InvalidSignature as exc:
        raise VerifyError(
            "signature does not match the file - it was modified in transit, "
            "or it is not the file this signature was made for") from exc
    # The trusted comment is signed separately; without this check an
    # attacker could keep a valid file signature and rewrite the version and
    # date an operator reads.
    try:
        pubkey.key.verify(signature.global_sig,
                          signature.sig + signature.trusted_comment.encode())
    except InvalidSignature as exc:
        raise VerifyError(
            "the file signature is valid but the trusted comment is not - "
            "the comment has been altered; trust nothing it says") from exc
    return signature.trusted_comment


# -- checksum files -------------------------------------------------------
def parse_checksums(text: str) -> dict[str, str]:
    """`sha256sum` output: '<hex>  <name>' (two spaces) or '<hex> *<name>'."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise VerifyError(f"malformed checksum line: {line!r}")
        try:
            bytes.fromhex(parts[0])
        except ValueError as exc:
            raise VerifyError(f"malformed checksum line: {line!r}") from exc
        out[parts[1].lstrip("*").strip()] = parts[0].lower()
    if not out:
        raise VerifyError("checksum file lists nothing")
    return out


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(artifact: pathlib.Path, checksums: dict[str, str]) -> str:
    name = artifact.name
    if name not in checksums:
        raise VerifyError(
            f"{name} is not listed in the checksum file "
            f"(it lists: {', '.join(sorted(checksums))})")
    actual = sha256_file(artifact)
    if actual != checksums[name]:
        raise VerifyError(
            f"SHA-256 mismatch for {name}: file is {actual}, "
            f"checksum file says {checksums[name]}")
    return actual
