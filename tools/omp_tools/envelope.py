"""Envelope canonicalization and checksum.

Checksum input is the body serialized per RFC 8785 (JCS). For bodies whose
numbers are all integers - which OMP producers in this repo guarantee - a
sorted-key compact JSON serialization is JCS-equivalent. Floats with
non-trivial shortest-round-trip forms would need a full JCS implementation;
`canonicalize` rejects them loudly rather than producing a wrong checksum.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

CORE_SCHEMAS = ("machine", "event", "process_run", "energy", "telemetry")


def _check_numbers(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}")
        # Integral floats round-trip identically to ints in JCS; anything
        # else needs a real JCS serializer.
        if value != int(value):
            raise ValueError(
                f"non-integral float at {path}: full RFC 8785 serialization "
                "required - keep producer values integral or add a JCS library"
            )
    elif isinstance(value, dict):
        for k, v in value.items():
            _check_numbers(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _check_numbers(v, f"{path}[{i}]")


def canonicalize(body: dict) -> str:
    _check_numbers(body)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(body: dict) -> str:
    return hashlib.sha256(canonicalize(body).encode("utf-8")).hexdigest()


def make_envelope(
    *,
    schema: str,
    body: dict,
    profile: str,
    gateway_id: str,
    machine_id: str,
    seq: int,
    ts: str,
    omp_version: str = "0.1.0",
    sig: str | None = None,
) -> dict:
    if schema not in CORE_SCHEMAS:
        raise ValueError(f"unknown schema {schema!r}")
    env = {
        "omp_version": omp_version,
        "profile": profile,
        "gateway_id": gateway_id,
        "machine_id": machine_id,
        "seq": seq,
        "ts": ts,
        "schema": schema,
        "body": body,
        "checksum": checksum(body),
    }
    if sig is not None:
        env["sig"] = sig
    return env
