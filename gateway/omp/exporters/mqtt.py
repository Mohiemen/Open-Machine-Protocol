"""MQTT exporter - topic convention omp/{site}/{area}/{line}/{machine}/{schema}."""
from __future__ import annotations

import json

from .base import Exporter


class MqttExporter(Exporter):
    name = "mqtt"

    def __init__(self, broker_host: str, broker_port: int = 1883,
                 topic_prefix: str = "omp", locations: dict | None = None,
                 client=None):
        """locations maps machine_id -> {site, area, line, station} from the
        registry. `client` injectable for tests; otherwise paho is required."""
        self.topic_prefix = topic_prefix
        self.locations = locations or {}
        if client is None:  # pragma: no cover - needs a broker
            import paho.mqtt.client as mqtt

            client = mqtt.Client()
            client.connect(broker_host, broker_port)
            client.loop_start()
        self.client = client

    def topic(self, envelope: dict) -> str:
        loc = self.locations.get(envelope["machine_id"], {})
        return "/".join(
            [
                self.topic_prefix,
                loc.get("site", "unknown"),
                loc.get("area", "unknown"),
                loc.get("line", "unknown"),
                envelope["machine_id"],
                envelope["schema"],
            ]
        )

    def publish(self, envelope: dict) -> None:
        info = self.client.publish(
            self.topic(envelope), json.dumps(envelope, ensure_ascii=False), qos=1
        )
        # paho returns an MQTTMessageInfo; wait for the broker handshake so
        # ack-after-publish is honest.
        if hasattr(info, "wait_for_publish"):
            info.wait_for_publish()
