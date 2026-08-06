"""omp-sniff - passive protocol capture with real-time annotation.

Captures raw traffic to annotated NDJSON records that drop straight into
adapter replay fixtures and PROTOCOL.md work (Weekend 1 of the Writing an
Adapter guide). Passive only: this tool never transmits.

Modes:
  --serial PORT      capture from a serial port (needs pyserial)
  --stdin            capture lines from stdin (pipes, socat, replays)
  --decode FILE      pretty-print a capture for protocol study

Record format, one per line:
  {"t": iso8601, "src": "serial:/dev/ttyUSB0", "hex": "43 59 ...", "text": "CYCLE 7"}
Annotations (typed into stderr-prompted TTY, or lines starting with '#'
in stdin mode) become {"t": ..., "note": "operator pressed start"}.
pcap capture is roadmap - use tcpdump/wireshark and contribute the pcap.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from . import __version__


def now_iso() -> str:
    t = dt.datetime.now(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def record(raw: bytes, src: str, ts: str | None = None) -> dict:
    text = raw.decode("ascii", errors="replace").strip()
    printable = text if text and all(31 < ord(c) < 127 or c in "\t" for c in text) else None
    rec = {"t": ts or now_iso(), "src": src,
           "hex": " ".join(f"{b:02x}" for b in raw)}
    if printable:
        rec["text"] = printable
    return rec


def note(text: str, ts: str | None = None) -> dict:
    return {"t": ts or now_iso(), "note": text}


def capture_stdin(out) -> int:
    """Lines starting with '#' become annotations; everything else is data."""
    for line in sys.stdin.buffer:
        line = line.rstrip(b"\r\n")
        if not line:
            continue
        if line.startswith(b"#"):
            rec = note(line[1:].strip().decode(errors="replace"))
        else:
            rec = record(line, "stdin")
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
    return 0


def capture_serial(port: str, baud: int, out) -> int:  # pragma: no cover - hardware
    try:
        import serial
    except ImportError:
        print("serial capture needs pyserial: pip install pyserial", file=sys.stderr)
        return 2
    print(f"# capturing {port} @ {baud} - Ctrl-C to stop; type a line + Enter "
          "to add an annotation", file=sys.stderr)
    with serial.Serial(port, baud, timeout=0.2) as s:
        try:
            import select

            while True:
                raw = s.readline()
                if raw:
                    out.write(json.dumps(record(raw.rstrip(b"\r\n"),
                                                f"serial:{port}"),
                                         ensure_ascii=False) + "\n")
                    out.flush()
                ready, _, _ = select.select([sys.stdin], [], [], 0)
                if ready:
                    text = sys.stdin.readline().strip()
                    if text:
                        out.write(json.dumps(note(text), ensure_ascii=False) + "\n")
                        out.flush()
        except KeyboardInterrupt:
            return 0


def decode(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "note" in rec:
                print(f"{rec['t']}  ── {rec['note']} ──")
            else:
                shown = rec.get("text") or rec["hex"]
                print(f"{rec['t']}  {shown}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omp-sniff", description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--serial", metavar="PORT")
    mode.add_argument("--stdin", action="store_true")
    mode.add_argument("--decode", metavar="FILE")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--out", metavar="FILE", default=None,
                        help="write capture here instead of stdout")
    parser.add_argument("--version", action="version",
                        version=f"omp-sniff {__version__}")
    args = parser.parse_args(argv)

    if args.decode:
        return decode(args.decode)
    out = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    try:
        if args.stdin:
            return capture_stdin(out)
        return capture_serial(args.serial, args.baud, out)
    finally:
        if args.out:
            out.close()


if __name__ == "__main__":
    sys.exit(main())
