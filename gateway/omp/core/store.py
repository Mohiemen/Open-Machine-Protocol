"""Gateway persistence - seq counters, envelope buffer, dead letters, cursors.

One SQLite database in WAL mode. Everything trust-relevant that must survive
power loss lives here: per-machine sequence counters (spec section 3: never
reused, persisted across restarts), the append-only envelope buffer with
per-exporter delivery cursors (at-least-once), and the dead-letter store
(invalid messages kept with their validation error, never exported as valid).
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seq_counters (
    machine_id TEXT PRIMARY KEY,
    last_seq   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS buffer (
    rowid_pk   INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    envelope   TEXT NOT NULL,
    UNIQUE (machine_id, seq)
);
CREATE TABLE IF NOT EXISTS dead_letters (
    rowid_pk   INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    received_ts TEXT NOT NULL,
    body       TEXT NOT NULL,
    error      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exporter_cursors (
    exporter   TEXT PRIMARY KEY,
    last_rowid INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: str | pathlib.Path):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    # -- seq ------------------------------------------------------------
    def next_seq(self, machine_id: str) -> int:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT last_seq FROM seq_counters WHERE machine_id=?",
                (machine_id,),
            ).fetchone()
            seq = (row[0] if row else 0) + 1
            self._conn.execute(
                "INSERT INTO seq_counters(machine_id, last_seq) VALUES(?, ?) "
                "ON CONFLICT(machine_id) DO UPDATE SET last_seq=excluded.last_seq",
                (machine_id, seq),
            )
            return seq

    # -- buffer ---------------------------------------------------------
    def append(self, envelope: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO buffer(machine_id, seq, envelope) VALUES(?,?,?)",
                (envelope["machine_id"], envelope["seq"],
                 json.dumps(envelope, ensure_ascii=False)),
            )

    def pending(self, exporter: str, limit: int = 500) -> list[tuple[int, dict]]:
        """Envelopes past this exporter's cursor, oldest first."""
        with self._lock:
            row = self._conn.execute(
                "SELECT last_rowid FROM exporter_cursors WHERE exporter=?",
                (exporter,),
            ).fetchone()
            after = row[0] if row else 0
            rows = self._conn.execute(
                "SELECT rowid_pk, envelope FROM buffer WHERE rowid_pk>? "
                "ORDER BY rowid_pk LIMIT ?",
                (after, limit),
            ).fetchall()
        return [(r[0], json.loads(r[1])) for r in rows]

    def ack(self, exporter: str, rowid: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO exporter_cursors(exporter, last_rowid) VALUES(?,?) "
                "ON CONFLICT(exporter) DO UPDATE SET last_rowid=excluded.last_rowid",
                (exporter, rowid),
            )

    # -- introspection (status CLI) -------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            seqs = dict(self._conn.execute(
                "SELECT machine_id, last_seq FROM seq_counters").fetchall())
            buffered = self._conn.execute(
                "SELECT COUNT(*) FROM buffer").fetchone()[0]
            dead = self._conn.execute(
                "SELECT COUNT(*) FROM dead_letters").fetchone()[0]
            cursors = dict(self._conn.execute(
                "SELECT exporter, last_rowid FROM exporter_cursors").fetchall())
        return {"machines": seqs, "buffered": buffered,
                "dead_letters": dead, "cursors": cursors}

    # -- dead letters ---------------------------------------------------
    def dead_letter(self, machine_id: str, received_ts: str, body: dict,
                    error: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO dead_letters(machine_id, received_ts, body, error) "
                "VALUES(?,?,?,?)",
                (machine_id, received_ts,
                 json.dumps(body, ensure_ascii=False), error),
            )

    def dead_letters(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT machine_id, received_ts, body, error FROM dead_letters "
                "ORDER BY rowid_pk DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"machine_id": m, "received_ts": t, "body": json.loads(b), "error": e}
            for m, t, b, e in rows
        ]
