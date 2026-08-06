"""Gateway trust core: seq persistence, dead letters, exporter cursors."""

from omp.adapter import Body
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.base import Exporter


def event(payload=None, event_type="cycle_complete"):
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": event_type, "payload": payload or {"cycle_count": 1}})


def test_valid_body_becomes_buffered_envelope(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    env = engine.process("m-one-01", event())
    assert env is not None
    assert env["seq"] == 1
    assert env["gateway_id"] == "gw-test-01"
    assert len(env["checksum"]) == 64
    assert store.pending("x")[0][1] == env


def test_seq_persists_across_restart(tmp_path):
    db = tmp_path / "b.db"
    store = Store(db)
    engine = Engine("gw-test-01", store)
    for _ in range(3):
        engine.process("m-one-01", event())
    store.close()
    # "restart"
    store2 = Store(db)
    engine2 = Engine("gw-test-01", store2)
    env = engine2.process("m-one-01", event())
    assert env["seq"] == 4, "seq must never reset across restarts"


def test_invalid_body_dead_letters_not_buffered(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    bad = Body(schema="event", profile="generic/0.1",
               body={"event_type": "Not-Valid!"})
    assert engine.process("m-one-01", bad) is None
    assert store.pending("x") == []
    dead = store.dead_letters()
    assert len(dead) == 1 and "Not-Valid" in dead[0]["body"]["event_type"]
    # seq 1 was consumed; next valid message is seq 2 - a visible gap,
    # never a silent reuse
    env = engine.process("m-one-01", event())
    assert env["seq"] == 2


def test_profile_constraint_enforced(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    bad = Body(schema="event", profile="textile-sewing/0.1",
               body={"event_type": "dosing_complete", "payload": {}})
    assert engine.process("m-one-01", bad) is None
    assert "not in core or profile" in store.dead_letters()[0]["error"]


def test_exporter_cursor_at_least_once(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    for _ in range(5):
        engine.process("m-one-01", event())

    class Collect(Exporter):
        name = "collect"

        def __init__(self):
            self.got = []

        def publish(self, envelope):
            self.got.append(envelope["seq"])

    exp = Collect()
    assert exp.drain(store) == 5
    assert exp.got == [1, 2, 3, 4, 5]
    assert exp.drain(store) == 0, "cursor must advance"
    engine.process("m-one-01", event())
    assert exp.drain(store) == 1 and exp.got[-1] == 6


def test_closed_stdout_pipe_does_not_ack_undelivered(tmp_path):
    """`omp-gateway run | head` is ordinary usage: it must not traceback, and
    it must not advance the cursor past an envelope nobody received."""
    import pytest

    from omp.exporters.base import ExporterClosed, StdoutExporter

    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    for _ in range(3):
        engine.process("m-one-01", event())

    class ClosedPipe:
        def write(self, _):
            raise BrokenPipeError(32, "Broken pipe")

    exp = StdoutExporter(stream=ClosedPipe())
    with pytest.raises(ExporterClosed):
        exp.drain(store)
    assert store.pending(exp.name), "undelivered envelopes stay pending"


def test_two_exporters_independent_cursors(tmp_path):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    engine.process("m-one-01", event())

    class Named(Exporter):
        def __init__(self, name):
            self.name = name
            self.count = 0

        def publish(self, envelope):
            self.count += 1

    a, b = Named("a"), Named("b")
    assert a.drain(store) == 1
    assert b.drain(store) == 1, "each exporter gets its own cursor"
