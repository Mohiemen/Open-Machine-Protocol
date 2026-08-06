#!/usr/bin/env python3
"""Reference OMP consumer - the six-stage pipeline from the Platform
Ingestion guide, deliberately boring, SQLite-backed.

    receive -> parse -> validate -> dedup -> verify -> store raw -> project

Usage:
    omp-simulate --profile textile-dyeing --machines 2 | python3 ingest.py db.sqlite
    python3 ingest.py db.sqlite --report

Every stage matches the guide: malformed input is quarantined with raw
bytes; invalid envelopes are quarantined, never repaired; dedup key is
(gateway_id, machine_id, seq); the same key with a different checksum is an
integrity ALARM stored alongside (never overwritten); raw envelopes are
immutable and projections are rebuildable from them; seq gaps are tracked
per machine and reported - never hidden.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from omp_tools.envelope import checksum as compute_checksum
from omp_tools.specload import load_spec
from omp_tools.validate import validate_envelope

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_envelopes (
    gateway_id TEXT, machine_id TEXT, seq INTEGER,
    envelope TEXT NOT NULL,
    checksums_valid INTEGER NOT NULL,
    PRIMARY KEY (gateway_id, machine_id, seq)
);
CREATE TABLE IF NOT EXISTS quarantine (raw TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS integrity_alarms (
    gateway_id TEXT, machine_id TEXT, seq INTEGER,
    first_envelope TEXT, second_envelope TEXT
);
CREATE TABLE IF NOT EXISTS machines (
    gateway_id TEXT, machine_id TEXT, valid_from_seq INTEGER,
    body TEXT, PRIMARY KEY (gateway_id, machine_id, valid_from_seq)
);
CREATE TABLE IF NOT EXISTS runs (
    gateway_id TEXT, machine_id TEXT, run_id TEXT,
    outcome TEXT, body TEXT,
    PRIMARY KEY (gateway_id, machine_id, run_id)
);
"""


class Consumer:
    def __init__(self, db_path: str, spec_dir=None):
        self.db = sqlite3.connect(db_path)
        self.db.executescript(SCHEMA)
        self.spec = load_spec(spec_dir)
        self.stats = {"stored": 0, "duplicates": 0, "quarantined": 0, "alarms": 0}

    # -- one line through all six stages --------------------------------
    def ingest_line(self, raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:  # 1: parse
            env = json.loads(raw)
            if not isinstance(env, dict):
                raise ValueError("not an object")
        except ValueError as exc:
            self._quarantine(raw, f"parse: {exc}")
            return
        errors = validate_envelope(env, self.spec)  # 2: validate (never repair)
        if errors:
            self._quarantine(raw, f"validate: {errors[0]}")
            return
        key = (env["gateway_id"], env["machine_id"], env["seq"])
        row = self.db.execute(
            "SELECT envelope FROM raw_envelopes WHERE gateway_id=? AND "
            "machine_id=? AND seq=?", key).fetchone()
        if row:  # 3: dedup
            prior = json.loads(row[0])
            if prior["checksum"] == env["checksum"]:
                self.stats["duplicates"] += 1  # exact redelivery: drop silently
            else:  # same key, different checksum: ALARM, store both, no overwrite
                self.db.execute(
                    "INSERT INTO integrity_alarms VALUES (?,?,?,?,?)",
                    (*key, row[0], json.dumps(env)))
                self.stats["alarms"] += 1
            self.db.commit()
            return
        checks_ok = compute_checksum(env["body"]) == env["checksum"]  # 4: verify
        self.db.execute(  # 5: store raw, immutable
            "INSERT INTO raw_envelopes VALUES (?,?,?,?,?)",
            (*key, json.dumps(env), int(checks_ok)))
        self._project(env)  # 6: project
        self.stats["stored"] += 1
        self.db.commit()

    def _quarantine(self, raw: str, reason: str) -> None:
        self.db.execute("INSERT INTO quarantine VALUES (?,?)", (raw, reason))
        self.stats["quarantined"] += 1
        self.db.commit()

    def _project(self, env: dict) -> None:
        if env["schema"] == "machine":
            # slowly changing dimension: each announcement opens a validity
            # period keyed by seq; history is never overwritten
            self.db.execute(
                "INSERT OR IGNORE INTO machines VALUES (?,?,?,?)",
                (env["gateway_id"], env["machine_id"], env["seq"],
                 json.dumps(env["body"])))
        elif env["schema"] == "process_run":
            body = env["body"]
            self.db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)",
                (env["gateway_id"], env["machine_id"], body["run_id"],
                 body["outcome"], json.dumps(body)))

    # -- gap tracking (the honest UI) -----------------------------------
    def gaps(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        rows = self.db.execute(
            "SELECT gateway_id, machine_id, seq FROM raw_envelopes "
            "ORDER BY gateway_id, machine_id, seq").fetchall()
        seen: dict[tuple, list[int]] = {}
        for gw, m, seq in rows:
            seen.setdefault((gw, m), []).append(seq)
        for (gw, m), seqs in seen.items():
            missing = sorted(set(range(1, max(seqs) + 1)) - set(seqs))
            if missing:
                out[f"{gw}/{m}"] = missing
        return out

    def report(self) -> str:
        lines = [f"{k}: {v}" for k, v in self.stats.items()]
        gaps = self.gaps()
        lines.append(f"machines with seq gaps: {len(gaps)}")
        for key, missing in gaps.items():
            lines.append(f"  {key} missing seq {missing} (seq_complete: false)")
        return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", help="SQLite database path")
    parser.add_argument("--report", action="store_true",
                        help="print stats/gaps for an existing db and exit")
    parser.add_argument("--spec-dir", default=None)
    args = parser.parse_args(argv)
    consumer = Consumer(args.db, args.spec_dir)
    if not args.report:
        for line in sys.stdin:
            consumer.ingest_line(line)
    print(consumer.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
