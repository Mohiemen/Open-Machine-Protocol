"""generic-serial driven end to end through the gateway engine via replay."""
import threading
import time

from omp.cli import load_adapter_class
from omp.core.engine import Engine
from omp.core.store import Store

ADAPTER_DIR = "adapters/generic-serial"

LINE_PROFILE = """
profile: textile-dyeing/0.1
machine_class: jigger
patterns:
  - match: '^TEMP=(?P<c>\\d+)$'
    emit: { schema: telemetry, channel: bath_temp, unit: Cel, value: c, mode: stats }
  - match: '^PHASE (?P<name>\\w+) START$'
    emit: { schema: event, event_type: phase_start, payload: { phase: name } }
"""

CAPTURE = "TEMP=30\nPHASE heat START\nTEMP=45\nTEMP=60\nnoise line\nPHASE hold START\n"


def run_adapter(tmp_path, capture=CAPTURE, stats_window_s=0.0):
    (tmp_path / "lines.yaml").write_text(LINE_PROFILE, encoding="utf-8")
    (tmp_path / "capture.txt").write_text(capture, encoding="utf-8")
    cls = load_adapter_class(ADAPTER_DIR)
    adapter = cls(config={
        "line_profile": str(tmp_path / "lines.yaml"),
        "replay_file": str(tmp_path / "capture.txt"),
        "stats_window_s": stats_window_s,
    })
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    out = []

    def emit(body):
        env = engine.process("f1-dye-jig01", body)
        out.append((body, env))

    t = threading.Thread(target=adapter.start, args=(emit,))
    t.start()
    deadline = time.time() + 5
    while time.time() < deadline and len(out) < 4:
        time.sleep(0.01)
    adapter.stop()
    t.join(timeout=5)
    return adapter, store, out


def test_probe_declares_capabilities(tmp_path):
    (tmp_path / "lines.yaml").write_text(LINE_PROFILE, encoding="utf-8")
    cls = load_adapter_class(ADAPTER_DIR)
    info = cls().probe({"line_profile": str(tmp_path / "lines.yaml"),
                        "replay_file": "x"})
    assert info.machine_class == "jigger"
    assert info.capabilities == ["event", "telemetry"]


def test_replay_emits_valid_profile_events(tmp_path):
    adapter, store, out = run_adapter(tmp_path)
    envs = [e for _, e in out if e is not None]
    assert store.dead_letters() == [], "everything emitted must validate"
    events = [e for e in envs if e["schema"] == "event"]
    assert [e["body"]["payload"]["phase"] for e in events] == ["heat", "hold"]
    # stats_window_s=0 closes the bath_temp window on the second sample
    telem = [e for e in envs if e["schema"] == "telemetry"]
    assert telem and telem[0]["body"]["stats"]["min"] == 30
    assert adapter.health().state == "ok"


def test_unmatched_lines_are_ignored_not_fatal(tmp_path):
    adapter, store, out = run_adapter(tmp_path, capture="garbage\nnoise\n")
    assert [e for _, e in out if e is not None] == []
    assert store.dead_letters() == []
