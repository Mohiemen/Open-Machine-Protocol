"""Exporters drain the buffer through per-exporter cursors (at-least-once).

An exporter acks a rowid only after the destination durably accepted the
envelope; a crash between publish and ack re-sends on restart, which is why
consumers deduplicate on (gateway_id, machine_id, seq).
"""
from __future__ import annotations

import json
import sys

from ..core.store import Store


class ExporterClosed(Exception):
    """The destination went away for good - e.g. the stdout pipe was closed
    by `head`. Callers stop draining rather than acking undelivered data."""


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
        try:
            self.stream.write(json.dumps(envelope, ensure_ascii=False) + "\n")
            # Flush before drain() acks. Python block-buffers 8 KiB whenever
            # stdout is a file or a pipe rather than a terminal, so without
            # this the cursor records "delivered" while the bytes are still
            # in this process's memory. A kill - or the power loss the buffer
            # exists to survive - then loses them, turning at-least-once into
            # at-most-once with nothing in the log to say so. It also made
            # `omp-gateway run > floor.ndjson` look dead for its first 8 KiB.
            self.stream.flush()
        except BrokenPipeError as exc:
            # `omp-gateway run | head` is ordinary usage, not an error - but
            # the envelope was NOT delivered, so surface it instead of letting
            # drain() ack it. The pipe can also close between the write and
            # the flush, which is why both are inside this try.
            raise ExporterClosed("stdout pipe closed") from exc
