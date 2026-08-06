"""The reference consumer must pass the consumer conformance suites.

These suites are the executable form of spec/conformance/consumer/cases.md.
Any consumer in any language can self-check against the same data — this test
holds *our* reference implementation to it, since it's what platform builders
are told to copy.
"""
import importlib.util
import json

import pytest
from omp_tools.specload import load_spec

SPEC = load_spec()
SUITES = sorted(p for p in (SPEC.spec_dir / "conformance" / "consumer").iterdir()
                if p.is_dir())
INGEST = SPEC.spec_dir.parent.parent / "examples" / "platform-ingest-reference" / "ingest.py"


def load_consumer_module():
    spec = importlib.util.spec_from_file_location("omp_ingest_reference", INGEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_suites_exist():
    assert len(SUITES) >= 8, [p.name for p in SUITES]


@pytest.mark.parametrize("suite", SUITES, ids=lambda p: p.name)
def test_reference_consumer_passes_suite(suite, tmp_path):
    expected = json.loads((suite / "expected.json").read_text(encoding="utf-8"))
    want = expected["expect"]
    mod = load_consumer_module()
    consumer = mod.Consumer(str(tmp_path / "db.sqlite"))
    for line in (suite / "input.ndjson").read_text(encoding="utf-8").splitlines():
        consumer.ingest_line(line)

    for field in ("stored", "duplicates", "alarms", "quarantined",
                  "unknown_event_types"):
        if field in want:
            assert consumer.stats[field] == want[field], (
                f"{suite.name}: {field} was {consumer.stats[field]}, "
                f"expected {want[field]} — {expected['description']}")
    if "gaps" in want:
        assert consumer.gaps() == want["gaps"], expected["description"]


def test_integrity_alarm_stores_both_versions(tmp_path):
    """The alarm case deserves its own assertion: neither version may be lost."""
    suite = SPEC.spec_dir / "conformance" / "consumer" / "integrity-alarm"
    mod = load_consumer_module()
    consumer = mod.Consumer(str(tmp_path / "db.sqlite"))
    for line in (suite / "input.ndjson").read_text(encoding="utf-8").splitlines():
        consumer.ingest_line(line)
    rows = consumer.db.execute(
        "SELECT first_envelope, second_envelope FROM integrity_alarms").fetchall()
    assert len(rows) == 1
    first, second = (json.loads(r) for r in rows[0])
    assert first["checksum"] != second["checksum"]
    assert first["seq"] == second["seq"], "same dedup key is what makes it an alarm"


def test_machine_change_opens_a_new_validity_period(tmp_path):
    suite = SPEC.spec_dir / "conformance" / "consumer" / "machine-record-change"
    mod = load_consumer_module()
    consumer = mod.Consumer(str(tmp_path / "db.sqlite"))
    for line in (suite / "input.ndjson").read_text(encoding="utf-8").splitlines():
        consumer.ingest_line(line)
    rows = consumer.db.execute(
        "SELECT valid_from_seq, body FROM machines ORDER BY valid_from_seq").fetchall()
    assert len(rows) == 2, "history must not be overwritten"
    stations = [json.loads(b)["location"]["station"] for _, b in rows]
    assert stations[0] != stations[1]
