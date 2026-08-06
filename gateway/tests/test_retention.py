"""Retention pruning must never outrun delivery.

These envelopes are compliance evidence. A pruning bug here destroys audit
records silently, so the tests lead with the safety property, not the feature.
"""
from omp.adapter import Body
from omp.core.engine import Engine
from omp.core.store import Store, _iso_minus_days, _now_iso
from omp.exporters.base import Exporter


def event(n=1):
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": "cycle_complete", "payload": {"cycle_count": n}})


class Collect(Exporter):
    def __init__(self, name):
        self.name = name
        self.got = []

    def publish(self, envelope):
        self.got.append(envelope["seq"])


def fill(tmp_path, n=5, age_days=60):
    """n envelopes, all stored `age_days` ago so they're retention-eligible."""
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    old = _iso_minus_days(_now_iso(), age_days)
    for i in range(n):
        env = engine.process("m-one-01", event(i))
        store._conn.execute("UPDATE buffer SET stored_at=? WHERE seq=?",
                            (old, env["seq"]))
    store._conn.commit()
    return store


# ------------------------------------------------------- the safety property
def test_never_prunes_past_a_lagging_exporter(tmp_path):
    store = fill(tmp_path)
    Collect("fast").drain(store)           # fast has everything
    # "slow" is a configured exporter that has received nothing at all
    result = store.prune(["fast", "slow"], retention_days=30)
    assert result["pruned"] == 0
    assert "delivered nothing" in result["reason"]
    assert len(store.pending("slow")) == 5, "undelivered evidence must survive"


def test_prunes_only_up_to_the_slowest_cursor(tmp_path):
    store = fill(tmp_path)
    fast, slow = Collect("fast"), Collect("slow")
    fast.drain(store)
    # slow receives just the first two
    for rowid, env in store.pending("slow", limit=2):
        slow.publish(env)
        store.ack("slow", rowid)

    result = store.prune(["fast", "slow"], retention_days=30)
    assert result["pruned"] == 2, "only what BOTH exporters received"
    assert [seq for _, seq in
            [(r, e["seq"]) for r, e in store.pending("slow")]] == [3, 4, 5]


def test_removed_exporter_does_not_pin_the_buffer_forever(tmp_path):
    store = fill(tmp_path)
    live = Collect("live")
    live.drain(store)
    store.ack("gone", 0)                   # stale cursor from a removed exporter
    # pruning is asked about the CURRENT set only
    assert store.prune(["live"], retention_days=30)["pruned"] == 5
    assert store.pending("live") == []


def test_recent_envelopes_are_kept(tmp_path):
    store = fill(tmp_path, age_days=0)     # stored just now
    Collect("only").drain(store)
    assert store.prune(["only"], retention_days=30)["pruned"] == 0
    assert len(store.pending("fresh-consumer")) == 5


def test_no_exporters_configured_prunes_nothing(tmp_path):
    store = fill(tmp_path)
    assert store.prune([], retention_days=30)["pruned"] == 0


# ------------------------------------------------------------ disk threshold
def test_disk_threshold_prunes_delivered_data_early(tmp_path):
    store = fill(tmp_path, age_days=0)     # too new for the time rule
    Collect("only").drain(store)
    result = store.prune(["only"], retention_days=30, max_bytes=1)
    assert result["pruned"] == 5
    assert "disk over" in result["reason"]


def test_disk_threshold_still_respects_the_cursor(tmp_path):
    store = fill(tmp_path, age_days=0)
    # nobody has delivered anything; a full disk must not justify data loss
    result = store.prune(["nobody"], retention_days=30, max_bytes=1)
    assert result["pruned"] == 0
    assert len(store.pending("nobody")) == 5


# ------------------------------------------------------------- visibility
def test_pruning_is_recorded_and_visible(tmp_path):
    store = fill(tmp_path)
    Collect("only").drain(store)
    store.prune(["only"], retention_days=30)
    history = store.prune_history()
    assert history and history[0]["rows"] == 5
    assert "older than" in history[0]["reason"]
    snap = store.snapshot()
    assert snap["recent_prunes"], "status must show that deletion happened"
    assert snap["db_bytes"] > 0
