"""generic-serial protocol layer - pure functions from lines to emissions.

A line profile (YAML, documented in First Real Machine section 5) maps regex
patterns to OMP emissions. This module is deliberately free of I/O so tests
and omp-sniff replay fixtures drive it directly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class LineProfile:
    profile: str                    # e.g. "textile-dyeing/0.1"
    machine_class: str
    patterns: list[dict]            # [{match, emit: {...}}]
    _compiled: list[tuple[re.Pattern, dict]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "LineProfile":
        lp = cls(
            profile=data["profile"],
            machine_class=data["machine_class"],
            patterns=data.get("patterns", []),
        )
        for p in lp.patterns:
            lp._compiled.append((re.compile(p["match"]), p["emit"]))
        return lp


def parse_line(lp: LineProfile, line: str) -> dict | None:
    """Returns an emission dict {schema, body} or None if no pattern matches.

    Telemetry emissions come out as single-sample bodies stamped by the
    caller; event payload fields referencing a named group are substituted
    with the captured (numeric where possible) value.
    """
    line = line.strip()
    if not line:
        return None
    for regex, emit in lp._compiled:
        m = regex.match(line)
        if not m:
            continue
        groups = m.groupdict()
        if emit["schema"] == "telemetry":
            raw = groups[emit["value"]]
            return {
                "schema": "telemetry",
                "channel": emit["channel"],
                "unit": emit["unit"],
                "value": _num(raw),
            }
        if emit["schema"] == "event":
            payload = {}
            for key, ref in (emit.get("payload") or {}).items():
                payload[key] = groups.get(ref, ref) if isinstance(ref, str) else ref
                if isinstance(payload[key], str) and ref in groups:
                    payload[key] = groups[ref]
            body = {"event_type": emit["event_type"]}
            if payload:
                body["payload"] = payload
            return {"schema": "event", "body": body}
        raise ValueError(f"line profile emit schema {emit['schema']!r} unsupported")
    return None


def _num(raw: str):
    try:
        f = float(raw)
    except ValueError:
        return raw
    return int(f) if f == int(f) else f


class StatsAggregator:
    """Aggregates telemetry samples into stats blocks (producers SHOULD use
    stats mode above 1 Hz - spec section 7.5). Integral averages keep the
    checksum canonicalization trivial."""

    def __init__(self, window_s: float = 60.0):
        self.window_s = window_s
        self._acc: dict[str, dict] = {}

    def add(self, channel: str, unit: str, value, ts: str, mono: float) -> dict | None:
        """Feed one sample; returns a completed telemetry body when the
        channel's window closes, else None."""
        a = self._acc.get(channel)
        if a is None:
            self._acc[channel] = {
                "unit": unit, "start_ts": ts, "start_mono": mono,
                "min": value, "max": value, "sum": value, "count": 1,
            }
            return None
        a["min"] = min(a["min"], value)
        a["max"] = max(a["max"], value)
        a["sum"] += value
        a["count"] += 1
        if mono - a["start_mono"] >= self.window_s:
            return self._close(channel, ts)
        return None

    def _close(self, channel: str, end_ts: str) -> dict:
        a = self._acc.pop(channel)
        return {
            "channel": channel,
            "unit": a["unit"],
            "mode": "stats",
            "stats": {
                "start_ts": a["start_ts"],
                "end_ts": end_ts,
                "min": a["min"],
                "max": a["max"],
                "avg": int(a["sum"] / a["count"]),
                "count": a["count"],
            },
        }

    def flush(self, end_ts: str) -> list[dict]:
        return [self._close(ch, end_ts) for ch in list(self._acc)]
