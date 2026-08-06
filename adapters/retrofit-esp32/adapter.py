"""retrofit-esp32 - gateway-side adapter for OMP retrofit nodes.

Consumes the node's JSON messages (omp-node/{node_id} on the local broker)
and translates them into OMP bodies: node "energy" -> energy (source
ct_clamp), node "start"/"stop" -> core events, node "hello" -> identity.
The node never builds envelopes; everything trust-relevant happens here and
in the gateway core.

Real mode subscribes via paho-mqtt. Dev/CI modes inject messages directly
(`messages` list in config) or replay an NDJSON capture (`replay_file`).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import queue
import threading

from omp.adapter import AdapterBase, Emit, MachineInfo

KIT_CLASS = {"ct_clamp": "unclassified", "vibration": "unclassified",
             "optical_counter": "unclassified"}


class Adapter(AdapterBase):
    name = "retrofit-esp32"
    version = "0.1.0"
    supported_profiles = ["generic/0.1"]

    def probe(self, config) -> MachineInfo:
        kit = config.get("kit", "ct_clamp")
        capabilities = ["energy", "event"] if kit == "ct_clamp" else ["event"]
        return MachineInfo(
            machine_class=KIT_CLASS.get(kit, "unclassified"),
            make="OMP retrofit", model=f"esp32-{kit}", serial=config.get("node_id"),
            capabilities=capabilities, data_source="retrofit",
        )

    # ------------------------------------------------------------------
    def start(self, emit: Emit) -> None:
        self._stop = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        source_thread = self._start_source()
        self._mark_connected()
        while not self._stop.is_set():
            try:
                raw = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if raw is None:
                break
            self._handle(emit, raw)
        if source_thread:
            source_thread.join(timeout=5)

    def _start_source(self):
        if "messages" in self.config:
            for m in self.config["messages"]:
                self._queue.put(json.dumps(m) if isinstance(m, dict) else m)
            self._queue.put(None)
            return None
        if "replay_file" in self.config:
            lines = pathlib.Path(self.config["replay_file"]).read_text(
                encoding="utf-8").splitlines()
            for line in lines:
                if line.strip():
                    self._queue.put(line)
            self._queue.put(None)
            return None
        return self._start_mqtt()  # pragma: no cover - needs a broker

    def _start_mqtt(self):  # pragma: no cover - needs a broker
        import paho.mqtt.client as mqtt

        client = mqtt.Client()
        client.on_message = lambda c, u, msg: self._queue.put(
            msg.payload.decode(errors="replace"))
        host = self.config.get("broker_host", "localhost")
        client.connect(host, self.config.get("broker_port", 1883))
        client.subscribe(f"omp-node/{self.config['node_id']}", qos=1)

        def run():
            while not self._stop.is_set():
                client.loop(timeout=0.5)
            client.disconnect()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------------
    def _handle(self, emit: Emit, raw: str) -> None:
        try:
            msg = json.loads(raw)
            mtype = msg["type"]
        except (ValueError, KeyError) as exc:
            self._mark_degraded(f"bad node message: {exc}")
            return
        self._mark_data()
        if mtype == "hello":
            # identity is handled at probe/registry level; a hello after
            # startup is a liveness signal, and its offline-drop counter is
            # worth surfacing rather than losing
            if msg.get("dropped_while_offline"):
                emit(self.body(schema="event", profile="generic/0.1", body={
                    "event_type": "maintenance_flag",
                    "payload": {"flag": "node_dropped_messages",
                                "count": int(msg["dropped_while_offline"])},
                }))
            return
        if mtype == "event" and msg.get("event") in ("start", "stop"):
            emit(self.body(schema="event", profile="generic/0.1", body={
                "event_type": msg["event"],
                "payload": {"reason": "load_threshold"},
            }))
            return
        if mtype == "energy":
            end = dt.datetime.now(dt.timezone.utc)
            start = end - dt.timedelta(seconds=int(msg["interval_s"]))
            iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"  # noqa: E731
            emit(self.body(schema="energy", profile="generic/0.1", body={
                # the node reports integral watt-hours; emit them as the
                # profile-extensible metric "wh" rather than mislabeling a
                # Wh count as kwh or losing sub-kWh resolution to rounding
                "metric": "wh",
                "value": int(msg["wh"]),
                "interval": {"start_ts": iso(start), "end_ts": iso(end)},
                "source": "ct_clamp",
            }, event_ts=iso(end)))
            return
        self._mark_degraded(f"unknown node message type {mtype!r}")

    def stop(self) -> None:
        self._stop.set()
