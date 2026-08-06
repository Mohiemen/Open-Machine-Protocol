"""generic-serial - profile-driven RS232/RS485 adapter.

Reads newline-delimited output from a legacy controller and maps it to OMP
emissions via a YAML line profile (First Real Machine, section 5). Requires
pyserial for real hardware; replay mode (`replay_file` in config) needs
nothing and is how tests and CI drive it.
"""
from __future__ import annotations

import pathlib
import threading
import time

import yaml

from omp.adapter import AdapterBase, Emit, MachineInfo, now_iso

from protocol import LineProfile, StatsAggregator, parse_line


class Adapter(AdapterBase):
    name = "generic-serial"
    version = "0.1.0"
    supported_profiles = ["textile-dyeing/0.1", "textile-sewing/0.1", "generic/0.1"]

    def _load_profile(self) -> LineProfile:
        data = yaml.safe_load(
            pathlib.Path(self.config["line_profile"]).read_text(encoding="utf-8")
        )
        return LineProfile.from_dict(data)

    def probe(self, config) -> MachineInfo:
        lp = LineProfile.from_dict(
            yaml.safe_load(
                pathlib.Path(config["line_profile"]).read_text(encoding="utf-8")
            )
        )
        capabilities = sorted(
            {"telemetry" if p["emit"]["schema"] == "telemetry" else "event"
             for p in lp.patterns}
        )
        if config.get("replay_file") is None:  # pragma: no cover - hardware
            import serial

            with serial.Serial(config["port"], config.get("baud", 9600), timeout=5) as s:
                s.readline()  # confirm the device talks
        return MachineInfo(
            machine_class=lp.machine_class, make=None, model=None, serial=None,
            capabilities=capabilities, data_source="native",
        )

    def start(self, emit: Emit) -> None:
        self._stop = threading.Event()
        lp = self._load_profile()
        agg = StatsAggregator(self.config.get("stats_window_s", 60))
        replay = self.config.get("replay_file")
        if replay:
            self._run_lines(
                emit, lp, agg,
                pathlib.Path(replay).read_text(encoding="utf-8").splitlines(),
            )
            self._flush(emit, lp, agg)
            self._stop.wait()
            return
        self._run_serial(emit, lp, agg)  # pragma: no cover - hardware

    def _run_lines(self, emit, lp, agg, lines) -> None:
        self._mark_connected()
        for line in lines:
            if self._stop.is_set():
                break
            self._handle(emit, lp, agg, line)

    def _handle(self, emit, lp, agg, line: str) -> None:
        try:
            emission = parse_line(lp, line)
        except ValueError as exc:
            self._mark_degraded(str(exc))
            return
        if emission is None:
            return
        self._mark_data()
        if emission["schema"] == "event":
            emit(self.body(schema="event", profile=lp.profile,
                           body=emission["body"]))
        else:
            done = agg.add(emission["channel"], emission["unit"],
                           emission["value"], now_iso(), time.monotonic())
            if done:
                emit(self.body(schema="telemetry", profile=lp.profile, body=done))

    def _flush(self, emit, lp, agg) -> None:
        for body in agg.flush(now_iso()):
            emit(self.body(schema="telemetry", profile=lp.profile, body=body))

    def _run_serial(self, emit, lp, agg):  # pragma: no cover - hardware
        import serial

        while not self._stop.is_set():
            try:
                with serial.Serial(self.config["port"],
                                   self.config.get("baud", 9600), timeout=1) as s:
                    self._mark_connected()
                    while not self._stop.is_set():
                        raw = s.readline()
                        if raw:
                            self._handle(
                                emit, lp, agg,
                                raw.decode(errors="replace"),
                            )
            except serial.SerialException as exc:
                self._mark_disconnected(str(exc))
                self._stop.wait(self.backoff())
        self._flush(emit, lp, agg)

    def stop(self) -> None:
        self._stop.set()
