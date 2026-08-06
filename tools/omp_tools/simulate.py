"""omp-simulate - generate realistic OMP envelope streams, no hardware needed.

Profiles: generic (core events), textile-sewing (cycle-based line),
textile-dyeing (batch with phase skeleton). Output is NDJSON on stdout, or
MQTT with --export. Time is simulated: a --duration of 8h emits immediately.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys

from . import __version__
from .envelope import make_envelope

EPOCH = dt.datetime(2026, 7, 24, 2, 0, 0, tzinfo=dt.timezone.utc)


def parse_duration(text: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(s|m|h)", text)
    if not m:
        raise argparse.ArgumentTypeError(f"bad duration {text!r} (use e.g. 10s, 5m, 8h)")
    return float(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)]


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


class Machine:
    def __init__(self, sim, index: int, machine_class: str, capabilities: list[str]):
        self.sim = sim
        self.machine_id = f"sim-{sim.line}-m{index:02d}"
        self.machine_class = machine_class
        self.capabilities = capabilities
        self.seq = 0

    def emit(self, schema: str, body: dict, t: dt.datetime):
        self.seq += 1
        env = make_envelope(
            schema=schema,
            body=body,
            profile=self.sim.profile_ref,
            gateway_id=self.sim.gateway_id,
            machine_id=self.machine_id,
            seq=self.seq,
            ts=iso(t),
        )
        self.sim.out(env)

    def announce(self, t: dt.datetime):
        self.emit(
            "machine",
            {
                "machine_class": self.machine_class,
                "make": "SimWorks",
                "model": "SW-100",
                "location": {
                    "site": self.sim.site,
                    "area": self.sim.area,
                    "line": self.sim.line,
                    "station": self.machine_id[-3:],
                },
                "capabilities": self.capabilities,
                "adapter": {"name": "omp-simulate", "version": __version__},
                "data_source": "native",
            },
            t,
        )


class Simulator:
    def __init__(self, args, emit_fn):
        self.profile = args.profile
        self.profile_ref = f"{args.profile}/0.1"
        self.site = args.site
        self.area = {"textile-dyeing": "dyeing"}.get(args.profile, "sewing")
        self.line = args.line
        self.gateway_id = "gw-sim-01"
        self.rng = random.Random(args.seed)
        self.out = emit_fn

    # ---------------------------------------------------------- sewing/generic
    def run_cyclic_machine(self, m: Machine, seconds: float):
        t = EPOCH
        end = EPOCH + dt.timedelta(seconds=seconds)
        m.announce(t)
        run_id = f"run-{m.machine_id}-1"
        m.emit("event", {"event_type": "run_start", "run_id": run_id}, t)
        first_seq = m.seq
        cycles = 0
        energy_anchor = t
        running = True
        while t < end:
            if running:
                cycle_s = self.rng.uniform(18, 45)
                t += dt.timedelta(seconds=cycle_s)
                if t >= end:
                    break
                cycles += 1
                m.emit(
                    "event",
                    {
                        "event_type": "cycle_complete",
                        "run_id": run_id,
                        "payload": {
                            "cycle_count": cycles,
                            "cycle_time_ms": int(cycle_s * 1000),
                        },
                    },
                    t,
                )
                if self.rng.random() < 0.04:
                    running = False
                    m.emit(
                        "event",
                        {"event_type": "stop", "payload": {"reason": "unknown"}},
                        t,
                    )
            else:
                stop_s = self.rng.uniform(30, 240)
                t += dt.timedelta(seconds=stop_s)
                running = True
                m.emit(
                    "event",
                    {
                        "event_type": "start",
                        "payload": {"reason": "unknown"},
                        "duration_ms": int(stop_s * 1000),
                    },
                    t,
                )
            if (t - energy_anchor).total_seconds() >= 3600:
                m.emit(
                    "energy",
                    {
                        "metric": "kwh",
                        "value": self.rng.randint(0, 2),
                        "interval": {
                            "start_ts": iso(energy_anchor),
                            "end_ts": iso(t),
                        },
                        "source": "ct_clamp",
                        "run_id": run_id,
                    },
                    t,
                )
                energy_anchor = t
        m.emit("event", {"event_type": "run_end", "run_id": run_id}, t)
        m.emit(
            "process_run",
            {
                "run_id": run_id,
                "run_type": "shift",
                "start_ts": iso(EPOCH),
                "end_ts": iso(t),
                "outcome": "completed",
                "quantities": [
                    {"name": "cycles_total", "value": cycles, "unit": "1"},
                ],
                "event_seq_range": {"first": first_seq, "last": m.seq},
            },
            t,
        )

    # -------------------------------------------------------------- dyeing
    def run_dye_machine(self, m: Machine, seconds: float):
        t = EPOCH
        m.announce(t)
        run_id = f"batch-{m.machine_id}-1"
        m.emit("event", {"event_type": "run_start", "run_id": run_id}, t)
        first_seq = m.seq
        fabric_kg = self.rng.randrange(300, 600, 20)
        # phase name -> (duration share, params builder)
        plan = [
            ("load", 0.05, lambda: {"fabric_kg": fabric_kg}),
            ("heat", 0.15, lambda: {"from_c": 30, "to_c": 60, "gradient_c_per_min": 2}),
            ("hold", 0.35, lambda: {"temp_c": 60, "duration_min": 45}),
            ("cool", 0.10, lambda: {"from_c": 60, "to_c": 40, "gradient_c_per_min": 2}),
            ("rinse", 0.20, lambda: {"cycles": 2, "temp_c": 40}),
            ("drain", 0.05, dict),
            ("unload", 0.10, dict),
        ]
        phases = []
        temp = 30
        for name, share, params in plan:
            start = t
            m.emit("event", {"event_type": "phase_start", "run_id": run_id,
                             "payload": {"phase": name}}, t)
            phase_s = seconds * share
            # temperature telemetry as stats over the phase
            if name == "heat":
                temp_lo, temp_hi = 30, 60
                temp = 60
            elif name == "hold":
                temp_lo, temp_hi = 59, 61
            elif name == "cool":
                temp_lo, temp_hi = 40, 60
                temp = 40
            else:
                temp_lo, temp_hi = temp - 1, temp + 1
            t += dt.timedelta(seconds=phase_s)
            m.emit(
                "telemetry",
                {
                    "channel": "bath_temp",
                    "unit": "Cel",
                    "mode": "stats",
                    "run_id": run_id,
                    "stats": {
                        "start_ts": iso(start),
                        "end_ts": iso(t),
                        "min": temp_lo,
                        "max": temp_hi,
                        "avg": (temp_lo + temp_hi) // 2,
                        "count": max(int(phase_s // 10), 1),
                    },
                },
                t,
            )
            if name == "hold" and self.rng.random() < 0.3:
                m.emit("event", {"event_type": "addition", "run_id": run_id,
                                 "payload": {"reason": "shade_correction"}}, t)
            m.emit("event", {"event_type": "phase_end", "run_id": run_id,
                             "payload": {"phase": name}}, t)
            phases.append(
                {"name": name, "start_ts": iso(start), "end_ts": iso(t),
                 "params": params()}
            )
        m.emit(
            "energy",
            {
                "metric": "kwh",
                "value": self.rng.randint(30, 60),
                "interval": {"start_ts": iso(EPOCH), "end_ts": iso(t)},
                "source": "submeter",
                "run_id": run_id,
            },
            t,
        )
        m.emit("event", {"event_type": "run_end", "run_id": run_id}, t)
        m.emit(
            "process_run",
            {
                "run_id": run_id,
                "run_type": "batch",
                "start_ts": iso(EPOCH),
                "end_ts": iso(t),
                "outcome": "completed",
                "phases": phases,
                "quantities": [
                    {"name": "fabric_kg", "value": fabric_kg, "unit": "kg"},
                    {"name": "water_l_total", "value": fabric_kg * 4, "unit": "L"},
                ],
                "event_seq_range": {"first": first_seq, "last": m.seq},
            },
            t,
        )

    def run(self, machines: int, seconds: float):
        for i in range(1, machines + 1):
            if self.profile == "textile-dyeing":
                m = Machine(self, i, "jet_dyeing",
                            ["event", "process_run", "energy", "telemetry"])
                self.run_dye_machine(m, seconds)
            else:
                cls = "lockstitch" if self.profile == "textile-sewing" else "unclassified"
                m = Machine(self, i, cls, ["event", "process_run", "energy"])
                self.run_cyclic_machine(m, seconds)


# ------------------------------------------------------------------- chaos
def corrupt(envelope: dict, rng: random.Random) -> dict:
    """Break a message *after* checksumming, like line noise or a bad adapter."""
    kind = rng.choice(["type_flip", "checksum", "field"])
    env = json.loads(json.dumps(envelope))
    body = env["body"]
    if kind == "type_flip" and env["schema"] == "event" and "payload" in body:
        for k, v in body["payload"].items():
            if isinstance(v, int):
                body["payload"][k] = str(v)
                break
        else:
            env["checksum"] = "0" * 64
    elif kind == "checksum":
        env["checksum"] = ("f" + env["checksum"][1:]) if env["checksum"][0] != "f" \
            else ("0" + env["checksum"][1:])
    else:
        env["unexpected_field"] = True
    return env


# ------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omp-simulate", description=__doc__)
    parser.add_argument("--profile", default="generic",
                        choices=["generic", "textile-sewing", "textile-dyeing"])
    parser.add_argument("--machines", type=int, default=1)
    parser.add_argument("--duration", type=parse_duration, default=parse_duration("10m"),
                        help="simulated wall time, e.g. 10s, 5m, 8h (default 10m)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--chaos", choices=["corrupt-fields"], default=None)
    parser.add_argument("--chaos-rate", type=float, default=0.05)
    parser.add_argument("--export", metavar="mqtt://HOST[:PORT]", default=None)
    parser.add_argument("--site", default="demo")
    parser.add_argument("--line", default="line1")
    parser.add_argument("--version", action="version",
                        version=f"omp-simulate {__version__}")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    sink = _make_sink(args)

    def out(envelope: dict):
        if args.chaos == "corrupt-fields" and rng.random() < args.chaos_rate:
            envelope = corrupt(envelope, rng)
        sink(envelope)

    Simulator(args, out).run(args.machines, args.duration)
    if hasattr(sink, "close"):
        sink.close()
    return 0


def _make_sink(args):
    if not args.export:
        def stdout_sink(env):
            print(json.dumps(env, ensure_ascii=False))
        return stdout_sink
    m = re.fullmatch(r"mqtt://([^:/]+)(?::(\d+))?", args.export)
    if not m:
        print(f"unsupported --export URL {args.export!r} (only mqtt:// here; "
              "REST/OPC UA/CSV are gateway exporters)", file=sys.stderr)
        raise SystemExit(2)
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("MQTT export needs paho-mqtt: pip install 'omp-tools[mqtt]'",
              file=sys.stderr)
        raise SystemExit(2) from None   # the message above is the whole story
    client = mqtt.Client()
    client.connect(m.group(1), int(m.group(2) or 1883))
    client.loop_start()
    area = {"textile-dyeing": "dyeing"}.get(args.profile, "sewing")

    class MqttSink:
        def __call__(self, env):
            topic = (f"omp/{args.site}/{area}/{args.line}/"
                     f"{env['machine_id']}/{env['schema']}")
            client.publish(topic, json.dumps(env, ensure_ascii=False), qos=1)

        def close(self):
            client.loop_stop()
            client.disconnect()

    return MqttSink()


if __name__ == "__main__":
    sys.exit(main())
