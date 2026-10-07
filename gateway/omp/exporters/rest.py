"""REST exporter - POST batched NDJSON to a platform endpoint.

Platform Ingestion s1: "Gateway POSTs batched NDJSON to your endpoint; you
return 200 only after durable write."

That sentence is the whole contract, and it cuts both ways: the consumer
promises not to 200 until the data is safe, and this exporter promises not to
ack until it sees that 200. A batch that fails for any reason - non-2xx,
timeout, connection reset - stays unacked in the buffer and is re-sent on the
next drain. Consumers deduplicate on (gateway_id, machine_id, seq), so a
re-send after an ambiguous failure is safe and expected.

Transport security is not optional here. Hardening Guide s5 marks it
**[Required]** and says this exporter "refuses plain HTTP to non-loopback by
default - do not override that flag in production", so plain HTTP to anything
but loopback raises at construction rather than quietly shipping factory data
in the clear.

stdlib only (urllib) - a gateway on a Pi should not need a HTTP library.
"""
from __future__ import annotations

import gzip
import http.client
import ipaddress
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from ..core.store import Store
from .base import Exporter, ExporterPaused


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect.

    urllib turns a redirected POST into a body-less GET, and a login page or
    captive portal at the other end answers that 200 - which would be acked as
    a delivered batch. A redirect can also hop from https to plain http and
    undo the transport refusal above. A moved endpoint is a configuration
    problem to surface, not something to chase.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RestConfigError(ValueError):
    """Refused at construction - a misconfiguration, not a runtime failure."""


def _is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def resolve_secret(value: str) -> str:
    """`env:VAR` indirection, the same convention adapter configs use, so
    tokens live in the environment rather than in a registry file in git."""
    if isinstance(value, str) and value.startswith("env:"):
        var = value[4:]
        try:
            return os.environ[var]
        except KeyError:
            raise RestConfigError(
                f"header references {value!r} but ${var} is not set") from None
    return value


class RestExporter(Exporter):
    name = "rest"

    def __init__(self, url: str, *, batch_size: int = 100, timeout_s: float = 30,
                 headers: dict | None = None, allow_plaintext_local: bool = False,
                 gzip_body: bool = True, opener=None):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise RestConfigError(f"unsupported scheme {parsed.scheme!r} in {url!r}")
        if parsed.scheme == "http":
            if not _is_loopback(parsed.hostname or ""):
                raise RestConfigError(
                    f"refusing plain HTTP to non-loopback host "
                    f"{parsed.hostname!r}: factory data would cross the network "
                    "in the clear. Use https://, or if this really is a local "
                    "sidecar, point it at 127.0.0.1 "
                    "(Hardening Guide s5, [Required])")
            if not allow_plaintext_local:
                raise RestConfigError(
                    "plain HTTP to loopback needs an explicit "
                    "allow_plaintext_local: true, so the choice is visible in "
                    "review (Hardening Guide s5)")
        self.url = url
        self.batch_size = batch_size
        self.timeout_s = timeout_s
        self.gzip_body = gzip_body
        self.headers = {k: resolve_secret(v) for k, v in (headers or {}).items()}
        self._opener = opener or urllib.request.build_opener(_NoRedirect).open

    # ------------------------------------------------------------------
    def post_batch(self, envelopes: list[dict]) -> None:
        """POST one NDJSON batch. Returns on 2xx; raises otherwise."""
        body = "".join(json.dumps(e, ensure_ascii=False) + "\n"
                       for e in envelopes).encode("utf-8")
        headers = {"Content-Type": "application/x-ndjson", **self.headers}
        if self.gzip_body:
            body = gzip.compress(body)
            headers["Content-Encoding"] = "gzip"
        req = urllib.request.Request(self.url, data=body, headers=headers,
                                     method="POST")
        with self._opener(req, timeout=self.timeout_s) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            if not 200 <= status < 300:
                raise urllib.error.HTTPError(
                    self.url, status, "non-2xx", resp.headers, None)

    def publish(self, envelope: dict) -> None:
        """Single-envelope path, for callers that don't batch."""
        self.post_batch([envelope])

    # ------------------------------------------------------------------
    def drain(self, store: Store, batch: int = 500) -> int:
        """Batched drain: ack a batch only once the endpoint has 2xx'd it.

        Overrides the per-envelope base implementation because acking each
        envelope separately would mean a batch that half-succeeded gets
        re-sent from the wrong place. The unit of delivery here is the batch.
        """
        sent = 0
        while True:
            rows = store.pending(self.name, min(batch, self.batch_size))
            if not rows:
                return sent
            envelopes = [e for _, e in rows]
            try:
                self.post_batch(envelopes)
            except urllib.error.HTTPError as exc:
                if 300 <= exc.code < 400:
                    raise ExporterPaused(
                        f"endpoint answered {exc.code} (redirect); not "
                        "following it - the batch was NOT delivered. Point "
                        "the exporter at the final URL") from exc
                if 400 <= exc.code < 500 and exc.code not in (408, 429):
                    # The endpoint says this batch is malformed or unauthorized.
                    # Hammering it every drain would not help, and stopping
                    # the gateway would halt collection on every machine for
                    # one destination's problem (a token rotation, a deploy).
                    # Pause this exporter with backoff - still without
                    # acking, because it was NOT delivered.
                    raise ExporterPaused(
                        f"endpoint rejected the batch with {exc.code} "
                        "(check credentials or payload contract)"
                    ) from exc
                return sent          # transient: try again next drain
            except (urllib.error.URLError, TimeoutError, OSError,
                    http.client.HTTPException):
                # unreachable, or a garbled/truncated response: not delivered
                # as far as we can tell, so the buffer keeps the data
                return sent
            for rowid, _ in rows:
                store.ack(self.name, rowid)
            sent += len(rows)
