"""REST exporter: batched NDJSON, ack only after a durable-write 200.

Platform Ingestion s1 defines the contract in one sentence - "you return 200
only after durable write" - so the tests are mostly about what happens when
that 200 does NOT arrive. Data that was not accepted must stay in the buffer.
"""
import gzip
import io
import json
import urllib.error

import pytest
from omp.adapter import Body
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.base import ExporterClosed
from omp.exporters.rest import RestConfigError, RestExporter


def event(n):
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": "cycle_complete", "payload": {"cycle_count": n}})


def seeded(tmp_path, n=5):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    for i in range(n):
        engine.process("m-one-01", event(i))
    return store


class FakeEndpoint:
    """Records batches; `status` and `raise_exc` drive the failure paths."""

    def __init__(self, status=200, raise_exc=None):
        self.status = status
        self.raise_exc = raise_exc
        self.batches: list[list[dict]] = []
        self.headers: list[dict] = []

    def __call__(self, req, timeout=None):
        if self.raise_exc:
            raise self.raise_exc
        body = req.data
        if req.headers.get("Content-encoding") == "gzip":
            body = gzip.decompress(body)
        self.batches.append([json.loads(x) for x in
                             body.decode().splitlines() if x])
        self.headers.append(dict(req.headers))
        if not 200 <= self.status < 300:
            raise urllib.error.HTTPError(req.full_url, self.status, "nope", {}, None)

        class Resp:
            status = self.status

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def getcode(self_inner):
                return self.status
        return Resp()


# ---------------------------------------------------------- security first
def test_refuses_plain_http_to_a_remote_host():
    """Hardening Guide s5 [Required]: no factory data in the clear."""
    with pytest.raises(RestConfigError, match="non-loopback"):
        RestExporter("http://platform.example.com/ingest")


def test_plain_http_to_loopback_needs_an_explicit_flag():
    with pytest.raises(RestConfigError, match="allow_plaintext_local"):
        RestExporter("http://127.0.0.1:8080/ingest")
    RestExporter("http://127.0.0.1:8080/ingest", allow_plaintext_local=True)
    RestExporter("http://localhost:8080/ingest", allow_plaintext_local=True)


def test_https_is_always_fine():
    RestExporter("https://platform.example.com/ingest")


def test_unsupported_scheme_is_refused():
    with pytest.raises(RestConfigError, match="scheme"):
        RestExporter("ftp://platform.example.com/ingest")


def test_secrets_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("OMP_TOKEN", "s3cret")
    e = RestExporter("https://x/ingest", headers={"Authorization": "env:OMP_TOKEN"})
    assert e.headers["Authorization"] == "s3cret"
    with pytest.raises(RestConfigError, match="not set"):
        RestExporter("https://x/ingest", headers={"Authorization": "env:NOPE"})


# ---------------------------------------------------------- delivery rules
def test_batches_ndjson_and_acks_on_200(tmp_path):
    store = seeded(tmp_path)
    ep = FakeEndpoint()
    exp = RestExporter("https://x/ingest", batch_size=3, opener=ep)
    assert exp.drain(store) == 5
    assert [len(b) for b in ep.batches] == [3, 2], "batched, not one-by-one"
    assert ep.batches[0][0]["schema"] == "event"
    assert ep.headers[0]["Content-type"] == "application/x-ndjson"
    assert store.pending("rest") == [], "all acked after 2xx"


def test_nothing_is_acked_when_the_endpoint_is_unreachable(tmp_path):
    store = seeded(tmp_path)
    ep = FakeEndpoint(raise_exc=urllib.error.URLError("connection refused"))
    exp = RestExporter("https://x/ingest", opener=ep)
    assert exp.drain(store) == 0
    assert len(store.pending("rest")) == 5, "undelivered data stays buffered"


def test_a_5xx_is_transient_and_retried_next_drain(tmp_path):
    store = seeded(tmp_path)
    ep = FakeEndpoint(status=503)
    exp = RestExporter("https://x/ingest", opener=ep)
    assert exp.drain(store) == 0
    assert len(store.pending("rest")) == 5
    ep.status = 200                       # platform recovers
    assert exp.drain(store) == 5
    assert store.pending("rest") == []


def test_a_timeout_leaves_the_batch_for_retry(tmp_path):
    store = seeded(tmp_path)
    exp = RestExporter("https://x/ingest",
                       opener=FakeEndpoint(raise_exc=TimeoutError()))
    assert exp.drain(store) == 0
    assert len(store.pending("rest")) == 5


def test_a_4xx_stops_rather_than_wedging_the_buffer(tmp_path):
    """401/400 means this batch will never be accepted. Retrying forever
    would block every later envelope behind it, so stop loudly - but still
    without acking, because it was not delivered."""
    store = seeded(tmp_path)
    exp = RestExporter("https://x/ingest", opener=FakeEndpoint(status=401))
    with pytest.raises(ExporterClosed, match="401"):
        exp.drain(store)
    assert len(store.pending("rest")) == 5


def test_429_and_408_are_treated_as_transient(tmp_path):
    for code in (429, 408):
        store = seeded(tmp_path / str(code))
        exp = RestExporter("https://x/ingest", opener=FakeEndpoint(status=code))
        assert exp.drain(store) == 0, f"{code} must not raise"
        assert len(store.pending("rest")) == 5


def test_partial_progress_survives_a_mid_drain_failure(tmp_path):
    """First batch accepted, second refused: the first stays acked, the rest
    stays pending. No envelope is lost and none is acked undelivered."""
    store = seeded(tmp_path, n=6)
    ep = FakeEndpoint()
    exp = RestExporter("https://x/ingest", batch_size=3, opener=ep)

    calls = {"n": 0}
    real = ep.__call__

    def flaky(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise urllib.error.URLError("dropped")
        return real(req, timeout)

    exp._opener = flaky
    assert exp.drain(store) == 3
    assert len(store.pending("rest")) == 3
    exp._opener = real
    assert exp.drain(store) == 3
    assert store.pending("rest") == []


def test_gzip_can_be_disabled(tmp_path):
    store = seeded(tmp_path, n=1)
    ep = FakeEndpoint()
    RestExporter("https://x/ingest", opener=ep, gzip_body=False).drain(store)
    assert "Content-encoding" not in ep.headers[0]


def test_registry_wiring_rejects_insecure_config(tmp_path):
    from omp.cli import _build_exporters

    with pytest.raises(SystemExit, match="non-loopback"):
        _build_exporters({"exporters": [
            {"type": "rest", "url": "http://platform.example.com/x"}]})
    built = _build_exporters({"exporters": [
        {"type": "rest", "url": "https://platform.example.com/x",
         "batch_size": 7}]})
    assert built[0].batch_size == 7


def test_output_is_exactly_ndjson(tmp_path):
    """The consumer parses line-delimited JSON; a pretty-printed body breaks it."""
    store = seeded(tmp_path, n=2)
    ep = FakeEndpoint()
    RestExporter("https://x/ingest", opener=ep, gzip_body=False).drain(store)
    raw = io.BytesIO()
    raw.write(b"")
    # reconstruct what was posted
    assert len(ep.batches[0]) == 2
    for env in ep.batches[0]:
        assert set(env) >= {"omp_version", "gateway_id", "seq", "checksum"}
