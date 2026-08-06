#!/usr/bin/env python3
"""OMP driver - launch and drive the project without hardware.

Every subcommand exits non-zero on failure, so they compose in CI and in
agent loops. Uses only the stdlib plus the project's own packages.

    python3 .claude/skills/run-open-machine-protocol/driver.py all

Subcommands:
    doctor       environment + install check
    quickstart   simulate | validate for every profile, and prove chaos fails
    conformance  run every spec conformance vector through omp-validate
    adapter      drive ANY adapter through the real gateway engine (no hardware)
    gateway      full signed daemon run, then verify the signatures
    consumer     reference platform consumer, including its edge cases
    all          everything above
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
PROFILES = ("generic", "textile-sewing", "textile-dyeing")


class Failure(Exception):
    pass


def say(ok: bool, what: str, detail: str = "") -> None:
    print(f"  [{PASS if ok else FAIL}] {what}{(' - ' + detail) if detail else ''}")
    if not ok:
        raise Failure(what)


def exe(name: str) -> str:
    """Resolve a console script next to the *running interpreter* first.

    The skill invokes this driver as `/path/to/venv/bin/python driver.py`
    without activating the venv, so bare PATH lookup would silently pick up a
    global install (or find nothing at all on a clean machine).
    """
    local = pathlib.Path(sys.executable).parent / name
    if local.exists():
        return str(local)
    return shutil.which(name) or name


def run(cmd: list[str], *, stdin: str | None = None, check: bool = True):
    cmd = [exe(cmd[0])] + cmd[1:]
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, cwd=REPO)
    if check and p.returncode != 0:
        raise Failure(f"{' '.join(cmd[:3])}... exited {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p


# --------------------------------------------------------------------- doctor
def cmd_doctor(args) -> None:
    print("doctor:")
    print(f"  interpreter: {sys.executable}")
    for name in ("omp-validate", "omp-simulate", "omp-sniff", "omp-gateway"):
        path = exe(name)
        say(pathlib.Path(path).exists(), f"{name} resolved",
            path if pathlib.Path(path).exists()
            else "not found - pip install -e ./gateway -e ./tools")
    import omp  # noqa: F401
    import omp_tools  # noqa: F401
    say(True, "omp + omp_tools importable")
    from omp_tools.specload import load_spec

    spec = load_spec()
    say(len(spec.validators) == 6, "6 core schemas loaded", str(spec.spec_dir))
    say(len(spec.profiles) >= 3, f"{len(spec.profiles)} profiles loaded",
        ", ".join(sorted(spec.profiles)))
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: F401
            Ed25519PrivateKey,
        )
        say(True, "cryptography usable (signing available)")
    except Exception as exc:  # noqa: BLE001
        say(False, "cryptography usable", f"{type(exc).__name__}: {exc}")


# ----------------------------------------------------------------- quickstart
def cmd_quickstart(args) -> None:
    print("quickstart (the documented no-hardware pipeline):")
    for profile in PROFILES:
        sim = run(["omp-simulate", "--profile", profile, "--machines", "3",
                   "--duration", "30m", "--seed", "1"])
        val = run(["omp-validate"], stdin=sim.stdout)
        n = len(sim.stdout.splitlines())
        say(val.returncode == 0 and n > 0, f"{profile}: {n} envelopes valid",
            val.stdout.strip())
    # chaos MUST make the validator fail - that is the point of the demo
    sim = run(["omp-simulate", "--profile", "textile-sewing", "--machines", "3",
               "--duration", "1h", "--seed", "9", "--chaos", "corrupt-fields"])
    val = run(["omp-validate"], stdin=sim.stdout, check=False)
    say(val.returncode == 1, "chaos stream is rejected (exit 1)",
        val.stdout.strip().splitlines()[-1] if val.stdout.strip() else "")


# ---------------------------------------------------------------- conformance
def cmd_conformance(args) -> None:
    print("conformance vectors:")
    from omp_tools.specload import load_spec
    from omp_tools.validate import validate_envelope

    spec = load_spec()
    files = sorted(spec.spec_dir.glob("conformance/core/*.ndjson")) + \
        sorted(spec.spec_dir.glob("profiles/*/conformance/*.ndjson"))
    say(len(files) >= 6, f"{len(files)} vector files found")
    total = 0
    for vf in files:
        expect_valid = vf.name == "valid.ndjson"
        for i, line in enumerate(vf.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(line)
            env = row if expect_valid else row["vector"]
            errors = validate_envelope(env, spec)
            ok = (not errors) if expect_valid else bool(errors)
            if not ok:
                say(False, f"{vf.parent.parent.name}/{vf.name}:{i}",
                    str(errors) if expect_valid else f"accepted: {row['_reason']}")
            total += 1
    say(True, f"all {total} vectors behave as specified")


# -------------------------------------------------------------------- adapter
def _drive_adapter(adapter_dir: str, config: dict, machine_id: str,
                   want: int, timeout: float = 10.0, signer=None):
    """Run an adapter through the real engine. Returns (adapter, store, envelopes)."""
    from omp.cli import load_adapter_class
    from omp.core.engine import Engine
    from omp.core.store import Store

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="omp-driver-"))
    cls = load_adapter_class(adapter_dir)
    adapter = cls(config=config)
    store = Store(tmp / "buffer.db")
    engine = Engine("gw-driver-01", store, signer=signer)
    out: list = []
    errs: list = []

    def emit(body):
        env = engine.process(machine_id, body)
        (out if env is not None else errs).append(env)

    t = threading.Thread(target=adapter.start, args=(emit,), daemon=True)
    t.start()
    deadline = time.time() + timeout
    while time.time() < deadline and len(out) < want:
        time.sleep(0.02)
    adapter.stop()
    t.join(timeout=5)
    return adapter, store, out


SERIAL_LINE_PROFILE = """
profile: textile-dyeing/0.1
machine_class: jigger
patterns:
  - match: '^TEMP=(?P<c>\\d+)$'
    emit: { schema: telemetry, channel: bath_temp, unit: Cel, value: c, mode: stats }
  - match: '^PHASE (?P<name>\\w+) START$'
    emit: { schema: event, event_type: phase_start, payload: { phase: name } }
"""
SERIAL_CAPTURE = "TEMP=30\nPHASE heat START\nTEMP=45\nTEMP=60\nnoise\nPHASE hold START\n"


def cmd_adapter(args) -> None:
    """Drive an adapter with a JSON config, or the built-in demo."""
    from omp_tools.specload import load_spec
    from omp_tools.validate import validate_envelope

    spec = load_spec()
    if args.adapter_dir:
        config = json.loads(pathlib.Path(args.config).read_text()) if args.config else {}
        print(f"adapter: {args.adapter_dir}")
        adapter, store, envs = _drive_adapter(args.adapter_dir, config,
                                              args.machine_id, args.expect)
        say(bool(envs), f"{len(envs)} envelope(s) emitted")
    else:
        print("adapter: built-in generic-serial replay demo")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="omp-driver-"))
        (tmp / "lines.yaml").write_text(SERIAL_LINE_PROFILE, encoding="utf-8")
        (tmp / "cap.txt").write_text(SERIAL_CAPTURE, encoding="utf-8")
        adapter, store, envs = _drive_adapter(
            str(REPO / "adapters" / "generic-serial"),
            {"line_profile": str(tmp / "lines.yaml"),
             "replay_file": str(tmp / "cap.txt"), "stats_window_s": 0.0},
            "f1-dye-jig01", want=3)
        say(len(envs) >= 3, f"{len(envs)} envelopes from the replay capture")
        kinds = [e["schema"] for e in envs]
        say("event" in kinds and "telemetry" in kinds, "events + telemetry emitted",
            ", ".join(sorted(set(kinds))))

    for env in envs:
        errors = validate_envelope(env, spec)
        say(not errors, f"seq {env['seq']} {env['schema']} conformant", str(errors))
    say(store.dead_letters() == [], "no dead letters")
    say(adapter.health().state == "ok", f"adapter health: {adapter.health().state}")
    if args.print_envelopes:
        for env in envs:
            print(json.dumps(env))


# -------------------------------------------------------------------- gateway
REGISTRY = """
machines:
  - machine_id: f1-dye-jig01
    adapter: generic-serial
    profile: textile-dyeing/0.1
    config:
      line_profile: {lp}
      replay_file: {cap}
      stats_window_s: 0.0
    location: {{ site: f1, area: dyeing, line: jigs, station: jig01 }}
"""


def cmd_gateway(args) -> None:
    print("gateway daemon (signed, end to end):")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="omp-driver-gw-"))
    (tmp / "lines.yaml").write_text(SERIAL_LINE_PROFILE, encoding="utf-8")
    (tmp / "cap.txt").write_text(SERIAL_CAPTURE, encoding="utf-8")
    (tmp / "registry.yaml").write_text(
        REGISTRY.format(lp=tmp / "lines.yaml", cap=tmp / "cap.txt"), encoding="utf-8")
    state = tmp / "state"

    p = run(["omp-gateway", "run", "--registry", str(tmp / "registry.yaml"),
             "--state-dir", str(state), "--adapters-dir", str(REPO / "adapters"),
             "--gateway-id", "gw-driver-01", "--sign", "--duration", "3"])
    envs = [json.loads(x) for x in p.stdout.splitlines() if x.startswith("{")]
    say(bool(envs), f"{len(envs)} envelopes exported")
    say(envs[0]["schema"] == "machine", "machine announced first (spec 7.1)")

    from omp_tools.sigverify import verify_envelope_sig
    from omp_tools.specload import load_spec
    from omp_tools.validate import validate_envelope

    spec = load_spec()
    ident = run(["omp-gateway", "show-identity", "--state-dir", str(state)])
    pub = [x.split("ed25519:")[1].strip() for x in ident.stdout.splitlines()
           if "pubkey:" in x][0]
    say(bool(pub), "gateway identity readable", ident.stdout.splitlines()[0])
    for env in envs:
        say(not validate_envelope(env, spec), f"seq {env['seq']} conformant")
        say(verify_envelope_sig(env, pub), f"seq {env['seq']} signature verifies")

    status = run(["omp-gateway", "status", "--state-dir", str(state)])
    say("dead_letters: 0" in status.stdout, "status clean",
        status.stdout.splitlines()[0])
    # a signed stream must also verify through the CLI an auditor would use
    stream = "\n".join(json.dumps(e) for e in envs)
    v = run(["omp-validate", "--pubkey", pub], stdin=stream)
    say(v.returncode == 0, "omp-validate --pubkey accepts the stream", v.stdout.strip())
    tampered = json.loads(json.dumps(envs[-1]))
    tampered["seq"] += 1
    v2 = run(["omp-validate", "--pubkey", pub], stdin=json.dumps(tampered), check=False)
    say(v2.returncode == 1, "tampered seq is rejected", v2.stdout.strip())


# ------------------------------------------------------------------- consumer
def cmd_consumer(args) -> None:
    print("reference platform consumer:")
    from omp_tools.envelope import checksum

    ingest = REPO / "examples" / "platform-ingest-reference" / "ingest.py"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="omp-driver-c-"))
    sim = run(["omp-simulate", "--profile", "textile-dyeing", "--machines", "1",
               "--duration", "1h", "--seed", "11"])
    lines = sim.stdout.splitlines()
    dropped = json.loads(lines[8])
    feed = [x for i, x in enumerate(lines) if i != 8]      # -> a seq gap
    feed.append(lines[5])                                   # -> exact duplicate
    tamper = json.loads(lines[6])                           # -> integrity alarm
    tamper["body"] = dict(tamper["body"], **{"x-tamper": {"altered": 1}})
    tamper["checksum"] = checksum(tamper["body"])
    feed.append(json.dumps(tamper))
    feed.append("{not json")                                # -> quarantine

    p = run([sys.executable, str(ingest), str(tmp / "db.sqlite")],
            stdin="\n".join(feed) + "\n")
    report = p.stdout
    for expect, why in (("duplicates: 1", "exact redelivery dropped silently"),
                        ("alarms: 1", "same key + different checksum = integrity alarm"),
                        ("quarantined: 1", "malformed input quarantined"),
                        (f"missing seq [{dropped['seq']}]", "seq gap detected"),
                        ("seq_complete: false", "gap propagates honestly")):
        say(expect in report, why, expect)


# ------------------------------------------------------------------------ all
def cmd_all(args) -> None:
    for fn in (cmd_doctor, cmd_quickstart, cmd_conformance, cmd_adapter,
               cmd_gateway, cmd_consumer):
        fn(args)
        print()
    print("all driver checks passed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="driver.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("doctor", cmd_doctor), ("quickstart", cmd_quickstart),
                     ("conformance", cmd_conformance), ("gateway", cmd_gateway),
                     ("consumer", cmd_consumer), ("all", cmd_all)):
        sub.add_parser(name, help=fn.__doc__ or name).set_defaults(func=fn)
    pa = sub.add_parser("adapter", help="drive an adapter through the engine")
    pa.add_argument("adapter_dir", nargs="?", help="adapter dir (default: demo)")
    pa.add_argument("--config", help="JSON file with the adapter config")
    pa.add_argument("--machine-id", default="drv-machine-01")
    pa.add_argument("--expect", type=int, default=1, help="envelopes to wait for")
    pa.add_argument("--print-envelopes", action="store_true")
    pa.set_defaults(func=cmd_adapter)
    args = ap.parse_args(argv)
    for attr, default in (("adapter_dir", None), ("config", None),
                          ("machine_id", "drv-machine-01"), ("expect", 1),
                          ("print_envelopes", False)):
        if not hasattr(args, attr):
            setattr(args, attr, default)
    try:
        args.func(args)
    except Failure as exc:
        print(f"\ndriver FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
