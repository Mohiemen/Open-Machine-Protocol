"""One exporter's unexpected failure must not stop export for everyone.

The daemon drains every exporter from one background thread. Before this,
anything an exporter raised other than ExporterClosed - a full disk under the
CSV exporter, an IncompleteRead from the REST endpoint - killed that thread,
while adapters kept buffering: collection looked healthy and nothing was ever
exported again.
"""
import http.client
import urllib.error

import pytest
from omp.adapter import Body
from omp.cli import _drain_exporters, _DrainState
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.base import Exporter, ExporterClosed, ExporterPaused
from omp.exporters.rest import RestExporter


def seeded(tmp_path, n=3):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    for i in range(n):
        engine.process("m-one-01", Body(
            schema="event", profile="generic/0.1",
            body={"event_type": "cycle_complete", "payload": {"cycle_count": i}}))
    return store


class Broken(Exporter):
    name = "broken"

    def drain(self, store, batch=500):
        raise OSError(28, "No space left on device")


class Collect(Exporter):
    name = "collect"

    def __init__(self):
        self.got = []

    def publish(self, envelope):
        self.got.append(envelope["seq"])


def test_a_failing_exporter_does_not_starve_the_others(tmp_path, capsys):
    store = seeded(tmp_path)
    good = Collect()
    _drain_exporters([Broken(), good], store, _DrainState())      # must not raise
    assert good.got == [1, 2, 3]
    assert len(store.pending("broken", 10)) == 3, "failed data stays buffered"
    assert "No space left" in capsys.readouterr().err


def test_a_repeating_error_is_logged_once_not_every_pass(tmp_path, capsys):
    store = seeded(tmp_path)
    state = _DrainState()
    for _ in range(5):
        _drain_exporters([Broken()], store, state)
    assert capsys.readouterr().err.count("No space left") == 1


def test_exporter_closed_still_stops_the_gateway(tmp_path):
    class Closed(Exporter):
        name = "closed"

        def drain(self, store, batch=500):
            raise ExporterClosed("pipe closed")
    with pytest.raises(ExporterClosed):
        _drain_exporters([Closed()], seeded(tmp_path), _DrainState())


@pytest.mark.parametrize("exc", [http.client.IncompleteRead(b"x"),
                                 http.client.BadStatusLine("garbage")])
def test_rest_treats_protocol_garbage_as_transient(tmp_path, exc):
    def opener(req, timeout=None):
        raise exc
    store = seeded(tmp_path)
    exp = RestExporter("https://x/ingest", opener=opener)
    assert exp.drain(store) == 0
    assert len(store.pending("rest", 10)) == 3


def test_rest_url_errors_were_already_transient(tmp_path):
    def opener(req, timeout=None):
        raise urllib.error.URLError("refused")
    assert RestExporter("https://x/ingest", opener=opener).drain(seeded(tmp_path)) == 0


# ------------------------------------------------- pause one, not the gateway
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Rejecting(Exporter):
    """Stands in for an endpoint answering 401/404: refuses until fixed."""
    name = "rejecting"

    def __init__(self):
        self.calls = 0
        self.accept = False

    def drain(self, store, batch=500):
        self.calls += 1
        if not self.accept:
            raise ExporterPaused("endpoint rejected the batch with 401")
        return Exporter.drain(self, store, batch)

    def publish(self, envelope):
        pass


def test_a_rejected_exporter_pauses_while_the_others_keep_shipping(tmp_path, capsys):
    store, clock = seeded(tmp_path), Clock()
    state, bad, good = _DrainState(clock=clock), Rejecting(), Collect()
    _drain_exporters([bad, good], store, state)       # must not raise
    assert good.got == [1, 2, 3]
    assert len(store.pending("rejecting", 10)) == 3, "nothing acked"
    assert "paused" in capsys.readouterr().err


def test_a_paused_exporter_is_not_retried_every_tick(tmp_path):
    store, clock = seeded(tmp_path), Clock()
    state, bad = _DrainState(clock=clock), Rejecting()
    for _ in range(50):                               # 50 ticks, no time passes
        _drain_exporters([bad], store, state)
    assert bad.calls == 1


def test_backoff_doubles_and_is_capped(tmp_path):
    store, clock = seeded(tmp_path), Clock()
    state, bad = _DrainState(clock=clock), Rejecting()
    waits = []
    for _ in range(8):
        _drain_exporters([bad], store, state)
        waits.append(state.paused["rejecting"][1])
        clock.t = state.paused["rejecting"][0]       # jump to the retry time
    assert waits[:3] == [30, 60, 120]
    assert max(waits) == 600


def test_a_paused_exporter_resumes_by_itself_when_the_endpoint_recovers(tmp_path, capsys):
    store, clock = seeded(tmp_path), Clock()
    state, bad = _DrainState(clock=clock), Rejecting()
    _drain_exporters([bad], store, state)
    bad.accept = True                                 # platform deploy finished
    clock.t += 31
    _drain_exporters([bad], store, state)
    assert store.pending("rejecting", 10) == []
    assert "rejecting" not in state.paused
    assert "recovered" in capsys.readouterr().err


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 404])
def test_rest_pauses_rather_than_closing_on_a_refusal(tmp_path, status):
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, status, "no", {}, None)
    exp = RestExporter("https://x/ingest", opener=opener)
    with pytest.raises(ExporterPaused):
        exp.drain(seeded(tmp_path))
