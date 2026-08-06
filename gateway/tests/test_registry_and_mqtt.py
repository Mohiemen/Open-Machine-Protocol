"""Registry validation and MQTT topic construction (fake client)."""
import pytest

from omp.core.registry import RegistryError, load_registry
from omp.exporters.mqtt import MqttExporter


def write(tmp_path, text):
    p = tmp_path / "registry.yaml"
    p.write_text(text, encoding="utf-8")
    return p


GOOD = """
machines:
  - machine_id: f1-line2-overlock04
    adapter: generic-modbus
    config: { port: /dev/ttyUSB0, baud: 9600, unit_id: 1 }
    location: { site: f1, area: sewing, line: line2, station: st04 }
"""


def test_good_registry(tmp_path):
    reg = load_registry(write(tmp_path, GOOD))
    assert reg["machines"][0]["machine_id"] == "f1-line2-overlock04"


@pytest.mark.parametrize("bad,msg", [
    ("machines:\n  - adapter: x\n", "missing machine_id"),
    ("machines:\n  - machine_id: BAD_ID\n    adapter: x\n", "must match"),
    ("machines:\n  - machine_id: m-ok-01\n    adapter: x\n"
     "  - machine_id: m-ok-01\n    adapter: y\n", "duplicate"),
    ("machines:\n  - machine_id: m-ok-01\n    adapter: x\n"
     "    location: { area: sewing }\n", "site"),
])
def test_bad_registries(tmp_path, bad, msg):
    with pytest.raises(RegistryError, match=msg):
        load_registry(write(tmp_path, bad))


class FakeClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, qos))


def test_mqtt_topic_convention():
    exp = MqttExporter("unused", locations={
        "f1-line2-overlock04": {"site": "f1", "area": "sewing",
                                "line": "line2", "station": "st04"}},
        client=FakeClient())
    exp.publish({"machine_id": "f1-line2-overlock04", "schema": "event"})
    topic, qos = exp.client.published[0]
    assert topic == "omp/f1/sewing/line2/f1-line2-overlock04/event"
    assert qos == 1
