#!/usr/bin/env python3
"""Regenerates the conformance vector NDJSON files with correct checksums.

Checksums are SHA-256 over the RFC 8785 (JCS) canonical serialization of
`body`. Vector bodies deliberately contain only strings, integers, and
booleans-free structures so that Python's json.dumps(sort_keys=True,
separators=(",", ":"), ensure_ascii=False) is JCS-equivalent (no float
shortest-round-trip cases arise). Keep it that way when adding vectors, or
switch to a full JCS library.

Run from this directory:  python3 gen_vectors.py
"""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def canon(body: dict) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(body: dict) -> str:
    return hashlib.sha256(canon(body).encode("utf-8")).hexdigest()


def env(schema, body, *, profile="generic/0.1", gateway="gw-test-01",
        machine="m-test-01", seq=1, ts="2026-07-24T09:00:00.000Z", **extra):
    e = {
        "omp_version": "0.1.0",
        "profile": profile,
        "gateway_id": gateway,
        "machine_id": machine,
        "seq": seq,
        "ts": ts,
        "schema": schema,
        "body": body,
        "checksum": checksum(body),
    }
    e.update(extra)
    return e


def write_ndjson(path: pathlib.Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT.parent.parent)} ({len(rows)} vectors)")


MACHINE_BODY = {
    "machine_class": "unclassified",
    "make": "Example",
    "model": "EX-1",
    "location": {"site": "f1", "area": "test", "line": "l1", "station": "s1"},
    "capabilities": ["event", "energy"],
    "adapter": {"name": "generic-serial", "version": "0.1.0"},
    "data_source": "native",
}

# ---------------------------------------------------------------- core valid
core_valid = [
    env("machine", MACHINE_BODY),
    env("event", {"event_type": "cycle_complete",
                  "payload": {"cycle_count": 14, "cycle_time_ms": 31240}}, seq=2),
    env("event", {"event_type": "error", "severity": "error",
                  "payload": {"code": "e12", "message": "sensor fault"}}, seq=3),
    env("event", {"event_type": "stop", "payload": {"reason": "unknown"},
                  "x-example": {"note": "extension blocks are legal and checksummed"}}, seq=4),
    env("process_run", {
        "run_id": "run-0001", "run_type": "shift",
        "start_ts": "2026-07-24T02:00:00.000Z", "end_ts": "2026-07-24T10:00:00.000Z",
        "outcome": "completed",
        "quantities": [{"name": "cycles_total", "value": 412, "unit": "1"}],
        "event_seq_range": {"first": 2, "last": 4},
    }, seq=5),
    env("energy", {"metric": "kwh", "value": 3,
                   "interval": {"start_ts": "2026-07-24T08:00:00Z",
                                "end_ts": "2026-07-24T09:00:00Z"},
                   "source": "ct_clamp"}, seq=6),
    env("telemetry", {"channel": "motor_current", "unit": "A", "mode": "stats",
                      "stats": {"start_ts": "2026-07-24T08:59:00Z",
                                "end_ts": "2026-07-24T09:00:00Z",
                                "min": 1, "max": 6, "avg": 4, "count": 60}}, seq=7),
    env("telemetry", {"channel": "bath_temp", "unit": "Cel", "mode": "samples",
                      "samples": [{"t": "2026-07-24T09:00:00.000Z", "v": 60}]},
        seq=8, profile="textile-dyeing/0.1"),
    # sig present (syntactically valid base64; signature verification is a
    # separate, key-dependent check outside static vectors)
    env("event", {"event_type": "start", "payload": {"reason": "shift_start"}},
        seq=9, sig="dGVzdC1zaWduYXR1cmUtbm90LXZlcmlmaWFibGU="),
]

# -------------------------------------------------------------- core invalid
def broken(reason, envelope):
    return {"_reason": reason, "vector": envelope}

core_invalid = [
    broken("unknown envelope field rejected (spec s2)",
           {**env("event", {"event_type": "start"}), "extra_field": True}),
    broken("unknown schema value (spec s8.3)",
           {**env("event", {"event_type": "start"}), "schema": "metrics"}),
    broken("gateway_id pattern violation (uppercase)",
           {**env("event", {"event_type": "start"}), "gateway_id": "GW-01"}),
    broken("seq must start at 1",
           {**env("event", {"event_type": "start"}), "seq": 0}),
    broken("ts must be UTC millisecond precision with Z",
           {**env("event", {"event_type": "start"}), "ts": "2026-07-24 09:00:00"}),
    broken("checksum mismatch - body was altered after checksumming",
           {**env("event", {"event_type": "cycle_complete",
                            "payload": {"cycle_count": 14}}),
            "body": {"event_type": "cycle_complete", "payload": {"cycle_count": 15}}}),
    broken("event_type pattern violation",
           env("event", {"event_type": "Cycle-Complete"})),
    broken("severity required for error events",
           env("event", {"event_type": "error", "payload": {"code": "e1"}})),
    broken("energy value must be >= 0",
           env("energy", {"metric": "kwh", "value": -1,
                          "interval": {"start_ts": "2026-07-24T08:00:00Z",
                                       "end_ts": "2026-07-24T09:00:00Z"},
                          "source": "native"})),
    broken("telemetry mode=samples requires samples",
           env("telemetry", {"channel": "motor_current", "unit": "A",
                             "mode": "samples"})),
    broken("process_run missing outcome",
           env("process_run", {"run_id": "r1", "run_type": "batch",
                               "start_ts": "2026-07-24T08:00:00Z",
                               "end_ts": "2026-07-24T09:00:00Z"})),
    broken("machine missing required adapter provenance",
           env("machine", {k: v for k, v in MACHINE_BODY.items() if k != "adapter"})),
    broken("extension block must be an object",
           env("event", {"event_type": "start", "x-example": "not-an-object"})),
]

# ---------------------------------------------------- textile-dyeing vectors
DYE = "textile-dyeing/0.1"
dye_valid = [
    env("event", {"event_type": "phase_start", "payload": {"phase": "heat"}},
        profile=DYE, machine="f1-dye-jet02", seq=10),
    env("event", {"event_type": "dosing_complete",
                  "payload": {"tank": "t2", "chemical_ref": "chem-104",
                              "target_amount": 12, "unit": "kg", "actual_amount": 12}},
        profile=DYE, machine="f1-dye-jet02", seq=11),
    env("event", {"event_type": "addition",
                  "payload": {"reason": "shade_correction", "detail": "0.2% navy"}},
        profile=DYE, machine="f1-dye-jet02", seq=12),
    env("process_run", {
        "run_id": "b-4471", "run_type": "batch", "program_ref": "recipe-88",
        "start_ts": "2026-07-24T02:00:00.000Z", "end_ts": "2026-07-24T06:30:00.000Z",
        "outcome": "completed",
        "phases": [
            {"name": "load", "start_ts": "2026-07-24T02:00:00Z",
             "end_ts": "2026-07-24T02:20:00Z", "params": {"fabric_kg": 480}},
            {"name": "heat", "start_ts": "2026-07-24T02:20:00Z",
             "end_ts": "2026-07-24T03:00:00Z",
             "params": {"from_c": 30, "to_c": 60, "gradient_c_per_min": 1}},
            {"name": "hold", "start_ts": "2026-07-24T03:00:00Z",
             "end_ts": "2026-07-24T03:45:00Z",
             "params": {"temp_c": 60, "duration_min": 45}},
            {"name": "drain", "start_ts": "2026-07-24T06:20:00Z",
             "end_ts": "2026-07-24T06:25:00Z", "params": {}},
            {"name": "unload", "start_ts": "2026-07-24T06:25:00Z",
             "end_ts": "2026-07-24T06:30:00Z", "params": {}},
        ],
        "quantities": [{"name": "fabric_kg", "value": 480, "unit": "kg"},
                       {"name": "water_l_total", "value": 1847, "unit": "L"}],
        "event_seq_range": {"first": 10, "last": 12},
    }, profile=DYE, machine="f1-dye-jet02", seq=13),
]
dye_invalid = [
    broken("unknown phase name for textile-dyeing",
           env("event", {"event_type": "phase_start", "payload": {"phase": "simmer"}},
               profile=DYE)),
    broken("dosing event missing chemical_ref",
           env("event", {"event_type": "dosing_start",
                         "payload": {"tank": "t1", "target_amount": 5, "unit": "kg"}},
               profile=DYE)),
    broken("heat phase params wrong type",
           env("process_run", {
               "run_id": "b-1", "run_type": "batch",
               "start_ts": "2026-07-24T02:00:00Z", "end_ts": "2026-07-24T03:00:00Z",
               "outcome": "completed",
               "phases": [{"name": "heat", "start_ts": "2026-07-24T02:00:00Z",
                           "end_ts": "2026-07-24T02:30:00Z",
                           "params": {"from_c": "thirty", "to_c": 60,
                                      "gradient_c_per_min": 1}}]}, profile=DYE)),
]

# --------------------------------------------------- textile-sewing vectors
SEW = "textile-sewing/0.1"
sew_valid = [
    env("event", {"event_type": "cycle_complete",
                  "payload": {"cycle_count": 101, "cycle_time_ms": 28400}},
        profile=SEW, machine="f1-line1-m03", seq=20),
    env("event", {"event_type": "needle_break", "payload": {"needle_position": 1}},
        profile=SEW, machine="f1-line1-m03", seq=21),
    env("event", {"event_type": "program_change", "payload": {"program_ref": "style-2291"}},
        profile=SEW, machine="f1-line1-m03", seq=22),
    env("process_run", {
        "run_id": "shift-a-0724", "run_type": "shift",
        "start_ts": "2026-07-24T02:00:00.000Z", "end_ts": "2026-07-24T10:00:00.000Z",
        "outcome": "completed",
        "quantities": [{"name": "pieces_produced", "value": 96, "unit": "1"},
                       {"name": "kwh_total", "value": 2, "unit": "kW.h"}],
        "event_seq_range": {"first": 20, "last": 22},
    }, profile=SEW, machine="f1-line1-m03", seq=23),
]
sew_invalid = [
    broken("textile-sewing defines no phases - any phases entry is non-conformant",
           env("process_run", {
               "run_id": "r1", "run_type": "shift",
               "start_ts": "2026-07-24T02:00:00Z", "end_ts": "2026-07-24T10:00:00Z",
               "outcome": "completed",
               "phases": [{"name": "sewing", "start_ts": "2026-07-24T02:00:00Z",
                           "end_ts": "2026-07-24T10:00:00Z"}]}, profile=SEW)),
    broken("machine_fault missing code",
           env("event", {"event_type": "machine_fault",
                         "payload": {"subsystem": "motor"}}, profile=SEW)),
    broken("event type not in core or textile-sewing vocabulary",
           env("event", {"event_type": "dosing_complete",
                         "payload": {"tank": "t1", "chemical_ref": "c1",
                                     "target_amount": 1, "unit": "kg"}}, profile=SEW)),
]

# ------------------------------------------------------------------- output
write_ndjson(ROOT / "core" / "valid.ndjson", core_valid)
write_ndjson(ROOT / "core" / "invalid.ndjson", core_invalid)
write_ndjson(ROOT.parent / "profiles" / "textile-dyeing" / "conformance" / "valid.ndjson", dye_valid)
write_ndjson(ROOT.parent / "profiles" / "textile-dyeing" / "conformance" / "invalid.ndjson", dye_invalid)
write_ndjson(ROOT.parent / "profiles" / "textile-sewing" / "conformance" / "valid.ndjson", sew_valid)
write_ndjson(ROOT.parent / "profiles" / "textile-sewing" / "conformance" / "invalid.ndjson", sew_invalid)
