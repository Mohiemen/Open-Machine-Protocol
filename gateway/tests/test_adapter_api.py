"""The API doc's contract: health from marks, backoff, and a doc-shaped
adapter driven end to end through the engine."""
import threading
import time

from omp.adapter import AdapterBase, Body, MachineInfo
from omp.core.engine import Engine
from omp.core.store import Store


class ReplayAdapter(AdapterBase):
    """Shaped like the doc's minimal example, machine side replaced by a
    fixture list (the replay-mode pattern from the Writing an Adapter guide)."""

    name = "test-replay"
    version = "0.1.0"
    supported_profiles = ["textile-sewing/0.1", "generic/0.1"]

    def __init__(self, lines, **kw):
        super().__init__(**kw)
        self.lines = lines

    def probe(self, config):
        return MachineInfo(machine_class="lockstitch", make=None, model=None,
                           serial=None, capabilities=["event"],
                           data_source="native")

    def start(self, emit):
        self._stop = threading.Event()
        self._mark_connected()
        cycles = 0
        for line in self.lines:
            if self._stop.is_set():
                break
            if line.startswith("CYCLE"):
                cycles += 1
                self._mark_data()
                emit(self.body(
                    schema="event",
                    profile="textile-sewing/0.1",
                    body={"event_type": "cycle_complete",
                          "payload": {"cycle_count": cycles}},
                ))
        self._stop.wait()

    def stop(self):
        self._stop.set()


def test_replay_adapter_end_to_end(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    adapter = ReplayAdapter(["CYCLE 1", "noise", "CYCLE 2", "CYCLE 3"])
    out = []

    def emit(body: Body):
        env = engine.process("m-one-01", body)
        assert env is not None
        out.append(env)

    t = threading.Thread(target=adapter.start, args=(emit,))
    t.start()
    deadline = time.time() + 5
    while len(out) < 3 and time.time() < deadline:
        time.sleep(0.01)
    adapter.stop()
    t.join(timeout=5)
    assert [e["seq"] for e in out] == [1, 2, 3]
    assert adapter.health().state == "ok"
    assert adapter.health().last_data_ts is not None


def test_health_marks_and_backoff():
    a = ReplayAdapter([])
    assert a.health().state == "disconnected"
    a._mark_connected()
    assert a.health().state == "ok"
    a._mark_degraded("checksum errors on the wire")
    h = a.health()
    assert h.state == "degraded" and h.error_count == 1
    a._mark_disconnected("no response to poll")
    assert a.health().state == "disconnected"
    d1, d2, d3 = a.backoff(), a.backoff(), a.backoff()
    assert d1 == 1.0 and d2 == 2.0 and d3 == 4.0
    a._mark_connected()
    assert a.backoff() == 1.0, "backoff resets on reconnect"
    assert a.health().reconnect_count == 1
