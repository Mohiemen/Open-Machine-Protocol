"""omp-sniff record format and the reference consumer's pipeline rules."""
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from omp_tools.envelope import checksum as envelope_checksum
from omp_tools.simulate import main as simulate_main
from omp_tools.sniff import decode, note, record

REPO = Path(__file__).resolve().parent.parent.parent
INGEST = REPO / "examples" / "platform-ingest-reference" / "ingest.py"


# ---------------------------------------------------------------- sniff
def test_record_printable_and_binary():
    r = record(b"CYCLE 7", "serial:/dev/ttyUSB0")
    assert r["text"] == "CYCLE 7" and r["hex"] == "43 59 43 4c 45 20 37"
    b = record(b"\x01\x03\x02", "stdin")
    assert "text" not in b and b["hex"] == "01 03 02"


def test_decode_renders_notes_and_text(tmp_path, capsys):
    cap = tmp_path / "c.ndjson"
    cap.write_text(
        json.dumps(record(b"TEMP=60", "stdin")) + "\n"
        + json.dumps(note("operator pressed start")) + "\n",
        encoding="utf-8",
    )
    decode(str(cap))
    out = capsys.readouterr().out
    assert "TEMP=60" in out and "operator pressed start" in out


def test_sniff_stdin_cli(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "omp_tools.sniff", "--stdin"],
        input="CYCLE 1\n# operator note\nCYCLE 2\n",
        capture_output=True, text=True, cwd=REPO,
    )
    lines = [json.loads(x) for x in proc.stdout.splitlines()]
    assert [r.get("text", r.get("note")) for r in lines] == \
        ["CYCLE 1", "operator note", "CYCLE 2"]


# ---------------------------------------------------------------- ingest
def sim_lines(*argv) -> list[str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        simulate_main(list(argv))
    return buf.getvalue().splitlines()


def test_ingest_pipeline_rules(tmp_path):
    lines = sim_lines("--profile", "textile-dyeing", "--machines", "1",
                      "--duration", "1h", "--seed", "11")
    envs = [json.loads(x) for x in lines]
    # craft the guide's edge cases:
    duplicate = lines[5]                            # exact redelivery
    # same dedup key, *different but internally valid* envelope - the body was
    # altered and re-checksummed, so it passes validation and must surface as
    # a dedup-stage integrity alarm (guide stage 3), not a quarantine
    tampered = json.loads(lines[6])
    tampered["body"] = dict(tampered["body"], **{"x-tamper": {"altered": 1}})
    tampered["checksum"] = envelope_checksum(tampered["body"])
    dropped = envs[8]                               # remove -> seq gap
    feed = [x for i, x in enumerate(lines) if i != 8]
    feed += [duplicate, json.dumps(tampered), "not json at all"]

    proc = subprocess.run(
        [sys.executable, str(INGEST), str(tmp_path / "db.sqlite")],
        input="\n".join(feed) + "\n", capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    report = proc.stdout
    assert "duplicates: 1" in report
    assert "alarms: 1" in report
    assert "quarantined: 1" in report
    assert f"missing seq [{dropped['seq']}]" in report
    assert "seq_complete: false" in report
