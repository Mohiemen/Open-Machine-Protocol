"""Validation and envelope construction - the gateway's trust core.

Reuses omp-tools for spec loading and canonicalization so the gateway and the
standalone validator can never disagree. Install both packages
(pip install -e ./gateway -e ./tools).
"""
from __future__ import annotations

try:
    from omp_tools.envelope import make_envelope
    from omp_tools.specload import load_spec
    from omp_tools.validate import validate_envelope
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "omp-gateway needs the omp-tools package for spec loading and "
        "validation: pip install -e ./tools"
    ) from exc

from ..adapter import Body, now_iso
from .store import Store


class Engine:
    """Turns adapter Bodies into validated, buffered envelopes.

    Per the spec: validation happens against core AND the declared profile
    BEFORE buffering; invalid messages go to the dead-letter store with the
    validation error attached and are never exported as valid data.
    """

    def __init__(self, gateway_id: str, store: Store, spec_dir=None, signer=None):
        """signer: optional omp.core.keys.GatewayKey - when set, every
        envelope carries an Ed25519 `sig` (hardening guide: required for
        deployments whose data may support compliance claims)."""
        self.gateway_id = gateway_id
        self.store = store
        self.spec = load_spec(spec_dir)
        self.signer = signer

    def process(self, machine_id: str, body: Body) -> dict | None:
        """Returns the buffered envelope, or None if dead-lettered."""
        ts = body.event_ts or now_iso()
        seq = self.store.next_seq(machine_id)
        try:
            envelope = make_envelope(
                schema=body.schema,
                body=body.body,
                profile=body.profile,
                gateway_id=self.gateway_id,
                machine_id=machine_id,
                seq=seq,
                ts=ts,
            )
            if self.signer is not None:
                envelope["sig"] = self.signer.sign(
                    self.gateway_id, machine_id, seq, envelope["checksum"]
                )
        except ValueError as exc:
            self.store.dead_letter(machine_id, ts, body.body, str(exc))
            return None
        errors = validate_envelope(envelope, self.spec)
        if errors:
            self.store.dead_letter(machine_id, ts, body.body, "; ".join(errors))
            return None
        self.store.append(envelope)
        return envelope
