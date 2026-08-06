"""Ed25519 signing end to end, and the run daemon + service CLI."""
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from omp.adapter import Body
from omp.cli import main as cli_main
from omp.core.engine import Engine
from omp.core.keys import GatewayKey, verify_signature
from omp.core.store import Store

from omp_tools.sigverify import verify_envelope_sig
from omp_tools.specload import load_spec
from omp_tools.validate import validate_envelope

SPEC = load_spec()
REPO = Path(__file__).resolve().parent.parent.parent


def event_body():
    return Body(schema="event", profile="generic/0.1",
                body={"event_type": "cycle_complete",
                      "payload": {"cycle_count": 1}})


# ---------------------------------------------------------------- signing
def test_sign_and_verify_roundtrip(tmp_path):
    key = GatewayKey.generate(tmp_path / "keys" / "gateway.pem")
    engine = Engine("gw-test-01", Store(tmp_path / "b.db"), signer=key)
    env = engine.process("m-one-01", event_body())
    assert "sig" in env
    assert validate_envelope(env, SPEC) == [], "signed envelope stays conformant"
    pub = key.public_key_b64()
    assert verify_signature(pub, env["sig"], env["gateway_id"],
                            env["machine_id"], env["seq"], env["checksum"])
    # tools-side verifier agrees with gateway-side construction
    assert verify_envelope_sig(env, pub)
    # tampered seq fails
    assert not verify_signature(pub, env["sig"], env["gateway_id"],
                                env["machine_id"], env["seq"] + 1,
                                env["checksum"])
    # wrong key fails
    other = GatewayKey.generate(tmp_path / "keys" / "other.pem")
    assert not verify_envelope_sig(env, other.public_key_b64())


def test_key_persistence_and_permissions(tmp_path):
    path = tmp_path / "keys" / "gateway.pem"
    k1 = GatewayKey.load_or_generate(path)
    k2 = GatewayKey.load_or_generate(path)
    assert k1.public_key_b64() == k2.public_key_b64(), "key must persist"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_validate_cli_pubkey_flag(tmp_path):
    key = GatewayKey.generate(tmp_path / "k.pem")
    engine = Engine("gw-test-01", Store(tmp_path / "b.db"), signer=key)
    signed = engine.process("m-one-01", event_body())
    unsigned = dict(signed)
    del unsigned["sig"]
    stream = json.dumps(signed) + "\n" + json.dumps(unsigned) + "\n"
    proc = subprocess.run(
        [sys.executable, "-m", "omp_tools.validate", "--pubkey",
         key.public_key_b64()],
        input=stream, capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 1
    assert "signature required" in proc.stdout
    assert "1 valid, 1 invalid" in proc.stdout


# ---------------------------------------------------------------- service CLI
def test_install_and_show_identity(tmp_path, capsys):
    assert cli_main(["install-service", "--prefix", str(tmp_path / "etc"),
                     "--state-dir", str(tmp_path / "var"),
                     "--gateway-id", "gw-test-f1-01"]) == 0
    out = capsys.readouterr().out
    assert "gateway_id: gw-test-f1-01" in out
    assert "pubkey: ed25519:" in out
    assert "omp-gateway.service" in out
    assert (tmp_path / "etc" / "registry.yaml").exists()
    assert cli_main(["show-identity", "--prefix", str(tmp_path / "etc"),
                     "--state-dir", str(tmp_path / "var")]) == 0
    out2 = capsys.readouterr().out
    assert "gw-test-f1-01" in out2 and "ed25519:" in out2


# ---------------------------------------------------------------- daemon
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

LINE_PROFILE = """
profile: textile-dyeing/0.1
machine_class: jigger
patterns:
  - match: '^PHASE (?P<name>\\w+) START$'
    emit: { schema: event, event_type: phase_start, payload: { phase: name } }
"""


def test_daemon_run_signed_end_to_end(tmp_path, capsys):
    (tmp_path / "lines.yaml").write_text(LINE_PROFILE, encoding="utf-8")
    (tmp_path / "cap.txt").write_text("PHASE heat START\nPHASE hold START\n",
                                      encoding="utf-8")
    (tmp_path / "registry.yaml").write_text(
        REGISTRY.format(lp=tmp_path / "lines.yaml", cap=tmp_path / "cap.txt"),
        encoding="utf-8")
    state = tmp_path / "state"
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["run", "--registry", str(tmp_path / "registry.yaml"),
                       "--state-dir", str(state),
                       "--adapters-dir", str(REPO / "adapters"),
                       "--gateway-id", "gw-f1-pilot-01",
                       "--sign", "--duration", "2"])
    assert rc == 0
    envs = [json.loads(x) for x in buf.getvalue().splitlines()]
    assert [e["schema"] for e in envs][:1] == ["machine"], \
        "startup announces the machine first (spec 7.1)"
    assert {e["schema"] for e in envs} == {"machine", "event"}
    key = GatewayKey.load(state / "keys" / "gateway.pem")
    for e in envs:
        assert validate_envelope(e, SPEC) == []
        assert verify_envelope_sig(e, key.public_key_b64())
    # machine announcement carries registry location + adapter provenance
    machine = envs[0]["body"]
    assert machine["location"]["site"] == "f1"
    assert machine["adapter"]["name"] == "generic-serial"

    # status reflects the run
    assert cli_main(["status", "--state-dir", str(state)]) == 0
    out = capsys.readouterr().out
    assert "f1-dye-jig01" in out and "dead_letters: 0" in out

    # regression: `run` must persist the gateway id, or show-identity - the
    # command that surfaces the pubkey for the key registry (DPP guide s6) -
    # blows up on a state dir that never saw install-service
    assert cli_main(["show-identity", "--state-dir", str(state)]) == 0
    ident = capsys.readouterr().out
    assert "gw-f1-pilot-01" in ident and "ed25519:" in ident


def test_show_identity_without_state_errors_cleanly(tmp_path, capsys):
    """Missing identity is an operator mistake, not a traceback."""
    assert cli_main(["show-identity", "--state-dir", str(tmp_path / "nope")]) == 1
    assert "install-service" in capsys.readouterr().err
