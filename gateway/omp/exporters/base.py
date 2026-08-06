"""Exporters drain the buffer through per-exporter cursors (at-least-once).

An exporter acks a rowid only after the destination durably accepted the
envelope; a crash between publish and ack re-sends on restart, which is why
consumers deduplicate on (gateway_id, machine_id, seq).
"""
from __future__ import annotations

import json
import sys

from ..core.store import Store


class Exporter:
    name = "base"

    def publish(self, envelope: dict) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def drain(self, store: Store, batch: int = 500) -> int:
        sent = 0
        while True:
            rows = store.pending(self.name, batch)
            if not rows:
                return sent
            for rowid, envelope in rows:
                self.publish(envelope)
                store.ack(self.name, rowid)
                sent += 1


class StdoutExporter(Exporter):
    name = "stdout"

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout

    def publish(self, envelope: dict) -> None:
        self.stream.write(json.dumps(envelope, ensure_ascii=False) + "\n")
