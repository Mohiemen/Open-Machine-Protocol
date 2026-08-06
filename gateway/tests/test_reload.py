"""Registry hot-reload: add machines without dropping the floor.

Driven as a subprocess because reload is SIGHUP-based and signals only land
in the main thread. Durations are short; each test is a few seconds.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
LINES = """
profile: generic/0.1
machine_class: unclassified
patterns:
  - match: '^TICK (?P<n>\\d+)$'
    emit: { schema: event, event_type: cycle_complete, payload: { cycle_count: n } }
"""
MACHINE = """  - machine_id: {mid}
    adapter: generic-serial
    profile: generic/0.1
    config: {{ line_profile: {lp}, replay_file: {cap}, stats_window_s: 0.0 }}
    location: {{ site: f1 }}
"""


@pytest.fixture
def floor(tmp_path):
    (tmp_path / "lines.yaml").write_text(LINES, encoding="utf-8")
    (tmp_path / "cap.txt").write_text("TICK 1\nTICK 2\n", encoding="utf-8")
    reg = tmp_path / "registry.yaml"

    def write_registry(*machine_ids):
        body = "machines:\n" + "".join(
            MACHINE.format(mid=m, lp=tmp_path / "lines.yaml",
                           cap=tmp_path / "cap.txt") for m in machine_ids)
        reg.write_text(body, encoding="utf-8")

    write_registry("m-one-01")
    out = open(tmp_path / "out.ndjson", "w")
    err = open(tmp_path / "err.txt", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "omp.cli", "run", "--registry", str(reg),
         "--state-dir", str(tmp_path / "state"), "--adapters-dir",
         str(REPO / "adapters"), "--gateway-id", "gw-rl-01",
         "--duration", "20", "--prune-interval", "0.5"],
        stdout=out, stderr=err, cwd=REPO)
    pidfile = tmp_path / "state" / "gateway.pid"
    deadline = time.time() + 15
    while time.time() < deadline and not pidfile.exists():
        time.sleep(0.1)
    assert pidfile.exists(), "gateway never wrote its pidfile"
    yield tmp_path, proc, write_registry, pidfile
    proc.terminate()
    proc.wait(timeout=10)
    out.close()
    err.close()


def wait_for(path: Path, needle: str, timeout: float = 15) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = path.read_text(encoding="utf-8")
        if needle in text:
            return text
        time.sleep(0.1)
    pytest.fail(f"{needle!r} never appeared in {path}:\n{path.read_text()}")


def envelopes(tmp_path) -> dict[str, list[int]]:
    seqs: dict[str, list[int]] = {}
    for line in (tmp_path / "out.ndjson").read_text(encoding="utf-8").splitlines():
        if line.startswith("{"):
            e = json.loads(line)
            seqs.setdefault(e["machine_id"], []).append(e["seq"])
    return seqs


def test_reload_adds_a_machine_without_disturbing_the_others(floor):
    tmp_path, proc, write_registry, pidfile = floor
    wait_for(tmp_path / "out.ndjson", "m-one-01")
    write_registry("m-one-01", "m-two-02")          # first entry byte-identical
    os.kill(int(pidfile.read_text()), signal.SIGHUP)
    wait_for(tmp_path / "err.txt", "# reloaded")

    text = wait_for(tmp_path / "out.ndjson", "m-two-02")
    assert "+1 -0 ~0" in (tmp_path / "err.txt").read_text()
    assert "1 untouched" in (tmp_path / "err.txt").read_text()
    seqs = envelopes(tmp_path)
    assert set(seqs) == {"m-one-01", "m-two-02"}
    for mid, s in seqs.items():
        assert s == list(range(1, len(s) + 1)), f"{mid} seq must stay continuous"
    assert text


def test_invalid_registry_is_refused_and_the_floor_keeps_running(floor):
    tmp_path, proc, write_registry, pidfile = floor
    wait_for(tmp_path / "out.ndjson", "m-one-01")
    before = envelopes(tmp_path)

    (tmp_path / "registry.yaml").write_text(
        "machines:\n  - machine_id: BAD_ID\n    adapter: generic-serial\n",
        encoding="utf-8")
    os.kill(int(pidfile.read_text()), signal.SIGHUP)
    err = wait_for(tmp_path / "err.txt", "reload REFUSED")

    assert "must match" in err, "the operator is told exactly what was wrong"
    assert "# reloaded" not in err, "nothing may be applied from a bad registry"
    assert proc.poll() is None, "a bad registry must not take the gateway down"
    assert set(envelopes(tmp_path)) == set(before), "machines keep running"


def test_reload_cli_without_a_running_gateway(tmp_path):
    from omp.cli import main as cli_main

    assert cli_main(["reload", "--state-dir", str(tmp_path)]) == 1
