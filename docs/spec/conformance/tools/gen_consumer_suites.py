#!/usr/bin/env python3
"""Generates the executable consumer conformance suites.

Each case in spec/conformance/consumer/cases.md becomes a directory with:

    input.ndjson    the stream to feed a consumer
    expected.json   observable outcomes any conformant consumer must produce

`expected.json` is deliberately implementation-agnostic: it states counts and
gaps, not table names, so a consumer written in any language can self-check.

Run from this directory:  python3 gen_consumer_suites.py
"""
from __future__ import annotations

import io
import json
import pathlib
from contextlib import redirect_stdout

from omp_tools.envelope import checksum
from omp_tools.simulate import main as simulate_main

OUT = pathlib.Path(__file__).resolve().parent.parent / "consumer"


def stream(profile="textile-dyeing", machines=1, duration="1h", seed=5):
    buf = io.StringIO()
    with redirect_stdout(buf):
        simulate_main(["--profile", profile, "--machines", str(machines),
                       "--duration", duration, "--seed", str(seed)])
    return [json.loads(x) for x in buf.getvalue().splitlines()]


def write(case: str, description: str, envelopes: list, expect: dict,
          note: str = "") -> None:
    d = OUT / case
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "input.ndjson", "w", encoding="utf-8") as f:
        for e in envelopes:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    (d / "expected.json").write_text(
        json.dumps({"case": case, "description": description,
                    **({"note": note} if note else {}), "expect": expect},
                   indent=2) + "\n", encoding="utf-8")
    print(f"wrote consumer/{case} ({len(envelopes)} lines)")


base = stream()
gw, mid = base[0]["gateway_id"], base[0]["machine_id"]
key = f"{gw}/{mid}"
n = len(base)

# 1 ------------------------------------------------------------------------
write("duplicate-delivery",
      "At-least-once delivery guarantees duplicates. An exact redelivery is "
      "dropped silently - not stored twice, not alarmed.",
      base + [base[3], base[7]],
      {"stored": n, "duplicates": 2, "alarms": 0, "quarantined": 0, "gaps": {}})

# 2 ------------------------------------------------------------------------
tampered = json.loads(json.dumps(base[6]))
tampered["body"] = dict(tampered["body"], **{"x-tamper": {"altered": 1}})
tampered["checksum"] = checksum(tampered["body"])   # internally valid!
write("integrity-alarm",
      "Same (gateway_id, machine_id, seq) with a DIFFERENT checksum is not a "
      "duplicate - it is an integrity alarm. Both versions are stored, neither "
      "overwrites the other, and it is surfaced loudly.",
      base + [tampered],
      {"stored": n, "duplicates": 0, "alarms": 1, "quarantined": 0, "gaps": {}},
      "The second envelope is internally consistent - its checksum matches its "
      "own body. Only the dedup-key collision reveals it. A consumer that "
      "upserts on the key would silently accept the rewrite.")

# 3 ------------------------------------------------------------------------
dropped = base[8]
write("gap-tracking",
      "A missing seq means missing data. The gap is tracked per machine and "
      "propagates as seq_complete:false into anything evidentiary - never hidden.",
      [e for e in base if e is not dropped],
      {"stored": n - 1, "duplicates": 0, "alarms": 0, "quarantined": 0,
       "gaps": {key: [dropped["seq"]]}})

# 4 ------------------------------------------------------------------------
shuffled = base[:5] + [base[7], base[6], base[5]] + base[8:]
write("out-of-order",
      "Exporter retries interleave. Arrival order is not seq order; a consumer "
      "orders by seq and must not treat late arrivals as gaps or duplicates.",
      shuffled,
      {"stored": n, "duplicates": 0, "alarms": 0, "quarantined": 0, "gaps": {}})

# 5 ------------------------------------------------------------------------
future = json.loads(json.dumps(base[4]))
future["seq"] = max(e["seq"] for e in base) + 1
future["body"] = {"event_type": "ph_correction", "payload": {"target_ph": 7}}
future["checksum"] = checksum(future["body"])
write("unknown-event-type",
      "Profiles add event types in MINOR releases. Spec s9: a consumer MUST "
      "accept unknown event types under a known profile major and treat them "
      "as opaque events - log and count them, never drop or crash.",
      base + [future],
      {"stored": n + 1, "duplicates": 0, "alarms": 0, "quarantined": 0,
       "gaps": {}, "unknown_event_types": 1},
      "Dropping this is the 'hard-coding profiles' mistake from the Platform "
      "Ingestion guide, and it silently discards real production data.")

# 6 ------------------------------------------------------------------------
without_run = [e for e in base if e["schema"] != "process_run"]
write("unclosed-run",
      "The gateway saw run_start, then power was cut before run_end. The run is "
      "held open for a configurable window, then closed as outcome:unknown in "
      "the consumer's projection - clearly distinct from a machine-reported outcome.",
      without_run,
      {"stored": len(without_run), "duplicates": 0, "alarms": 0,
       "quarantined": 0, "gaps": {}, "runs_closed_as_unknown": 1},
      "A consumer that reports this run as 'completed', or omits it entirely, "
      "is misrepresenting what the machine said.")

# 7 ------------------------------------------------------------------------
moved = json.loads(json.dumps(base[0]))
moved["seq"] = max(e["seq"] for e in base) + 1
moved["body"] = json.loads(json.dumps(base[0]["body"]))
moved["body"]["location"] = dict(moved["body"]["location"], station="s09")
moved["checksum"] = checksum(moved["body"])
write("machine-record-change",
      "Machines re-announce on change. A machine record is a slowly changing "
      "dimension: a new location opens a new validity period, it does not "
      "overwrite history. Genealogy depends on this.",
      base + [moved],
      {"stored": n + 1, "duplicates": 0, "alarms": 0, "quarantined": 0,
       "gaps": {}, "machine_validity_periods": 2},
      "Overwriting the earlier record would silently re-attribute every past "
      "envelope to the machine's new station.")

# 8 ------------------------------------------------------------------------
multi = stream(machines=3, seed=11)
# One gateway draining its buffer after an outage: strictly ascending seq
# within each machine, arbitrarily interleaved across them. Built by
# round-robining the per-machine streams, which is what the exporter cursor
# actually produces.
by_machine: dict[str, list] = {}
for e in multi:
    by_machine.setdefault(e["machine_id"], []).append(e)
replayed = []
while any(by_machine.values()):
    for mkey in list(by_machine):
        if by_machine[mkey]:
            replayed.append(by_machine[mkey].pop(0))
write("replay-burst",
      "After an outage a gateway replays in seq order per machine but "
      "interleaved across machines. The end state must equal live delivery - "
      "idempotency via the dedup key makes this free.",
      replayed,
      {"stored": len(multi), "duplicates": 0, "alarms": 0, "quarantined": 0,
       "gaps": {}},
      "Per-machine seq stays ascending; only the cross-machine order changes. "
      "A consumer that assumes globally ordered arrival will see phantom gaps.")
