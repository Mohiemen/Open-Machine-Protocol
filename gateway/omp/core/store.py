"""Gateway persistence - seq counters, envelope buffer, dead letters, cursors.

One SQLite database in WAL mode. Everything trust-relevant that must survive
power loss lives here: per-machine sequence counters (spec section 3: never
reused, persisted across restarts), the append-only envelope buffer with
per-exporter delivery cursors (at-least-once), and the dead-letter store
(invalid messages kept with their validation error, never exported as valid).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
import threading


def _now_iso() -> str:
    t = dt.datetime.now(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def _iso_minus_days(iso: str, days: float) -> str:
    t = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=dt.timezone.utc) - dt.timedelta(days=days)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"

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
    stored_at  TEXT,
    UNIQUE (machine_id, seq)
);
CREATE TABLE IF NOT EXISTS prune_log (
    rowid_pk   INTEGER PRIMARY KEY AUTOINCREMENT,
    pruned_at  TEXT NOT NULL,
    rows       INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    oldest_seq INTEGER,
    newest_seq INTEGER
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
        # migrate buffers created before stored_at existed
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(buffer)")}
        if "stored_at" not in cols:
            self._conn.execute("ALTER TABLE buffer ADD COLUMN stored_at TEXT")
            self._conn.commit()
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
    def append(self, envelope: dict, stored_at: str | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO buffer(machine_id, seq, envelope, stored_at) "
                "VALUES(?,?,?,?)",
                (envelope["machine_id"], envelope["seq"],
                 json.dumps(envelope, ensure_ascii=False),
                 stored_at or _now_iso()),
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

    # -- retention ------------------------------------------------------
    def prune(self, exporters: list[str], *, retention_days: float = 30,
              max_bytes: int | None = None, now: str | None = None) -> dict:
        """Drop delivered envelopes past the retention bound.

        The hard rule: **never prune past the slowest exporter's cursor.**
        Buffered-but-undelivered envelopes are data nobody has yet received,
        and deleting them would turn at-least-once into at-most-once silently.
        A stalled exporter therefore stops pruning entirely - the disk fills,
        which is loud, instead of evidence vanishing, which is not.

        `exporters` is the CURRENTLY configured set: a cursor left behind by
        an exporter that has since been removed from the registry must not
        pin the buffer forever.

        Returns a summary; every prune is also recorded in prune_log so
        `omp-gateway status` can show that deletion happened and why.
        """
        now = now or _now_iso()
        with self._lock, self._conn:
            if not exporters:
                return {"pruned": 0, "reason": "no exporters configured"}
            rows = self._conn.execute(
                "SELECT exporter, last_rowid FROM exporter_cursors").fetchall()
            cursors = {e: r for e, r in rows}
            # an exporter that has never drained sits at 0 and blocks pruning,
            # which is the safe reading of "has everyone received this?"
            safe_upto = min(cursors.get(name, 0) for name in exporters)
            if safe_upto <= 0:
                return {"pruned": 0,
                        "reason": "an exporter has delivered nothing yet"}

            cutoff = _iso_minus_days(now, retention_days)
            deleted, reason = 0, ""
            cur = self._conn.execute(
                "SELECT COUNT(*), MIN(seq), MAX(seq) FROM buffer "
                "WHERE rowid_pk <= ? AND stored_at IS NOT NULL AND stored_at < ?",
                (safe_upto, cutoff))
            n, lo, hi = cur.fetchone()
            if n:
                self._conn.execute(
                    "DELETE FROM buffer WHERE rowid_pk <= ? AND "
                    "stored_at IS NOT NULL AND stored_at < ?", (safe_upto, cutoff))
                deleted, reason = n, f"older than {retention_days}d"

            if max_bytes is not None and self._db_bytes() > max_bytes:
                # oldest-first, still never past safe_upto
                extra = self._conn.execute(
                    "SELECT COUNT(*) FROM buffer WHERE rowid_pk <= ?",
                    (safe_upto,)).fetchone()[0]
                if extra:
                    self._conn.execute(
                        "DELETE FROM buffer WHERE rowid_pk <= ?", (safe_upto,))
                    deleted += extra
                    reason = (reason + " + " if reason else "") + \
                        f"disk over {max_bytes}B"
            if deleted:
                self._conn.execute(
                    "INSERT INTO prune_log(pruned_at, rows, reason, oldest_seq,"
                    " newest_seq) VALUES(?,?,?,?,?)",
                    (now, deleted, reason, lo, hi))
            return {"pruned": deleted, "reason": reason or "nothing eligible",
                    "safe_upto": safe_upto}

    def _db_bytes(self) -> int:
        page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = self._conn.execute("PRAGMA page_size").fetchone()[0]
        return page_count * page_size

    def _prune_history(self, limit: int) -> list[dict]:
        """Caller holds the lock."""
        rows = self._conn.execute(
            "SELECT pruned_at, rows, reason FROM prune_log "
            "ORDER BY rowid_pk DESC LIMIT ?", (limit,)).fetchall()
        return [{"pruned_at": a, "rows": b, "reason": c} for a, b, c in rows]

    def prune_history(self, limit: int = 5) -> list[dict]:
        with self._lock:
            return self._prune_history(limit)

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
            db_bytes = self._db_bytes()
            prunes = self._prune_history(3)
        return {"machines": seqs, "buffered": buffered,
                "dead_letters": dead, "cursors": cursors,
                "db_bytes": db_bytes, "recent_prunes": prunes}

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
