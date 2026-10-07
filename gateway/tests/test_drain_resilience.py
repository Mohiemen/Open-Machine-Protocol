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
from omp.cli import _drain_exporters
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.base import Exporter, ExporterClosed
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
    _drain_exporters([Broken(), good], store, {})      # must not raise
    assert good.got == [1, 2, 3]
    assert len(store.pending("broken", 10)) == 3, "failed data stays buffered"
    assert "No space left" in capsys.readouterr().err


def test_a_repeating_error_is_logged_once_not_every_pass(tmp_path, capsys):
    store = seeded(tmp_path)
    last: dict = {}
    for _ in range(5):
        _drain_exporters([Broken()], store, last)
    assert capsys.readouterr().err.count("No space left") == 1


def test_exporter_closed_still_stops_the_gateway(tmp_path):
    class Closed(Exporter):
        name = "closed"

        def drain(self, store, batch=500):
            raise ExporterClosed("pipe closed")
    with pytest.raises(ExporterClosed):
        _drain_exporters([Closed()], seeded(tmp_path), {})


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
