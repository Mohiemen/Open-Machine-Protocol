"""omp-gateway tail - the documented `tail | omp-validate` loop.

The property that matters most is negative: tailing must never ack. An
observer that advanced an exporter cursor would let retention prune data no
exporter ever delivered, so watching the stream would destroy it.
"""
import io
import json
from contextlib import redirect_stdout

from omp.adapter import Body
from omp.cli import main as cli_main
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.base import Exporter


def event(n):
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": "cycle_complete", "payload": {"cycle_count": n}})


def seeded(tmp_path, n=5):
    store = Store(tmp_path / "buffer.db")
    engine = Engine("gw-test-01", store)
    for i in range(n):
        engine.process("m-one-01", event(i))
    return store


def tail(tmp_path, *extra) -> list[dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["tail", "--state-dir", str(tmp_path), "--no-follow", *extra])
    assert rc == 0
    return [json.loads(x) for x in buf.getvalue().splitlines() if x.startswith("{")]


# ------------------------------------------------------------ the safety net
def test_tailing_never_acks(tmp_path):
    store = seeded(tmp_path)

    class Collect(Exporter):
        name = "real-exporter"

        def publish(self, envelope):
            pass

    assert len(tail(tmp_path)) == 5
    tail(tmp_path)                       # observe repeatedly
    tail(tmp_path, "--last", "2")
    # the exporter that has NOT run still sees everything pending
    assert len(store.pending("real-exporter")) == 5, \
        "observing the stream must not mark anything delivered"
    # and retention still refuses to prune, because nothing was delivered
    assert store.prune(["real-exporter"], retention_days=0)["pruned"] == 0


# ---------------------------------------------------------------- behaviour
def test_no_follow_dumps_what_is_buffered(tmp_path):
    """This is the documented `omp-gateway tail | omp-validate` case - it must
    print the buffer and exit, not sit at zero waiting for new arrivals."""
    seeded(tmp_path)
    envs = tail(tmp_path)
    assert [e["seq"] for e in envs] == [1, 2, 3, 4, 5]


def test_last_n(tmp_path):
    seeded(tmp_path)
    assert [e["seq"] for e in tail(tmp_path, "--last", "2")] == [4, 5]
    assert [e["seq"] for e in tail(tmp_path, "--last", "99")] == [1, 2, 3, 4, 5]


def test_machine_filter(tmp_path):
    store = Store(tmp_path / "buffer.db")
    engine = Engine("gw-test-01", store)
    engine.process("m-one-01", event(1))
    engine.process("m-two-02", event(1))
    engine.process("m-one-01", event(2))
    envs = tail(tmp_path, "--machine", "m-one-01")
    assert [e["machine_id"] for e in envs] == ["m-one-01", "m-one-01"]


def test_output_is_valid_ndjson_for_the_pipeline(tmp_path):
    """`tail | omp-validate` only works if every line is a conformant envelope."""
    from omp_tools.specload import load_spec
    from omp_tools.validate import validate_envelope

    seeded(tmp_path)
    spec = load_spec()
    for env in tail(tmp_path):
        assert validate_envelope(env, spec) == []


def test_missing_buffer_is_an_error_not_a_traceback(tmp_path, capsys):
    assert cli_main(["tail", "--state-dir", str(tmp_path / "nope"),
                     "--no-follow"]) == 1
    assert "no gateway buffer" in capsys.readouterr().err
