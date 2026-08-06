"""Ed25519 signature verification for consumers/auditors.

Same construction as the gateway's signer (gateway/omp/core/keys.py): the
signature covers the UTF-8 bytes of gateway_id, machine_id, seq, checksum
joined by single newlines. Needs the `cryptography` package
(pip install 'omp-tools[signing]').
"""
from __future__ import annotations

import base64


def sig_input(gateway_id: str, machine_id: str, seq: int, checksum: str) -> bytes:
    return f"{gateway_id}\n{machine_id}\n{seq}\n{checksum}".encode()


def verify_envelope_sig(envelope: dict, pubkey_b64: str) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "signature verification needs cryptography: "
            "pip install 'omp-tools[signing]'"
        ) from exc
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pubkey_b64))
        pub.verify(
            base64.b64decode(envelope["sig"]),
            sig_input(envelope["gateway_id"], envelope["machine_id"],
                      envelope["seq"], envelope["checksum"]),
        )
        return True
    except Exception:  # noqa: BLE001 - any failure is "not verified"
        return False
