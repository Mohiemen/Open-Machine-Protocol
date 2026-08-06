"""Shared transport pool: two machines, one RS485 pair, no interleaving.

The failure this prevents is subtle and nasty on real hardware - unit 1's
reply arriving in unit 2's read - so the central test drives two adapters
against a bus that *detects* interleaving rather than merely counting calls.
"""
import threading
import time

from omp.adapter import AdapterBase, MachineInfo
from omp.core.transports import SharedTransport, TransportPool


class InterleaveDetectingBus:
    """A fake multi-drop bus. If a second transaction starts before the
    first finishes, that is exactly the bug, so record it."""

    def __init__(self):
        self.in_flight = 0
        self.violations = 0
        self.transactions = 0
        self._guard = threading.Lock()

    def txn(self, request: bytes) -> bytes:
        with self._guard:
            self.in_flight += 1
            if self.in_flight > 1:
                self.violations += 1
        time.sleep(0.002)                      # the wire takes time
        with self._guard:
            self.in_flight -= 1
            self.transactions += 1
        return b"reply:" + request


# ---------------------------------------------------------------- unit level
def test_pool_returns_one_transport_per_key():
    pool = TransportPool()
    opens = []
    factory = lambda: opens.append(1) or object()  # noqa: E731
    a = pool.get("serial:///dev/ttyUSB0", factory)
    b = pool.get("serial:///dev/ttyUSB0", factory)
    c = pool.get("serial:///dev/ttyUSB1", factory)
    assert a is b, "same physical link must be the same transport"
    assert c is not a
    a.exchange(lambda link: None)
    b.exchange(lambda link: None)
    assert len(opens) == 1, "the shared link is opened once, lazily"
    assert a.users == 2


def test_link_closes_only_when_the_last_user_releases():
    pool = TransportPool()

    class Link:
        closed = False

        def close(self):
            Link.closed = True

    t = pool.get("k", Link)
    pool.get("k", Link)
    t.exchange(lambda link: None)
    pool.release("k")
    assert not Link.closed, "one machine leaving must not close its neighbour's bus"
    assert pool.keys == ["k"]
    pool.release("k")
    assert Link.closed and pool.keys == []


def test_reset_reopens_on_next_exchange():
    pool = TransportPool()
    opens = []
    t = pool.get("k", lambda: opens.append(1) or object())
    t.exchange(lambda link: None)
    t.reset()
    t.exchange(lambda link: None)
    assert len(opens) == 2, "a link-level failure reopens rather than wedging"


# ------------------------------------------------------------ the real point
class BusAdapter(AdapterBase):
    """Minimal adapter that hammers a shared bus, like two Modbus units."""

    name = "test-bus"
    version = "0.1.0"

    def probe(self, config):
        return MachineInfo(machine_class="unclassified", make=None, model=None,
                           serial=None, capabilities=["event"], data_source="native")

    def start(self, emit):
        self._stop = threading.Event()
        bus = self.config["bus"]
        link = self.transport(self.config["port"], lambda: bus)
        for i in range(15):
            if self._stop.is_set():
                break
            # the whole round trip inside one exchange - this is the contract
            link.exchange(lambda b, i=i: b.txn(f"{self.config['unit']}:{i}".encode()))
        self._stop.wait()

    def stop(self):
        self._stop.set()


def test_two_machines_on_one_bus_never_interleave():
    pool = TransportPool()
    bus = InterleaveDetectingBus()
    adapters = [
        BusAdapter(config={"bus": bus, "port": "/dev/ttyUSB0", "unit": u},
                   transport_pool=pool)
        for u in (1, 2)
    ]
    threads = [threading.Thread(target=a.start, args=(lambda body: None,))
               for a in adapters]
    for t in threads:
        t.start()
    deadline = time.time() + 10
    while time.time() < deadline and bus.transactions < 30:
        time.sleep(0.01)
    for a in adapters:
        a.stop()
    for t in threads:
        t.join(timeout=5)

    assert bus.transactions == 30, "both machines completed their polls"
    assert bus.violations == 0, (
        f"{bus.violations} interleaved transactions - unit 1 and unit 2 would "
        "be reading each other's replies on a real RS485 pair")
    assert pool.get("/dev/ttyUSB0", lambda: bus).users == 3


def test_adapter_releases_its_transports():
    pool = TransportPool()
    bus = InterleaveDetectingBus()
    a = BusAdapter(config={"bus": bus, "port": "/dev/ttyUSB0", "unit": 1},
                   transport_pool=pool)
    a.transport("/dev/ttyUSB0", lambda: bus)
    assert pool.keys == ["/dev/ttyUSB0"]
    a.release_transports()
    assert pool.keys == [], "releasing the last user frees the link"


def test_default_pool_exists_so_adapters_work_unwired():
    """run-once and adapter tests construct adapters with no pool."""
    a = BusAdapter(config={})
    assert isinstance(a.transport("k", object), SharedTransport)
    a.release_transports()
