"""Gateway keypair - Ed25519 signing per spec section 2.

The spec defines the signature input as `gateway_id || machine_id || seq ||
checksum` without pinning the concatenation encoding. This implementation
uses the UTF-8 bytes of the four values joined by single newlines
(f"{gateway_id}\\n{machine_id}\\n{seq}\\n{checksum}") - unambiguous because
none of the fields can contain a newline. Pinning this encoding in the spec
is a tracked clarification RFC; until then this file is the reference
behavior and omp-validate verifies the same construction.

Private keys are generated on-device and never leave it (hardening guide
section 4): the key file is chmod 0600 and no code here serializes the
private key anywhere else.
"""
from __future__ import annotations

import base64
import os
import pathlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def sig_input(gateway_id: str, machine_id: str, seq: int, checksum: str) -> bytes:
    return f"{gateway_id}\n{machine_id}\n{seq}\n{checksum}".encode("utf-8")


class GatewayKey:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._key = private_key

    # -- creation / loading --------------------------------------------
    @classmethod
    def generate(cls, path: str | pathlib.Path) -> "GatewayKey":
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        return cls(key)

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "GatewayKey":
        pem = pathlib.Path(path).read_bytes()
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 private key")
        return cls(key)

    @classmethod
    def load_or_generate(cls, path: str | pathlib.Path) -> "GatewayKey":
        return cls.load(path) if pathlib.Path(path).exists() else cls.generate(path)

    # -- use ------------------------------------------------------------
    def sign(self, gateway_id: str, machine_id: str, seq: int,
             checksum: str) -> str:
        raw = self._key.sign(sig_input(gateway_id, machine_id, seq, checksum))
        return base64.b64encode(raw).decode("ascii")

    def public_key_b64(self) -> str:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode("ascii")


def verify_signature(pubkey_b64: str, sig_b64: str, gateway_id: str,
                     machine_id: str, seq: int, checksum: str) -> bool:
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pubkey_b64))
        pub.verify(base64.b64decode(sig_b64),
                   sig_input(gateway_id, machine_id, seq, checksum))
        return True
    except Exception:  # noqa: BLE001 - any failure is "not verified"
        return False
