"""retrofit-esp32 adapter: node JSON -> valid OMP envelopes via the engine."""
import json
import threading
import time

from omp.cli import load_adapter_class
from omp.core.engine import Engine
from omp.core.store import Store

ADAPTER_DIR = "adapters/retrofit-esp32"

NODE_MESSAGES = [
    {"type": "hello", "node_id": "omp-node-3f2a", "machine_id": "f1-line1-m03",
     "kit": "ct_clamp", "fw": "0.1.0", "dropped_while_offline": 0},
    {"type": "event", "node_id": "omp-node-3f2a", "machine_id": "f1-line1-m03",
     "event": "start", "uptime_ms": 1000},
    {"type": "energy", "node_id": "omp-node-3f2a", "machine_id": "f1-line1-m03",
     "wh": 42, "interval_s": 60, "uptime_ms": 61000},
    {"type": "event", "node_id": "omp-node-3f2a", "machine_id": "f1-line1-m03",
     "event": "stop", "uptime_ms": 90000},
    {"type": "hello", "node_id": "omp-node-3f2a", "machine_id": "f1-line1-m03",
     "kit": "ct_clamp", "fw": "0.1.0", "dropped_while_offline": 3},
]


def run_adapter(tmp_path, messages, expect):
    cls = load_adapter_class(ADAPTER_DIR)
    adapter = cls(config={"node_id": "omp-node-3f2a", "kit": "ct_clamp",
                          "messages": messages})
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    out = []

    def emit(body):
        out.append(engine.process("f1-line1-m03", body))

    t = threading.Thread(target=adapter.start, args=(emit,))
    t.start()
    deadline = time.time() + 5
    while time.time() < deadline and len(out) < expect:
        time.sleep(0.01)
    adapter.stop()
    t.join(timeout=5)
    return adapter, store, out


def test_probe_declares_retrofit_source():
    cls = load_adapter_class(ADAPTER_DIR)
    info = cls().probe({"node_id": "omp-node-3f2a", "kit": "ct_clamp"})
    assert info.data_source == "retrofit"
    assert info.capabilities == ["energy", "event"]
    assert info.serial == "omp-node-3f2a"


def test_node_messages_become_valid_envelopes(tmp_path):
    adapter, store, out = run_adapter(tmp_path, NODE_MESSAGES, expect=4)
    assert store.dead_letters() == []
    assert all(e is not None for e in out)
    kinds = [(e["schema"], e["body"].get("event_type") or e["body"].get("metric"))
             for e in out]
    assert kinds == [("event", "start"), ("energy", "wh"), ("event", "stop"),
                     ("event", "maintenance_flag")]
    energy = next(e for e in out if e["schema"] == "energy")
    assert energy["body"]["value"] == 42
    assert energy["body"]["source"] == "ct_clamp"
    flag = out[-1]["body"]["payload"]
    assert flag == {"flag": "node_dropped_messages", "count": 3}


def test_malformed_node_message_degrades_not_crashes(tmp_path):
    bad = ["not json", json.dumps({"no_type": True}),
           json.dumps({"type": "mystery"})]
    adapter, store, out = run_adapter(tmp_path, bad, expect=0)
    assert out == []
    health = adapter.health()
    assert health.state == "degraded"
    assert health.error_count == 3
