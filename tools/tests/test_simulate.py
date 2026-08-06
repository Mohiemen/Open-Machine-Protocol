"""Simulator output must be conformant, and chaos must be caught."""
import io
import json
from contextlib import redirect_stdout

import pytest

from omp_tools.simulate import main as simulate_main
from omp_tools.specload import load_spec
from omp_tools.validate import validate_envelope

SPEC = load_spec()


def run_sim(*argv) -> list[dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert simulate_main(list(argv)) == 0
    return [json.loads(line) for line in buf.getvalue().splitlines()]


@pytest.mark.parametrize("profile", ["generic", "textile-sewing", "textile-dyeing"])
def test_simulate_is_conformant(profile):
    envs = run_sim("--profile", profile, "--machines", "3",
                   "--duration", "30m", "--seed", "7")
    assert len(envs) > 10
    schemas = {e["schema"] for e in envs}
    assert {"machine", "event", "process_run"} <= schemas
    for e in envs:
        assert validate_envelope(e, SPEC) == [], e


def test_seq_monotonic_per_machine():
    envs = run_sim("--profile", "textile-sewing", "--machines", "2",
                   "--duration", "20m", "--seed", "1")
    seen: dict[str, int] = {}
    for e in envs:
        last = seen.get(e["machine_id"], 0)
        assert e["seq"] == last + 1
        seen[e["machine_id"]] = e["seq"]


def test_run_summary_cites_event_range():
    envs = run_sim("--profile", "textile-dyeing", "--machines", "1",
                   "--duration", "1h", "--seed", "3")
    runs = [e for e in envs if e["schema"] == "process_run"]
    assert runs
    r = runs[0]["body"]["event_seq_range"]
    assert 1 <= r["first"] <= r["last"]


def test_chaos_produces_invalid_messages():
    envs = run_sim("--profile", "textile-sewing", "--machines", "5",
                   "--duration", "1h", "--seed", "42",
                   "--chaos", "corrupt-fields", "--chaos-rate", "0.2")
    bad = [e for e in envs if validate_envelope(e, SPEC)]
    assert bad, "chaos mode produced no invalid messages"
    good = [e for e in envs if not validate_envelope(e, SPEC)]
    assert good, "chaos mode corrupted everything"
