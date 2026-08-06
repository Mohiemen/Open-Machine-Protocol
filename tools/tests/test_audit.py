"""omp-validate --audit: the five DPP Evidence Chain checks."""
import io
import json
from contextlib import redirect_stdout

import pytest
from omp_tools.audit import audit_bundle, records_hash
from omp_tools.envelope import checksum
from omp_tools.simulate import main as simulate_main
from omp_tools.specload import load_spec
from omp_tools.validate import main as validate_main

SPEC = load_spec()


def bundle(seed="21"):
    buf = io.StringIO()
    with redirect_stdout(buf):
        simulate_main(["--profile", "textile-dyeing", "--machines", "1",
                       "--duration", "4h", "--seed", seed])
    return [json.loads(x) for x in buf.getvalue().splitlines()]


def flags(envs, **kw):
    checks, citation = audit_bundle(envs, SPEC, **kw)
    return {c.name: c.passed for c in checks}, citation


# ---------------------------------------------------------------- happy path
def test_clean_bundle_passes_what_it_can():
    f, citation = flags(bundle())
    assert f["completeness"] and f["integrity"] and f["consistency"] and f["conformance"]
    # unsigned + no key: NOT false, and never silently true
    assert f["authenticity"] is None
    v = citation["evidence"]["verification"]
    assert v["signatures_valid"] is None, "unchecked must not read as passed"
    assert v["seq_complete"] is True
    assert citation["evidence"]["run_id"].startswith("batch-")
    assert len(citation["evidence"]["records_hash"]) == 64
    assert v["data_source"] == "native", "honesty ladder reaches claim level"


def test_records_hash_is_order_independent_and_content_bound():
    envs = bundle()
    assert records_hash(envs) == records_hash(list(reversed(envs)))
    mutated = [dict(e) for e in envs]
    mutated[3]["checksum"] = "0" * 64
    assert records_hash(mutated) != records_hash(envs), "digest must bind content"


# ---------------------------------------------------------------- failures
def test_missing_envelope_fails_completeness():
    envs = bundle()
    victim = next(e for e in envs if e["schema"] == "event")
    f, citation = flags([e for e in envs if e is not victim])
    assert f["completeness"] is False
    assert citation["evidence"]["verification"]["seq_complete"] is False


def test_altered_body_fails_integrity():
    envs = bundle()
    for e in envs:
        if e["schema"] == "energy":
            e["body"]["value"] = 999999      # checksum left stale, as a tamper would
            break
    f, _ = flags(envs)
    assert f["integrity"] is False


def test_falsified_summary_fails_consistency_on_its_own():
    """Independent of checksums: does the summary follow from its events?"""
    envs = bundle()
    run = next(e for e in envs if e["schema"] == "process_run")
    run["body"]["phases"].append(
        {"name": "pretreat", "start_ts": run["body"]["start_ts"],
         "end_ts": run["body"]["end_ts"], "params": {"type": "scour"}})
    run["body"]["quantities"].append({"name": "kwh_total", "value": 7, "unit": "kW.h"})
    run["checksum"] = checksum(run["body"])   # re-checksummed: integrity passes
    f, _ = flags(envs)
    assert f["integrity"] is True
    assert f["consistency"] is False, "a re-checksummed lie must still be caught"


def test_signature_verification(tmp_path):
    from omp.core.keys import GatewayKey

    key = GatewayKey.generate(tmp_path / "k.pem")
    other = GatewayKey.generate(tmp_path / "o.pem")
    envs = bundle()
    for e in envs:
        e["sig"] = key.sign(e["gateway_id"], e["machine_id"], e["seq"], e["checksum"])
    pub = key.public_key_b64()
    f, citation = flags(envs, pubkey=pub)
    assert f["authenticity"] is True
    assert citation["evidence"]["gateway_pubkey"] == f"ed25519:{pub}"

    envs[5]["sig"] = other.sign(envs[5]["gateway_id"], envs[5]["machine_id"],
                                envs[5]["seq"], envs[5]["checksum"])
    f2, _ = flags(envs, pubkey=pub)
    assert f2["authenticity"] is False


def test_signed_bundle_without_key_is_not_evaluated():
    envs = bundle()
    for e in envs:
        e["sig"] = "dGVzdA=="
    f, _ = flags(envs)
    assert f["authenticity"] is None, "no key supplied means not checked, not failed"


# ---------------------------------------------------------------- selection
def test_bundle_without_a_run_is_rejected():
    envs = [e for e in bundle() if e["schema"] != "process_run"]
    with pytest.raises(ValueError, match="no process_run"):
        audit_bundle(envs, SPEC)


def test_multi_run_bundle_requires_run_id():
    envs = bundle("21") + bundle("22")
    with pytest.raises(ValueError, match="several runs"):
        audit_bundle(envs, SPEC)
    run_id = next(e for e in envs if e["schema"] == "process_run")["body"]["run_id"]
    checks, citation = audit_bundle(envs, SPEC, run_id=run_id)
    assert citation["evidence"]["run_id"] == run_id


# ---------------------------------------------------------------- CLI
def test_cli_audit_exit_codes(tmp_path, capsys):
    envs = bundle()
    good = tmp_path / "good.ndjson"
    good.write_text("\n".join(json.dumps(e) for e in envs) + "\n", encoding="utf-8")
    assert validate_main(["--audit", str(good)]) == 0
    out = capsys.readouterr().out
    assert "audit passed" in out and "citation block" in out
    assert "must not assert what was not checked" in out

    envs[4]["body"]["payload"] = {"tampered": 1}
    bad = tmp_path / "bad.ndjson"
    bad.write_text("\n".join(json.dumps(e) for e in envs) + "\n", encoding="utf-8")
    assert validate_main(["--audit", str(bad)]) == 1
    assert "AUDIT FAILED" in capsys.readouterr().out
