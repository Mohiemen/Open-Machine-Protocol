"""The adapter plugin API.

Normative contract: docs/docs/architecture/04-interfaces/adapter-plugin-api.md.
The example adapter in that document runs against this module unmodified.

The gateway owns envelope construction, seq assignment, validation,
checksumming, signing, buffering, and export. Adapters translate one machine
family's signals into bodies and report their own health honestly.
"""
from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Callable
from dataclasses import dataclass


def now_iso() -> str:
    t = dt.datetime.now(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


@dataclass
class Body:
    schema: str            # machine | event | process_run | energy | telemetry
    profile: str           # e.g. "textile-dyeing/0.1"
    body: dict             # conforms to schema + profile
    event_ts: str | None = None  # machine-reported time if known, else None


Emit = Callable[[Body], None]


@dataclass
class MachineInfo:
    machine_class: str          # from a supported profile's taxonomy
    make: str | None
    model: str | None
    serial: str | None
    capabilities: list[str]     # schemas this source will emit
    data_source: str            # native | retrofit | hybrid


@dataclass
class AdapterHealth:
    state: str                  # ok | degraded | disconnected | failed
    connected_since: str | None = None
    last_data_ts: str | None = None
    reconnect_count: int = 0
    error_count: int = 0
    detail: str | None = None


@dataclass
class _HealthState:
    state: str = "disconnected"
    connected_since: str | None = None
    last_data_ts: str | None = None
    reconnect_count: int = 0
    error_count: int = 0
    detail: str | None = None


class AdapterBase:
    """Subclass and set name, version, supported_profiles; implement
    probe(), start(), stop(). health() is provided from the _mark_* calls
    unless overridden."""

    name: str = "unnamed-adapter"
    version: str = "0.0.0"
    supported_profiles: list[str] = []

    def __init__(self, config: dict | None = None, scratch_dir: str | None = None,
                 transport_pool=None):
        self.config: dict = config or {}
        self.scratch_dir = scratch_dir
        self._health_lock = threading.Lock()
        self._health = _HealthState()
        self._backoff_s = 1.0
        if transport_pool is None:
            from .core.transports import default_pool

            transport_pool = default_pool
        self._transport_pool = transport_pool
        self._held_transports: set[str] = set()

    # -- lifecycle ------------------------------------------------------
    def probe(self, config: dict) -> MachineInfo:  # pragma: no cover - abstract
        raise NotImplementedError

    def start(self, emit: Emit) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- helpers for subclasses ----------------------------------------
    def body(self, *, schema: str, profile: str, body: dict,
             event_ts: str | None = None) -> Body:
        return Body(schema=schema, profile=profile, body=body, event_ts=event_ts)

    def transport(self, key: str, factory):
        """Get the shared link identified by `key`, opening it if needed.

        Key by what is physically shared - the device path for RS485, or
        host:port - so every adapter on one multi-drop bus gets the same
        SharedTransport and their transactions serialize:

            link = self.transport(self.config["port"],
                                  lambda: serial.Serial(port, baud))
            reply = link.exchange(lambda s: (s.write(req), s.read(256))[1])

        Do the write and the matching read inside one `exchange()`. Splitting
        them lets another machine's request land between yours and its reply,
        and each adapter then reads the other's answer.
        """
        t = self._transport_pool.get(key, factory)
        self._held_transports.add(key)
        return t

    def release_transports(self) -> None:
        """Let go of every shared link this adapter holds. The gateway calls
        this after stop(); the link closes once its last user releases it."""
        for key in list(self._held_transports):
            self._transport_pool.release(key)
        self._held_transports.clear()

    def _mark_connected(self) -> None:
        with self._health_lock:
            if self._health.state != "ok":
                self._health.reconnect_count += (
                    1 if self._health.connected_since is not None else 0
                )
            self._health.state = "ok"
            self._health.connected_since = now_iso()
            self._health.detail = None
        self._backoff_s = 1.0

    def _mark_data(self) -> None:
        with self._health_lock:
            self._health.last_data_ts = now_iso()

    def _mark_degraded(self, detail: str) -> None:
        with self._health_lock:
            self._health.state = "degraded"
            self._health.error_count += 1
            self._health.detail = detail

    def _mark_disconnected(self, detail: str) -> None:
        with self._health_lock:
            self._health.state = "disconnected"
            self._health.error_count += 1
            self._health.detail = detail

    def _mark_failed(self, detail: str) -> None:
        with self._health_lock:
            self._health.state = "failed"
            self._health.detail = detail

    def backoff(self) -> float:
        """Exponential backoff delay in seconds, 1 s to 5 min."""
        delay = self._backoff_s
        self._backoff_s = min(self._backoff_s * 2, 300.0)
        return delay

    # -- health ---------------------------------------------------------
    def health(self) -> AdapterHealth:
        with self._health_lock:
            h = self._health
            return AdapterHealth(
                state=h.state,
                connected_since=h.connected_since,
                last_data_ts=h.last_data_ts,
                reconnect_count=h.reconnect_count,
                error_count=h.error_count,
                detail=h.detail,
            )
