"""Shared transport pool - one physical link, several machines.

Adapter Plugin API s4: "One adapter instance per machine, even for multi-drop
buses - shared transports are managed via the gateway's transport pool
(`self.transport(...)` helper on AdapterBase) so two instances can share one
RS485 line safely."

The unit that must be atomic on a multi-drop bus is the whole **transaction**
- write the request, read that request's response - not the individual reads
and writes. Two adapters polling unit 1 and unit 2 over the same RS485 pair
must never have their frames interleave, or each reads the other's reply. So
the pool hands out a SharedTransport whose `exchange()` holds the bus lock for
the entire round trip.

This is deliberately protocol-agnostic: the pool knows about locking and
lifecycle, the adapter knows about framing.
"""
from __future__ import annotations

import threading


class SharedTransport:
    """One physical link, opened lazily, used by one caller at a time."""

    def __init__(self, key: str, factory):
        self.key = key
        self._factory = factory
        self._obj = None
        self._lock = threading.RLock()   # re-entrant: exchange() may nest
        self._users = 0

    # -- use ------------------------------------------------------------
    def exchange(self, fn):
        """Run `fn(link)` with exclusive use of the link for the whole call.

        Pass a function that performs the complete request/response round
        trip. Holding the lock across both halves is the entire point.
        """
        with self._lock:
            if self._obj is None:
                self._obj = self._factory()
            return fn(self._obj)

    def reset(self) -> None:
        """Drop the underlying link so the next exchange reopens it.

        Called by an adapter that saw a link-level failure. Other adapters on
        the same bus simply reopen on their next exchange - one machine's bad
        cable should not permanently wedge its neighbours.
        """
        with self._lock:
            obj, self._obj = self._obj, None
            close = getattr(obj, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 - already discarding it
                    pass

    # -- lifecycle ------------------------------------------------------
    def _acquire(self) -> None:
        with self._lock:
            self._users += 1

    def _release(self) -> bool:
        """Returns True when the last user let go."""
        with self._lock:
            self._users = max(self._users - 1, 0)
            if self._users == 0:
                self.reset()
                return True
            return False

    @property
    def users(self) -> int:
        return self._users


class TransportPool:
    """Keyed registry of shared links. Key by what is physically shared -
    the serial device path, or host:port - never by machine."""

    def __init__(self):
        self._lock = threading.Lock()
        self._transports: dict[str, SharedTransport] = {}

    def get(self, key: str, factory) -> SharedTransport:
        with self._lock:
            t = self._transports.get(key)
            if t is None:
                t = SharedTransport(key, factory)
                self._transports[key] = t
            t._acquire()
            return t

    def release(self, key: str) -> None:
        with self._lock:
            t = self._transports.get(key)
            if t is not None and t._release():
                del self._transports[key]

    def close_all(self) -> None:
        with self._lock:
            for t in self._transports.values():
                t.reset()
            self._transports.clear()

    @property
    def keys(self) -> list[str]:
        with self._lock:
            return sorted(self._transports)


#: Process-wide default, so `run-once` and adapter tests get pooling without
#: wiring one up. The daemon installs its own on each adapter.
default_pool = TransportPool()
