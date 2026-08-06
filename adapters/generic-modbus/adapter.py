"""generic-modbus - YAML register maps instead of code.

Polls holding/input registers over Modbus TCP or RTU and emits per the
mapping file's `mode` (on_increment | on_change | stats) - the format from
First Real Machine section 4. Read-only by construction: the protocol layer
cannot build write frames.

Transport is injectable (`transport` in config, a callable bytes->bytes) so
tests and captured fixtures drive the full path without a device.
"""
from __future__ import annotations

import pathlib
import threading
import time

import yaml

from omp.adapter import AdapterBase, Emit, MachineInfo, now_iso

import protocol as mb
from protocol import decode_value, reg_count, resolve_address

# reuse the serial adapter's aggregator shape locally (kept self-contained)


class _Stats:
    def __init__(self, window_s: float):
        self.window_s = window_s
        self.acc: dict[str, dict] = {}

    def add(self, channel, unit, value, ts, mono):
        a = self.acc.get(channel)
        if a is None:
            self.acc[channel] = {"unit": unit, "start_ts": ts, "mono": mono,
                                 "min": value, "max": value, "sum": value,
                                 "count": 1}
            return None
        a.update(min=min(a["min"], value), max=max(a["max"], value),
                 sum=a["sum"] + value, count=a["count"] + 1)
        if mono - a["mono"] >= self.window_s:
            return self.close(channel, ts)
        return None

    def close(self, channel, end_ts):
        a = self.acc.pop(channel)
        return {"channel": channel, "unit": a["unit"], "mode": "stats",
                "stats": {"start_ts": a["start_ts"], "end_ts": end_ts,
                          "min": a["min"], "max": a["max"],
                          "avg": int(a["sum"] / a["count"]),
                          "count": a["count"]}}

    def flush(self, end_ts):
        return [self.close(c, end_ts) for c in list(self.acc)]


class Adapter(AdapterBase):
    name = "generic-modbus"
    version = "0.1.0"
    supported_profiles = ["textile-sewing/0.1", "textile-dyeing/0.1", "generic/0.1"]

    # ---------------------------------------------------------------- setup
    def _mapping(self) -> dict:
        return yaml.safe_load(
            pathlib.Path(self.config["mapping_file"]).read_text(encoding="utf-8")
        )

    def _transport(self):
        """Returns a callable(request_bytes) -> response_bytes."""
        if callable(self.config.get("transport")):
            return self.config["transport"]
        if "host" in self.config:  # pragma: no cover - hardware
            import socket

            sock = socket.create_connection(
                (self.config["host"], self.config.get("tcp_port", 502)),
                timeout=self.config.get("timeout_ms", 2000) / 1000,
            )

            def tcp(request: bytes) -> bytes:
                sock.sendall(request)
                return sock.recv(260)

            return tcp
        # pragma: no cover - hardware
        import serial

        port = serial.Serial(self.config["port"], self.config.get("baud", 9600),
                             timeout=self.config.get("timeout_ms", 2000) / 1000)

        def rtu(request: bytes) -> bytes:
            port.reset_input_buffer()
            port.write(request)
            return port.read(256)

        return rtu

    def _is_tcp(self) -> bool:
        return "host" in self.config or self.config.get("framing") == "tcp"

    # ---------------------------------------------------------------- API
    def probe(self, config) -> MachineInfo:
        mapping = yaml.safe_load(
            pathlib.Path(config["mapping_file"]).read_text(encoding="utf-8")
        )
        capabilities = sorted({
            "telemetry" if r["emit"]["schema"] == "telemetry" else "event"
            for r in mapping["registers"]
        })
        return MachineInfo(
            machine_class=mapping["machine_class"], make=None, model=None,
            serial=None, capabilities=capabilities, data_source="native",
        )

    def start(self, emit: Emit) -> None:
        self._stop = threading.Event()
        mapping = self._mapping()
        profile = mapping["profile"]
        poll_s = mapping.get("poll_interval_ms", 1000) / 1000
        unit_id = self.config.get("unit_id", 1)
        stats = _Stats(self.config.get("stats_window_s", 60))
        last: dict[str, int | float] = {}
        tid = 0
        transport = None
        max_polls = self.config.get("max_polls")  # replay/CI bound
        polls = 0

        while not self._stop.is_set():
            if transport is None:
                try:
                    transport = self._transport()
                    self._mark_connected()
                except Exception as exc:  # noqa: BLE001 - report, retry
                    self._mark_disconnected(f"connect: {exc}")
                    self._stop.wait(self.backoff())
                    continue
            try:
                for reg in mapping["registers"]:
                    tid = (tid + 1) & 0xFFFF
                    value = self._read(transport, tid, unit_id, reg)
                    self._mark_data()
                    self._emit_value(emit, profile, stats, last, reg, value)
            except mb.ModbusError as exc:
                self._mark_degraded(str(exc))
            except Exception as exc:  # noqa: BLE001 - link dropped
                self._mark_disconnected(str(exc))
                transport = None
                self._stop.wait(self.backoff())
                continue
            polls += 1
            if max_polls and polls >= max_polls:
                break
            self._stop.wait(poll_s)

        for body in stats.flush(now_iso()):
            emit(self.body(schema="telemetry", profile=profile, body=body))
        self._stop.wait()

    def _read(self, transport, tid, unit_id, reg):
        func, offset = resolve_address(reg["address"])
        count = reg_count(reg.get("type", "u16"))
        if self._is_tcp():
            request = mb.build_read_tcp(tid, unit_id, func, offset, count)
            regs = mb.parse_read_tcp(transport(request), tid, func)
        else:
            request = mb.build_read_rtu(unit_id, func, offset, count)
            regs = mb.parse_read_rtu(transport(request), unit_id, func)
        return decode_value(regs, reg.get("type", "u16"), reg.get("scale", 1))

    def _emit_value(self, emit, profile, stats, last, reg, value):
        conf = reg["emit"]
        mode = conf["mode"]
        name = reg["name"]
        if mode == "stats":
            done = stats.add(conf["channel"], conf["unit"], value,
                             now_iso(), time.monotonic())
            if done:
                emit(self.body(schema="telemetry", profile=profile, body=done))
            return
        prev = last.get(name)
        last[name] = value
        if prev is None:
            return  # first read establishes the baseline, no event
        if mode == "on_increment" and value > prev:
            emit(self.body(schema="event", profile=profile, body={
                "event_type": conf["event_type"],
                "payload": {conf.get("payload_field", name): value},
            }))
        elif mode == "on_change" and value != prev:
            enum = conf.get("enum", {})
            emit(self.body(schema="event", profile=profile, body={
                "event_type": conf.get("event_type", "state_change"),
                "payload": {"from_state": str(enum.get(prev, prev)),
                            "to_state": str(enum.get(value, value))},
            }))

    def stop(self) -> None:
        self._stop.set()
