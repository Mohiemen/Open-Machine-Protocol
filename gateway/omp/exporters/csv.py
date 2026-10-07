"""CSV exporter - rotating evidence files for air-gapped and sneakernet sites.

Platform Ingestion s1: "air-gapped or tiny factories, same envelopes, rotating
files, sneakernet-compatible". The files are the delivery, so the same rule
as every other exporter applies: ack a rowid only after the bytes are on disk.
That means flush AND fsync before the cursor moves; a flushed-but-not-synced
row is exactly the at-most-once-in-disguise bug the stdout exporter had.

Envelopes are nested JSON, so the CSV carries every top-level envelope field
as a column and `body` as a JSON string. Nothing is dropped: any top-level key
this version does not know lands in `extra` (JSON), so a file is always
convertible back to the exact envelope with `read_envelopes` - and the
checksum, which covers the body, still verifies after the round trip.

Filenames are `omp-YYYYMMDD-NNNN.csv` (UTC day of the envelope's `ts`, then a
per-day index), so a plain directory listing sorts chronologically. A file
rolls over on a new day or when it reaches `max_bytes`.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from ..core.store import Store
from .base import Exporter

COLUMNS = ["omp_version", "profile", "gateway_id", "machine_id", "seq", "ts",
           "schema", "body", "checksum", "sig", "extra"]
_JSON_COLUMNS = ("body",)
_KNOWN = set(COLUMNS) - {"extra"}
_NAME = re.compile(r"omp-(\d{8})-(\d{4})\.csv")


class CsvConfigError(ValueError):
    """Refused at construction - a misconfiguration, not a runtime failure."""


def _day(envelope: dict) -> str:
    # `ts` is ISO 8601 UTC (spec s2), so the date is its first ten characters.
    return str(envelope["ts"])[:10].replace("-", "")


def _row(envelope: dict) -> list[str]:
    row = []
    for col in COLUMNS[:-1]:
        v = envelope.get(col)
        if v is None:
            row.append("")
        elif col in _JSON_COLUMNS:
            row.append(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
        else:
            row.append(str(v))
    extra = {k: v for k, v in envelope.items() if k not in _KNOWN}
    row.append(json.dumps(extra, ensure_ascii=False, separators=(",", ":"))
               if extra else "")
    return row


class CsvExporter(Exporter):
    name = "csv"

    def __init__(self, directory: str | os.PathLike, *,
                 max_bytes: int = 10 * 1024 * 1024, batch_size: int = 500):
        if max_bytes < 1024:
            raise CsvConfigError("max_bytes must be at least 1024")
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.batch_size = batch_size
        self._fh = None
        self._day = None
        self._index = 0

    # -- file management ---------------------------------------------------
    def _path(self, day: str, index: int) -> Path:
        return self.dir / f"omp-{day}-{index:04d}.csv"

    def _latest_index(self, day: str) -> int:
        found = [int(m.group(2)) for p in self.dir.iterdir()
                 if (m := _NAME.fullmatch(p.name)) and m.group(1) == day]
        return max(found, default=0)

    def _repair_tail(self, path: Path) -> None:
        """Cut a torn final row left by a crash mid-write.

        JSON is escaped onto one line, so a complete row always ends in a
        newline; anything after the last one was never acknowledged and will
        be re-sent from the buffer.
        """
        data = path.read_bytes()
        if data and not data.endswith(b"\n"):
            keep = data.rfind(b"\n") + 1
            with open(path, "r+b") as f:
                f.truncate(keep)
                f.flush()
                os.fsync(f.fileno())

    def _open(self, day: str) -> None:
        self._close()
        index = self._latest_index(day) or 1
        path = self._path(day, index)
        if path.exists():
            self._repair_tail(path)
            if path.stat().st_size >= self.max_bytes:
                index += 1
                path = self._path(day, index)
        new = not path.exists() or path.stat().st_size == 0
        self._fh = open(path, "a", encoding="utf-8", newline="")
        self._day, self._index = day, index
        if new:
            csv.writer(self._fh, lineterminator="\n").writerow(COLUMNS)

    def _close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def _write(self, envelope: dict) -> None:
        day = _day(envelope)
        if self._fh is None or day != self._day:
            self._open(day)
        elif self._fh.tell() >= self.max_bytes:
            self._close()
            self._index += 1
            self._fh = open(self._path(day, self._index), "a",
                            encoding="utf-8", newline="")
            csv.writer(self._fh, lineterminator="\n").writerow(COLUMNS)
        csv.writer(self._fh, lineterminator="\n").writerow(_row(envelope))

    def _sync(self) -> None:
        if self._fh:
            self._fh.flush()
            os.fsync(self._fh.fileno())

    # -- Exporter ----------------------------------------------------------
    def publish(self, envelope: dict) -> None:
        self._write(envelope)
        self._sync()

    def drain(self, store: Store, batch: int = 500) -> int:
        """One fsync per batch, then ack the batch.

        If the write raises (disk full, directory gone) nothing past the last
        completed batch is acked, so the buffer keeps the data and the next
        drain retries - a full disk is loud, not lossy.
        """
        sent = 0
        while True:
            rows = store.pending(self.name, min(batch, self.batch_size))
            if not rows:
                return sent
            for _, envelope in rows:
                self._write(envelope)
            self._sync()
            store.ack(self.name, rows[-1][0])
            sent += len(rows)


def read_envelopes(paths):
    """Yield envelopes back from CSV files, in the order given.

    The inverse of the exporter: pass the sorted file list and the output is
    the original NDJSON stream, ready for `omp-validate`.
    """
    for path in paths:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                env = {}
                for col in COLUMNS[:-1]:
                    v = row.get(col, "")
                    if v == "":
                        continue
                    if col in _JSON_COLUMNS:
                        env[col] = json.loads(v)
                    elif col == "seq":
                        env[col] = int(v)
                    else:
                        env[col] = v
                if row.get("extra"):
                    env.update(json.loads(row["extra"]))
                yield env
