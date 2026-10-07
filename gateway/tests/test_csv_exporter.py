"""CSV exporter: ack only after fsync, rotate by day and size, round-trip.

The files are the evidence in an air-gapped site, so the tests are about what
survives: a failed write must not move the cursor, a torn row from a crash
must not poison the file, and a rotated set must read back into envelopes that
still validate.
"""
import json

import pytest
from omp.adapter import Body
from omp.core.engine import Engine
from omp.core.store import Store
from omp.exporters.csv import COLUMNS, CsvConfigError, CsvExporter, read_envelopes


def event(n):
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": "cycle_complete",
                      "payload": {"cycle_count": n, "note": 'a,"quoted"\nline'}})


def seeded(tmp_path, n=5):
    store = Store(tmp_path / "b.db")
    engine = Engine("gw-test-01", store)
    for i in range(n):
        engine.process("m-one-01", event(i))
    return store


def files(d):
    return sorted(d.glob("omp-*.csv"))


def test_round_trip_is_exact_and_checksums_verify(tmp_path):
    store = seeded(tmp_path)
    original = [e for _, e in store.pending("csv", 100)]
    out = tmp_path / "out"
    assert CsvExporter(out).drain(store) == 5
    back = list(read_envelopes(files(out)))
    assert back == original
    # validates through the real tool path, not just equality
    from omp_tools.validate import load_spec, validate_envelope
    spec = load_spec(None)
    assert all(validate_envelope(e, spec) == [] for e in back)


def test_unknown_top_level_keys_survive_in_extra(tmp_path):
    store = seeded(tmp_path, 1)
    env = store.pending("csv", 1)[0][1]
    env["x-vendor"] = {"k": 1}
    exp = CsvExporter(tmp_path / "out")
    exp.publish(env)
    assert next(read_envelopes(files(tmp_path / "out")))["x-vendor"] == {"k": 1}


def test_cursor_moves_only_after_the_batch_is_written(tmp_path, monkeypatch):
    store = seeded(tmp_path)
    exp = CsvExporter(tmp_path / "out")

    def boom():
        raise OSError("disk full")
    monkeypatch.setattr(exp, "_sync", boom)
    with pytest.raises(OSError):
        exp.drain(store)
    assert len(store.pending("csv", 100)) == 5      # nothing acked
    monkeypatch.undo()
    assert CsvExporter(tmp_path / "out").drain(store) == 5   # retry delivers


def test_rotates_by_size_and_names_sort_chronologically(tmp_path):
    store = seeded(tmp_path, 40)
    out = tmp_path / "out"
    CsvExporter(out, max_bytes=1024).drain(store)
    fs = files(out)
    assert len(fs) > 1
    assert [f.name for f in fs] == sorted(f.name for f in fs)
    seqs = [e["seq"] for e in read_envelopes(fs)]
    assert seqs == list(range(1, 41))                # nothing lost or reordered
    assert all(f.read_text().startswith(",".join(COLUMNS)) for f in fs)


def test_rotates_on_a_new_day(tmp_path):
    store = seeded(tmp_path, 2)
    a, b = (e for _, e in store.pending("csv", 2))
    a["ts"], b["ts"] = "2026-10-07T23:59:59.000Z", "2026-10-08T00:00:01.000Z"
    out = tmp_path / "out"
    exp = CsvExporter(out)
    exp.publish(a)
    exp.publish(b)
    assert [f.name for f in files(out)] == ["omp-20261007-0001.csv",
                                            "omp-20261008-0001.csv"]


def test_restart_appends_to_the_same_file_without_a_second_header(tmp_path):
    store = seeded(tmp_path, 4)
    out = tmp_path / "out"
    envs = [e for _, e in store.pending("csv", 10)]
    CsvExporter(out).publish(envs[0])
    CsvExporter(out).publish(envs[1])                # new process, same day
    assert len(files(out)) == 1
    assert files(out)[0].read_text().count("omp_version") == 1
    assert [e["seq"] for e in read_envelopes(files(out))] == [1, 2]


def test_torn_final_row_is_cut_on_restart(tmp_path):
    store = seeded(tmp_path, 3)
    out = tmp_path / "out"
    envs = [e for _, e in store.pending("csv", 10)]
    CsvExporter(out).publish(envs[0])
    with open(files(out)[0], "a") as f:              # crash mid-row
        f.write("0.1.0,generic/0.1,gw-test-01,m-one-01,2,2026-")
    exp = CsvExporter(out)
    exp.publish(envs[1])
    assert [e["seq"] for e in read_envelopes(files(out))] == [1, 2]


def test_rejects_a_silly_size(tmp_path):
    with pytest.raises(CsvConfigError):
        CsvExporter(tmp_path, max_bytes=10)


def test_registry_builds_a_csv_exporter(tmp_path):
    from omp.cli import _build_exporters
    (exp,) = _build_exporters({"exporters": [{"type": "csv",
                                              "dir": str(tmp_path / "o")}]})
    assert isinstance(exp, CsvExporter)
    json.dumps(exp.name)


class _TearingFile:
    """Writes half of the next row, then fails - a disk filling mid-row."""

    def __init__(self, real):
        self.real = real

    def write(self, data):
        self.real.write(data[: len(data) // 2])
        self.real.flush()
        raise OSError("disk full")

    def __getattr__(self, name):
        return getattr(self.real, name)


def test_a_torn_row_from_a_failed_write_does_not_glue_to_the_retry(tmp_path):
    store = seeded(tmp_path, 4)
    exp = CsvExporter(tmp_path / "out", batch_size=2)
    exp.publish(store.pending("csv", 1)[0][1])        # open a real handle
    exp._fh = _TearingFile(exp._fh)
    with pytest.raises(OSError):
        exp.drain(store)
    assert exp.drain(store) == 4                      # retry on SAME instance
    seqs = [e["seq"] for e in read_envelopes(files(tmp_path / "out"))]
    assert set(seqs) == {1, 2, 3, 4}, "every row readable, none garbled"


@pytest.mark.parametrize("bad", [0, -5, "1048576", 1.5, True, None])
def test_bad_sizes_are_config_errors_not_tracebacks(tmp_path, bad):
    with pytest.raises(CsvConfigError):
        CsvExporter(tmp_path, max_bytes=bad)
    with pytest.raises(CsvConfigError):
        CsvExporter(tmp_path, batch_size=bad)


def test_registry_reports_a_bad_size_cleanly(tmp_path):
    from omp.cli import _build_exporters
    with pytest.raises(SystemExit, match="max_bytes"):
        _build_exporters({"exporters": [{"type": "csv", "dir": str(tmp_path),
                                         "max_bytes": "10MB"}]})


def test_new_file_fsyncs_its_directory(tmp_path, monkeypatch):
    import os
    import stat
    synced = []
    real = os.fsync
    monkeypatch.setattr("omp.exporters.csv.os.fsync",
                        lambda fd: (synced.append(stat.S_ISDIR(os.fstat(fd).st_mode)),
                                    real(fd))[1])
    store = seeded(tmp_path, 1)
    CsvExporter(tmp_path / "out").publish(store.pending("csv", 1)[0][1])
    assert True in synced, "directory entry was never made durable"


def test_present_but_empty_fields_survive_the_round_trip(tmp_path):
    store = seeded(tmp_path, 1)
    env = store.pending("csv", 1)[0][1]
    env["sig"] = ""
    env["x-empty"] = ""
    env["x-null"] = None
    CsvExporter(tmp_path / "out").publish(env)
    assert next(read_envelopes(files(tmp_path / "out"))) == env
